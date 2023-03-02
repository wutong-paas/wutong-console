import datetime
import os
from typing import Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.bcode import ErrK8sComponentNameExists
from exceptions.main import ResourceNotEnoughException, AccountOverdueException
from repository.application.app_repository import service_webhooks_repo
from repository.component.component_repo import service_source_repo
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from service.application_service import application_service
from service.base_services import base_service
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/buildsource", response_model=Response, name="查询构建源")
async def get_build_source(serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           env=Depends(deps.get_current_team_env)) -> Any:
    """
    查询构建源信息
    ---
    """
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    service_ids = [service.service_id]
    build_infos = base_service.get_build_infos(session=session, tenant_env=env, service_ids=service_ids)
    bean = build_infos.get(service.service_id, None)
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


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
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
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
        result = general_message(200, "success", "修改成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/env/{env_id}/apps/source_code", response_model=Response, name="源码创建组件")
async def code_create_component(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    data = await request.json()
    group_id = data.get("group_id", -1)
    service_code_from = data.get("code_from", None)
    service_cname = data.get("service_cname", None)
    service_code_clone_url = data.get("git_url", None)
    git_password = data.get("password", None)
    git_user_name = data.get("username", None)
    service_code_id = data.get("git_project_id", None)
    service_code_version = data.get("code_version", "master")
    is_oauth = data.get("is_oauth", False)
    check_uuid = data.get("check_uuid")
    event_id = data.get("event_id")
    server_type = data.get("server_type", "git")
    user_id = user.user_id
    oauth_service_id = data.get("service_id")
    git_full_name = data.get("full_name")
    git_service = None
    open_webhook = False
    k8s_component_name = data.get("k8s_component_name", "")
    host = os.environ.get('DEFAULT_DOMAIN', "http://" + request.client.host)
    if k8s_component_name and application_service.is_k8s_component_name_duplicate(session, group_id,
                                                                                  k8s_component_name):
        raise ErrK8sComponentNameExists
    result = {}
    try:
        if not service_code_clone_url:
            return JSONResponse(general_message(400, "code url is null", "仓库地址未指明"), status_code=400)
        if not service_code_from:
            return JSONResponse(general_message(400, "params error", "参数service_code_from未指明"), status_code=400)
        if not server_type:
            return JSONResponse(general_message(400, "params error", "仓库类型未指明"), status_code=400)
        # 创建源码组件
        if service_code_clone_url:
            service_code_clone_url = service_code_clone_url.strip()

        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        code, msg_show, new_service = application_service.create_source_code_app(
            session,
            response_region,
            env,
            user,
            service_code_from,
            service_cname,
            service_code_clone_url,
            service_code_id,
            service_code_version,
            server_type,
            check_uuid,
            event_id,
            oauth_service_id,
            git_full_name,
            k8s_component_name=k8s_component_name)
        if code != 200:
            return JSONResponse(general_message(code, "service create fail", msg_show), status_code=code)
        # 添加username,password信息
        if git_password or git_user_name:
            application_service.create_service_source_info(session, env, new_service, git_user_name, git_password)

        # 自动添加hook
        if open_webhook and is_oauth and not new_service.open_webhooks:
            service_webhook = service_webhooks_repo.create_service_webhooks(session, new_service.service_id,
                                                                            "code_webhooks")
            service_webhook.state = True
            service_webhook.deploy_keyword = "deploy"
            # service_webhook.save()
            try:
                git_service.create_hook(host, git_full_name, endpoint='console/webhooks/' + new_service.service_id)
                new_service.open_webhooks = True
            except Exception as e:
                logger.exception(e)
                new_service.open_webhooks = False
            # new_service.save()
        code, msg_show = application_service.add_service_to_group(session, env, response_region, group_id,
                                                                  new_service.service_id)

        if code != 200:
            logger.debug("service.create", msg_show)
        bean = jsonable_encoder(new_service)
        result = general_message(200, "success", "创建成功", bean=bean)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "失败"), status_code=412)
    return JSONResponse(result, status_code=result["code"])
