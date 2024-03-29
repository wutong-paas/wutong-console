from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import Params, paginate
from loguru import logger

from clients.remote_app_client import remote_app_client
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.return_message import general_message
from core.utils.status_translate import get_status_info_map
from database.session import SessionClass
from exceptions.exceptions import GroupNotExistError
from models.region.models import RegionApp
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_app_repo import region_app_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.application_service import application_service
from service.base_services import base_service
from service.common_services import common_services
from service.region_service import region_services
from service.team_service import team_services

router = APIRouter()


@router.get("/teams/{team_name}/service/group", response_model=Response, name="应用列表、状态展示")
async def get_app_state(request: Request,
                        page: int = Query(default=1, ge=1, le=9999),
                        page_size: int = Query(default=10, ge=-1, le=999),
                        team_name: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    """
     应用组件列表、状态展示
     """
    try:
        code = 200
        # page = int(request.query_params.get("page", 1))
        # page_size = int(request.query_params.get("page_size", 10))
        group_id = request.query_params.get("group_id", None)
        if group_id is None or not group_id.isdigit():
            code = 400
            result = general_message(code, "group_id is missing or not digit!", "group_id缺失或非数字")
            return JSONResponse(result, status_code=code)

        query = request.query_params.get("query", "")
        # region_name = request.headers.get("X_REGION_NAME")

        if not team:
            result = general_message(400, "tenant not exist", "{}团队不存在".format(team_name))
            return JSONResponse(result, status_code=400)

        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        region_name = region.region_name

        if group_id == "-1":
            # query service which not belong to any app
            no_group_service_list = service_info_repo.get_no_group_service_status_by_group_id(
                session=session,
                team_name=team_name,
                team_id=team.tenant_id,
                region_name=region_name,
                enterprise_id=team.enterprise_id)
            if page_size == "-1" or page_size == "" or page_size == "0":
                page_size = len(no_group_service_list) if len(no_group_service_list) > 0 else 10
            params = Params(page=page, size=page_size)
            pg = paginate(no_group_service_list, params)
            total = pg.total
            result = general_message(code, "query success", "应用查询成功", list=no_group_service_list, total=total)
            return JSONResponse(result, status_code=code)

        team_id = team.tenant_id
        group_count = application_repo.get_group_count_by_team_id_and_group_id(session=session, team_id=team_id,
                                                                               group_id=group_id)
        if group_count == 0:
            result = general_message(202, "group is not yours!", "当前组已删除或您无权限查看！", bean={})
            return JSONResponse(result, status_code=202)

        group_service_list = service_info_repo.get_group_service_by_group_id(
            session=session,
            group_id=group_id,
            region_name=region_name,
            team_id=team.tenant_id,
            team_name=team_name,
            enterprise_id=team.enterprise_id,
            query=query)
        if page_size == -1 or str(page_size) == "" or page_size == 0:
            page_size = len(group_service_list) if len(group_service_list) > 0 else 10
        if page_size == 999:
            page_size = 100
        params = Params(page=page, size=page_size)
        pg = paginate(group_service_list, params)
        total = pg.total
        result = general_message(code, "query success", "应用查询成功", list=jsonable_encoder(pg.items),
                                 total=total)
        return JSONResponse(result, status_code=200)
    except GroupNotExistError as e:
        logger.exception(e)
        return JSONResponse(general_message(400, "query success", "该应用不存在"), status_code=400)


@router.get("/teams/{team_name}/overview", response_model=Response, name="总览团队信息")
async def overview_team_info(region_name: Optional[str] = None,
                             team_name: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)
                             ) -> Any:
    """
     总览 团队信息
     ---
     parameters:
         - name: team_name
           description: 团队名
           required: true
           type: string
           paramType: path
     """
    if not team:
        return JSONResponse(general_message(400, "tenant not exist", "{}团队不存在".format(team_name)), status_code=400)

    overview_detail = dict()
    users = team_services.get_team_users(session=session, team=team)
    if users:
        user_nums = len(users)
        overview_detail["user_nums"] = user_nums
        team_service_num = service_info_repo.get_team_service_num_by_team_id(
            session=session, team_id=team.tenant_id, region_name=region_name)
        source = common_services.get_current_region_used_resource(session=session, tenant=team, region_name=region_name)

        region = region_repo.get_region_by_region_name(session, region_name)
        if not region:
            overview_detail["region_health"] = False
            return general_message(200, "success", "查询成功", bean=overview_detail)

        # 同步应用到集群
        groups = application_repo.get_tenant_region_groups(session, team.tenant_id, region.region_name)
        batch_create_app_body = []
        region_app_ids = []
        if groups:
            app_ids = [group.ID for group in groups]
            region_apps = region_app_repo.list_by_app_ids(session, region.region_name, app_ids)
            app_id_rels = {rapp.app_id: rapp.region_app_id for rapp in region_apps}
            for group in groups:
                if app_id_rels.get(group.ID):
                    region_app_ids.append(app_id_rels[group.ID])
                    continue
                create_app_body = dict()
                group_services = base_service.get_group_services_list(session=session, team_id=team.tenant_id,
                                                                      region_name=region.region_name, group_id=group.ID)
                service_ids = []
                if group_services:
                    service_ids = [service["service_id"] for service in group_services]
                create_app_body["app_name"] = group.group_name
                create_app_body["console_app_id"] = group.ID
                create_app_body["service_ids"] = service_ids
                if group.k8s_app:
                    create_app_body["k8s_app"] = group.k8s_app
                batch_create_app_body.append(create_app_body)

        if len(batch_create_app_body) > 0:
            try:
                body = {"apps_info": batch_create_app_body}
                applist = remote_app_client.batch_create_application(session, region.region_name, team_name, body)
                app_list = []
                if applist:
                    for app in applist:
                        data = RegionApp(
                            app_id=app["app_id"], region_app_id=app["region_app_id"], region_name=region.region_name)
                        app_list.append(data)
                        region_app_ids.append(app["region_app_id"])
                region_app_repo.bulk_create(session=session, app_list=app_list)
            except Exception as e:
                logger.exception(e)

        running_app_num = 0
        try:
            resp = remote_build_client.list_app_statuses_by_app_ids(session, team_name, region_name,
                                                                    {"app_ids": region_app_ids})
            app_statuses = resp.get("list", [])
            # todo
            for app_status in app_statuses:
                if app_status.get("status") == "RUNNING":
                    running_app_num += 1
        except Exception as e:
            logger.exception(e)
        team_app_num = application_repo.get_tenant_region_groups_count(session, team.tenant_id, region_name)
        overview_detail["team_app_num"] = team_app_num
        overview_detail["team_service_num"] = team_service_num
        overview_detail["eid"] = team.enterprise_id
        overview_detail["team_service_memory_count"] = 0
        overview_detail["team_service_total_disk"] = 0
        overview_detail["team_service_total_cpu"] = 0
        overview_detail["team_service_total_memory"] = 0
        overview_detail["team_service_use_cpu"] = 0
        overview_detail["cpu_usage"] = 0
        overview_detail["memory_usage"] = 0
        overview_detail["running_app_num"] = running_app_num
        overview_detail["running_component_num"] = 0
        overview_detail["team_alias"] = team.tenant_alias
        if source:
            try:
                overview_detail["region_health"] = True
                overview_detail["team_service_memory_count"] = int(source["memory"])
                overview_detail["team_service_total_disk"] = int(source["disk"])
                overview_detail["team_service_total_cpu"] = int(source["limit_cpu"])
                overview_detail["team_service_total_memory"] = int(source["limit_memory"])
                overview_detail["team_service_use_cpu"] = int(source["cpu"])
                overview_detail["running_component_num"] = int(source.get("service_running_num", 0))
                cpu_usage = 0
                memory_usage = 0
                if int(source["limit_cpu"]) != 0:
                    cpu_usage = float(int(source["cpu"])) / float(int(source["limit_cpu"])) * 100
                if int(source["limit_memory"]) != 0:
                    memory_usage = float(int(source["memory"])) / float(int(source["limit_memory"])) * 100
                overview_detail["cpu_usage"] = round(cpu_usage, 2)
                overview_detail["memory_usage"] = round(memory_usage, 2)
            except Exception as e:
                logger.debug(source)
                logger.exception(e)
        else:
            overview_detail["region_health"] = False
        return general_message(200, "success", "查询成功", bean=overview_detail)
    else:
        data = {"user_nums": 1, "team_service_num": 0, "total_memory": 0, "eid": team.enterprise_id}
        return general_message(200, "success", "团队信息总览获取成功", bean=data)


@router.get("/teams/{team_name}/overview/groups", response_model=Response, name="团队应用列表")
async def team_app_group(request: Request,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
       应用列表
       ---
       parameters:
           - name: team_name
             description: 团队名
             required: true
             type: string
             paramType: path
           - name: query
             description: 应用搜索名称
             required: false
             type: string
             paramType: query
   """
    if not team:
        return JSONResponse(general_message(400, "tenant not exist", "团队不存在"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name

    query = request.query_params.get("query", "")
    app_type = request.query_params.get("app_type", "")
    groups_services = application_service.get_groups_and_services(session=session, tenant=team, region=region_name,
                                                                  query=query, app_type=app_type)
    return general_message(200, "success", "查询成功", list=groups_services)


@router.get("/teams/{team_name}/overview/service/over", response_model=Response, name="团队应用信息")
async def team_app_group(
        request: Request,
        region_name: Optional[str] = None,
        team_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("page_size", 10)
    order = request.query_params.get('order_type', 'desc')
    fields = request.query_params.get('fields', 'update_time')
    query_key = request.query_params.get("query_key", '')
    service_status = request.query_params.get("service_status", 'all')
    if not team:
        return JSONResponse(general_message(400, "tenant not exist", "{}团队不存在".format(team_name)), status_code=40)
    services_list = base_service.get_fuzzy_services_list(session=session,
                                                         team_id=team.tenant_id, region_name=region_name,
                                                         query_key=query_key, fields=fields, order=order)
    if services_list:
        try:
            service_ids = [service["service_id"] for service in services_list]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name,
                                                            tenant_name=team_name,
                                                            service_ids=service_ids,
                                                            enterprise_id=team.enterprise_id)
            status_cache = {}
            statuscn_cache = {}
            for status in status_list:
                status_cache[status["service_id"]] = status["status"]
                statuscn_cache[status["service_id"]] = status["status_cn"]
            result = []
            for service in services_list:
                service = dict(service)
                if service["group_id"] is None:
                    service["group_name"] = "未分组"
                    service["group_id"] = "-1"
                if service_status == "all":
                    service["status_cn"] = statuscn_cache.get(service["service_id"], "未知")
                    status = status_cache.get(service["service_id"], "unknow")
                    if status == "unknow" and service["create_status"] != "complete":
                        service["status"] = "creating"
                        service["status_cn"] = "创建中"
                    else:
                        service["status"] = status_cache.get(service["service_id"], "unknow")
                        service["status_cn"] = get_status_info_map(service["status"]).get("status_cn")
                    if service["status"] == "closed" or service["status"] == "undeploy":
                        service["min_memory"] = 0
                    result.append(service)
                else:
                    if status_cache.get(service.service_id) == service_status:
                        service["status"] = status_cache.get(service.service_id, "unknow")
                        service["status_cn"] = get_status_info_map(service["status"]).get("status_cn")
                        if service["status"] == "closed" or service["status"] == "undeploy":
                            service["min_memory"] = 0
                        result.append(service)
            params = Params(page=page, size=page_size)
            pg = paginate(result, params)
            total = pg.total
            result = pg.items
            result = general_message(200, "query user success", "查询用户成功", list=result, total=total)
        except Exception as e:
            logger.exception(e)
            return general_message(200, "failed", "查询失败", list=services_list)
        return JSONResponse(result, status_code=result["code"])
    else:
        result = general_message(200, "success", "当前团队没有创建应用")
        return JSONResponse(result, status_code=result["code"])
