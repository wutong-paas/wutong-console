import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.exceptions import UserFavoriteNotExistError
from exceptions.main import AbortRequest, ServiceHandleException
from models.teams import PermRelTenant
from models.users.users import UserFavorite, Users
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.users.user_favorite_repo import user_favorite_repo
from repository.users.user_oauth_repo import oauth_user_repo
from repository.users.user_repo import user_repo
from schemas.response import Response
from service.enterprise_service import enterprise_services
from service.team_service import team_services
from service.user_service import user_svc, user_kind_role_service

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/users", response_model=Response, name="查询用户列表")
async def get_users(enterprise_id,
                    query: Optional[str] = None,
                    page: Optional[int] = 1,
                    page_size: Optional[int] = 10,
                    session: SessionClass = Depends(deps.get_session)) -> Any:
    data = []
    try:
        users, total = user_svc.get_user_by_eid(session=session, eid=enterprise_id, name=query, page=page,
                                                page_size=page_size)
    except Exception as e:
        logger.debug(e)
        users = []
        total = 0
    if users:
        for user in users:
            default_favorite_name = None
            default_favorite_url = None
            user_default_favorite = user_favorite_repo.get_one_by_model(session=session,
                                                                        query_model=UserFavorite(user_id=user.user_id,
                                                                                                 is_default=True))
            if user_default_favorite:
                default_favorite_name = user_default_favorite.name
                default_favorite_url = user_default_favorite.url
            data.append({
                "email": user.email,
                "nick_name": user.nick_name,
                "real_name": (user.nick_name if user.real_name is None else user.real_name),
                "user_id": user.user_id,
                "phone": user.phone,
                "create_time": user.create_time,
                "default_favorite_name": default_favorite_name,
                "default_favorite_url": default_favorite_url,
            })
    result = general_message(200, "success", None, list=jsonable_encoder(data), page_size=page_size, page=page,
                             total=total)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/users", response_model=Response, name="添加用户")
async def add_users(
        request: Request,
        enterprise_id,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    tenant_name = data.get("tenant_name", None)
    user_name = data.get("user_name", None)
    email = data.get("email", None)
    password = data.get("password", None)
    re_password = data.get("re_password", None)
    role_ids = data.get("role_ids", None)
    phone = data.get("phone", None)
    real_name = data.get("real_name", None)
    tenant = team_services.get_tenant_by_tenant_name(session, tenant_name)

    has_number = any([i.isdigit() for i in password])
    my_re = re.compile(r'[A-Za-z]', re.S)
    has_char = re.findall(my_re, password)
    has_special = re.search(r"\W", password)

    if len(password) < 8:
        result = general_message(400, "len error", "密码长度最少为8位")
        return JSONResponse(result, status_code=400)

    if not (has_char and has_special and has_number):
        result = general_message(400, "complexity error", "请确保密码包含字母、数字和特殊字符")
        return JSONResponse(result, status_code=400)
    # check user info
    try:
        user_svc.check_params(session, user_name, email, password, re_password, user.enterprise_id, phone)
    except AbortRequest as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    client_ip = user_svc.get_client_ip(request)
    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    # create user
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)

    if oauth_instance:
        user = user_svc.create_enterprise_center_user_set_password(session, user_name, email, password, "admin add",
                                                                   enterprise_id,
                                                                   client_ip, phone, real_name, oauth_instance)
    else:
        user = user_svc.create_user_set_password(session, user_name, email, password, "admin add", enterprise_id,
                                                 client_ip,
                                                 phone,
                                                 real_name)
    session.add(user)
    session.flush()
    result = general_message(200, "success", "添加用户成功")
    if tenant:
        create_perm_param = {
            "user_id": user.user_id,
            "tenant_id": tenant.ID,
            "identity": "",
            "enterprise_id": enterprise.ID,
        }
        prt = PermRelTenant(**create_perm_param)
        session.add(prt)
        if role_ids:
            user_kind_role_service.update_user_roles(session=session,
                                                     kind="team", kind_id=tenant.tenant_id, user=user,
                                                     role_ids=role_ids)
            user.is_active = True
            session.add(user)
            result = general_message(200, "success", "添加用户成功")
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/{enterprise_id}/user/favorite", response_model=Response, name="查询用户收藏列表")
async def get_user_favorite(session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user)) -> Any:
    user_favorites = user_favorite_repo.list_by_model(session=session, query_model=UserFavorite(user_id=user.user_id))
    data = []
    if user_favorites:
        for user_favorite in user_favorites:
            data.append({
                "name": user_favorite.name,
                "url": user_favorite.url,
                "favorite_id": user_favorite.ID,
                "custom_sort": user_favorite.custom_sort,
                "is_default": user_favorite.is_default
            })
    result = general_message(200, "success", None, list=data)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/user/favorite", response_model=Response, name="新增收藏试图")
async def add_favorite(request: Request,
                       session: SessionClass = Depends(deps.get_session),
                       user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    name = data.get("name")
    url = data.get("url")
    is_default = data.get("is_default", False)
    if name and url:
        try:
            old_favorite = user_favorite_repo.get_user_favorite_by_name(session=session, user_id=user.user_id,
                                                                        name=name)
            if old_favorite:
                result = general_message(400, "fail", "收藏视图名称已存在")
                return JSONResponse(result, status_code=status.HTTP_400_BAD_REQUEST)
            user_favorite_repo.create_user_favorite(session=session, user_id=user.user_id, name=name, url=url,
                                                    is_default=is_default)
            result = general_message(200, "success", "收藏视图创建成功")
            return JSONResponse(result, status_code=status.HTTP_200_OK)
        except Exception as e:
            logger.error(e)
            result = general_message(400, "fail", "收藏视图创建失败")
            return JSONResponse(result, status_code=status.HTTP_400_BAD_REQUEST)
    else:
        result = general_message(400, "fail", "参数错误")
        return JSONResponse(result, status_code=status.HTTP_400_BAD_REQUEST)


@router.delete("/enterprise/{enterprise_id}/user/favorite/{favorite_id}", response_model=Response, name="删除收藏试图")
async def delete_favorite(favorite_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    result = general_message(200, "success", "删除成功")
    try:
        user_favorite_repo.delete_user_favorite_by_id(session=session, user_id=user.user_id, favorite_id=favorite_id)
    except UserFavoriteNotExistError as e:
        logger.error(e)
        result = general_message(404, "fail", "收藏视图不存在")
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.put("/enterprise/{enterprise_id}/user/{user_id}", response_model=Response, name="更新用户信息")
async def update_user_info(request: Request,
                           enterprise_id: Optional[str] = None,
                           user_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           current_user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    password = data.get("password", None)
    real_name = data.get("real_name", None)
    phone = data.get("phone", None)

    user = user_svc.update_user_set_password(request=request, session=session, enterprise_id=enterprise_id,
                                             user_id=user_id,
                                             raw_password=password, real_name=real_name, phone=phone)
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, current_user.user_id)
    if oauth_instance:
        data = {
            "password": password,
            "real_name": real_name,
            "phone": phone,
        }
        oauth_instance.update_user(enterprise_id, user.enterprise_center_user_id, data)
    result = general_message(200, "success", "更新用户成功")
    return JSONResponse(result, status_code=200)


@router.delete("/enterprise/{enterprise_id}/user/{user_id}", response_model=Response, name="删除用户")
async def delete_user(request: Request,
                      enterprise_id: Optional[str] = None,
                      user_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      current_user: Users = Depends(deps.get_current_user)) -> Any:
    user = user_repo.get_enterprise_user_by_id(session=session, enterprise_id=enterprise_id, user_id=user_id)
    if not user:
        result = general_message(400, "fail", "未找到该用户")
        return JSONResponse(result, 403)

    if current_user.user_id == int(user_id):
        return JSONResponse(general_message(400, "failed", "不能删除自己"), status_code=400)

    user_svc.delete_user(session=session, user_id=user_id)
    oauth_instance, oauth_user = user_svc.check_user_is_enterprise_center_user(session, user_id)
    if oauth_instance:
        oauth_instance.delete_user(enterprise_id, user.enterprise_center_user_id)
    oauth_user_repo.del_all_user_oauth(session, user_id)
    request.app.state.redis.delete("user_%d" % user.user_id)
    result = general_message(200, "success", "删除用户成功")
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/{enterprise_id}/user/{user_id}/teams", response_model=Response, name="查询用户列表")
async def get_users_team(request: Request,
                         enterprise_id: Optional[str] = None,
                         user_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    name = request.query_params.get("name", None)
    user = user_repo.get_by_primary_key(session=session, primary_key=user_id)
    teams = team_services.list_user_teams(session, enterprise_id, user, name)
    result = general_message(200, "team query success", "查询成功", list=jsonable_encoder(teams))
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/{enterprise_id}/users/{user_id}/teams/{tenant_name}/roles", response_model=Response,
             name="设置用户团队角色")
async def set_users_team_roles(request: Request,
                               enterprise_id: Optional[str] = None,
                               user_id: Optional[str] = None,
                               tenant_name: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    role_ids = data.get('role_ids', [])
    try:
        res = enterprise_services.create_user_roles(session, enterprise_id, user_id, tenant_name, role_ids)
        result = general_message(200, "ok", "设置成功", bean=res)
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.get("/teams/{team_name}/users/{user_id}/roles", response_model=Response,
            name="查询用户权限列表")
async def get_users_team_roles(user_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    user = None
    team_users = team_services.get_team_users(session, team)
    for team_user in team_users:
        if team_user.user_id == int(user_id):
            user = team_user
            continue
    data = user_kind_role_service.get_user_roles(session=session, kind="team", kind_id=team.tenant_id, user=user)
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)
