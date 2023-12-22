from typing import Any, Optional
from fastapi import APIRouter, Depends
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.api.team_api import team_api
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.alarm.alarm_group_repo import alarm_group_repo
from schemas.alarm_group import CreateAlarmGroupParam, PutAlarmGroupParam, AddAlarmUserParam, DeleteAlarmUserParam
from schemas.response import Response

router = APIRouter()


@router.get("/plat/alarm/group", response_model=Response, name="查询通知分组")
async def get_alarm_group(
        query: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询通知分组
    """
    alarm_group_list = []
    team_names = []
    alarm_groups = alarm_group_repo.get_alarm_group(session, query)
    for alarm_group in alarm_groups:
        group_name = alarm_group.group_name
        team_name = alarm_group.team_name
        group_id = alarm_group.ID
        group_type = alarm_group.group_type
        if group_type == "plat":
            team_name = "平台"
        if team_name not in team_names:
            team_names.append(team_name)
            if group_name:
                data = {"children": [
                    {"name": group_name, "node": 1, "id": group_id, "key": make_uuid(), "team_name": team_name}],
                        "name": team_name,
                        "node": 0,
                        "key": make_uuid()}
            else:
                data = {"name": team_name,
                        "node": 0,
                        "key": make_uuid()}
            alarm_group_list.append(data)
        else:
            for alarm_group_item in alarm_group_list:
                if alarm_group_item["name"] == team_name:
                    if alarm_group_item.get("children"):
                        alarm_group_item["children"].append(
                            {"name": group_name, "node": 1, "id": group_id, "key": make_uuid(), "team_name": team_name})
                    else:
                        alarm_group_item.update(
                            {"children": [{"name": group_name, "node": 1, "id": group_id, "key": make_uuid(),
                                           "team_name": team_name}]})

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
    team_name = params.team_name
    group_type = params.group_type
    if not group_name:
        return JSONResponse(general_message(400, "group name is not null", "分组名称不能为空"), status_code=200)

    alarm_group = alarm_group_repo.get_alarm_group_by_team(session, group_name, group_type, team_name)
    if alarm_group:
        return JSONResponse(general_message(500, "group name is exist", "分组名称已存在"), status_code=200)

    alarm_group_info = {
        "group_name": group_name,
        "team_name": team_name,
        "group_type": group_type,
        "operator": user.nick_name
    }
    try:
        alarm_group_repo.create_alarm_group(session, alarm_group_info)
    except:
        return JSONResponse(general_message(500, "create group failed", "创建分组失败"), status_code=200)

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
        return JSONResponse(general_message(500, "delete group failed", "删除通知分组失败"), status_code=200)

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
            return JSONResponse(general_message(500, "group is not exist", "分组不存在"), status_code=200)

        team_name = alarm_group.team_name
        group_type = alarm_group.group_type
        is_alarm_group = alarm_group_repo.get_alarm_group_by_team(session, group_name, group_type, team_name)
        if is_alarm_group:
            return JSONResponse(general_message(500, "group name is exist", "分组名称已存在"), status_code=200)
        alarm_group.group_name = group_name
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "put group failed", "编辑通知分组失败"), status_code=200)

    return JSONResponse(general_message(200, "put group success", "编辑通知分组成功"), status_code=200)


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
        return JSONResponse(general_message(500, "group is not exist", "分组不存在"), status_code=200)

    user_names = []
    for user in users:
        user_name = user.get("user_name")
        user_names.append(user_name)

    try:
        user_names = ','.join(user_names)
        contacts = alarm_group.contacts + "," + user_names
        contacts = contacts.split(",")
        contacts = list(set(contacts))
        alarm_group.contacts = ','.join(contacts)
    except Exception as err:
        logger.error(err)
        return JSONResponse(general_message(500, "add user failed", "添加联系人失败"), status_code=200)

    return JSONResponse(general_message(200, "add user success", "添加联系人成功"), status_code=200)


@router.get("/plat/alarm/group/users", response_model=Response, name="查询联系人")
async def get_alarm_group_user(
        group_id: Optional[int] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询联系人
    """
    alarm_group = alarm_group_repo.get_alarm_group_by_id(session, group_id)
    if not alarm_group:
        return JSONResponse(general_message(500, "group is not exist", "分组不存在"), status_code=200)

    group_users = []
    contacts = alarm_group.contacts
    if contacts:
        contacts = contacts.split(",")
        users_info = team_api.get_users_info(contacts, user.token)
        for user_info in users_info:
            user = {
                "user_name": user_info.get("username"),
                "nick_name": user_info.get("nickName"),
                "phone": user_info.get("mobile"),
                "email": user_info.get("email"),
            }
            group_users.append(user)
    return JSONResponse(
        general_message(200, "add user success", "查询联系人成功", list=group_users if group_users else []),
        status_code=200)


@router.delete("/plat/alarm/group/users", response_model=Response, name="删除联系人")
async def get_alarm_group_user(
        params: Optional[DeleteAlarmUserParam] = DeleteAlarmUserParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除联系人
    """
    try:
        pass
        # alarm_group_user_repo.delete_alarm_user_by_group_id(session, params.group_id, params.user_name)
    except:
        return JSONResponse(general_message(500, "delete user failed", "删除联系人失败"), status_code=200)
    return JSONResponse(
        general_message(200, "delete user success", "删除联系人成功"),
        status_code=200)
