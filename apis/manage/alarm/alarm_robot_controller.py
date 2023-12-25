from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.alarm.alarm_robot_repo import alarm_robot_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.alarm_robot import AlarmRobotParam, UpdateAlarmRobotParam
from schemas.response import Response
from fastapi.encoders import jsonable_encoder
from service.alarm.alarm_service import alarm_service
from repository.alarm.alarm_region_repo import alarm_region_repo
from repository.region.region_info_repo import region_repo

router = APIRouter()


@router.post("/plat/alarm/group/robot", response_model=Response, name="添加机器人")
async def add_alarm_robot(
        request: Request,
        params: Optional[AlarmRobotParam] = AlarmRobotParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    添加机器人
    """

    user_name = user.nick_name
    robot_name = params.robot_name
    webhook_addr = params.webhook_addr
    team_code = params.team_code

    robot = alarm_robot_repo.get_alarm_robot_by_name(session, robot_name)
    if robot:
        return JSONResponse(general_message(500, "robot already exists", "机器人已存在"), status_code=200)

    robot_info = {
        "robot_name": robot_name,
        "webhook_addr": webhook_addr,
        "operator": user_name,
        "team_code": team_code
    }
    try:
        body = {
            "name": robot_name,
            "type": "wechat",
            "address": webhook_addr
        }
        alarm_robot = alarm_robot_repo.add_alarm_robot(session, robot_info)
        regions = team_region_repo.get_regions(session)
        for region in regions:
            region_code = region.region_name
            try:
                alarm_region_rel = alarm_region_repo.get_alarm_region(session, alarm_robot.ID, region_code, "wechat")
                if alarm_region_rel:
                    obs_uid = alarm_region_rel.obs_uid
                    body.update({"uid": obs_uid})
                body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact", body, region)
            except Exception as err:
                logger.warning(err)
                continue
            if body and body["code"] == 200:
                uid = body["data"]["uid"]
                data = {
                    "group_id": alarm_robot.ID,
                    "alarm_type": "wechat",
                    "obs_uid": uid,
                    "region_code": region_code
                }
                if not alarm_region_rel:
                    alarm_region_repo.create_alarm_region(session, data)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "添加机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "添加机器人成功"), status_code=200)


@router.delete("/plat/alarm/group/robot", response_model=Response, name="删除机器人")
async def delete_alarm_robot(
        robot_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除机器人
    """

    try:
        robot = alarm_robot_repo.get_alarm_robot_by_name(session, robot_name)
        if not robot:
            return JSONResponse(general_message(500, "robot not exists", "机器人不存在"), status_code=200)

        alarm_region_rels = alarm_region_repo.get_alarm_regions(session, robot.ID, "wechat")
        for alarm_region_rel in alarm_region_rels:
            region = region_repo.get_region_by_region_name(session, alarm_region_rel.region_code)
            try:
                if alarm_region_rel:
                    obs_uid = alarm_region_rel.obs_uid
                    body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact/" + obs_uid, {}, region)
            except Exception as err:
                logger.warning(err)
                continue

        alarm_region_repo.delete_alarm_region_by_group_id(session, robot.ID)
        alarm_robot_repo.delete_alarm_region(session, robot_name, "wechat")
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "删除机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "删除机器人成功"), status_code=200)


@router.get("/plat/alarm/group/robot", response_model=Response, name="查询机器人列表")
async def get_alarm_robot(
        team_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询机器人列表
    """

    try:
        robots = alarm_robot_repo.get_all_alarm_robot(session, team_code)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "查询机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "查询机器人成功", list=jsonable_encoder(robots)),
                        status_code=200)


@router.put("/plat/alarm/group/robot", response_model=Response, name="编辑机器人")
async def put_alarm_robot(
        params: Optional[UpdateAlarmRobotParam] = UpdateAlarmRobotParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    编辑机器人
    """

    try:
        robot = alarm_robot_repo.get_alarm_robot_by_id(session, params.robot_id)
        robot_by_name = alarm_robot_repo.get_alarm_robot_by_name(session, params.robot_name)
        if robot_by_name and robot_by_name.ID != robot.ID:
            return JSONResponse(general_message(500, "robot already exists", "已存在该名字机器人"), status_code=200)

        body = {
            "name": robot_name,
            "type": "wechat",
            "address": webhook_addr
        }
        status = 0
        alarm_region_rels = alarm_region_repo.get_alarm_regions(session, robot.ID, "wechat")
        for alarm_region_rel in alarm_region_rels:
            region = region_repo.get_region_by_region_name(session, alarm_region_rel.region_code)
            try:
                if alarm_region_rel:
                    obs_uid = alarm_region_rel.obs_uid
                    body.update({"uid": obs_uid})
                    body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact", body, region)
                    if body and body["code"] == 200:
                        status = 1
            except Exception as err:
                logger.warning(err)
                continue

        if not status:
            return JSONResponse(general_message(500, "add robot failed", "编辑机器人失败"), status_code=200)
        robot.robot_name = params.robot_name
        robot.webhook_addr = params.webhook_addr
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "编辑机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "编辑机器人成功"),
                        status_code=200)


@router.post("/plat/alarm/group/robot/test", response_model=Response, name="测试机器人")
async def test_alarm_robot(
        request: Request,
        params: Optional[AlarmRobotParam] = AlarmRobotParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    测试机器人
    """

    robot_name = params.robot_name
    webhook_addr = params.webhook_addr

    robot = alarm_robot_repo.get_alarm_robot_by_name(session, robot_name)
    if robot:
        return JSONResponse(general_message(500, "robot already exists", "机器人已存在"), status_code=200)

    try:
        # https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=a70ff990-c290-4a08-a349-12a7700a175d
        body = {
            "type": "wechat",
            "address": webhook_addr
        }
        regions = team_region_repo.get_regions(session)
        for region in regions:
            try:
                body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact/test", body, region)
            except Exception as err:
                logger.error(err)
                continue
            if body and body["code"] == 200 and body["data"]["status"] == 200:
                return JSONResponse(general_message(200, "test success", "测试成功"), status_code=200)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "test failed", "测试失败"), status_code=200)
    return JSONResponse(general_message(500, "test failed", "测试失败"), status_code=200)