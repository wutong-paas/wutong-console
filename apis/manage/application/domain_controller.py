from typing import Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_repo, group_service_relation_repo
from repository.component.service_domain_repo import domain_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.app_config.domain_service import domain_service

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/team/{team_name}/app/{app_id}/domain", response_model=Response,
            name="应用HTTP网关查询")
async def get_domain_info(request: Request,
                          app_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          team=Depends(deps.get_current_team)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    search_conditions = request.query_params.get("search_conditions", None)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    # todo 简化查询
    region = region_repo.get_region_by_region_name(session, region.region_name)
    tenant_tuples, total = domain_service.get_app_service_domain_list(region=region, tenant=team, app_id=app_id,
                                                                      search_conditions=search_conditions,
                                                                      page=page,
                                                                      page_size=page_size, session=session)
    # 拼接展示数据
    domain_list = list()
    for tenant_tuple in tenant_tuples:
        service = service_repo.get_service_by_service_id(session, tenant_tuple[9])
        service_cname = service.service_cname if service else ''
        service_alias = service.service_alias if service else tenant_tuple[6]
        group_name = ''
        group_id = 0
        if service:
            gsr = group_service_relation_repo.get_group_by_service_id(session, service.service_id)
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
    result = general_message(200, "success", "查询成功", list=domain_list, bean=bean)
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/{enterprise_id}/team/{team_name}/app/{app_id}/tcpdomain", response_model=Response,
            name="应用TCP网关查询")
async def get_tcp_domain_info(request: Request,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    search_conditions = request.query_params.get("search_conditions", None)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    # todo 简化查询
    region = region_repo.get_region_by_region_name(session, region.region_name)

    tenant_tuples, total = domain_service.get_app_service_tcp_domain_list(region=region, tenant=team, app_id=app_id,
                                                                          search_conditions=search_conditions,
                                                                          page=page,
                                                                          page_size=page_size, session=session)

    # 拼接展示数据
    domain_list = list()
    for tenant_tuple in tenant_tuples:
        service = service_repo.get_service_by_service_id(session, tenant_tuple[7])
        service_alias = service.service_cname if service else ''
        group_name = ''
        group_id = 0
        if service:
            gsr = group_service_relation_repo.get_group_by_service_id(session, service.service_id)
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
    result = general_message(200, "success", "查询成功", list=domain_list, bean=bean)
    return JSONResponse(result, status_code=200)
