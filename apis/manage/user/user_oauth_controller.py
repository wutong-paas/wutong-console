import os
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger
from starlette import status
from core import deps
from core.utils.oauth.oauth_types import NoSupportOAuthType
from core.utils.oauth_types import get_oauth_instance, support_oauth_type
from core.utils.return_message import error_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.users.user_oauth_repo import oauth_repo, oauth_user_repo
from schemas.response import Response
from service.application_service import application_service
from service.oauth_service import oauth_sev_user_service
from service.region_service import EnterpriseConfigService

router = APIRouter()


@router.put("/oauth/oauth-config", response_model=Response, name="设置oauth第三方服务集成")
async def set_oauth_third(request: Request,
                          session=Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    data = data.get("oauth_services")
    enable = data.get("enable")
    EnterpriseConfigService(user.enterprise_id).update_config_enable_status(session=session,
                                                                            key="OAUTH_SERVICES",
                                                                            enable=enable)
    rst = {"data": {"bean": {"oauth_services": data}}}
    return JSONResponse(rst, status_code=status.HTTP_200_OK)


@router.get("/enterprise/{enterprise_id}/oauth/oauth-services", response_model=Response, name="查询oauth服务集成")
async def get_oauth_services(enterprise_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session)) -> Any:
    all_services_list = []
    service = oauth_repo.get_conosle_oauth_service(session, enterprise_id)
    all_services = oauth_repo.get_all_oauth_services(session, enterprise_id)
    if all_services is not None:
        for l_service in all_services:
            api = get_oauth_instance(l_service.oauth_type, service, None)
            authorize_url = api.get_authorize_url()
            all_services_list.append({
                "service_id": l_service.ID,
                "enable": l_service.enable,
                "name": l_service.name,
                "client_id": l_service.client_id,
                "auth_url": l_service.auth_url,
                "redirect_uri": l_service.redirect_uri,
                "oauth_type": l_service.oauth_type,
                "home_url": l_service.home_url,
                "eid": l_service.eid,
                "access_token_url": l_service.access_token_url,
                "api_url": l_service.api_url,
                "client_secret": l_service.client_secret,
                "is_auto_login": l_service.is_auto_login,
                "is_git": l_service.is_git,
                "authorize_url": authorize_url,
                "enterprise_id": l_service.eid,
            })
    rst = {"data": {"list": all_services_list}}
    return JSONResponse(rst, status_code=status.HTTP_200_OK)


@router.post("/enterprise/{enterprise_id}/oauth/oauth-services", response_model=Response, name="添加oauth服务集成")
async def add_oauth_services(
        request: Request,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    values = data.get("oauth_services")
    eid = user.enterprise_id
    try:
        services = oauth_repo.create_or_update_console_oauth_services(session, values, eid)
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"msg": "添加失败"}, status_code=status.HTTP_400_BAD_REQUEST)
    service = oauth_repo.get_conosle_oauth_service(session, eid)
    api = get_oauth_instance(service.oauth_type, service, None)
    authorize_url = api.get_authorize_url()
    data = []
    for service in services:
        data.append({
            "service_id": service.ID,
            "name": service.name,
            "oauth_type": service.oauth_type,
            "client_id": service.client_id,
            "client_secret": service.client_secret,
            "enable": service.enable,
            "eid": service.eid,
            "redirect_uri": service.redirect_uri,
            "home_url": service.home_url,
            "auth_url": service.auth_url,
            "access_token_url": service.access_token_url,
            "api_url": service.api_url,
            "is_auto_login": service.is_auto_login,
            "is_git": service.is_git,
            "authorize_url": authorize_url,
        })
    rst = {"data": {"bean": {"oauth_services": data}}}
    return JSONResponse(rst, status_code=status.HTTP_200_OK)


@router.get("/oauth/type", response_model=Response, name="获取Oauth类型")
async def get_oauth_type() -> Any:
    try:
        data = list(support_oauth_type.keys())
    except Exception as e:
        logger.debug(e)
        return JSONResponse(error_message(e), status_code=status.HTTP_200_OK)
    rst = {"data": {"bean": {"oauth_type": data}}}
    return JSONResponse(rst, status_code=status.HTTP_200_OK)


@router.delete("/oauth/oauth-services/{service_id}", response_model=Response, name="删除Oauth配置")
async def delete_oauth(
        service_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    try:
        oauth_repo.delete_oauth_service(session, service_id)
        oauth_user_repo.delete_users_by_services_id(session, service_id)
        rst = {"data": {"bean": None}, "status": 200}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.debug(e)
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "未找到oauth服务"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)


@router.get("/oauth/redirect", response_model=Response, name="获取redirect")
async def get_redirect(
        request: Request,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    code = request.query_params.get("code")
    service_id = request.query_params.get("service_id")
    service = application_service.get_oauth_services_by_service_id(session, service_id)
    route_mode = os.getenv("ROUTE_MODE", "hash")
    path = "/#/oauth/callback?service_id={}&code={}"
    if route_mode == "history":
        path = "/oauth/callback?service_id={}&code={}"
    return RedirectResponse(path.format(service.ID, code))


@router.get("/oauth/authorize", response_model=Response, name="获取authorize")
async def get_authorize(
        request: Request,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    code = request.query_params.get("code")
    service_id = request.query_params.get("service_id")
    domain = request.query_params.get("domain")
    home_split_url = None
    try:
        oauth_service = application_service.get_oauth_services_by_service_id(session, service_id)
        if oauth_service.oauth_type == "enterprisecenter" and domain:
            home_split_url = urlsplit(oauth_service.home_url)
            oauth_service.proxy_home_url = home_split_url.scheme + "://" + domain + home_split_url.path
    except Exception as e:
        logger.debug(e)
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "未找到oauth服务, 请检查该服务是否存在且属于开启状态"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    try:
        api = get_oauth_instance(oauth_service.oauth_type, oauth_service, None)
    except NoSupportOAuthType as e:
        logger.debug(e)
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "未找到oauth服务"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    try:
        oauth_user, access_token, refresh_token = api.get_user_info(code=code)
    except Exception as e:
        logger.exception(e)
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "失败"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    if api.is_communication_oauth():
        logger.debug(oauth_user.enterprise_domain)
        logger.debug(domain.split(".")[0])
        logger.debug(home_split_url.netloc.split("."))
        if oauth_user.enterprise_domain != domain.split(".")[0] and \
                domain.split(".")[0] != home_split_url.netloc.split(".")[0]:
            raise ServiceHandleException(msg="Domain Inconsistent", msg_show="登录失败", status_code=401, error_code=10405)
        client_ip = request.META.get("REMOTE_ADDR", None)
        oauth_user.client_ip = client_ip
        oauth_sev_user_service.get_or_create_user_and_enterprise(session, oauth_user)
    return oauth_sev_user_service.set_oauth_user_relation(session, api, oauth_service, oauth_user, access_token,
                                                          refresh_token,
                                                          code)


@router.get("/oauth/user", response_model=Response, name="获取oauth用户")
async def get_oauth_user(
        request: Request,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    id = request.query_params.get("id")
    code = request.query_params.get("code")
    service_id = request.query_params.get("service_id")
    if code is not None:
        user_info = oauth_user_repo.get_user_oauth_by_code(session=session, code=code, service_id=service_id)
    elif id is not None:
        user_info = oauth_user_repo.get_user_oauth_by_id(session=session, id=id, service_id=service_id)
    else:
        user_info = None
    if user_info:
        if user_info.user_id:
            is_link = True
        else:
            is_link = False
        data = {
            "oauth_user_id": user_info.oauth_user_id,
            "oauth_user_name": user_info.oauth_user_name,
            "oauth_user_email": user_info.oauth_user_email,
            "is_authenticated": user_info.is_authenticated,
            "is_expired": user_info.is_expired,
            "is_link": is_link,
            "service_id": service_id,
        }
        rst = {"data": {"bean": {"user_info": data}}}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    rst = {"data": {"bean": None}, "status": 404, "msg_show": "未找到oauth服务"}
    return JSONResponse(rst, status_code=status.HTTP_404_NOT_FOUND)


@router.post("/oauth/user/link", response_model=Response, name="链接oauth用户")
async def link_oauth_user(
        request: Request,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    data = await request.json()
    oauth_user_id = str(data.get("oauth_user_id"))
    service_id = data.get("service_id")
    try:
        oauth_service = application_service.get_oauth_services_by_service_id(session=session, service_id=service_id)
    except Exception as e:
        logger.debug(e)
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "未找到oauth服务, 请检查该服务是否存在且属于开启状态"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    user_id = user.user_id
    oauth_user = oauth_user_repo.user_oauth_exists(session=session, service_id=service_id, oauth_user_id=oauth_user_id)
    link_user = oauth_repo.get_user_oauth_by_user_id(session=session, service_id=service_id, user_id=user_id)
    if link_user is not None and link_user.oauth_user_id != oauth_user_id:
        rst = {"data": {"bean": None}, "status": 400, "msg_show": "绑定失败， 该用户已绑定其他账号"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    if oauth_user:
        oauth_user.user_id = user_id
        # oauth_user.save()
        data = {
            "oauth_user_id": oauth_user.oauth_user_id,
            "oauth_user_name": oauth_user.oauth_user_name,
            "oauth_user_email": oauth_user.oauth_user_email,
            "is_authenticated": oauth_user.is_authenticated,
            "is_expired": oauth_user.is_expired,
            "is_link": True,
            "service_id": service_id,
            "oauth_type": oauth_service.oauth_type,
        }
        rst = {"data": {"bean": data}, "status": 200, "msg_show": "绑定成功"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
    else:
        rst = {"data": {"bean": None}, "status": 404, "msg_show": "绑定失败，请重新认证"}
        return JSONResponse(rst, status_code=status.HTTP_200_OK)
