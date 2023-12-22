from typing import Any, Optional
from fastapi import APIRouter, Depends
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.alarm.alarm_robot_repo import alarm_robot_repo
from schemas.alarm_robot import AlarmRobotParam, UpdateAlarmRobotParam
from schemas.response import Response
from fastapi.encoders import jsonable_encoder

router = APIRouter()


@router.post("/plat/alarm/group/robot", response_model=Response, name="添加机器人")
async def add_alarm_robot(
        params: Optional[AlarmRobotParam] = AlarmRobotParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    添加机器人
    """

    user_name = user.nick_name
    robot_name = params.robot_name
    webhook_addr = params.webhook_addr

    robot = alarm_robot_repo.get_alarm_robot_by_name(session, robot_name)
    if robot:
        return JSONResponse(general_message(500, "robot already exists", "机器人已存在"), status_code=200)

    robot_info = {
        "robot_name": robot_name,
        "webhook_addr": webhook_addr,
        "operator": user_name,
    }
    try:
        alarm_robot_repo.add_alarm_robot(session, robot_info)
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
        alarm_robot_repo.delete_alarm_robot_by_name(session, robot_name)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "删除机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "删除机器人成功"), status_code=200)


@router.get("/plat/alarm/group/robot", response_model=Response, name="查询机器人列表")
async def get_alarm_robot(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询机器人列表
    """

    try:
        robots = alarm_robot_repo.get_all_alarm_robot(session)
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

        robot.robot_name = params.robot_name
        robot.webhook_addr = params.webhook_addr
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add robot failed", "编辑机器人失败"), status_code=200)
    return JSONResponse(general_message(200, "add robot success", "编辑机器人成功"),
                        status_code=200)
