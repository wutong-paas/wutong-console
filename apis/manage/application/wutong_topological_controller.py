from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import port_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.port_service import port_service
from service.region_service import region_services
from service.topological_service import topological_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/regions/{region_name}/topological", response_model=Response, name="应用拓扑图")
async def get_topological(
        region_name,
        env_id: Optional[str] = None,
        group_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    应用拓扑图(未分组应用无拓扑图, 直接返回列表展示)
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    code = 200
    if group_id == "-1":
        no_service_list = service_info_repo.get_no_group_service_status_by_group_id(
            session=session, tenant_env=env, region_name=region_name, tenant_env_id=env.env_id)
        return JSONResponse(general_message(200, "query success", "应用查询成功", list=no_service_list), status_code=200)
    else:
        if group_id is None or not group_id.isdigit():
            code = 400
            return JSONResponse(general_message(code, "group_id is missing or not digit!", "group_id缺失或非数字"),
                                status_code=code)
        env_id = env.env_id
        group_count = application_repo.get_group_count_by_team_id_and_group_id(session=session, env_id=env_id,
                                                                               group_id=group_id)
        if group_count == 0:
            code = 202
            return JSONResponse(general_message(code, "group is not yours!", "当前组已删除或您无权限查看!", bean={}),
                                status_code=code)
        topological_info = topological_service.get_group_topological_graph(session=session,
                                                                           group_id=group_id, region=region_name,
                                                                           tenant_env=env)
        result = general_message(code, "Obtain topology success.", "获取拓扑图成功", bean=topological_info)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/topological/ports", response_model=Response,
            name="组件拓扑图打开(关闭)对外端口")
async def open_topological_port(
        request: Request,
        env_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    组件拓扑图打开(关闭)对外端口
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    open_outer = data.get("open_outer", False)
    close_outer = data.get("close_outer", False)
    container_port = data.get("container_port", None)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    # 开启对外端口
    if open_outer:
        tenant_service_port = port_service.get_service_port_by_port(session, service, int(container_port))
        if service.service_source == "third_party":
            msg, msg_show, code = port_service.check_domain_thirdpart(session, env, service)
            if code != 200:
                logger.exception(msg, msg_show)
                return JSONResponse(general_message(code, msg, msg_show), status_code=code)
        code, msg, data = port_service.manage_port(session, env, service, response_region, int(container_port),
                                                   "open_outer", tenant_service_port.protocol,
                                                   tenant_service_port.port_alias)
        if code != 200:
            return JSONResponse(general_message(412, "open outer fail", "打开对外端口失败"), status_code=412)
        return JSONResponse(general_message(200, "open outer success", "开启成功"), status_code=200)
    # 关闭该组件所有对外端口
    if close_outer:
        tenant_service_ports = port_service.get_service_ports(session, service)
        for tenant_service_port in tenant_service_ports:
            code, msg, data = port_service.manage_port(session, env, service, response_region,
                                                       tenant_service_port.container_port, "close_outer",
                                                       tenant_service_port.protocol, tenant_service_port.port_alias)
            if code != 200:
                return JSONResponse(general_message(412, "open outer fail", "关闭对外端口失败"), status_code=412)
        return JSONResponse(general_message(200, "close outer success", "关闭对外端口成功"), status_code=200)

    # 校验要依赖的组件是否开启了对外端口
    open_outer_services = port_repo.get_service_ports_is_outer_service(session,
                                                                       env.env_id,
                                                                       service.service_id)
    if not open_outer_services:
        if service.service_source == "third_party":
            msg, msg_show, code = port_service.check_domain_thirdpart(session, env, service)
            if code != 200:
                logger.exception(msg, msg_show)
                return JSONResponse(general_message(code, msg, msg_show), status_code=code)
        service_ports = port_repo.get_service_ports(session, env.env_id, service.service_id)
        port_list = [service_port.container_port for service_port in service_ports]
        if len(port_list) == 1:
            # 一个端口直接开启
            tenant_service_port = port_service.get_service_port_by_port(session, service, int(port_list[0]))
            code, msg, data = port_service.manage_port(session, env, service, response_region, int(
                port_list[0]), "open_outer", tenant_service_port.protocol, tenant_service_port.port_alias)
            if code != 200:
                return JSONResponse(general_message(412, "open outer fail", "打开对外端口失败"), status_code=412)
            return JSONResponse(general_message(200, "open outer success", "开启成功"), status_code=200)
        else:
            # 多个端口需要用户选择后开启
            return JSONResponse(
                general_message(201, "the service does not open an external port", "该组件未开启对外端口", list=port_list),
                status_code=201)
    else:
        return JSONResponse(general_message(202, "the service has an external port open", "该组件已开启对外端口"),
                            status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/{group_id}/outer-service", response_model=Response, name="拓扑图中Internet详情")
async def get_topological_internet_info(
        request: Request,
        env_id: Optional[str] = None,
        group_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    拓扑图中Internet详情
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    if group_id == "-1":
        code = 200
        no_service_list = service_info_repo.get_no_group_service_status_by_group_id(
            session=session, tenant_env=env, region_name=response_region, tenant_env_id=env.env_id)
        result = general_message(200, "query success", "应用获取成功", list=no_service_list)
    else:
        code = 200
        if group_id is None or not group_id.isdigit():
            code = 400
            result = general_message(code, "group_id is missing or not digit!", "group_id缺失或非数字")
            return JSONResponse(result, status_code=code)
        group_count = application_repo.get_group_count_by_team_id_and_group_id(session=session, env_id=env_id,
                                                                               group_id=group_id)
        if group_count == 0:
            code = 202
            result = general_message(code, "group is not yours!", "当前组已删除或您无权限查看!",
                                     bean={"json_svg": {}, "json_data": {}})
            return JSONResponse(result, status_code=200)
        else:
            data = topological_service.get_internet_topological_graph(session=session, group_id=group_id,
                                                                      env_name=env.env_name)
            result = general_message(code, "Obtain topology internet success.", "获取拓扑图Internet成功", bean=data)
    return JSONResponse(result, status_code=code)


@router.get("/teams/{team_name}/env/{env_id}/topological/services/{serviceAlias}", response_model=Response,
            name="拓扑图中组件详情")
async def get_topological_info(
        env_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    拓扑图中组件详情
    ---
    parameters:
        - name: team_name
          description: 团队名
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
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    if not service:
        return JSONResponse(general_message(400, "service not found", "参数错误"), status_code=400)
    result = topological_service.get_group_topological_graph_details(
        session=session,
        tenant_env=env,
        env_id=env.env_id,
        env_name=env.env_name,
        service=service,
        region_name=service.service_region)
    result = general_message("0", "success", "成功", bean=result)
    return JSONResponse(result, status_code=200)
