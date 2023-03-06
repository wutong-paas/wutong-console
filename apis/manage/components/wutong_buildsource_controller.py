import datetime
from typing import Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from repository.component.component_repo import service_source_repo
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from service.base_services import base_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/buildsource", response_model=Response, name="查询构建源")
async def get_build_source(serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           env=Depends(deps.get_current_team_env)) -> Any:
    """
    查询构建源信息
    ---
    """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    service_ids = [service.service_id]
    build_infos = base_service.get_build_infos(session=session, tenant_env=env, service_ids=service_ids)
    bean = build_infos.get(service.service_id, None)
    result = general_message("0", "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/buildsource", response_model=Response, name="修改构建源")
async def modify_build_source(request: Request,
                              serviceAlias: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              user=Depends(deps.get_current_user),
                              env=Depends(deps.get_current_team_env)) -> Any:
    """
    修改构建源
    ---
    """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
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
        server_type = data.get("server_type", "")

        if not service_source:
            return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

        service_source_user = service_source_repo.get_service_source(
            session=session, env_id=service.tenant_env_id, service_id=service.service_id)

        if not service_source_user:
            service_source_info = {
                "service_id": service.service_id,
                "tenant_env_id": service.tenant_env_id,
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
            elif server_type == "oss":
                service.code_version = ""
            else:
                service.code_version = "master"
            if git_url:
                service.git_url = git_url
            service.service_source = service_source
            service.code_from = ""
            service.server_type = server_type
            service.cmd = ""
            service.image = ""
            service.service_key = "application"
            # service_repo.save_service(service)
        elif service_source == "docker_run":
            service.service_source = "docker_run"
            if image:
                image = image.strip()
                image_list = image.split(':')
                if len(image_list) > 1:
                    version = image_list[-1]
                else:
                    version = "latest"
                    image = image + ":" + version
                service.image = image
                service.version = version
            service.cmd = cmd
            service.server_type = server_type
            service.git_url = ""
            service.code_from = "image_manual"
            service.service_key = "application"
            # service_repo.save_service(service)
        result = general_message("0", "success", "修改成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=200)
