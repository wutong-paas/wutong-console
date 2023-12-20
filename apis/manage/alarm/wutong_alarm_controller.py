from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.alarm.alarm_group_repo import alarm_group_repo
from repository.alarm.alarm_user_repo import alarm_group_user_repo
from schemas.alarm_group import CreateAlarmGroupParam, PutAlarmGroupParam, AddAlarmUserParam
from schemas.response import Response

router = APIRouter()


@router.get("/plat/alarm/group", response_model=Response, name="查询通知分组")
async def get_alarm_group(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询通知分组
    """
    alarm_group_list = []
    team_names = []
    alarm_groups = alarm_group_repo.get_alarm_group(session)
    for alarm_group in alarm_groups:
        group_name = alarm_group.group_name
        team_name = alarm_group.team_name
        group_id = alarm_group.ID
        if not team_name:
            team_name = "平台"
        if team_name not in team_names:
            team_names.append(team_name)
            if group_name:
                data = {"children": [{"name": group_name, "key": 1, "id": group_id}],
                        "name": team_name,
                        "key": 0}
            else:
                data = {"name": team_name,
                        "key": 0}
            alarm_group_list.append(data)
        else:
            for alarm_group_item in alarm_group_list:
                if alarm_group_item["name"] == team_name:
                    alarm_group_item["children"].append({"name": group_name, "key": 1, "id": group_id})

    return JSONResponse(general_message(200, "create group success", "查询通知分组成功", list=alarm_group_list),
                        status_code=200)


@router.post("/plat/alarm/group", response_model=Response, name="创建通知分组")
async def create_alarm_group(
        params: Optional[CreateAlarmGroupParam] = CreateAlarmGroupParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    创建通知分组
    """
    group_name = params.group_name
    if not group_name:
        return JSONResponse(general_message(400, "group name is not null", "分组名称不能为空"), status_code=400)

    alarm_group = alarm_group_repo.get_alarm_group_by_team(session, group_name, params.team_name)
    if alarm_group:
        return JSONResponse(general_message(500, "group name is exist", "分组名称已存在"), status_code=500)

    alarm_group_info = {
        "group_name": group_name,
        "team_name": params.team_name,
        "operator": user.nick_name
    }
    try:
        alarm_group_repo.create_alarm_group(session, alarm_group_info)
    except:
        return JSONResponse(general_message(500, "create group failed", "创建分组失败"), status_code=500)

    return JSONResponse(general_message(200, "create group success", "创建分组成功"), status_code=200)


@router.delete("/plat/alarm/group", response_model=Response, name="删除通知分组")
async def delete_alarm_group(
        group_id: Optional[int] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除通知分组
    """
    try:
        alarm_group_repo.delete_alarm_group_by_id(session, group_id)
    except:
        return JSONResponse(general_message(500, "delete group failed", "删除通知分组失败"), status_code=500)

    return JSONResponse(general_message(200, "delete group success", "删除通知分组成功"), status_code=200)


@router.put("/plat/alarm/group", response_model=Response, name="编辑通知分组")
async def put_alarm_group(
        params: Optional[PutAlarmGroupParam] = PutAlarmGroupParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    编辑通知分组
    """
    group_name = params.group_name
    group_id = params.group_id
    try:
        alarm_group = alarm_group_repo.get_alarm_group_by_id(session, group_id)
        if not alarm_group:
            return JSONResponse(general_message(500, "group is not exist", "分组不存在"), status_code=500)

        team_name = alarm_group.team_name
        is_alarm_group = alarm_group_repo.get_alarm_group_by_team(session, group_name, team_name)
        if is_alarm_group:
            return JSONResponse(general_message(500, "group name is exist", "分组名称已存在"), status_code=500)
        alarm_group.group_name = group_name
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "delete group failed", "编辑通知分组失败"), status_code=500)

    return JSONResponse(general_message(200, "delete group success", "编辑通知分组成功"), status_code=200)


@router.post("/plat/alarm/group/users", response_model=Response, name="添加联系人")
async def add_alarm_group_user(
        params: Optional[AddAlarmUserParam] = AddAlarmUserParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    添加联系人
    """
    group_id = params.group_id
    users = params.users

    alarm_group = alarm_group_repo.get_alarm_group_by_id(session, group_id)
    if not alarm_group:
        return JSONResponse(general_message(500, "group is not exist", "分组不存在"), status_code=500)

    for user in users:
        user.update({"group_id": group_id})
        group_users = alarm_group_user_repo.get_alarm_user_by_group_id(session, group_id)
        for group_user in group_users:
            user_name = group_user.user_name
            if user_name == user.get("user_name"):
                return JSONResponse(general_message(500, "user is exist", "联系人已存在"), status_code=500)

    try:
        alarm_group_user_repo.add_alarm_user(session, users)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add user failed", "添加联系人失败"), status_code=500)

    return JSONResponse(general_message(200, "add user success", "添加联系人成功"), status_code=200)


@router.get("/plat/alarm/group/users", response_model=Response, name="查询联系人")
async def get_alarm_group_user(
        group_id: Optional[int] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询联系人
    """
    group_users = alarm_group_user_repo.get_alarm_user_by_group_id(session, group_id)
    return JSONResponse(
        general_message(200, "add user success", "查询联系人成功", list=jsonable_encoder(group_users) if group_users else []),
        status_code=200)
