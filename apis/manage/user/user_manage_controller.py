import pickle
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from jose import jwt
from loguru import logger
from sqlalchemy import select

from core import deps
from core.setting import role_required
from core.setting import settings
from core.utils.perms import list_enterprise_perms_by_roles
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from models.teams import PermRelTenant, TeamInfo
from models.teams.enterprise import TeamEnterprise
from models.users.users import Users
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from repository.teams.team_enterprise_repo import tenant_enterprise_repo
from repository.users.user_oauth_repo import oauth_repo
from repository.users.user_repo import user_repo
from repository.users.user_role_repo import user_role_repo
from schemas.response import Response
from service.region_service import get_region_list_by_team_name
from service.user_service import user_svc, user_kind_perm_service

router = APIRouter()


# 生成token
def create_access_token(user, access_token_expires):
    """创建tokens函数
    :param data: 对用JWT的Payload字段，这里是tokens的载荷，在这里就是用户的信息
    :return:
    """
    data = {'user_id': user.user_id,
            'username': user.nick_name,
            'exp': access_token_expires,
            'email': user.email}

    # 深拷贝data
    to_encode = data.copy()

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


@router.post("/users/login", response_model=Response, name="用户登录")
async def user_login(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    用户登录接口
    ---
    parameters:
        - name: nick_name
          description: 用户名
          required: true
          type: string
          paramType: form
        - name: password
          description: 密码
          required: true
          type: string
          paramType: form
    """
    try:
        from_data = await request.form()
        nick_name = from_data["nick_name"]
        password = from_data["password"]

        if not nick_name:
            code = 400
            result = general_message(code, "username is missing", "请填写用户名")
            return JSONResponse(result, status_code=400)
        elif not password:
            code = 400
            result = general_message(code, "password is missing", "请填写密码")
            return JSONResponse(result, status_code=400)
        user, msg, code = user_svc.is_exist(session=session, username=nick_name, password=password)
        if not user:
            code = 400
            result = general_message(code, "authorization fail ", msg)
            return JSONResponse(result, status_code=400)

        if not user.is_active:
            result = general_message(400, "登录失败", "用户帐户被禁用")
            return JSONResponse(result, status_code=400)

        # 创建token
        # 定义tokens过期时间
        access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAY)
        expires = datetime.utcnow() + access_token_expires
        token = create_access_token(user, expires)
        response_data = {"token": token}
        result = general_message(200, "login success", "登录成功", bean=response_data)
        response = JSONResponse(result, status_code=200)
        expiration = int(time.mktime((datetime.now() + timedelta(days=30)).timetuple()))
        response.set_cookie(key="token", value=token, expires=expiration)
        role_required.login(response, user, token)
        request.app.state.redis.set("user_%d" % user.user_id, pickle.dumps(user), 24 * 60 * 60)
        return response

    except Exception as e:
        logger.exception(e)
        result = general_message(400, "login failed", "登录失败")
        return JSONResponse(result, status_code=400)


def num_to_char(num):
    """数字转中文"""
    num = str(num)
    new_str = ""
    num_dict = {"0": u"零", "1": u"一", "2": u"二", "3": u"三", "4": u"四", "5": u"五", "6": u"六", "7": u"七", "8": u"八",
                "9": u"九"}
    listnum = list(num)
    shu = []
    for i in listnum:
        shu.append(num_dict[i])
    new_str = "".join(shu)
    return new_str


@router.get("/users/logout", response_model=Response, name="用户登出")
async def user_logout(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    用户登出
    """
    try:
        code = 200
        user = role_required.logout(request)
        if not user:
            code = 405
            return general_message(code, "not login", "未登录状态, 不需注销")

        result = general_message(code, "logout success", "登出成功")
        response = JSONResponse(result)
        response.delete_cookie('tenant_name')
        response.delete_cookie('uid')
        response.delete_cookie('token')
        response.delete_cookie('third_token')
        return response
    except Exception as e:
        logger.exception(e)
        return general_message(405, "logout failed", "登出失败")


@router.post("/users/register", response_model=Response, name="用户注册")
async def user_register(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    from_data = await request.form()

    user_name = from_data["user_name"]
    email = from_data["email"]
    phone = from_data["phone"]
    real_name = from_data["real_name"]
    password = from_data["password"]
    re_password = from_data["password_repeat"]
    client_ip = request.client.host

    user_info = dict()
    user_info["email"] = email
    user_info["nick_name"] = user_name
    user_info["client_ip"] = client_ip
    user_info["is_active"] = 1
    user_info["phone"] = phone
    user_info["real_name"] = real_name
    user_info["origion"] = ''
    user_info["github_token"] = ''
    user_info["rf"] = ''
    user_info["union_id"] = ''
    user = Users(**user_info)
    user.set_password(password)

    if len(password) < 8:
        result = general_message(400, "len error", "密码长度最少为8位")
        return JSONResponse(result)

    # check user info
    try:
        user_svc.check_params(session, user_name, email, password, re_password, user.enterprise_id, phone)
    except AbortRequest as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    # todo
    user_svc.create_user(session=session, user=user)

    enterprise = enterprise_repo.get_enterprise_first(session=session)

    # check user info
    # try:
    #     user_svc.check_params(session, user_name, email, password, re_password, user.enterprise_id, phone)
    # except AbortRequest as e:
    #     return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)

    # user_svc.create_user(session, user)

    if not enterprise:
        enter_name = from_data["enter_name"]
        enterprise = tenant_enterprise_repo.create_enterprise(session=session, enterprise_name=None,
                                                              enterprise_alias=enter_name)
        # 创建用户在企业的权限
        user_svc.make_user_as_admin_for_enterprise(session, user.user_id, enterprise.enterprise_id)

    user.enterprise_id = enterprise.enterprise_id

    data = dict()
    data["user_id"] = user.user_id
    data["nick_name"] = user.nick_name
    data["email"] = user.email
    data["phone"] = user.phone
    data["real_name"] = user.real_name
    data["enterprise_id"] = user.enterprise_id
    access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAY)
    expires = datetime.utcnow() + access_token_expires
    token = create_access_token(user, expires)
    data["token"] = token
    request.app.state.redis.set("user_%d" % user.user_id, pickle.dumps(user), 24 * 60 * 60)
    return general_message(200, "register success", "注册成功", bean=data)


@router.get("/users/details", response_model=Response, name="获取用户详情")
async def get_user_details(session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user)) -> Any:
    # 查询企业信息
    enterprise = tenant_enterprise_repo.get_one_by_model(session=session,
                                                         query_model=TeamEnterprise(enterprise_id=user.enterprise_id))
    # 查询角色权限信息
    roles = user_svc.list_roles(session, user.enterprise_id, user.user_id)
    permissions = list_enterprise_perms_by_roles(roles)

    user_detail = dict()
    user_detail["user_id"] = user.user_id
    user_detail["user_name"] = user.nick_name
    user_detail["real_name"] = user.real_name
    user_detail["email"] = user.email
    user_detail["enterprise_id"] = user.enterprise_id
    user_detail["phone"] = user.phone
    user_detail["git_user_id"] = user.git_user_id
    user_detail["is_sys_admin"] = user_repo.is_sys_admin(session=session, user_id=user.user_id)
    if enterprise:
        user_detail["is_enterprise_active"] = enterprise.is_active
    # todo is_enterprise_admin
    # user_detail["is_enterprise_admin"] = self.is_enterprise_admin
    user_detail["is_enterprise_admin"] = True
    # enterprise roles
    user_detail["roles"] = roles
    # enterprise permissions
    user_detail["permissions"] = permissions
    tenant_list = []
    # 查询团队信息
    tenant_ids_results = session.execute(
        select(PermRelTenant.tenant_id).where(PermRelTenant.user_id == user.user_id))
    tenant_ids = tenant_ids_results.scalars().all()
    if len(tenant_ids) > 0:
        tenants_results = session.execute(
            select(TeamInfo).where(TeamInfo.ID.in_(tenant_ids)).order_by(TeamInfo.create_time.desc()))
        tenants = tenants_results.scalars().all()
        for tenant in tenants:
            tenant_info = dict()
            is_team_owner = False
            team_region_list = get_region_list_by_team_name(session=session, team_name=tenant.tenant_name)
            tenant_info["team_id"] = tenant.ID
            tenant_info["team_name"] = tenant.tenant_name
            tenant_info["team_alias"] = tenant.tenant_alias
            tenant_info["limit_memory"] = tenant.limit_memory
            tenant_info["pay_level"] = tenant.pay_level
            tenant_info["region"] = team_region_list
            tenant_info["creater"] = tenant.creater
            tenant_info["create_time"] = tenant.create_time

            if tenant.creater == user.user_id:
                is_team_owner = True
            role_list = user_role_repo.get_user_roles(session=session, kind="team", kind_id=tenant.tenant_id,
                                                      user=user)
            tenant_info["role_name_list"] = role_list["roles"]
            # todo is_enterprise_admin
            is_enterprise_admin = enterprise_user_perm_repo.is_admin(session, user.enterprise_id, user.user_id)
            perms = user_kind_perm_service.get_user_perms(session=session,
                                                          kind="team", kind_id=tenant.tenant_id, user=user,
                                                          is_owner=is_team_owner,
                                                          is_ent_admin=is_enterprise_admin)
            tenant_info["tenant_actions"] = perms["permissions"]
            tenant_info["is_team_owner"] = is_team_owner
            tenant_list.append(tenant_info)
    user_detail["teams"] = tenant_list
    oauth_services = oauth_repo.get_user_oauth_services_info(
        session=session, eid=user.enterprise_id, user_id=user.user_id)
    user_detail["oauth_services"] = oauth_services
    result = general_message(200, "Obtain my details to be successful.", "获取我的详情成功", bean=jsonable_encoder(user_detail))

    return JSONResponse(result, status_code=result["code"])


@router.post("/users/changepwd", response_model=Response, name="修改密码")
async def change_password(request: Request,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    """
    修改密码
    ---
    parameters:
        - name: password
          description: 原密码
          required: true
          type: string
          paramType: form
        - name: new_password
          description: 新密码
          required: true
          type: string
          paramType: form
        - name: new_password2
          description: 确认密码
          required: true
          type: string
          paramType: form
    """
    try:
        data = await request.json()
        password = data["password"]
        new_password = data["new_password"]
        new_password2 = data["new_password2"]
        if not user_svc.check_user_password(session=session, user_id=user.user_id, password=password):
            result = general_message(400, "old password error", "旧密码错误")
        elif new_password != new_password2:
            result = general_message(400, "two password disagree", "两个密码不一致")
        elif password == new_password:
            result = general_message(400, "old and new password agree", "新旧密码一致")
        else:
            status, info = user_svc.update_password(session=session, user_id=user.user_id, new_password=new_password)
            oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)
            if oauth_instance:
                data = {
                    "password": new_password,
                    "real_name": request.user.real_name,
                }
                oauth_instance.update_user(request.user.enterprise_id, request.user.enterprise_center_user_id, data)
            if status:
                code = 200
                result = general_message(200, "change password success", "密码修改成功")
            else:
                result = general_message(400, "password change failed", "密码修改失败")
        return JSONResponse(result, status_code=result["code"])
    except Exception as e:
        logger.exception(e)
        result = general_message(400, "password change failed", "密码修改失败")
        return JSONResponse(result, status_code=400)
