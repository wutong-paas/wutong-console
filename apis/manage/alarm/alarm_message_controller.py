from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.alarm.alarm_service import alarm_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/plat/alarm/message", response_model=Response, name="查询告警消息")
async def get_alarm_message(
        request: Request,
        query: Optional[str] = "alerting",
        team_code: Optional[str] = "",
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询告警消息
    """

    regions = team_region_repo.get_regions(session)
    data_list = []
    for region in regions:
        try:
            res = await alarm_service.obs_service_alarm(request,
                                                        "/v1/alert/alerts?type=" + query + "&team=" + team_code, {},
                                                        region)
        except Exception as err:
            logger.warning(err)
            continue
        if res and res["code"] == 200:
            data_list += res["data"]

    result = []
    for data in data_list:
        team_code = data.get("team")
        env_code = data.get("env")
        app_code = data.get("app")
        service_code = data.get("component")

        env = env_services.get_env_by_team_code(session, team_code, env_code)
        if env:
            env_name = env.env_alias
            team_name = env.team_alias
            app = application_repo.get_app_by_k8s_app(session, env.env_id, env.region_code, app_code, None)
            app_name = app.group_name
            service = service_info_repo.get_service_by_k8s(session, service_code, env.env_id)
            service_name = service.service_cname

            result.append({
                "team_name": team_name,
                "env_name": env_name,
                "app_name": app_name,
                "service_name": service_name,
                "message": data.get("content"),
                "status": data.get("status"),
                "title": data.get("title"),
                "time": data.get("time"),
            })

    return JSONResponse(general_message(200, "get alarm message success", "查询成功", list=result), status_code=200)
