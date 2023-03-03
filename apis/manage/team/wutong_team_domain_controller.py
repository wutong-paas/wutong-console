from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select, func
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import ServiceDomain, ServiceTcpDomain
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.domain_service import domain_service
from service.app_config.port_service import port_service
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/domain/query", response_model=Response, name="网关访问策略管理")
async def get_domain_query(request: Request,
                           session: SessionClass = Depends(deps.get_session),
                           env=Depends(deps.get_current_team_env)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    search_conditions = request.query_params.get("search_conditions", None)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    region = region_repo.get_region_by_region_name(session, region_name)
    # 查询分页排序
    if search_conditions:
        # 获取总数
        parms = {
            "tenant_id": env.tenant_id,
            "region_id": region.region_id,
            "search_conditions": search_conditions
        }
        sql = "select count(sd.domain_name) \
            from service_domain sd \
                left join service_group_relation sgr on sd.service_id = sgr.service_id \
                left join service_group sg on sgr.group_id = sg.id  \
            where sd.tenant_id=:tenant_id and sd.region_id=:region_id \
                and (sd.domain_name like '%' :search_conditions '%' \
                    or sd.service_alias like '%' :search_conditions '%' \
                    or sg.group_name like '%' :search_conditions '%');"
        res = session.execute(sql, parms)
        domain_count = res.fetchall()

        total = domain_count[0][0]
        start = (page - 1) * page_size
        remaining_num = total - (page - 1) * page_size
        end = page_size
        if remaining_num < page_size:
            end = remaining_num
        if remaining_num <= 0:
            tenant_tuples = []
        else:
            parms = {
                "tenant_id": env.tenant_id,
                "region_id": region.region_id,
                "search_conditions": search_conditions,
                "start": start,
                "end": end
            }
            sql = "select sd.domain_name, sd.type, sd.is_senior, sd.certificate_id, sd.service_alias, \
                    sd.protocol, sd.service_name, sd.container_port, sd.http_rule_id, sd.service_id, \
                    sd.domain_path, sd.domain_cookie, sd.domain_heander, sd.the_weight, \
                    sd.is_outer_service, sd.path_rewrite, sd.rewrites \
                from service_domain sd \
                    left join service_group_relation sgr on sd.service_id = sgr.service_id \
                    left join service_group sg on sgr.group_id = sg.id \
                where sd.tenant_id=:tenant_id \
                    and sd.region_id=:region_id \
                    and (sd.domain_name like '%' :search_conditions '%' \
                        or sd.service_alias like '%' :search_conditions '%' \
                        or sg.group_name like '%' :search_conditions '%') \
                order by type desc LIMIT :start,:end;"
            tenant_tuples = session.execute(sql, parms).fetchall()
    else:
        # 获取总数
        domain_count = (session.execute(
            select(func.count(ServiceDomain.ID)).where(ServiceDomain.tenant_id == env.tenant_id,
                                                       ServiceDomain.region_id == region.region_id))).first()

        total = domain_count[0]
        start = (page - 1) * page_size
        remaining_num = total - (page - 1) * page_size
        end = page_size
        if remaining_num <= page_size:
            end = remaining_num
        if remaining_num < 0:
            tenant_tuples = []
        else:
            tenant_tuples = (session.execute("""select domain_name, type, is_senior, certificate_id, service_alias, protocol,
                service_name, container_port, http_rule_id, service_id, domain_path, domain_cookie,
                domain_heander, the_weight, is_outer_service, path_rewrite, rewrites from service_domain where tenant_id='{0}'
                and region_id='{1}' order by type desc LIMIT {2},{3};""".format(env.tenant_id, region.region_id,
                                                                                start,
                                                                                end))).fetchall()
    # 拼接展示数据
    domain_list = list()
    for tenant_tuple in tenant_tuples:
        service = service_info_repo.get_service_by_service_id(session, tenant_tuple[9])
        service_cname = service.service_cname if service else ''
        service_alias = service.service_alias if service else tenant_tuple[6]
        group_name = ''
        group_id = 0
        if service:
            gsr = app_component_relation_repo.get_group_by_service_id(session, service.service_id)
            if gsr:
                group = application_repo.get_group_by_id(session, int(gsr.group_id))
                group_name = group.group_name if group else ''
                group_id = int(gsr.group_id)
        domain_dict = dict()
        certificate_info = domain_repo.get_certificate_by_pk(session, int(tenant_tuple[3]))
        if not certificate_info:
            domain_dict["certificate_alias"] = ''
        else:
            domain_dict["certificate_alias"] = certificate_info.alias
        domain_dict["domain_name"] = tenant_tuple[5] + "://" + tenant_tuple[0]
        domain_dict["type"] = tenant_tuple[1]
        domain_dict["is_senior"] = tenant_tuple[2]
        domain_dict["group_name"] = group_name
        domain_dict["service_cname"] = service_cname
        domain_dict["service_alias"] = service_alias
        domain_dict["container_port"] = tenant_tuple[7]
        domain_dict["http_rule_id"] = tenant_tuple[8]
        domain_dict["service_id"] = tenant_tuple[9]
        domain_dict["domain_path"] = tenant_tuple[10]
        domain_dict["domain_cookie"] = tenant_tuple[11]
        domain_dict["domain_heander"] = tenant_tuple[12]
        domain_dict["the_weight"] = tenant_tuple[13]
        domain_dict["is_outer_service"] = tenant_tuple[14]
        domain_dict["path_rewrite"] = tenant_tuple[15]
        domain_dict["rewrites"] = tenant_tuple[16]
        domain_dict["group_id"] = group_id
        domain_list.append(domain_dict)
    bean = dict()
    bean["total"] = total
    return general_message("0", "success", "查询成功", list=domain_list, bean=bean)


@router.get("/teams/{team_name}/env/{env_id}/domain/get_port", response_model=Response, name="获取可用的port")
async def get_port(
        request: Request,
        env_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    ipres, ipdata = remote_build_client.get_ips(session, region_name, env)
    if int(ipres.status) != 200:
        result = general_message(400, "call region error", "请求数据中心异常")
        return JSONResponse(result, status_code=result["code"])
    result = general_message("0", "success", "可用端口查询成功", list=ipdata.get("list"))
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/tcpdomain", response_model=Response, name="tcp/udp策略操作")
async def service_tcp_domain(request: Request,
                             session: SessionClass = Depends(deps.get_session)
                             ) -> Any:
    # 获取单个tcp/udp策略信息
    tcp_rule_id = request.query_params.get("tcp_rule_id", None)
    # 判断参数
    if not tcp_rule_id:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)

    tcpdomain = tcp_domain_repo.get_service_tcpdomain_by_tcp_rule_id(tcp_rule_id)
    if tcpdomain:
        bean = tcpdomain.__dict__
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
        result = general_message("0", "success", "查询成功", bean=bean)
    else:
        bean = dict()
        result = general_message("0", "success", "查询成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/env/{env_id}/tcpdomain", response_model=Response, name="修改tcp/udp策略操作")
async def service_tcp_domain(request: Request,
                             env_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             user=Depends(deps.get_current_user)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
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
        return JSONResponse(general_message(400, "not found service", "组件不存在"), status_code=400)

    # 查询端口协议
    tenant_service_port = port_service.get_service_port_by_port(session=session, service=service, port=container_port)
    if tenant_service_port:
        protocol = tenant_service_port.protocol
    else:
        protocol = ''

    # Check if the given endpoint exists.
    region = region_repo.get_region_by_region_name(session, service.service_region)
    service_tcpdomain = tcp_domain_repo.get_tcpdomain_by_end_point(region.region_id, end_point)
    if service_tcpdomain and service_tcpdomain[0].tcp_rule_id != tcp_rule_id:
        return JSONResponse(general_message(400, "failed", "策略已存在"), status_code=400)

    # 修改策略
    code, msg = domain_service.update_tcpdomain(session=session, tenant_env=env, user=user, service=service,
                                                end_point=end_point, container_port=container_port,
                                                tcp_rule_id=tcp_rule_id,
                                                protocol=protocol, type=type, rule_extensions=rule_extensions,
                                                default_ip=default_ip)

    if code != 200:
        return JSONResponse(general_message(code, "bind domain error", msg), status_code=code)

    return general_message("0", "success", "策略修改成功")


@router.get("/teams/{team_name}/env/{env_id}/tcpdomain/query", response_model=Response, name="查询团队下tcp/udp策略")
async def get_domain_query(request: Request,
                           session: SessionClass = Depends(deps.get_session),
                           env=Depends(deps.get_current_team_env)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    search_conditions = request.query_params.get("search_conditions", None)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    region = region_repo.get_region_by_region_name(session, region_name)
    try:
        # 查询分页排序
        if search_conditions:
            # 获取总数
            parms = {
                "tenant_id": env.tenant_id,
                "region_id": region.region_id,
                "search_conditions": search_conditions
            }
            sql = "select count(1) from service_tcp_domain std \
                            left join service_group_relation sgr on std.service_id = sgr.service_id \
                            left join service_group sg on sgr.group_id = sg.id  \
                        where std.tenant_id=:tenant_id and std.region_id=:region_id \
                            and (std.end_point like '%' :search_conditions '%' \
                                or std.service_alias like '%' :search_conditions '%' \
                                or sg.group_name like '%' :search_conditions '%');"
            domain_count = session.execute(sql, parms).fetchall()

            total = domain_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            parms.update({"start": start})
            parms.update({"end": end})
            sql = "select std.end_point, std.type, std.protocol, std.service_name, std.service_alias, \
                            std.container_port, std.tcp_rule_id, std.service_id, std.is_outer_service \
                        from service_tcp_domain std \
                            left join service_group_relation sgr on std.service_id = sgr.service_id \
                            left join service_group sg on sgr.group_id = sg.id  \
                        where std.tenant_id=:tenant_id and std.region_id=:region_id \
                            and (std.end_point like '%' :search_conditions '%' \
                                or std.service_alias like '%' :search_conditions '%' \
                                or sg.group_name like '%' :search_conditions '%') \
                        order by type desc LIMIT :start,:end;"
            tenant_tuples = session.execute(sql, parms).fetchall()
        else:
            # 获取总数
            domain_count = (session.execute(
                select(func.count(ServiceTcpDomain.ID)).where(ServiceTcpDomain.tenant_id == env.tenant_id,
                                                              ServiceTcpDomain.region_id == region.region_id))).first()

            total = domain_count[0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            tenant_tuples = (session.execute("""
                            select end_point, type,
                            protocol, service_name,
                            service_alias, container_port,
                            tcp_rule_id, service_id,
                            is_outer_service
                            from service_tcp_domain
                            where tenant_id='{0}' and region_id='{1}' order by type desc
                            LIMIT {2},{3};
                        """.format(env.tenant_id, region.region_id, start, end))).fetchall()
    except Exception as e:
        logger.exception(e)
        return JSONResponse(general_message(405, "faild", "查询数据库失败"), status_code=405)

    # 拼接展示数据
    domain_list = list()
    for tenant_tuple in tenant_tuples:
        service = service_info_repo.get_service_by_service_id(session, tenant_tuple[7])
        service_alias = service.service_cname if service else ''
        group_name = ''
        group_id = 0
        if service:
            gsr = app_component_relation_repo.get_group_by_service_id(session, service.service_id)
            if gsr:
                group = application_repo.get_group_by_id(session, int(gsr.group_id))
                group_name = group.group_name if group else ''
                group_id = int(gsr.group_id)
        domain_dict = dict()
        domain_dict["end_point"] = tenant_tuple[0]
        domain_dict["type"] = tenant_tuple[1]
        domain_dict["protocol"] = tenant_tuple[2]
        domain_dict["group_name"] = group_name
        domain_dict["service_alias"] = tenant_tuple[3]
        domain_dict["container_port"] = tenant_tuple[5]
        domain_dict["service_cname"] = service_alias
        domain_dict["tcp_rule_id"] = tenant_tuple[6]
        domain_dict["service_id"] = tenant_tuple[7]
        domain_dict["is_outer_service"] = tenant_tuple[8]
        domain_dict["group_id"] = group_id
        domain_dict["service_source"] = service.service_source if service else ''

        domain_list.append(domain_dict)
    bean = dict()
    bean["total"] = total
    return general_message("0", "success", "查询成功", list=domain_list, bean=bean)


@router.get("/teams/{team_name}/env/{env_id}/certificates", response_model=Response, name="网关证书管理")
async def get_tenant_certificates(request: Request,
                                  session: SessionClass = Depends(deps.get_session),
                                  env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取团队下的证书
    ---
    parameters:
        - name: tenantName
          description: 团队名
          required: true
          type: string
          paramType: path

    """
    page = int(request.query_params.get("page_num", 1))
    page_size = int(request.query_params.get("page_size", 10))
    certificates, nums = domain_service.get_certificate(session=session, tenant_env=env, page=page, page_size=page_size)
    bean = {"nums": nums}
    result = general_message("0", "success", "查询成功", list=certificates, bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/env/{env_id}/certificates", response_model=Response, name="添加网关证书")
async def add_tenant_certificates(request: Request,
                                  session: SessionClass = Depends(deps.get_session),
                                  env=Depends(deps.get_current_team_env)) -> Any:
    data = await request.json()
    alias = data.get("alias", None)
    if len(alias) > 64:
        return JSONResponse(general_message(400, "alias len is not allow more than 64", "证书名称最大长度64位"), status_code=400)
    private_key = data.get("private_key", None)
    certificate = data.get("certificate", None)
    certificate_type = data.get("certificate_type", None)
    certificate_id = make_uuid()
    try:
        new_c = domain_service.add_certificate(session, env, alias, certificate_id, certificate, private_key,
                                               certificate_type)
        bean = {"alias": alias, "id": new_c.ID}
        result = general_message("0", "success", "操作成功", bean=bean)
        return JSONResponse(result, status_code=result["code"])
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.get("/teams/{team_name}/env/{env_id}/certificates/{certificate_id}", response_model=Response, name="获取网关证书")
async def get_certificates(request: Request,
                           certificate_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)
                           ) -> Any:
    code, msg, certificate = domain_service.get_certificate_by_pk(session, certificate_id)
    if code != 200:
        return JSONResponse(general_message(code, "delete error", msg), status_code=code)

    result = general_message("0", "success", "查询成功", bean=certificate)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/certificates/{certificate_id}", response_model=Response, name="修改网关证书")
async def modify_certificates(request: Request,
                              env_id: Optional[str] = None,
                              certificate_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    if not certificate_id:
        return JSONResponse(general_message(400, "no param certificate_id", "缺少未指明具体证书"), status_code=400)
    new_alias = data.get("alias", None)
    if len(new_alias) > 64:
        return JSONResponse(general_message(400, "alias len is not allow more than 64", "证书名称最大长度64位"), status_code=400)

    private_key = data.get("private_key", None)
    certificate = data.get("certificate", None)
    certificate_type = data.get("certificate_type", None)
    domain_service.update_certificate(session, env, certificate_id, new_alias, certificate, private_key,
                                      certificate_type)
    result = general_message("0", "success", "证书修改成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/certificates/{certificate_id}", response_model=Response, name="删除网关证书")
async def delete_certificates(
        certificate_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    domain_service.delete_certificate_by_pk(session, certificate_id)
    result = general_message("0", "success", "证书删除成功")
    return JSONResponse(result, status_code=200)
