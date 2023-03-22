from functools import cmp_to_key
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import paginate, Params
from loguru import logger
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from schemas.team import CloseTeamAppParam
from service.app_actions.app_delete import component_delete_service
from service.app_actions.app_log import event_service
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.region_service import region_services

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/apps/close", response_model=Response, name="关闭团队应用")
async def close_teams_app(params: Optional[CloseTeamAppParam] = CloseTeamAppParam(),
                          env_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if params.region_name:
        app_manage_service.close_all_component_in_tenant(session=session, tenant_env=env,
                                                         region_name=params.region_name,
                                                         user=user)
    else:
        app_manage_service.close_all_component_in_team(session=session, tenant_env=env, user=user)
    return JSONResponse(general_message("0", "success", "操作成功"), status_code=200)


def __sort_events(event1, event2):
    event1_start_time = event1.get("StartTime") if isinstance(event1, dict) else event1.start_time
    event2_start_time = event2.get("StartTime") if isinstance(event2, dict) else event2.start_time
    if event1_start_time < event2_start_time:
        return 1
    if event1_start_time > event2_start_time:
        return -1
    if event1_start_time == event2_start_time:
        event1_ID = event1.get("ID") if isinstance(event1, dict) else event1.ID
        event2_ID = event2.get("ID") if isinstance(event2, dict) else event2.ID
        if event1_ID < event2_ID:
            return 1
        if event1_ID > event2_ID:
            return -1
        return 0


@router.get("/teams/{team_name}/env/{env_id}/apps", response_model=Response, name="总览环境应用信息")
async def overview_env_app_info(request: Request,
                                page: int = Query(default=1, ge=1, le=9999),
                                page_size: int = Query(default=10, ge=1, le=500),
                                env_id: Optional[str] = None,
                                session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    总览 团队应用信息
    """
    query = request.query_params.get("query", "")
    status = request.query_params.get("status", "all")
    project_id = request.query_params.get("project_id", None)
    count = {
        "RUNNING": 0,
        "CLOSED": 0,
        "ABNORMAL": 0,
        "NIL": 0,
        "STARTING": 0,
        "DEPLOYED": 0,
        "UNKNOWN": 0,
        "": 0
    }

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    region_name = region.region_name
    groups = application_repo.get_tenant_region_groups(session, env.env_id, region_name, query, project_id=project_id)
    total = len(groups)
    app_num_dict = {"total": total}
    start = (page - 1) * page_size
    end = page * page_size
    apps = []
    if groups:
        group_ids = [group.ID for group in groups]
        apps, count = application_service.get_multi_apps_all_info(session=session, app_ids=group_ids,
                                                                  region=region_name,
                                                                  tenant_env=env,
                                                                  status=status)

    apps = apps[start:end]
    app_num_dict.update(count)
    return JSONResponse(general_message("0", "success", "查询成功", list=jsonable_encoder(apps), bean=app_num_dict),
                        status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/event", response_model=Response, name="应用事件动态")
async def env_services_event(
        # request: Request,
        env_id: Optional[str] = None,
        page: int = Query(default=1, ge=1, le=9999),
        page_size: int = Query(default=3, ge=1, le=500),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    组件事件动态
    """
    # page = request.query_params.get("page", 1)
    # page_size = request.query_params.get("page_size", 3)
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    total = 0
    region_list = region_repo.get_team_opened_region(session, env.env_name)
    event_service_dynamic_list = []
    if region_list:
        for region in region_list:
            try:
                events, event_count, has_next = event_service.get_target_events(session=session, target="tenant",
                                                                                target_id=env.env_id,
                                                                                tenant_env=env,
                                                                                region=region.region_name,
                                                                                page=int(page),
                                                                                page_size=int(page_size))
                event_service_dynamic_list = event_service_dynamic_list + events
                total = total + event_count
            except Exception as e:
                logger.error("Region api return error {0}, ignore it".format(e))

    event_service_dynamic_list = sorted(event_service_dynamic_list, key=cmp_to_key(__sort_events))

    service_ids = []
    for event in event_service_dynamic_list:
        if event["Target"] == "service":
            service_ids.append(event["TargetID"])

    services = service_info_repo.list_by_component_ids(session, service_ids)

    event_service_list = []
    for event in event_service_dynamic_list:
        if event["Target"] == "service":
            for service in services:
                if service.service_id == event["TargetID"]:
                    event["service_alias"] = service.service_alias
                    event["service_name"] = service.service_cname
        event_service_list.append(event)

    params = Params(page=page, size=page_size)
    pg = paginate(event_service_list, params)
    total = pg.total
    event_page_list = pg.items
    event_list = [event for event in event_page_list]
    result = general_message("0", 'success', "查询成功", list=event_list, total=total)
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/again_delete", response_model=Response, name="二次确认删除应用")
async def again_delete_app(request: Request,
                           env_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user)) -> Any:
    """
    二次确认删除组件
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    service_id = data.get("service_id", None)
    service = service_info_repo.get_service_by_service_id(session, service_id)
    # app_manage_service.delete_again(session, user, env, service)
    component_delete_service.logic_delete(session=session, user=user, tenant_env=env, is_force=True, service=service)
    result = general_message("0", "success", "操作成功", bean={})
    return JSONResponse(result, status_code=200)
