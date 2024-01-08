import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from core.utils.validation import name_rule_verification
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.alarm.alarm_strategy_repo import alarm_strategy_repo
from repository.region.region_info_repo import region_repo
from schemas.alarm_strategy import AlarmStrategyParam, StrategyEnableParam
from schemas.response import Response
from service.alarm.alarm_service import alarm_service
from service.alarm.alarm_strategy_service import alarm_strategy_service
from service.tenant_env_service import env_services
from repository.component.group_service_repo import service_info_repo
from core.api.team_api import team_api
from repository.env.user_env_auth_repo import user_env_auth_repo

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

    try:
        name_rule_verification(strategy_name, strategy_code)
    except ServiceHandleException as err:
        return JSONResponse(general_message(err.status_code, err.msg, err.msg_show), status_code=200)

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if alarm_strategy:
        return JSONResponse(general_message(500, "param error", "告警策略标识已存在"), status_code=200)

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    alarm_object = alarm_strategy_service.analysis_object(session, alarm_object)

    body = {
        "title": strategy_name,
        "team": team_code,
        "code": strategy_code,
        "teamName": env.team_alias,
        "env": env_code,
        "envName": env.env_alias,
        "envId": env.env_id,
        "regionCode": env.region_code,
        "objects": alarm_object,
        "rules": alarm_rules,
        "notifies": alarm_notice,
    }

    region_code = env.region_code
    try:
        region = region_repo.get_region_by_region_name(session, region_code)
        res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule", body, region)
    except ServiceHandleException as err:
        return JSONResponse(general_message(err.error_code, "create strategy error", err.msg), status_code=200)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "create strategy error", "创建obs策略失败"), status_code=200)
    if res["code"] != 200:
        return JSONResponse(general_message(res["code"], "create strategy error", res["message"]), status_code=200)

    object_code = alarm_notice.get("code")
    object_type = alarm_notice.get("type")

    alarm_strategy_info = {
        "strategy_name": strategy_name,
        "strategy_code": strategy_code,
        "desc": desc,
        "team_code": team_code,
        "env_code": env_code,
        "alarm_object": json.dumps(alarm_object),
        "alarm_rules": json.dumps(alarm_rules),
        "object_code": object_code,
        "object_type": object_type,
        "enable": True
    }

    service_ids = []
    for object in alarm_object:
        components = object.get("components")
        for component in components:
            service_ids.append(component.get("serviceId"))

    services = service_info_repo.get_services_by_service_ids(session, service_ids)
    for service in services:
        if service.obs_strategy_code:
            service.obs_strategy_code = service.obs_strategy_code + "," + strategy_code
        else:
            service.obs_strategy_code = strategy_code

    alarm_strategy_repo.create_alarm_strategy(session, alarm_strategy_info)
    return JSONResponse(general_message(200, "success", "创建成功"), status_code=200)


@router.get("/plat/alarm/strategy", response_model=Response, name="查询告警策略")
async def get_alarm_strategy(
        strategy_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询告警策略
    """

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if not alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略不存在"), status_code=200)

    try:
        data = alarm_strategy_service.get_alarm_strategy_data(session, alarm_strategy)
    except ServiceHandleException as err:
        return JSONResponse(general_message(err.status_code, err.msg, err.msg_show), status_code=200)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "query strategy error", "查询策略失败"), status_code=200)

    return JSONResponse(general_message(200, "success", "查询成功", bean=data), status_code=200)


@router.get("/plat/alarm/strategy-list", response_model=Response, name="查询告警策略列表")
async def get_alarm_strategy(
        team_code: Optional[str] = None,
        query: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询告警策略列表
    """
    data_list = []
    is_auth = False
    alarm_strategys = alarm_strategy_repo.get_alarm_strategy_by_team_code(session, team_code, query)

    # 判断是否是平台、团队管理员
    is_super_admin = team_api.get_user_env_auth(user, None, "1")
    auth_teams = team_api.get_auth_by_teams(user)
    auth_teams_dict = {}
    for auth_team in auth_teams:
        auth_teams_dict.update({auth_team.get("teamId"): auth_team.get("teamManage")})

    for alarm_strategy in alarm_strategys:
        try:
            data = alarm_strategy_service.get_alarm_strategy_data(session, alarm_strategy)
        except ServiceHandleException as err:
            logger.warning(err)
            continue
        except Exception as err:
            logger.error(err)
            return JSONResponse(general_message(500, "query strategy error", "查询策略失败"), status_code=200)

        env = env_services.get_env_by_team_code(session, alarm_strategy.team_code, alarm_strategy.env_code)
        if not env:
            continue

        # 判断用户权限
        if is_super_admin:
            is_auth = True
        if not is_auth:
            is_auth = auth_teams_dict.get(env.tenant_id, False)
        if not is_auth:
            is_auth = user_env_auth_repo.is_auth_in_env(session, env.env_id, user.user_name)
        if is_auth:
            data_list.append(data)

    return JSONResponse(general_message(200, "success", "查询成功", list=data_list), status_code=200)


@router.put("/plat/alarm/strategy", response_model=Response, name="更新告警策略")
async def update_alarm_strategy(
        request: Request,
        strategy_code: Optional[str] = None,
        params: Optional[AlarmStrategyParam] = AlarmStrategyParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    更新告警策略
    """

    try:
        name_rule_verification(params.strategy_name, strategy_code)
    except ServiceHandleException as err:
        return JSONResponse(general_message(err.status_code, err.msg, err.msg_show), status_code=200)

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if not alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略不存在"), status_code=200)

    team_code = params.team_code
    env_code = params.env_code

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    alarm_object = alarm_strategy_service.analysis_object(session, params.alarm_object)

    region_code = env.region_code
    if alarm_strategy.enable:
        try:
            body = {
                "title": params.strategy_name,
                "team": team_code,
                "code": alarm_strategy.strategy_code,
                "teamName": env.team_alias,
                "env": env_code,
                "envName": env.env_alias,
                "envId": env.env_id,
                "regionCode": env.region_code,
                "objects": alarm_object,
                "rules": params.alarm_rules,
                "notifies": params.alarm_notice,
            }
            region = region_repo.get_region_by_region_name(session, region_code)
            res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule", body, region)
        except Exception as err:
            logger.error(err)
            return JSONResponse(general_message(500, "update strategy error", "更新obs策略失败"), status_code=200)
        if res and res["code"] != 200:
            return JSONResponse(general_message(res["code"], "update strategy error", res["message"]), status_code=200)

    try:
        service_ids = []
        for object in alarm_object:
            components = object.get("components")
            for component in components:
                service_ids.append(component.get("serviceId"))

        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        for service in services:
            if service.obs_strategy_code:
                obs_strategy_code = service.obs_strategy_code.split(",")
                if strategy_code in obs_strategy_code:
                    continue
                service.obs_strategy_code = service.obs_strategy_code + "," + strategy_code
            else:
                service.obs_strategy_code = strategy_code

        alarm_notice = params.alarm_notice
        object_code = alarm_notice.get("code")
        object_type = alarm_notice.get("type")
        alarm_strategy_info = {
            "strategy_name": params.strategy_name,
            "desc": params.desc,
            "team_code": team_code,
            "env_code": env_code,
            "alarm_object": json.dumps(alarm_object),
            "alarm_rules": json.dumps(params.alarm_rules),
            "object_code": object_code,
            "object_type": object_type,
            "enable": alarm_strategy.enable,
        }
        alarm_strategy_repo.update_alarm_strategy(session, alarm_strategy.ID, alarm_strategy_info)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "update strategy error", "更新策略失败"), status_code=200)

    return JSONResponse(general_message(200, "success", "更新成功"), status_code=200)


@router.delete("/plat/alarm/strategy", response_model=Response, name="删除告警策略")
async def delete_alarm_strategy(
        request: Request,
        strategy_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除告警策略
    """

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if not alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略不存在"), status_code=200)

    team_code = alarm_strategy.team_code
    env_code = alarm_strategy.env_code

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    region_code = env.region_code

    # 开启后删除obs策略
    if alarm_strategy.enable:
        try:
            region = region_repo.get_region_by_region_name(session, region_code)
            res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule/" + alarm_strategy.strategy_code, {},
                                                        region)
            if res["code"] != 200:
                return JSONResponse(general_message(res["code"], "update strategy error", res["message"]),
                                    status_code=200)
        except Exception as err:
            logger.error(err)
            return JSONResponse(general_message(500, "update strategy error", "删除obs策略失败"), status_code=200)

    try:
        service_ids = []
        alarm_objects = json.loads(alarm_strategy.alarm_object)
        for alarm_object in alarm_objects:
            components = alarm_object.get("components")
            for component in components:
                service_ids.append(component.get("serviceId"))

        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        for service in services:
            service.obs_strategy_code = None
        alarm_strategy_repo.delete_alarm_strategy(session, alarm_strategy.ID)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "update strategy error", "删除策略失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "删除成功"), status_code=200)


@router.put("/plat/alarm/strategy/enable", response_model=Response, name="开关告警策略")
async def put_alarm_strategy(
        request: Request,
        params: Optional[StrategyEnableParam] = StrategyEnableParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    开关告警策略
    """

    strategy_code = params.strategy_code
    enable = params.enable
    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if not alarm_strategy:
        return JSONResponse(general_message(500, "param error", "策略不存在"), status_code=200)

    team_code = alarm_strategy.team_code
    env_code = alarm_strategy.env_code

    env = env_services.get_env_by_team_code(session, team_code, env_code)
    if not env:
        return JSONResponse(general_message(500, "param error", "环境不存在"), status_code=200)

    region_code = env.region_code
    try:
        region = region_repo.get_region_by_region_name(session, region_code)
        if not enable:
            res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule/" + alarm_strategy.strategy_code, {},
                                                        region,
                                                        method="DELETE")
        else:
            body = {
                "title": alarm_strategy.strategy_name,
                "team": team_code,
                "code": alarm_strategy.strategy_code,
                "env": env_code,
                "envId": env.env_id,
                "regionCode": env.region_code,
                "objects": json.loads(alarm_strategy.alarm_object),
                "rules": json.loads(alarm_strategy.alarm_rules),
                "notifies": {
                    "code": alarm_strategy.object_code,
                    "type": alarm_strategy.object_type,
                },
            }
            region_code = env.region_code
            try:
                region = region_repo.get_region_by_region_name(session, region_code)
                res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule", body, region, method="POST")
            except Exception as err:
                logger.error(err)
                return JSONResponse(general_message(500, "enable strategy error", "开关策略失败"), status_code=200)
            if res["code"] != 200:
                return JSONResponse(general_message(res["code"], "enable strategy error", res["message"]),
                                    status_code=200)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "enable strategy error", "开关obs策略失败"), status_code=200)

    try:
        alarm_strategy.enable = enable
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "enable strategy error", "开关策略失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "开关成功"), status_code=200)


@router.get("/plat/alarm/strategy/check", response_model=Response, name="验证告警策略")
async def check_alarm_strategy(
        strategy_name: Optional[str] = None,
        strategy_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    验证告警策略
    """

    try:
        name_rule_verification(strategy_name, strategy_code)
    except ServiceHandleException as err:
        return JSONResponse(general_message(err.status_code, err.msg, err.msg_show), status_code=200)

    alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
    if alarm_strategy:
        return JSONResponse(general_message(500, "param error", "告警策略标识已存在"), status_code=200)

    return JSONResponse(general_message(200, "success", "验证成功"), status_code=200)
