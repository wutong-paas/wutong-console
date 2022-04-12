import datetime
from typing import Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger

from core import deps
from core.utils.oauth_types import get_oauth_instance
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from repository.component.component_repo import service_source_repo
from repository.component.group_service_repo import service_repo
from repository.users.user_oauth_repo import oauth_repo
from schemas.response import Response
from service.application_service import application_service
from service.base_services import base_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/buildsource", response_model=Response, name="查询构建源")
async def get_build_source(serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    """
    查询构建源信息
    ---
    """
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    service_ids = [service.service_id]
    build_infos = base_service.get_build_infos(session=session, tenant=team, service_ids=service_ids)
    bean = build_infos.get(service.service_id, None)
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/buildsource", response_model=Response, name="修改构建源")
async def modify_build_source(request: Request,
                              serviceAlias: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              user=Depends(deps.get_current_user),
                              team=Depends(deps.get_current_team)) -> Any:
    """
    修改构建源
    ---
    """
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    try:
        data = await request.json()
        image = data.get("image", None)
        cmd = data.get("cmd", None)
        service_source = data.get("service_source")
        git_url = data.get("git_url", None)
        code_version = data.get("code_version", None)
        user_name = data.get("user_name", None)
        password = data.get("password", None)
        is_oauth = data.get("is_oauth", False)
        user_id = user.user_id
        oauth_service_id = data.get("service_id")
        git_full_name = data.get("full_name")

        if not service_source:
            return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

        service_source_user = service_source_repo.get_service_source(
            session=session, team_id=service.tenant_id, service_id=service.service_id)

        if not service_source_user:
            service_source_info = {
                "service_id": service.service_id,
                "team_id": service.tenant_id,
                "user_name": user_name,
                "password": password,
                "create_time": datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            }
            service_source_repo.create_service_source(session, **service_source_info)
        else:
            service_source_user.user_name = user_name
            service_source_user.password = password
            # service_source_user.save()
        if service_source == "source_code":
            if code_version:
                service.code_version = code_version
            else:
                service.code_version = "master"
            if git_url:
                if is_oauth:
                    try:
                        oauth_service = application_service.get_oauth_services_by_service_id(session=session,
                                                                                             service_id=oauth_service_id)
                        oauth_user = oauth_repo.get_user_oauth_by_user_id(session=session, service_id=oauth_service_id,
                                                                          user_id=user_id)
                    except Exception as e:
                        logger.debug(e)
                        rst = {"data": {"bean": None}, "status": 400, "msg_show": "Oauth服务可能已被删除，请重新配置"}
                        return JSONResponse(rst, status_code=200)
                    try:
                        instance = get_oauth_instance(oauth_service.oauth_type, oauth_service, oauth_user)
                    except Exception as e:
                        logger.debug(e)
                        rst = {"data": {"bean": None}, "status": 400, "msg_show": "未找到OAuth服务"}
                        return JSONResponse(rst, status_code=200)
                    if not instance.is_git_oauth():
                        rst = {"data": {"bean": None}, "status": 400, "msg_show": "该OAuth服务不是代码仓库类型"}
                        return JSONResponse(rst, status_code=200)
                    service_code_from = "oauth_" + oauth_service.oauth_type
                    service.code_from = service_code_from
                    service.git_url = git_url
                    service.git_full_name = git_full_name
                    service.oauth_service_id = oauth_service_id
                    service.creater = user_id
                else:
                    service.git_url = git_url
            # service_repo.save_service(service)
        elif service_source == "docker_run":
            if image:
                version = image.split(':')[-1]
                if not version:
                    version = "latest"
                    image = image + ":" + version
                service.image = image
                service.version = version
            service.cmd = cmd
            # service_repo.save_service(service)
        result = general_message(200, "success", "修改成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=result["code"])
