import json
from typing import Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status

from apis.manage.components.wutong_domain_controller import validate_domain
from core import deps
from core.utils.constants import DomainType
from core.utils.reqparse import parse_item
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.main import AbortRequest, ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import configuration_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.app_actions.app_manage import app_manage_service
from service.app_config.domain_service import domain_service
from service.app_config.port_service import port_service
from service.region_service import EnterpriseConfigService, region_services

router = APIRouter()


@router.get("/teams/{team_name}/group/service/visit", response_model=Response, name="获取组件访问信息")
async def get_group_service_visit(service_alias: Optional[str] = None,
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
        - name: service_list
          description: 组件别名列表
          required: true
          type: string
          paramType: path
    """

    try:
        if not service_alias:
            return JSONResponse(general_message(200, "not service", "当前组内无组件", bean={"is_null": True}), status_code=200)
        service_access_list = list()
        if not team:
            return JSONResponse(general_message(400, "not tenant", "团队不存在"), status_code=400)
        service_list = service_alias.split('-')
        for service_alias in service_list:
            bean = dict()
            service = service_info_repo.get_service_by_service_alias(session=session, service_alias=service_alias)
            access_type, data = port_service.get_access_info(session=session, tenant=team, service=service)
            bean["access_type"] = access_type
            bean["access_info"] = jsonable_encoder(data)
            service_access_list.append(bean)
        return JSONResponse(general_message(200, "success", "操作成功", list=service_access_list), status_code=200)
    except Exception as e:
        logger.exception(e)
        return error_message(e.__str__())


@router.delete("/teams/{team_name}/batch_delete", response_model=Response, name="批量删除组件")
async def batch_delete_components(request: Request,
                                  session: SessionClass = Depends(deps.get_session),
                                  user=Depends(deps.get_current_user),
                                  team=Depends(deps.get_current_team)) -> Any:
    """
    批量删除组件

    """
    data = await request.json()
    service_ids = data.get("service_ids", None)
    service_id_list = service_ids.split(",")
    services = service_info_repo.get_services_by_service_ids(session, service_id_list)
    msg_list = []
    for service in services:
        code, msg = app_manage_service.batch_delete(session=session, user=user, tenant=team, service=service,
                                                    is_force=True)
        msg_dict = dict()
        msg_dict['status'] = code
        msg_dict['msg'] = msg
        msg_dict['service_id'] = service.service_id
        msg_dict['service_cname'] = service.service_cname
        msg_list.append(msg_dict)
    code = 200
    result = general_message(code, "success", "操作成功", list=msg_list)
    return JSONResponse(result, status_code=result['code'])


@router.post("/teams/{team_name}/httpdomain", response_model=Response, name="添加HTTP网关策略")
async def add_http_domain(request: Request,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user),
                          team=Depends(deps.get_current_team)) -> Any:
    """
    添加http策略

    """
    data = await request.json()
    container_port = data.get("container_port", None)
    domain_name = data.get("domain_name", None)
    flag, msg = validate_domain(domain_name)
    if not flag:
        result = general_message(400, "invalid domain", msg)
        return JSONResponse(result, status_code=400)
    certificate_id = data.get("certificate_id", None)
    service_id = data.get("service_id", None)
    do_path = data.get("domain_path", "")
    domain_cookie = data.get("domain_cookie", None)
    domain_heander = data.get("domain_heander", None)
    rule_extensions = data.get("rule_extensions", None)
    whether_open = data.get("whether_open", False)
    the_weight = data.get("the_weight", 100)
    domain_path = do_path if do_path else "/"
    auto_ssl = data.get("auto_ssl", False)
    auto_ssl_config = data.get("auto_ssl_config", None)
    # path-rewrite
    path_rewrite = data.get("path_rewrite", False)
    rewrites = data.get("rewrites", None)

    # 判断参数
    if len(do_path) > 1024:
        raise AbortRequest(msg="Maximum length of location 1024", msg_show="Location最大长度1024")
    if not container_port or not domain_name or not service_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    service = service_info_repo.get_service_by_service_id(session, service_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)
    protocol = "http"
    if certificate_id:
        protocol = "https"
    # 判断策略是否存在
    service_domain = domain_repo.get_domain_by_name_and_port_and_protocol(session,
                                                                          service.service_id, container_port,
                                                                          domain_name,
                                                                          protocol, domain_path)
    if service_domain:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)

    if auto_ssl:
        auto_ssl = True
    if auto_ssl:
        auto_ssl_configs = EnterpriseConfigService(team.enterprise_id).get_auto_ssl_info(session=session)
        if not auto_ssl_configs:
            result = general_message(400, "failed", "未找到自动分发证书相关配置")
            return JSONResponse(result, status_code=400)

        else:
            if auto_ssl_config not in list(auto_ssl_configs.keys()):
                result = general_message(400, "failed", "未找到该自动分发方式")
                return JSONResponse(result, status_code=400)

    # 域名，path相同的组件，如果已存在http协议的，不允许有httptohttps扩展功能，如果以存在https，且有改扩展功能的，则不允许添加http协议的域名
    domains = domain_repo.get_domain_by_name_and_path(session, domain_name, domain_path)
    domain_protocol_list = []
    is_httptohttps = False
    if domains:
        for domain in domains:
            domain_protocol_list.append(domain.protocol)
            if "httptohttps" in domain.rule_extensions:
                is_httptohttps = True

    if is_httptohttps:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)
    add_httptohttps = False
    if rule_extensions:
        for rule in rule_extensions:
            if rule["key"] == "httptohttps":
                add_httptohttps = True
    if "http" in domain_protocol_list and add_httptohttps:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)

    if service.service_source == "third_party":
        msg, msg_show, code = port_service.check_domain_thirdpart(session=session, tenant=team, service=service)
        if code != 200:
            logger.exception(msg, msg_show)
            return JSONResponse(general_message(code, msg, msg_show), status_code=code)

    if whether_open:
        tenant_service_port = port_service.get_service_port_by_port(session=session, service=service,
                                                                    port=container_port)
        # 仅开启对外端口
        code, msg, data = port_service.manage_port(session=session, tenant=team, service=service,
                                                   region_name=service.service_region,
                                                   container_port=int(tenant_service_port.container_port),
                                                   action="only_open_outer",
                                                   protocol=tenant_service_port.protocol,
                                                   port_alias=tenant_service_port.port_alias)
        if code != 200:
            return JSONResponse(general_message(code, "change port fail", msg), status_code=code)
    tenant_service_port = port_service.get_service_port_by_port(session=session, service=service, port=container_port)
    if not tenant_service_port.is_outer_service:
        return JSONResponse(general_message(200, "not outer port", "没有开启对外端口", bean={"is_outer_service": False}),
                            status_code=200)

    # 绑定端口(添加策略)
    httpdomain = {
        "domain_name": domain_name,
        "container_port": container_port,
        "protocol": protocol,
        "certificate_id": certificate_id,
        "domain_type": DomainType.WWW,
        "domain_path": domain_path,
        "domain_cookie": domain_cookie,
        "domain_heander": domain_heander,
        "the_weight": the_weight,
        "rule_extensions": rule_extensions,
        "auto_ssl": auto_ssl,
        "auto_ssl_config": auto_ssl_config,
        "path_rewrite": path_rewrite,
        "rewrites": rewrites
    }
    try:
        data = domain_service.bind_httpdomain(session=session, tenant=team, user=user, service=service,
                                              httpdomain=httpdomain)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show),
                            status_code=e.status_code)
    result = general_message(201, "success", "策略添加成功", bean=data)
    return JSONResponse(result, status_code=status.HTTP_201_CREATED)


@router.get("/teams/{team_name}/domain/{rule_id}/put_gateway", response_model=Response, name="获取策略的网关自定义参数")
async def get_domain_parameter(rule_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    if not rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)
    cf = configuration_repo.get_configuration_by_rule_id(session, rule_id)
    bean = dict()
    if cf:
        bean["rule_id"] = cf.rule_id
        bean["value"] = json.loads(cf.value)
    result = general_message(200, "success", "查询成功", bean=bean)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/domain/{rule_id}/put_gateway", response_model=Response, name="修改网关的自定义参数")
async def set_domain_parameter(request: Request,
                               rule_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    # todo await？？
    value = await parse_item(request, 'value', required=True, error='value is a required parameter')
    domain_service.update_http_rule_config(session=session, team=team, region_name=response_region, rule_id=rule_id,
                                           configs=value)
    result = general_message(200, "success", "更新成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/httpdomain", response_model=Response, name="获取单个http策略")
async def add_http_domain(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    http_rule_id = request.query_params.get("http_rule_id", None)
    # 判断参数
    if not http_rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)
    domain = domain_repo.get_service_domain_by_http_rule_id(session, http_rule_id)
    if domain:
        bean = jsonable_encoder(domain)
        service = service_info_repo.get_service_by_service_id(session, domain.service_id)
        service_alias = service.service_cname if service else ''
        group_name = ''
        g_id = 0
        if service:
            gsr = app_component_relation_repo.get_group_by_service_id(session, service.service_id)
            if gsr:
                group = application_repo.get_group_by_id(session, int(gsr.group_id))
                group_name = group.group_name if group else ''
                g_id = int(gsr.group_id)
        if domain.certificate_id:
            certificate_info = domain_repo.get_certificate_by_pk(session, int(domain.certificate_id))

            bean.update({"certificate_name": certificate_info.alias})
        bean.update({"service_alias": service_alias})
        bean.update({"group_name": group_name})
        bean.update({"g_id": g_id})
        if bean["rewrites"] is not None and bean["rewrites"] != "":
            bean.update({"rewrites": json.loads(bean["rewrites"])})
        else:
            bean.update({"rewrites": []})
    else:
        bean = dict()
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/httpdomain", response_model=Response, name="编辑http策略")
async def add_http_domain(request: Request,
                          session: SessionClass = Depends(deps.get_session),
                          team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    container_port = data.get("container_port", None)
    domain_name = data.get("domain_name", None)
    flag, msg = validate_domain(domain_name)
    if not flag:
        result = general_message(400, "invalid domain", msg)
        return JSONResponse(result, status_code=400)
    certificate_id = data.get("certificate_id", None)
    service_id = data.get("service_id", None)
    do_path = data.get("domain_path", "")
    domain_cookie = data.get("domain_cookie", None)
    domain_heander = data.get("domain_heander", None)
    rule_extensions = data.get("rule_extensions", None)
    http_rule_id = data.get("http_rule_id", None)
    the_weight = data.get("the_weight", 100)
    domain_path = do_path if do_path else "/"
    auto_ssl = data.get("auto_ssl", False)
    auto_ssl_config = data.get("auto_ssl_config", None)
    # path-rewrite
    path_rewrite = data.get("path_rewrite", False)
    rewrites = data.get("rewrites", None)

    # 判断参数
    if len(do_path) > 1024:
        raise AbortRequest(msg="Maximum length of location 1024", msg_show="Location最大长度1024")
    if not service_id or not container_port or not domain_name or not http_rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    service = service_info_repo.get_service_by_service_id(session, service_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)

    # 域名，path相同的组件，如果已存在http协议的，不允许有httptohttps扩展功能，如果以存在https，且有改扩展功能的，则不允许添加http协议的域名
    add_httptohttps = False
    if rule_extensions:
        for rule in rule_extensions:
            if rule["key"] == "httptohttps":
                add_httptohttps = True

    domains = domain_repo.get_domain_by_name_and_path_and_protocol(session, domain_name, domain_path, "http")
    rule_id_list = []
    if domains:
        for domain in domains:
            rule_id_list.append(domain.http_rule_id)
    if len(rule_id_list) > 1 and add_httptohttps:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)
    if len(rule_id_list) == 1 and add_httptohttps and http_rule_id != rule_id_list[0]:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)
    update_data = {
        "domain_name": domain_name,
        "container_port": container_port,
        "certificate_id": certificate_id,
        "domain_type": DomainType.WWW,
        "domain_path": domain_path,
        "domain_cookie": domain_cookie,
        "domain_heander": domain_heander,
        "the_weight": the_weight,
        "rule_extensions": rule_extensions,
        "auto_ssl": auto_ssl,
        "auto_ssl_config": auto_ssl_config,
        "path_rewrite": path_rewrite,
        "rewrites": rewrites
    }
    domain_service.update_httpdomain(session=session, tenant=team, service=service, http_rule_id=http_rule_id,
                                     update_data=update_data)
    result = general_message(200, "success", "策略编辑成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/httpdomain", response_model=Response, name="删除http策略")
async def delete_http_domain(request: Request,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    service_id = data.get("service_id", None)
    http_rule_id = data.get("http_rule_id", None)
    if not http_rule_id or not service_id:
        return JSONResponse(general_message(400, "params error", "参数错误"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    domain_service.unbind_httpdomain(session=session, tenant=team, region=response_region, http_rule_id=http_rule_id)
    result = general_message(200, "success", "策略删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/tcpdomain", response_model=Response, name="添加tcp网关策略")
async def add_tcp_domain(request: Request,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user),
                         team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    container_port = data.get("container_port", None)
    service_id = data.get("service_id", None)
    end_point = data.get("end_point", None)
    whether_open = data.get("whether_open", False)
    rule_extensions = data.get("rule_extensions", None)
    default_port = data.get("default_port", None)
    default_ip = data.get("default_ip", None)

    if not container_port or not service_id or not end_point:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    service = service_info_repo.get_service_by_service_id(session, service_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)

    # Check if the given endpoint exists.
    region = region_repo.get_region_by_region_name(session, service.service_region)
    service_tcpdomain = tcp_domain_repo.get_tcpdomain_by_end_point(session, region.region_id, end_point)
    if service_tcpdomain:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)

    if service.service_source == "third_party":
        msg, msg_show, code = port_service.check_domain_thirdpart(session=session, tenant=team, service=service)
        if code != 200:
            logger.exception(msg, msg_show)
            return JSONResponse(general_message(code, msg, msg_show), status_code=code)

    if whether_open:
        tenant_service_port = port_service.get_service_port_by_port(session=session, service=service,
                                                                    port=container_port)
        # 仅打开对外端口
        code, msg, data = port_service.manage_port(session=session, tenant=team, service=service,
                                                   region_name=service.service_region,
                                                   container_port=int(tenant_service_port.container_port),
                                                   action="only_open_outer",
                                                   protocol=tenant_service_port.protocol,
                                                   port_alias=tenant_service_port.port_alias)
        if code != 200:
            return JSONResponse(general_message(code, "change port fail", msg), status_code=code)
    tenant_service_port = port_service.get_service_port_by_port(session=session, service=service, port=container_port)

    if not tenant_service_port.is_outer_service:
        return JSONResponse(general_message(200, "not outer port", "没有开启对外端口", bean={"is_outer_service": False}),
                            status_code=200)

    # 添加tcp策略
    data = domain_service.bind_tcpdomain(session=session, tenant=team, user=user, service=service,
                                         end_point=end_point, container_port=container_port, default_port=default_port,
                                         rule_extensions=rule_extensions, default_ip=default_ip)
    result = general_message(200, "success", "tcp策略添加成功", bean=data)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/tcpdomain", response_model=Response, name="获取单个tcp/udp策略信息")
async def get_tcp_domain(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    tcp_rule_id = request.query_params.get("tcp_rule_id", None)
    # 判断参数
    if not tcp_rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    tcpdomain = tcp_domain_repo.get_service_tcpdomain_by_tcp_rule_id(session, tcp_rule_id)
    if tcpdomain:
        bean = jsonable_encoder(tcpdomain)
        service = service_info_repo.get_service_by_service_id(session, tcpdomain.service_id)
        service_alias = service.service_cname if service else ''
        group_name = ''
        g_id = 0
        if service:
            gsr = app_component_relation_repo.get_group_by_service_id(session, service.service_id)
            if gsr:
                group = application_repo.get_group_by_id(session, int(gsr.group_id))
                group_name = group.group_name if group else ''
                g_id = int(gsr.group_id)
        bean.update({"service_alias": service_alias})
        bean.update({"group_name": group_name})
        bean.update({"g_id": g_id})
        result = general_message(200, "success", "查询成功", bean=bean)
    else:
        bean = dict()
        result = general_message(200, "success", "查询成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/tcpdomain", response_model=Response, name="修改单个tcp/udp策略信息")
async def set_tcp_domain(request: Request,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user),
                         team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    container_port = data.get("container_port", None)
    service_id = data.get("service_id", None)
    end_point = data.get("end_point", None)
    tcp_rule_id = data.get("tcp_rule_id", None)
    rule_extensions = data.get("rule_extensions", None)
    type = data.get("type", None)
    default_ip = data.get("default_ip", None)

    # 判断参数
    if not tcp_rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    service = service_info_repo.get_service_by_service_id(session, service_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)

    # 查询端口协议
    tenant_service_port = port_service.get_service_port_by_port(session=session, service=service, port=container_port)
    if tenant_service_port:
        protocol = tenant_service_port.protocol
    else:
        protocol = ''

    # Check if the given endpoint exists.
    region = region_repo.get_region_by_region_name(session, service.service_region)
    service_tcpdomain = tcp_domain_repo.get_tcpdomain_by_end_point(session, region.region_id, end_point)
    if service_tcpdomain and service_tcpdomain[0].tcp_rule_id != tcp_rule_id:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)

    # 修改策略
    code, msg = domain_service.update_tcpdomain(session=session, tenant=team, user=user, service=service,
                                                end_point=end_point, container_port=container_port,
                                                tcp_rule_id=tcp_rule_id,
                                                protocol=protocol, type=type, rule_extensions=rule_extensions,
                                                default_ip=default_ip)

    if code != 200:
        return JSONResponse(general_message(code, "bind domain error", msg), status_code=code)

    result = general_message(200, "success", "策略修改成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/tcpdomain", response_model=Response, name="删除单个tcp/udp策略信息")
async def delete_tcp_domain(request: Request,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    tcp_rule_id = data.get("tcp_rule_id", None)
    if not tcp_rule_id:
        return JSONResponse(general_message(400, "params error", "参数错误"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    domain_service.unbind_tcpdomain(session=session, tenant=team, region=response_region, tcp_rule_id=tcp_rule_id)
    result = general_message(200, "success", "策略删除成功")
    return JSONResponse(result, status_code=result["code"])
