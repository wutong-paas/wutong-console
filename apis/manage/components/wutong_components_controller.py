from typing import Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import delete

from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core import deps
from core.enum.component_enum import is_support

from core.utils.constants import PluginCategoryConstants
from core.utils.reqparse import parse_argument, parse_item
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.bcode import ErrK8sComponentNameExists
from exceptions.main import ServiceHandleException, MarketAppLost, RbdAppNotFound, ResourceNotEnoughException, \
    AccountOverdueException, AbortRequest, CallRegionAPIException, ErrInsufficientResource
from models.component.models import ComponentEnvVar
from models.users.users import Users
from repository.application.app_repository import service_webhooks_repo
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from service.app_actions.app_log import event_service
from service.app_actions.app_manage import app_manage_service
from service.app_config.app_relation_service import dependency_service
from service.app_config.port_service import port_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.application_service import application_service
from service.component_service import component_log_service
from service.compose_service import compose_service
from service.git_service import git_service
from service.market_app_service import market_app_service
from service.plugin.app_plugin_service import app_plugin_service
from service.probe_service import probe_service
from service.region_service import region_services
from service.upgrade_service import upgrade_service
from service.user_service import user_svc

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/visit", response_model=Response, name="获取组件访问信息")
async def get_app_visit_info(serviceAlias: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件访问信息
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
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    bean = dict()
    access_type, data = port_service.get_access_info(session=session, tenant=team, service=service)
    bean["access_type"] = access_type
    bean["access_info"] = data
    result = general_message(200, "success", "操作成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/pods", response_model=Response, name="获取组件实例")
async def get_pods_info(serviceAlias: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    """
     获取组件实例
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

    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)
    data = remote_component_client.get_service_pods(session,
                                                    service.service_region,
                                                    team.tenant_name,
                                                    service.service_alias,
                                                    team.enterprise_id)
    result = {}
    if data["bean"]:

        def foobar(data):
            if data is None:
                return
            res = []
            for d in data:
                bean = dict()
                bean["pod_name"] = d["pod_name"]
                bean["pod_status"] = d["pod_status"]
                bean["manage_name"] = "manager"
                container = d["container"]
                container_list = []
                for key, val in list(container.items()):
                    if key == "POD":
                        continue
                    container_dict = dict()
                    container_dict["container_name"] = key
                    memory_limit = float(val["memory_limit"]) / 1024 / 1024
                    memory_usage = float(val["memory_usage"]) / 1024 / 1024
                    usage_rate = 0
                    if memory_limit:
                        usage_rate = memory_usage * 100 / memory_limit
                    container_dict["memory_limit"] = round(memory_limit, 2)
                    container_dict["memory_usage"] = round(memory_usage, 2)
                    container_dict["usage_rate"] = round(usage_rate, 2)
                    container_list.append(container_dict)
                    if service.k8s_component_name.startswith(key):
                        if len(container_list) > 1:
                            container_list[0], container_list[len(container_list) - 1] = container_list[
                                                                                             len(container_list) - 1], \
                                                                                         container_list[0]
                bean["container"] = container_list
                res.append(bean)
            return res

        pods = data["bean"]
        newpods = foobar(pods.get("new_pods", None))
        old_pods = foobar(pods.get("old_pods", None))
        result = {"new_pods": newpods, "old_pods": old_pods}
    result = general_message(200, "success", "操作成功", list=result)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/resource", response_model=Response, name="查询组件资源")
async def get_resource(serviceAlias: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       team=Depends(deps.get_current_team)) -> Any:
    """
    组件资源查询
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
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    data = {"service_ids": [service.service_id]}
    body = remote_build_client.get_service_resources(session, team.tenant_name, service.service_region, data)
    bean = body["bean"]
    result = bean.get(service.service_id)
    resource = dict()
    resource["memory"] = result.get("memory", 0) if result else 0
    resource["disk"] = result.get("disk", 0) if result else 0
    resource["cpu"] = result.get("cpu", 0) if result else 0
    result = general_message(200, "success", "查询成功", bean=resource)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/brief", response_model=Response, name="获取组件详情信息")
async def get_brief(serviceAlias: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    team=Depends(deps.get_current_team)) -> Any:
    """
     组件详情信息
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
    msg = "查询成功"
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    if service.service_source == "market":
        try:
            market_app_service.check_market_service_info(session=session, tenant=team, service=service)
        except MarketAppLost as e:
            msg = e.msg
        except RbdAppNotFound as e:
            msg = e.msg
        except ServiceHandleException as e:
            logger.debug(e)
    result = general_message(200, "success", msg, bean=jsonable_encoder(service))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/brief", response_model=Response, name="修改组件名称")
async def modify_components_name(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    service_cname = data.get("service_cname", None)
    k8s_component_name = data.get("k8s_component_name", "")
    app = application_service.get_service_group_info(session, service.service_id)
    if app:
        if application_service.is_k8s_component_name_duplicate(session, app.ID, k8s_component_name, service.service_id):
            raise ErrK8sComponentNameExists
    is_pass, msg = application_service.check_service_cname(service_cname)
    if not is_pass:
        return JSONResponse(general_message(400, "param error", msg), status_code=400)
    service.k8s_component_name = k8s_component_name
    service.service_cname = service_cname
    remote_component_client.update_service(session, service.service_region, team.tenant_name, service.service_alias,
                                           {"k8s_component_name": k8s_component_name})
    result = general_message(200, "success", "修改成功", bean=jsonable_encoder(service))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/analyze_plugins", response_model=Response, name="查询组件的性能分析插件")
async def get_analyze_plugins(serviceAlias: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    """
     查询组件的性能分析插件
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
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    service_abled_plugins = app_plugin_service.get_service_abled_plugin(session=session, service=service)
    analyze_plugins = []
    for plugin in service_abled_plugins:
        if plugin.category == PluginCategoryConstants.PERFORMANCE_ANALYSIS:
            analyze_plugins.append(plugin)

    result = general_message(200, "success", "查询成功", list=[jsonable_encoder(p) for p in analyze_plugins])
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/volume-opts", response_model=Response, name="获取组件可用的存储列表")
async def get_volume_opts_list(serviceAlias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件可用的存储列表
    ---
    parameters:
    """
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    volume_types = volume_service.get_service_support_volume_options(session=session, tenant=team, service=service)
    result = general_message(200, "success", "查询成功", list=volume_types)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/build_envs", response_model=Response, name="获取构建组件的环境变量参数")
async def get_build_envs(serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    # 获取组件构建时环境变量
    build_env_dict = dict()
    build_envs = env_var_service.get_service_build_envs(session=session, service=service)
    if build_envs:
        for build_env in build_envs:
            build_env_dict[build_env.attr_name] = build_env.attr_value
    result = general_message(200, "success", "查询成功", bean=build_env_dict)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/set/is_upgrade", response_model=Response, name="设置是否自动升级")
async def set_is_upgrade(request: Request,
                         serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    data = await request.json()
    build_upgrade = data.get("build_upgrade", True)

    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)

    service.build_upgrade = build_upgrade
    result = general_message(200, "success", "操作成功", bean={"build_upgrade": service.build_upgrade})
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/restart", response_model=Response, name="重启组件")
async def restart_component(serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user),
                            team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session=session, user_id=user.user_id)
    code, msg = app_manage_service.restart(session=session, tenant=team, service=service, user=user)
    bean = {}
    if code != 200:
        return JSONResponse(general_message(code, "restart app error", msg, bean=bean), status_code=code)
    result = general_message(code, "success", "操作成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/stop", response_model=Response, name="停止组件")
async def stop_component(serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user),
                         team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)

    app_manage_service.stop(session=session, tenant=team, service=service, user=user)
    result = general_message(200, "success", "操作成功", bean={})
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/start", response_model=Response, name="启动组件")
async def start_component(serviceAlias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user),
                          team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)
    try:
        code, msg = app_manage_service.start(session=session, tenant=team, service=service, user=user)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "start app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "操作失败"), status_code=412)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/upgrade", response_model=Response, name="更新组件")
async def upgrade_component(serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user),
                            team=Depends(deps.get_current_team)) -> Any:
    """
    更新
    """
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)
    try:
        code, msg, _ = app_manage_service.upgrade(session=session, tenant=team, service=service, user=user)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "upgrade app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "操作失败"), status_code=412)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/group", response_model=Response, name="修改组件所在组")
async def group_component(request: Request,
                          serviceAlias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    data = await request.json()
    group_id = data.get("group_id", None)
    if group_id is None:
        return JSONResponse(general_message(400, "param error", "请指定修改的组"), status_code=400)
    group_id = int(group_id)
    if group_id == -1:
        application_service.delete_service_group_relation_by_service_id(session=session, service_id=service.service_id)
    else:
        # check target app exists or not
        application_service.get_group_by_id(session=session, tenant=team, region=service.service_region,
                                            group_id=group_id)
        # update service relation
        application_service.update_or_create_service_group_relation(session=session, tenant=team, service=service,
                                                                    group_id=group_id)

    result = general_message(200, "success", "修改成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/delete", response_model=Response, name="删除组件")
async def delete_component(request: Request,
                           serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user),
                           team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    data = await request.json()
    is_force = data.get("is_force", False)

    code, msg = app_manage_service.delete(session=session, tenant=team, service=service, user=user, is_force=is_force)
    bean = {}
    if code != 200:
        return JSONResponse(general_message(code, "delete service error", msg, bean=bean), status_code=code)
    result = general_message(code, "success", "操作成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/un_dependency", response_model=Response, name="获取组件可以依赖但未依赖的组件")
async def get_un_dependency(request: Request,
                            serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    page_num = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 25))
    search_key = request.query_params.get("search_key", None)
    condition = request.query_params.get("condition", None)
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    un_dependencies = dependency_service.get_undependencies(session=session, tenant=team, service=service)
    service_ids = [s.service_id for s in un_dependencies]
    service_group_map = application_service.get_services_group_name(session=session, service_ids=service_ids)
    un_dep_list = []
    for un_dep in un_dependencies:
        dep_service_info = {
            "service_cname": un_dep.service_cname,
            "service_id": un_dep.service_id,
            "service_type": un_dep.service_type,
            "service_alias": un_dep.service_alias,
            "group_name": service_group_map[un_dep.service_id]["group_name"],
            "group_id": service_group_map[un_dep.service_id]["group_id"]
        }

        if search_key is not None and condition:
            if condition == "group_name":
                if search_key.lower() in service_group_map[un_dep.service_id]["group_name"].lower():
                    un_dep_list.append(dep_service_info)
            elif condition == "service_name":
                if search_key.lower() in un_dep.service_cname.lower():
                    un_dep_list.append(dep_service_info)
            else:
                result = general_message(400, "error", "condition参数错误")
                return JSONResponse(result, status_code=400)
        elif search_key is not None and not condition:
            if search_key.lower() in service_group_map[
                un_dep.service_id]["group_name"].lower() or search_key.lower() in un_dep.service_cname.lower():
                un_dep_list.append(dep_service_info)
        elif search_key is None and not condition:
            un_dep_list.append(dep_service_info)

    rt_list = un_dep_list[(page_num - 1) * page_size:page_num * page_size]
    result = general_message(200, "success", "查询成功", list=rt_list, total=len(un_dep_list))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/deploytype", response_model=Response, name="修改组件的组件类型标签")
async def modify_deploy_type(request: Request,
                             serviceAlias: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             user=Depends(deps.get_current_user),
                             team=Depends(deps.get_current_team)) -> Any:
    """
    修改组件的组件类型标签
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    try:
        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        data = await request.json()
        extend_method = data.get("extend_method", None)
        if not extend_method:
            raise AbortRequest(msg="select the application type", msg_show="请选择组件类型")

        if not is_support(extend_method):
            raise AbortRequest(msg="do not support service type", msg_show="组件类型非法")
        logger.debug("team: {0}, service:{1}, extend_method:{2}".format(team, service, extend_method))
        app_manage_service.change_service_type(session=session, tenant=team, service=service,
                                               extend_method=extend_method, user_name=user.nick_name)
        result = general_message(200, "success", "操作成功")
    except CallRegionAPIException as e:
        result = general_message(e.code, "failure", e.message)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/market_service/upgrade", response_model=Response,
            name="判断云市安装的组件是否有（小版本，大版本）更新")
async def get_market_service_upgrade(serviceAlias: Optional[str] = None,
                                     session: SessionClass = Depends(deps.get_session),
                                     team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    versions = []
    try:
        versions = market_app_service.list_upgradeable_versions(session, team, service)
    except RbdAppNotFound:
        return JSONResponse(general_message(404, "service lost", "未找到该组件"), status_code=404)
    except Exception as e:
        logger.debug(e)
        return JSONResponse(general_message(200, "success", "查询成功", list=versions), status_code=200)
    return JSONResponse(general_message(200, "success", "查询成功", list=versions), status_code=200)


@router.post("/teams/{team_name}/apps/{serviceAlias}/market_service/upgrade", response_model=Response,
             name="云市安装的组件升级")
async def market_service_upgrade(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user=Depends(deps.get_current_user)) -> Any:
    version = await parse_item(request, "group_version", required=True)
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    # get app
    app = application_repo.get_by_service_id(session, team.tenant_id, service.service_id)

    upgrade_service.upgrade_component(session, team, region, user, app, service, version)
    return JSONResponse(general_message(200, "success", "升级成功"), status_code=200)


@router.get("/teams/{team_name}/groups/{group_id}/apps/{app_id}/components", response_model=Response, name="获取组件实例")
async def get_pods_info(request: Request,
                        group_id: Optional[str] = None,
                        app_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user),
                        team=Depends(deps.get_current_team)) -> Any:
    app_model_key = parse_argument(
        request, 'app_model_key', value_type=str, required=True, error='app_model_key is a required parameter')
    components = market_app_service.list_wutong_app_components(session,
                                                               user.enterprise_id, team, app_id,
                                                               app_model_key, group_id)
    return JSONResponse(general_message(200, "success", "查询成功", list=components), status_code=200)


@router.get("/teams/{team_name}/apps/{serviceAlias}/logs", response_model=Response, name="查看容器日志")
async def get_container_log(request: Request,
                            team_name: Optional[str] = None,
                            serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    pod_name = request.query_params.get("pod_name")
    if not pod_name:
        raise AbortRequest("the field 'pod_name' is required")
    container_name = request.query_params.get("container_name")
    if not container_name:
        raise AbortRequest("the field 'container_name' is required")
    follow = True if request.query_params.get("follow") == "true" else False
    stream = component_log_service.get_component_log_stream(session, team_name, region_name,
                                                            serviceAlias,
                                                            pod_name, container_name, follow)
    response = StreamingResponse(stream)
    # disabled the GZipMiddleware on this call by inserting a fake header into the StreamingHttpResponse
    # response['Content-Encoding'] = 'identity'
    return response


@router.put("/teams/{team_name}/apps/{serviceAlias}/check_update", response_model=Response, name="组件检测信息修改")
async def get_app_visit_info(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    组件检测信息修改
    ---
    serializer: TenantServiceUpdateSerilizer
    """
    data = await request.json()
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    code, msg = application_service.update_check_app(session, team, service, data)
    if code != 200:
        return JSONResponse(general_message(code, "update service info error", msg), status_code=code)
    result = general_message(200, "success", "修改成功")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/docker_compose", response_model=Response, name="docker_compose创建组件")
async def docker_compose_components(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user: Users = Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    group_name = data.get("group_name", None)
    k8s_app = data.get("k8s_app", None)
    hub_user = data.get("user_name", "")
    hub_pass = data.get("password", "")
    yaml_content = data.get("yaml_content", "")
    group_note = data.get("group_note", "")
    if group_note and len(group_note) > 2048:
        return JSONResponse(general_message(400, "node too long", "应用备注长度限制2048"), status_code=400)
    if not group_name:
        return JSONResponse(general_message(400, 'params error', "请指明需要创建的compose组名"), status_code=400)
    if not yaml_content:
        return JSONResponse(general_message(400, "params error", "未指明yaml内容"), status_code=400)
    # Parsing yaml determines whether the input is illegal
    code, msg, json_data = compose_service.yaml_to_json(yaml_content)
    if code != 200:
        return JSONResponse(general_message(code, "parse yaml error", msg), status_code=code)
    region = await region_services.get_region_by_request(session, request)
    # 创建组
    group_info = application_service.create_app(
        session, team, region.region_name, group_name, group_note, user.get_username(), k8s_app=k8s_app)
    code, msg, group_compose = compose_service.create_group_compose(
        session, team, region.region_name, group_info["group_id"], yaml_content, hub_user, hub_pass)
    if code != 200:
        return JSONResponse(general_message(code, "create group compose error", msg), status_code=code)
    bean = dict()
    bean["group_id"] = group_compose.group_id
    bean["compose_id"] = group_compose.compose_id
    bean["app_name"] = group_info["application_name"]
    result = general_message(200, "operation success", "compose组创建成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/groups/{group_id}/compose_build", response_model=Response, name="compose应用构建")
async def compose_build(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user: Users = Depends(deps.get_current_user)) -> Any:
    probe_map = dict()
    services = None
    data = await request.json()
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)
    try:
        compose_id = data.get("compose_id", None)
        if not compose_id:
            return JSONResponse(general_message(400, "params error", "参数异常"), status_code=400)
        group_compose = compose_service.get_group_compose_by_compose_id(session, compose_id)
        services = compose_service.get_compose_services(session, compose_id)
        # 数据中心创建组件
        new_app_list = []
        for service in services:
            new_service = application_service.create_region_service(session, team, service, user.nick_name)
            new_app_list.append(new_service)
        group_compose.create_status = "complete"
        # group_compose.save()
        for s in new_app_list:
            try:
                app_manage_service.deploy(session, team, s, user, oauth_instance=oauth_instance)
            except ErrInsufficientResource as e:
                result = general_message(e.error_code, e.msg, e.msg_show)
                return JSONResponse(result, status_code=e.status_code)
            except Exception as e:
                logger.exception(e)
                continue

        result = general_message(200, "success", "构建成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
        if services:
            for service in services:
                if probe_map:
                    probe_id = probe_map.get(service.service_id)
                    probe_service.delete_service_probe(session, team, service, probe_id)
                event_service.delete_service_events(session, service)
                port_service.delete_region_port(session, team, service)
                volume_service.delete_region_volumes(session, team, service)
                env_var_service.delete_region_env(session, team, service)
                dependency_service.delete_region_dependency(session, team, service)
                app_manage_service.delete_region_service(session, team, service)
                service.create_status = "checked"
        raise e
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/keyword", response_model=Response, name="修改组件触发自动部署关键字")
async def update_keyword(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    keyword = data.get("keyword", None)
    if not keyword:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    is_pass, msg = application_service.check_service_cname(keyword)
    if not is_pass:
        return JSONResponse(general_message(400, "param error", msg), status_code=400)
    service_webhook = service_webhooks_repo.get_service_webhooks_by_service_id_and_type(
        session, service.service_id, "code_webhooks")
    if not service_webhook:
        return JSONResponse(general_message(412, "keyword is null", "组件自动部署属性不存在"), status_code=412)
    service_webhook.deploy_keyword = keyword
    # service_webhook.save()
    result = general_message(200, "success", "修改成功", bean=jsonable_encoder(service_webhook))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/build_envs", response_model=Response, name="修改构建组件的环境变量参数")
async def update_build_envs(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    build_env_dict = data.get("build_env_dict", None)
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    build_envs = env_var_service.get_service_build_envs(session, service)
    # 传入为空，清除
    if not build_env_dict:
        for build_env in build_envs:
            session.execute(delete(ComponentEnvVar).where(
                ComponentEnvVar.ID == build_env.ID
            ))
            session.flush()
        return JSONResponse(general_message(200, "success", "设置成功"))

    # 传入有值，清空再添加
    if build_envs:
        for build_env in build_envs:
            session.execute(delete(ComponentEnvVar).where(
                ComponentEnvVar.ID == build_env.ID
            ))
            session.flush()
    for key, value in list(build_env_dict.items()):
        name = "构建运行时环境变量"
        attr_name = key
        attr_value = value
        is_change = True
        code, msg, data = env_var_service.add_service_build_env_var(session, service, 0, name, attr_name,
                                                                    attr_value, is_change)
        if code != 200:
            continue

    result = general_message(200, "success", "环境变量添加成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/code/branch", response_model=Response, name="获取组件代码仓库分支")
async def get_code_branch(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    branches = git_service.get_service_code_branch(session, user, service)
    bean = {"current_version": service.code_version}
    result = general_message(200, "success", "查询成功", bean=bean, list=branches)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/rollback", response_model=Response,
             name="组件版本回滚")
async def components_rollback(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user=Depends(deps.get_current_user)) -> Any:
    """
    回滚组件
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
        - name: deploy_version
          description: 回滚的版本
          required: true
          type: string
          paramType: form

    """
    try:
        data = await request.json()
        deploy_version = data.get("deploy_version", None)
        upgrade_or_rollback = data.get("upgrade_or_rollback", None)
        if not deploy_version or not upgrade_or_rollback:
            return JSONResponse(general_message(400, "deploy version is not found", "请指明版本及操作类型"), status_code=400)

        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        code, msg = app_manage_service.roll_back(session,
                                                 team, service, user, deploy_version,
                                                 upgrade_or_rollback)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "roll back app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "failed"), status_code=412)
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/version/{version_id}", response_model=Response,
               name="删除组件的某次构建版本")
async def delete_components_version(
        request: Request,
        serviceAlias: Optional[str] = None,
        version_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user=Depends(deps.get_current_user)) -> Any:
    """
    删除组件的某次构建版本
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
        - name: version_id
          description: 版本ID
          required: true
          type: string
          paramType: path

    """
    if not version_id:
        return JSONResponse(general_message(400, "attr_name not specify", "请指定需要删除的具体版本"), status_code=400)

    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    remote_build_client.delete_service_build_version(session, response_region, team.tenant_name,
                                                     service.service_alias,
                                                     version_id)
    # event_repo.delete_event_by_build_version(self.service.service_id, version_id)
    result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result["code"])
