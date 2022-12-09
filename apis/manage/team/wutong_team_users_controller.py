from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import paginate, Params
from loguru import logger

from core import deps
from core.perm.perm import check_perm
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException, NoPermissionsError
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.teams.team_repo import team_repo
from repository.teams.team_roles_repo import team_roles_repo
from repository.users.user_role_repo import user_role_repo
from schemas.response import Response
from service.team_service import team_services
from service.user_service import user_kind_role_service

router = APIRouter()


@router.get("/teams/{team_name}/users", response_model=Response, name="团队用户管理")
async def get_team_users(request: Request,
                         team_name: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取某团队下的所有用户(每页展示八个用户)
    """
    try:
        code = 200
        name = request.query_params.get("query", None)
        page = request.query_params.get("page", 1)
        user_list = team_repo.get_tenant_users_by_tenant_name(session, team_name, name)
        if not user_list:
            users = []
            total = 0
        else:
            users_list = list()
            tenant_id = team_roles_repo.get_team_id_by_team_name(session, team_name)
            for user in user_list:
                # get role list
                role_info_list = user_role_repo.get_user_roles(
                    session=session, kind="team", kind_id=tenant_id, user=user)
                users_list.append({
                    "user_id": user.user_id,
                    "user_name": user.get_name(),
                    "nick_name": user.nick_name,
                    "email": user.email,
                    "role_info": role_info_list["roles"]
                })
            params = Params(page=page, size=8)
            pg = paginate(users_list, params)
            total = pg.total
            users = pg.items
        result = general_message(code, "team members query success", "查询成功", list=users, total=total)
    except ServiceHandleException as e:
        result = general_message(400, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/users/batch/delete", response_model=Response, name="删除团队成员")
async def delete_team_user(request: Request,
                           team_name: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user),
                           team=Depends(deps.get_current_team)) -> Any:
    """
            删除租户内的用户
            (可批量可单个)

            """
    is_perm = check_perm(session, user, team, "teamMember_delete")
    if not is_perm:
        raise NoPermissionsError

    try:
        from_data = await request.json()
        user_ids = from_data["user_ids"]
        if not user_ids:
            return JSONResponse(general_message(400, "failed", "删除成员不能为空"), status_code=400)

        if user.user_id in user_ids:
            return JSONResponse(general_message(400, "failed", "不能删除自己"), status_code=400)

        for user_id in user_ids:
            if user_id == team.creater:
                return JSONResponse(general_message(400, "failed", "不能删除团队创建者！"), 400)
        try:
            team_services.batch_delete_users(request=request, session=session, tenant_name=team_name,
                                             user_id_list=user_ids)
            result = general_message(200, "delete the success", "删除成功")
        except ServiceHandleException as e:
            logger.exception(e)
            result = general_message(400, e.msg, e.msg_show)
        except Exception as e:
            logger.exception(e)
            result = error_message()
        return JSONResponse(result, status_code=result["code"])
    except Exception as e:
        logger.exception(e)
        result = error_message()
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/users/roles", response_model=Response, name="团队成员角色管理")
async def get_team_user_roles(session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    team_users = team_services.get_team_users(session=session, team=team)
    data = user_kind_role_service.get_users_roles(
        session=session, kind="team", kind_id=team.tenant_id, users=team_users, creater_id=team.creater)
    return JSONResponse(general_message(200, "success", None, list=data), status_code=200)


@router.put("/teams/{team_name}/users/{user_id}/roles", response_model=Response, name="团队成员角色管理")
async def put_team_user_roles(request: Request,
                              user_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team),
                              user=Depends(deps.get_current_user)) -> Any:
    is_perm = check_perm(session, user, team, "teamMember_edit")
    if not is_perm:
        raise NoPermissionsError
    user = None
    data = await request.json()
    roles = data.get("roles")
    team_users = team_services.get_team_users(session=session, team=team)
    for team_user in team_users:
        if team_user.user_id == int(user_id):
            user = team_user
            break

    user_role_repo.delete_user_roles(session, "team", team.tenant_id, user)
    user_role_repo.update_user_roles(session=session, kind="team", kind_id=team.tenant_id, user=user,
                                     role_ids=roles)
    data = user_role_repo.get_user_roles(session=session, kind="team", kind_id=team.tenant_id, user=user)
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/notjoinusers", response_model=Response, name="获取企业下未加入当前团队的用户列表")
async def get_tenant_certificates(request: Request,
                                  session: SessionClass = Depends(deps.get_session),
                                  team=Depends(deps.get_current_team)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    query = request.query_params.get("query")
    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, team.enterprise_id)
    user_list = team_services.get_not_join_users(session=session, enterprise=enterprise, tenant=team, query=query)
    total = len(user_list)
    data = user_list[(page - 1) * page_size:page * page_size]
    result = general_message(200, None, None, list=jsonable_encoder(data), page=page, page_size=page_size, total=total)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/pemtransfer", response_model=Response, name="移交团队管理权")
async def user_perm_transfer(request: Request,
                             team=Depends(deps.get_current_team)) -> Any:
    """
     移交团队管理权
     """
    data = await request.json()
    user_id = data.get("user_id")
    team.creater = user_id
    result = general_message(msg="success", msg_show="移交成功", code=200)
    return JSONResponse(result, status_code=200)
