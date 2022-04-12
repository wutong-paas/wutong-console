from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Header
from fastapi.responses import JSONResponse
from starlette import status

from core import deps
from core.utils.oauth_types import get_oauth_instance
from database.session import SessionClass
from repository.users.user_oauth_repo import oauth_repo
from schemas.response import Response
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
