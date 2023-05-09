import re
from typing import Any, Optional

import yaml
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
from clients.remote_component_client import remote_component_client
from common.api_base_http_client import ApiBaseHttpClient
from core import deps
from core.setting import settings
from core.utils.reqparse import parse_item
from core.utils.return_message import general_message, error_message, general_data
from database.session import SessionClass
from exceptions.bcode import ErrComponentBuildFailed
from exceptions.main import AccountOverdueException, ResourceNotEnoughException, ErrInsufficientResource, \
    ServiceHandleException
from models.component.models import Component
from repository.component.graph_repo import component_graph_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_component_repo import team_component_repo
from schemas.components import DockerRunParams, DockerRunCheckParam, BuildParam
from schemas.response import Response
from service.app_actions.app_log import event_service, log_service, ws_service
from service.app_actions.app_manage import app_manage_service
from service.app_config.app_relation_service import dependency_service
from service.app_config.component_graph import component_graph_service
from service.app_config.port_service import port_service
from service.app_config.service_monitor_service import service_monitor_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.application_service import application_service
from service.component_service import component_check_service
from service.market_app_service import market_app_service
from service.monitor_service import monitor_service
from service.multi_app_service import multi_app_service
from service.region_service import region_services
from service.tenant_env_service import env_services
from service.yaml.yaml_service import yaml_service

router = APIRouter()


def validate_request(item, name):
    if not item:
        return JSONResponse(general_message(400, "params error", "the field '" + name + "' is required"),
                            status_code=400)
    return None


@router.post("/teams/{team_name}/env/{env_id}/apps/docker_run", response_model=Response, name="添加组件-指定镜像")
async def docker_run(
        request: Request,
        params: DockerRunParams,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    image和docker-run创建组件
    """
    if params.k8s_component_name and application_service.is_k8s_component_name_duplicate(session,
                                                                                         params.group_id,
                                                                                         params.k8s_component_name):
        return JSONResponse(general_message(400, "k8s component name exists", "组件英文名已存在"), status_code=400)
    try:
        if not params.image_type:
            return JSONResponse(general_message(400, "image_type cannot be null", "参数错误"), status_code=400)
        if not params.docker_cmd:
            return JSONResponse(general_message(400, "docker_cmd cannot be null", "参数错误"), status_code=400)
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        region_name = region.region_name

        code, msg_show, new_service = application_service.create_docker_run_app(session=session,
                                                                                region_name=region_name,
                                                                                tenant_env=env,
                                                                                user=user,
                                                                                service_cname=params.service_cname,
                                                                                docker_cmd=params.docker_cmd,
                                                                                image_type=params.image_type,
                                                                                k8s_component_name=params.k8s_component_name)
        if code != 200:
            return JSONResponse(general_message(code, "service create fail", msg_show), status_code=200)

        # 添加username,password信息
        if params.password or params.user_name:
            application_service.create_service_source_info(session=session, tenant_env=env, service=new_service,
                                                           user_name=params.user_name,
                                                           password=params.password)

        code, msg_show = application_service.add_component_to_app(session=session, tenant_env=env,
                                                                  region_name=region_name,
                                                                  app_id=params.group_id,
                                                                  component_id=new_service.service_id)
        if code != 200:
            logger.debug("service.create", msg_show)
        result = general_message("0", "success", "创建成功", bean=jsonable_encoder(new_service))
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", re), status_code=10410)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/get_check_uuid", response_model=Response,
            name="组件构建检测")
async def get_check_uuid(service_alias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         env=Depends(deps.get_current_team_env)) -> Any:
    check_uuid = (
        session.execute(
            select(Component.check_uuid).where(Component.service_alias == service_alias,
                                               Component.tenant_env_id == env.env_id))
    ).scalars().first()

    return JSONResponse(general_message("0", "success", "获取成功", bean={"check_uuid": check_uuid}), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/check", response_model=Response, name="组件构建检测")
async def get_check_detail(check_uuid: Optional[str] = None,
                           env_id: Optional[str] = None,
                           service_alias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取组件检测信息
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: check_uuid
          description: 检测id
          required: true
          type: string
          paramType: query

    """
    if not check_uuid:
        return JSONResponse(general_message(400, "params error", "参数错误，请求参数应该包含请求的ID"), status_code=400)
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    service = team_component_repo.get_one_by_model(session=session,
                                                   query_model=Component(service_alias=service_alias,
                                                                         tenant_env_id=env.env_id))
    if not service:
        return JSONResponse(general_message(400, "not found service", "组件不存在"), status_code=400)
    code, msg, data = component_check_service.get_service_check_info(session=session, tenant_env=env,
                                                                     region=service.service_region,
                                                                     check_uuid=check_uuid)
    logger.debug("check resp! {0}".format(data))

    # 如果已创建完成
    if service.create_status == "complete":
        service_info = data.get("service_info")
        if service_info is not None and len(service_info) > 1 and service_info[0].get("language") == "Java-maven":
            pass
        else:
            component_check_service.update_service_check_info(session=session, tenant_env=env, service=service,
                                                              data=data)
        check_brief_info = component_check_service.wrap_service_check_info(session=session, service=service, data=data)
        return JSONResponse(general_message("0", "success", "请求成功", bean=check_brief_info), status_code=200)

    if data["service_info"] and len(data["service_info"]) < 2:
        # No need to save env, ports and other information for multiple services here.
        logger.debug("start save check info ! {0}".format(service.create_status))
        component_check_service.save_service_check_info(session=session, tenant_env=env, service=service, data=data)
    check_brief_info = component_check_service.wrap_service_check_info(session=session, service=service, data=data)
    code_from = service.code_from
    if code_from in list(settings.source_code_type.keys()):
        for i in check_brief_info["service_info"]:
            if i["type"] == "source_from":
                result_url = re.split("[:,@]", i["value"])
                if len(result_url) != 2:
                    i["value"] = result_url[0] + '//' + result_url[-2] + result_url[-1]
    result = general_message("0", "success", "请求成功", bean=check_brief_info)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/check", response_model=Response, name="组件构建检测")
async def check(
        params: Optional[DockerRunCheckParam] = DockerRunCheckParam(),
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    """
    组件信息检测
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path

    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    service = team_component_repo.get_one_by_model(session=session,
                                                   query_model=Component(service_alias=service_alias,
                                                                         tenant_env_id=env.env_id))
    if not service:
        return JSONResponse(general_message(400, "not found service", "组件不存在"), status_code=400)
    code, msg, service_info = application_service.check_service(session=session, tenant_env=env, service=service,
                                                                is_again=params.is_again, user=user)
    if code != 200:
        result = general_message(code, "check service error", msg)
    else:
        result = general_message("0", "success", "操作成功", bean=jsonable_encoder(service_info))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/build", response_model=Response, name="构建组件")
async def component_build(params: Optional[BuildParam] = BuildParam(),
                          env_id: Optional[str] = None,
                          service_alias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    """
    组件构建
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
    """
    is_deploy = params.is_deploy
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = team_component_repo.get_one_by_model(session=session,
                                                   query_model=Component(service_alias=service_alias,
                                                                         tenant_env_id=env.env_id))
    if not service:
        return JSONResponse(general_message(400, "not found service", "组件不存在"), status_code=400)
    try:
        if service.service_source == "third_party":
            is_deploy = False
            # create third component from region
            new_service = application_service.create_third_party_service(session=session, tenant_env=env,
                                                                         service=service, user_name=user.nick_name)
        else:
            # 数据中心创建组件
            new_service = application_service.create_region_service(session=session, tenant_env=env, service=service,
                                                                    user_name=user.nick_name)

        service = new_service
        if is_deploy:
            try:
                app_manage_service.deploy(session=session, tenant_env=env, service=service, user=user)
            except ErrInsufficientResource as e:
                return JSONResponse(general_message(e.error_code, e.msg, e.msg_show), e.error_code)
            except Exception as e:
                logger.exception(e)
                err = ErrComponentBuildFailed()
                return JSONResponse(general_message(err.error_code, e, err.msg_show), err.error_code)
            # 添加组件部署关系
            application_service.create_deploy_relation_by_service_id(session=session, service_id=service.service_id)
        return JSONResponse(general_message("0", "success", "构建成功"), status_code=200)
    except ApiBaseHttpClient.RemoteInvokeError as e:
        logger.exception(e)
        if e.status == 403:
            result = general_message(10407, "no cloud permission", e.message)
        elif e.status == 400:
            if "is exist" in e.message.get("body", ""):
                result = general_message(400, "the service is exist in region", "该组件在数据中心已存在，你可能重复创建？")
            else:
                result = general_message(400, "call cloud api failure", e.message)
        else:
            result = general_message(400, "call cloud api failure", e.message)
    if service.service_source != "third_party":
        event_service.delete_service_events(session=session, service=service)
        port_service.delete_region_port(session=session, tenant_env=env, service=service)
        volume_service.delete_region_volumes(session=session, tenant_env=env, service=service)
        env_var_service.delete_region_env(session=session, tenant_env=env, service=service)
        dependency_service.delete_region_dependency(session=session, tenant_env=env, service=service)
        app_manage_service.delete_region_service(session=session, tenant_env=env, service=service)
    service.create_status = "checked"

    session.merge(service)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/pods/{pod_name}/detail", response_model=Response,
            name="pod详情")
async def pod_detail(
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        pod_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        service = team_component_repo.get_one_by_model(session=session,
                                                       query_model=Component(service_alias=service_alias,
                                                                             tenant_env_id=env.env_id))
        if not service:
            return JSONResponse(general_message(400, "not found service", "组件不存在"), status_code=400)
        data = remote_component_client.pod_detail(session,
                                                  service.service_region, env,
                                                  service.service_alias,
                                                  pod_name)
        result = general_message("0", 'success', "查询成功", data.get("bean", None))
    except remote_component_client.CallApiError as e:
        logger.exception(e)
        result = error_message(e.message)
    return result


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/vertical", response_model=Response, name="垂直升级组件")
async def component_vertical(request: Request,
                             env_id: Optional[str] = None,
                             service_alias: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             user=Depends(deps.get_current_user)) -> Any:
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        data = await request.json()
        new_memory = data.get("new_memory", 0)
        new_gpu_type = data.get("new_gpu_type", None)
        new_gpu = data.get("new_gpu", None)
        new_cpu = data.get("new_cpu", None)
        service = service_info_repo.get_service(session, service_alias, env.env_id)
        code, msg = app_manage_service.vertical_upgrade(
            session,
            env,
            service,
            user,
            int(new_memory),
            new_gpu_type=new_gpu_type,
            new_gpu=new_gpu,
            new_cpu=new_cpu)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "vertical upgrade error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "失败"), status_code=412)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/horizontal", response_model=Response, name="水平升级组件")
async def component_horizontal(request: Request,
                               env_id: Optional[str] = None,
                               service_alias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               user=Depends(deps.get_current_user)) -> Any:
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        data = await request.json()
        new_node = data.get("new_node", None)
        if not new_node:
            return JSONResponse(general_message(400, "node is null", "请选择节点个数"), status_code=400)

        service = service_info_repo.get_service(session, service_alias, env.env_id)
        oauth_instance, _ = None, None
        app_manage_service.horizontal_upgrade(
            session, env, service, user, int(new_node), oauth_instance=oauth_instance)
        result = general_message("0", "success", "操作成功", bean={})
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "失败"), status_code=412)
    except ServiceHandleException as re:
        logger.exception(re)
        return JSONResponse(general_message(re.status_code, re.msg, re.msg_show), status_code=re.status_code)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/graphs", response_model=Response, name="查询组件图表")
async def component_graphs(service_alias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           env=Depends(deps.get_current_team_env)) -> Any:
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    graphs = component_graph_service.list_component_graphs(session, service.service_id)
    result = general_message("0", "success", "查询成功", list=graphs)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/internal-graphs", response_model=Response,
            name="查询组件内部图表")
async def component_graphs() -> Any:
    graphs = component_graph_service.list_internal_graphs()
    result = general_message("0", "success", "查询成功", list=graphs)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/internal-graphs", response_model=Response,
             name="一键导入内部图表")
async def import_component_graphs(request: Request,
                                  service_alias: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  env=Depends(deps.get_current_team_env)
                                  ) -> Any:
    graph_name = await parse_item(request, "graph_name", required=True)
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    component_graph_service.create_internal_graphs(session, service.service_id, graph_name)
    result = general_message("0", "success", "导入成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/service_monitor", response_model=Response,
            name="查询组件监控点")
async def component_monitor(service_alias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            env=Depends(deps.get_current_team_env)) -> Any:
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    sms = service_monitor_service.get_component_service_monitors(session, env.env_id, service.service_id)
    return JSONResponse(general_data(list=[jsonable_encoder(p) for p in sms]), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/service_monitor", response_model=Response,
             name="添加组件监控点")
async def add_component_monitor(request: Request,
                                env_id: Optional[str] = None,
                                service_alias: Optional[str] = None,
                                session: SessionClass = Depends(deps.get_session),
                                user=Depends(deps.get_current_user)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    data = await request.json()
    port = data.get("port", None)
    name = data.get("name", None)
    service_show_name = data.get("service_show_name", None)
    path = data.get("path", "/metrics")
    interval = data.get("interval", "10s")
    if not port or not name or not service_show_name:
        return JSONResponse(general_message(400, "port or name or service_show_name must be set", "参数不全"),
                            status_code=400)
    if not path.startswith("/"):
        return JSONResponse(general_message(400, "path must start with /", "参数错误"), status_code=400)

    service = service_info_repo.get_service(session, service_alias, env.env_id)
    sm = service_monitor_service.create_component_service_monitor(session, env, service, name, path, port,
                                                                  service_show_name, interval, user)
    return JSONResponse(general_data(bean=jsonable_encoder(sm)), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/metrics", response_model=Response, name="查询组件指标")
async def component_metrics(
        request: Request,
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    metrics = monitor_service.get_monitor_metrics(
        session, region_name, env, "component", component_id=service.service_id)
    return JSONResponse(general_message("0", "OK", "获取成功", list=metrics), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/graphs", response_model=Response, name="添加组件图表")
async def add_component_graphs(request: Request,
                               service_alias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               env=Depends(deps.get_current_team_env)) -> Any:
    data = await request.json()
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    try:
        graph = component_graph_service.create_component_graph(session, service.service_id, data['title'],
                                                               data['promql'])
    except FileNotFoundError as e:
        return JSONResponse(general_message(400, "failed", "系统找不到指定的文件"), status_code=400)
    result = general_message("0", "success", "创建成功", bean=graph)
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{service_alias}/graphs", response_model=Response, name="批量删除组件图表")
async def delete_component_graphs(request: Request,
                                  service_alias: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  env=Depends(deps.get_current_team_env)) -> Any:
    graph_ids = await parse_item(request, "graph_ids", required=True)
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    component_graph_service.batch_delete(session, service.service_id, graph_ids)
    result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{service_alias}/service_monitor/{name}", response_model=Response,
            name="修改监控点")
async def modify_component_monitor(request: Request,
                                   env_id: Optional[str] = None,
                                   service_alias: Optional[str] = None,
                                   name: Optional[str] = None,
                                   session: SessionClass = Depends(deps.get_session),
                                   user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    port = data.get("port", None)
    service_show_name = data.get("service_show_name", None)
    path = data.get("path", "/metrics")
    interval = data.get("interval", "10s")
    if not port or not name or not service_show_name:
        return JSONResponse(general_message(400, "port or name or service_show_name must be set", "参数不全"),
                            status_code=400)
    if not path.startswith("/"):
        return JSONResponse(general_message(400, "path must start with /", "参数错误"), status_code=400)

    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    service = service_info_repo.get_service(session, service_alias, env.env_id)
    sm = service_monitor_service.update_component_service_monitor(session, env, service, user, name, path,
                                                                  port,
                                                                  service_show_name, interval)
    return JSONResponse(general_data(bean=jsonable_encoder(sm)), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{service_alias}/service_monitor/{name}", response_model=Response,
               name="删除监控点")
async def delete_component_monitor(
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    sm = service_monitor_service.delete_component_service_monitor(session, env, service, user, name)
    return JSONResponse(general_data(bean=jsonable_encoder(sm)), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/history_log", response_model=Response,
            name="获取组件历史日志")
async def get_history_log(request: Request,
                          env_id: Optional[str] = None,
                          service_alias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    code, msg, file_list = log_service.get_history_log(session, env, service)
    log_domain_url = ws_service.get_log_domain(session, request, service.service_region)
    if code != 200 or file_list is None:
        file_list = []

    file_urls = [{"file_name": f["filename"], "file_url": log_domain_url + "/" + f["relative_path"]} for f in file_list]

    result = general_message("0", "success", "查询成功", list=file_urls)
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{service_alias}/graphs/{graph_id}", response_model=Response,
               name="删除组件图表")
async def delete_component_graphs(
        service_alias: Optional[str] = None,
        graph_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    graph = component_graph_repo.get_graph(session, service.service_id, graph_id)
    graphs = component_graph_service.delete_component_graph(session, graph)
    result = general_message("0", "success", "删除成功", list=graphs)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{service_alias}/graphs/{graph_id}", response_model=Response,
            name="修改组件图表")
async def modify_component_graphs(
        request: Request,
        service_alias: Optional[str] = None,
        graph_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    data = await request.json()
    service = service_info_repo.get_service(session, service_alias, env.env_id)
    graph = component_graph_repo.get_graph(session, service.service_id, graph_id)
    graphs = component_graph_service.update_component_graph(session, graph, data["title"], data["promql"],
                                                            data["sequence"])
    result = general_message("0", "success", "修改成功", list=graphs)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/multi/check", response_model=Response, name="进入多组件创建流程")
async def get_check_detail(
        request: Request,
        env_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    check_uuid = request.query_params.get("check_uuid", None)
    if not check_uuid:
        return JSONResponse(general_message(400, "params error", "the field 'check_uuid' is required"), status_code=400)
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    services = multi_app_service.list_services(session, response_region, env, check_uuid)
    result = general_message("0", "successfully entered the multi-service creation process", "成功进入多组件创建流程",
                             list=services)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/multi/create", response_model=Response, name="创建组件")
async def multi_create(
        request: Request,
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    resp = validate_request(service_alias, "serviceAlias")
    if resp:
        return resp
    data = await request.json()
    service_infos = data.get("service_infos", None)
    resp = validate_request(service_infos, "service_infos")
    if resp:
        return resp

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    group_id, service_ids = multi_app_service.create_services(
        session=session,
        region_name=response_region,
        tenant_env=env,
        user=user,
        service_alias=service_alias,
        service_infos=service_infos)

    result = general_message(
        200,
        "successfully create the multi-services",
        "成功创建多组件应用",
        bean={
            "group_id": group_id,
            "service_ids": service_ids,
        })

    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/yaml", response_model=Response, name="yaml安装组件")
async def yaml_install(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    data = await request.json()
    group_id = data.get("group_id")
    yaml_dirs = data.get("yaml_dirs")
    yaml_data = []

    if not yaml_dirs or not group_id:
        return JSONResponse(general_message(400, "failed", msg_show="参数错误"), status_code=400)

    for yaml_dir in yaml_dirs:
        yaml_file = open(yaml_dir, "r", encoding='utf-8')
        file_data = yaml_file.read()
        yaml_file.close()
        try:
            yaml_data += list(yaml.safe_load_all(file_data))
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                err_msg = "Error parsing Yaml file at line %s, column %s." % (mark.line, mark.column + 1)
            else:
                err_msg = "Something went wrong while parsing yaml file"
            file_name = yaml_dir.split("\\")[-1]
            err_msg = {file_name: err_msg}
            return JSONResponse(general_message(400, "yaml file error", msg_show="yaml解析失败", bean=err_msg),
                                status_code=200)

    yaml_service.install_yaml_service(session=session,
                                      user=user,
                                      env=env,
                                      app_id=group_id,
                                      version="1.0",
                                      region_name=env.region_code,
                                      is_deploy=False,
                                      install_from_cloud=False,
                                      yaml_data=yaml_data)
    return JSONResponse(general_message(200, "success", msg_show="安装成功"), status_code=200)
