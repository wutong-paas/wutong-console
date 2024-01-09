from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import JSONResponse
from core.api.team_api import team_api
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.alarm.alarm_service import alarm_service
from service.tenant_env_service import env_services
from repository.env.user_env_auth_repo import user_env_auth_repo
from repository.alarm.alarm_strategy_repo import alarm_strategy_repo

router = APIRouter()


@router.get("/plat/alarm/message", response_model=Response, name="查询告警消息")
async def get_alarm_message(
        request: Request,
        query: Optional[str] = "alerting",
        team_code: Optional[str] = "",
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询告警消息
    """

    regions = team_region_repo.get_regions(session)
    data_list = []
    for region in regions:
        try:
            res = alarm_service.obs_service_alarm(request,
                                                        "/v1/alert/alerts?type=" + query + "&team=" + team_code, {},
                                                        region)
        except Exception as err:
            logger.warning(err)
            continue
        if res and res["code"] == 200:
            data_list += res["data"]

    # 判断是否是平台、团队管理员
    is_super_admin = team_api.get_user_env_auth(user, None, "1")
    auth_teams = team_api.get_auth_by_teams(user)
    auth_teams_dict = {}
    for auth_team in auth_teams:
        auth_teams_dict.update({auth_team.get("teamId"): auth_team.get("teamManage")})

    is_auth = False
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

            # 判断用户权限
            if is_super_admin:
                is_auth = True
            if not is_auth:
                is_auth = auth_teams_dict.get(env.tenant_id, False)
            if not is_auth:
                is_auth = user_env_auth_repo.is_auth_in_env(session, env.env_id, user.user_name)
            if is_auth:
                strategy_code = data.get("title")
                alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
                if not alarm_strategy:
                    continue

                result.append({
                    "team_name": team_name,
                    "env_name": env_name,
                    "app_name": app_name,
                    "service_name": service_name,
                    "message": data.get("content"),
                    "status": data.get("status"),
                    "title": alarm_strategy.strategy_name,
                    "code": strategy_code,
                    "time": data.get("time"),
                })

    # 按时间降序排序
    result = sorted(result, key=lambda x: x['time'], reverse=True)

    return JSONResponse(general_message(200, "get alarm message success", "查询成功", list=result), status_code=200)
