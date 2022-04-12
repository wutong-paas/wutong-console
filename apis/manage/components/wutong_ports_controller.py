from typing import Any, Optional
from fastapi import Request, APIRouter, Header, Depends
from fastapi.encoders import jsonable_encoder
from loguru import logger

from core.utils.reqparse import parse_item
from core import deps
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.component.service_config_repo import domain_repo
from repository.component.group_service_repo import service_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from core.utils.return_message import general_message
from fastapi.responses import JSONResponse

from service.app_config.domain_service import domain_service
from service.app_config.port_service import port_service
from service.team_service import team_services
from service.user_service import user_svc

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/ports", response_model=Response, name="获取组件的端口信息")
async def get_ports(serviceAlias: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件的端口信息
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
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    tenant_service_ports = port_service.get_service_ports(session=session, service=service)
    port_list = []
    for port in tenant_service_ports:
        port_info = port.__dict__
        variables = port_service.get_port_variables(session=session, tenant=team, service=service, port_info=port)
        port_info["environment"] = variables["environment"]
        outer_url = ""
        inner_url = ""

        if port_info["environment"] and port.is_inner_service:
            try:
                inner_host, inner_port = "127.0.0.1", None
                for pf in port_info["environment"]:
                    if not pf.get("name"):
                        continue
                    if pf.get("name").endswith("PORT"):
                        inner_port = pf.get("value")
                    if pf.get("name").endswith("HOST"):
                        inner_host = pf.get("value")
                inner_url = "{0}:{1}".format(inner_host, inner_port)
            except Exception as se:
                logger.exception(se)
        port_info["inner_url"] = inner_url
        outer_service = variables.get("outer_service", None)
        if outer_service:
            outer_url = "{0}:{1}".format(variables["outer_service"]["domain"], variables["outer_service"]["port"])
        port_info["outer_url"] = outer_url
        port_info["bind_domains"] = []
        bind_domains = domain_service.get_port_bind_domains(session=session, service=service,
                                                            container_port=port.container_port)
        if bind_domains:
            for bind_domain in bind_domains:
                if not bind_domain.domain_path:
                    bind_domain.domain_path = '/'
                    domain_repo.save_service_domain(session, bind_domain)
        port_info["bind_domains"] = [domain.__dict__ for domain in bind_domains]
        bind_tcp_domains = domain_service.get_tcp_port_bind_domains(session=session, service=service,
                                                                    container_port=port.container_port)

        if bind_tcp_domains:
            port_info["bind_tcp_domains"] = [domain.__dict__ for domain in bind_tcp_domains]
        else:
            port_info["bind_tcp_domains"] = []
        port_list.append(port_info)
    result = general_message(200, "success", "查询成功", list=jsonable_encoder(port_list))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/ports/{port}", response_model=Response,
            name="修改组件的某个端口（打开|关闭|修改协议|修改环境变量）")
async def update_ports(request: Request,
                       serviceAlias: Optional[str] = None,
                       port: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       user=Depends(deps.get_current_user),
                       team=Depends(deps.get_current_team)) -> Any:
    """
    修改组件的某个端口（打开|关闭|修改协议|修改环境变量）
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
        - name: port
          description: 端口号
          required: true
          type: string
          paramType: path
        - name: action
          description: 操作类型（open_outer|close_outer|open_inner|close_inner|change_protocol|change_port_alias）
          required: true
          type: string
          paramType: form
        - name: port_alias
          description: 端口别名(修改端口别名时必须)
          required: false
          type: string
          paramType:
        - name: protocol
          description: 端口协议(修改端口协议时必须)
          required: false
          type: string
          paramType: path

    """
    data = await request.json()
    action = data.get("action", None)
    port_alias = data.get("port_alias", None)
    protocol = data.get("protocol", None)
    container_port = port
    k8s_service_name = await parse_item(request, "k8s_service_name", default="")
    if not container_port:
        raise AbortRequest("container_port not specify", "端口变量名未指定")

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    response_region = region.region_name
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)

    if service.service_source == "third_party" and ("outer" in action):
        msg, msg_show, code = port_service.check_domain_thirdpart(session=session, tenant=team, service=service)
        if code != 200:
            logger.exception(msg, msg_show)
            return JSONResponse(general_message(code, msg, msg_show), status_code=code)

    code, msg, data = port_service.manage_port(session=session, tenant=team, service=service,
                                               region_name=response_region, container_port=int(container_port),
                                               action=action,
                                               protocol=protocol, port_alias=port_alias,
                                               k8s_service_name=k8s_service_name, user_name=user.nick_name)
    if code != 200:
        return JSONResponse(general_message(code, "change port fail", msg), status_code=code)

    session.commit()
    result = general_message(200, "success", "操作成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/ports", response_model=Response, name="为组件添加端口")
async def add_ports(request: Request,
                    serviceAlias: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    user=Depends(deps.get_current_user),
                    team=Depends(deps.get_current_team)) -> Any:
    """
    为组件添加端口
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
        - name: port
          description: 端口
          required: true
          type: integer
          paramType: form
        - name: protocol
          description: 端口协议
          required: true
          type: string
          paramType: form
        - name: port_alias
          description: 端口别名
          required: true
          type: string
          paramType: form
        - name: is_inner_service
          description: 是否打开对内组件
          required: true
          type: boolean
          paramType: form
        - name: is_outer_service
          description: 是否打开对外组件
          required: true
          type: boolean
          paramType: form

    """
    data = await request.json()
    port = data.get("port", None)
    protocol = data.get("protocol", None)
    port_alias = data.get("port_alias", None)
    is_inner_service = data.get('is_inner_service', False)
    is_outer_service = data.get('is_outer_service', False)

    service = service_repo.get_service(session, serviceAlias, team.tenant_id)

    if not port:
        return JSONResponse(general_message(400, "params error", "缺少端口参数"), status_code=400)
    if not protocol:
        return JSONResponse(general_message(400, "params error", "缺少协议参数"), status_code=400)
    if not port_alias:
        port_alias = service.service_alias.upper().replace("-", "_") + str(port)
    code, msg, port_info = port_service.add_service_port(session=session, tenant=team, service=service,
                                                         container_port=port, protocol=protocol, port_alias=port_alias,
                                                         is_inner_service=is_inner_service,
                                                         is_outer_service=is_outer_service, k8s_service_name=None,
                                                         user_name=user.nick_name)
    if code != 200:
        return JSONResponse(general_message(code, "add port error", msg), status_code=code)

    result = general_message(200, "success", "端口添加成功", bean=jsonable_encoder(port_info))
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/ports/{port}", response_model=Response, name="删除组件的某个端口")
async def delete_ports(serviceAlias: Optional[str] = None,
                       port: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       user=Depends(deps.get_current_user),
                       team=Depends(deps.get_current_team)) -> Any:
    """
     删除组件的某个端口
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
         - name: port
           description: 端口号
           required: true
           type: string
           paramType: path

     """
    try:
        service = service_repo.get_service(session, serviceAlias, team.tenant_id)
        container_port = port
        if not container_port:
            raise AbortRequest("container_port not specify", "端口变量名未指定")
        data = port_service.delete_port_by_container_port(session=session, tenant=team, service=service,
                                                          container_port=int(container_port),
                                                          user_name=user.nick_name)
        result = general_message(200, "success", "删除成功", bean=jsonable_encoder(data))
    except AbortRequest as e:
        result = general_message(e.status_code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])
