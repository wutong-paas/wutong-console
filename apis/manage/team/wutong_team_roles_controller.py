from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core import deps
from core.perm.perm import check_perm
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException, NoPermissionsError
from repository.teams.team_roles_repo import team_roles_repo
from schemas.response import Response
from service.user_service import role_perm_service

router = APIRouter()


@router.get("/teams/{team_name}/roles", response_model=Response, name="团队角色获取")
async def get_team_roles_lc(team_name: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session)) -> Any:
    roles = team_roles_repo.get_role_by_team_name(session, "team", team_name)
    data = []
    for row in roles:
        data.append({"name": row.name, "ID": row.ID})
    result = general_message(200, "success", None, list=data)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/roles", response_model=Response, name="团队角色创建")
async def create_team_roles(request: Request,
                            team_name: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session)) -> Any:

    is_perm = check_perm(session, user, team, "gatewayRule_describe")
    if not is_perm:
        raise NoPermissionsError

    try:
        data = await request.json()
        name = data.get("name")
        add = team_roles_repo.create_role_by_team_name(session, name, "team", team_name)
        result = general_message(200, "success", "创建角色成功", bean=jsonable_encoder(add))
    except ServiceHandleException as e:
        code = 400
        result = general_message(code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/roles/perms", response_model=Response, name="团队角色权限管理")
async def get_team_roles_perms(team_name: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    roles = team_roles_repo.get_role_by_team_name(session, "team", team_name)
    data = team_roles_repo.get_roles_perms(session, roles, "team")
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/roles/{role_id}/perms", response_model=Response, name="团队角色权限管理")
async def get_team_role_id_perms(role_id: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session),
                                 team=Depends(deps.get_current_team)) -> Any:
    role = team_roles_repo.get_role_by_id(session, "team", team.tenant_id, role_id, with_default=True)
    data = team_roles_repo.get_role_perms(session, role, kind="team")
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/roles/{role_id}/perms", response_model=Response, name="修改团队角色权限")
async def get_team_role_id_perms(request: Request,
                                 role_id: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session),
                                 team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    perms_model = data.get("permissions")
    role = team_roles_repo.get_role_by_id(session, "team", team.tenant_id, role_id, with_default=True)
    role_perm_service.update_role_perms(session, role.ID, perms_model, kind="team")
    data = team_roles_repo.get_role_perms(session, role, kind="team")
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/roles/{role_id}", response_model=Response, name="删除团队角色")
async def delete_team_role(role_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    team_roles_repo.delete_role(session, "team", team.tenant_id, role_id)
    result = general_message(200, "success", "删除角色成功")
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/roles/{role_id}", response_model=Response, name="更新团队角色权限")
async def update_team_role_id_perms(request: Request,
                                    role_id: Optional[str] = None,
                                    session: SessionClass = Depends(deps.get_session),
                                    team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    name = data.get("name")
    role = team_roles_repo.update_role(session, "team", team.tenant_id, role_id, name)
    data = jsonable_encoder(role)
    del data["kind"]
    del data["kind_id"]
    result = general_message(200, "success", "更新角色成功", bean=data)
    return JSONResponse(result, status_code=200)
