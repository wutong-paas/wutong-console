import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from core.utils.validation import is_qualified_code
from database.session import SessionClass
from repository.alarm.alarm_strategy_repo import alarm_strategy_repo
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.alarm_strategy import AlarmStrategyParam
from schemas.response import Response
from service.alarm.alarm_service import alarm_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.post("/plat/alarm/strategy", response_model=Response, name="创建告警策略")
async def create_alarm_strategy(
        request: Request,
        params: Optional[AlarmStrategyParam] = AlarmStrategyParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    创建告警策略
    """

    strategy_name = params.strategy_name
    strategy_code = params.strategy_code
    desc = params.desc
    team_code = params.team_code
    env_code = params.env_code
    alarm_object = params.alarm_object
    alarm_rules = params.alarm_rules
    alarm_notice = params.alarm_notice

    if not strategy_name or not strategy_code:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

    if not is_qualified_code(strategy_code):
        return JSONResponse(general_message(400, "param error", "策略编码不合法"), status_code=400)

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略已存在"), status_code=200)

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    body = {
        "title": strategy_name,
        "team": team_code,
        "env": env_code,
        "envId": env.env_id,
        "regionCode": env.region_code,
        "objects": alarm_object,
        "rules": alarm_rules,
        "notifies": alarm_notice,
    }
    obs_uid = None
    region_code = env.region_code
    try:
        region = region_repo.get_region_by_region_name(session, region_code)
        res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule", body, region)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "create strategy error", "创建策略失败"), status_code=200)
    if res and res["code"] == 200:
        obs_uid = res["data"]["uid"]

    if not obs_uid:
        return JSONResponse(general_message(500, "create strategy error", "创建策略失败"), status_code=200)

    alarm_strategy_info = {
        "strategy_name": strategy_name,
        "strategy_code": strategy_code,
        "desc": desc,
        "team_code": team_code,
        "env_code": env_code,
        "alarm_object": json.dumps(alarm_object),
        "alarm_rules": json.dumps(alarm_rules),
        "alarm_notice": json.dumps(alarm_notice),
        "obs_uid": obs_uid,
        "enable": True
    }
    alarm_strategy_repo.create_alarm_strategy(session, alarm_strategy_info)
    return JSONResponse(general_message(200, "success", "创建成功"), status_code=200)


@router.get("/plat/alarm/strategy", response_model=Response, name="查询告警策略")
async def get_alarm_strategy(
        request: Request,
        strategy_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询告警策略
    """

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if not alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略不存在"), status_code=200)

    team_code = alarm_strategy.team_code
    env_code = alarm_strategy.env_code
    alarm_objects = json.loads(alarm_strategy.alarm_object)
    alarm_rules = json.loads(alarm_strategy.alarm_rules)
    alarm_notice = json.loads(alarm_strategy.alarm_notice)

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    team_name = env.team_alias
    env_name = env.env_alias

    alarm_object_data = []
    for alarm_object in alarm_objects:
        app_code = alarm_object.get("app")
        service_code = alarm_object.get("serviceAlias")
        app = application_repo.get_app_by_k8s_app(session, env.env_id, env.region_code, app_code, None)
        service = service_info_repo.get_service(session, service_code, env.env_id)
        if not app or not service:
            return JSONResponse(general_message(500, "param error", "应用或组件不存在"), status_code=200)
        app_name = app.group_name
        service_name = service.service_cname
        alarm_object_data.append({
            "app": app_code,
            "app_name": app_name,
            "component": service.k8s_component_name,
            "serviceAlias": service_code,
            "service_name": service_name,
            "projectId": app.project_id,
        })

    data = {
        "strategy_name": alarm_strategy.strategy_name,
        "strategy_code": alarm_strategy.strategy_code,
        "desc": alarm_strategy.desc,
        "team_code": alarm_strategy.team_code,
        "team_name": team_name,
        "env_code": alarm_strategy.env_code,
        "env_name": env_name,
        "alarm_object": alarm_object_data,
        "alarm_rules": alarm_rules,
        "alarm_notice": alarm_notice
    }

    return JSONResponse(general_message(200, "success", "查询成功", bean=data), status_code=200)
