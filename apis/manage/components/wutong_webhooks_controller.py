import base64
import os
import pickle
import re
from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.idaasapi import idaas_api
from core.utils.constants import AppConstants
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from models.component.models import TeamComponentInfo, DeployRelation
from repository.application.app_repository import service_webhooks_repo
from repository.component.deploy_repo import deploy_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.team_component_repo import team_component_repo
from schemas.response import Response
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/webhooks/get-url", response_model=Response, name="获取自动部署回调地址")
async def get_auto_url(request: Request,
                       serviceAlias: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       team=Depends(deps.get_current_team)) -> Any:
    """
    判断该组件是否有webhooks自动部署功能，有则返回URL
    """
    try:
        deployment_way = request.query_params.get("deployment_way", None)
        if not deployment_way:
            result = general_message(400, "Parameter cannot be empty", "缺少参数")
            return JSONResponse(result, status_code=400)
        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        tenant_id = team.tenant_id
        service_alias = service.service_alias
        service_obj = team_component_repo.get_one_by_model(session=session,
                                                           query_model=TeamComponentInfo(tenant_id=tenant_id,
                                                                                         service_alias=service_alias))
        if service_obj.service_source == AppConstants.MARKET:
            result = general_message(200, "failed", "该组件不符合要求", bean={"display": False})
            return JSONResponse(result, status_code=200)
        if service_obj.service_source == AppConstants.SOURCE_CODE:
            support_type = 1
        else:
            support_type = 2

        service_id = service_obj.service_id
        # 从环境变量中获取域名，没有在从请求中获取
        host = os.environ.get('DEFAULT_DOMAIN', request.headers.get("referer"))

        service_webhook = service_webhooks_repo.get_or_create_service_webhook(session, service.service_id,
                                                                              deployment_way)

        # api处发自动部署
        if deployment_way == "api_webhooks":
            # 生成秘钥
            deploy = deploy_repo.get_deploy_relation_by_service_id(session=session, service_id=service_id)
            secret_key = pickle.loads(base64.b64decode(deploy)).get("secret_key")
            url = host + "console/" + "custom/deploy/" + service_obj.service_id
            result = general_message(
                200,
                "success",
                "获取URl及开启状态成功",
                bean={
                    "url": url,
                    "secret_key": secret_key,
                    "status": service_webhook.state,
                    "display": True,
                    "support_type": support_type
                })
        # 镜像处发自动部署
        elif deployment_way == "image_webhooks":
            url = host + "console/" + "image/webhooks/" + service_obj.service_id

            result = general_message(
                200,
                "success",
                "获取URl及开启状态成功",
                bean={
                    "url": url,
                    "status": service_webhook.state,
                    "display": True,
                    "support_type": support_type,
                    "trigger": service_webhook.trigger,
                })
        # 源码处发自动部署
        else:
            url = host + "console/" + "webhooks/" + service_obj.service_id
            deploy_keyword = service_webhook.deploy_keyword
            result = general_message(
                200,
                "success",
                "获取URl及开启状态成功",
                bean={
                    "url": url,
                    "status": service_webhook.state,
                    "display": True,
                    "support_type": support_type,
                    "deploy_keyword": deploy_keyword
                })
        return JSONResponse(result, status_code=200)
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=500)


@router.post("/teams/{team_name}/apps/{serviceAlias}/webhooks/status", response_model=Response, name="开启或关闭自动部署功能")
async def run_or_stop_auto(request: Request,
                           serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    """
    开启或关闭自动部署功能
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: action
          description: 操作 打开:open 关闭:close
          required: true
          type: string 格式：{"action":"open"}
          paramType: body

    """
    try:
        data = await request.json()
        action = data.get("action", None)
        deployment_way = data.get("deployment_way", None)
        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        if not action or not deployment_way:
            result = general_message(400, "Parameter cannot be empty", "缺少参数")
            return JSONResponse(result, status_code=400)
        if action != "open" and action != "close":
            result = general_message(400, "action error", "操作类型不存在")
            return JSONResponse(result, status_code=400)
        service_webhook = service_webhooks_repo.get_service_webhooks_by_service_id_and_type(
            session, service.service_id, deployment_way)
        if not service_webhook:
            service_webhook = service_webhooks_repo.create_service_webhooks(session, service.service_id, deployment_way)
        if action == "open":
            service_webhook.state = True
            result = general_message(200, "success", "开启成功")
        else:
            service_webhook.state = False
            result = general_message(200, "success", "关闭成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
        return JSONResponse(result, status_code=500)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/apps/{serviceAlias}/webhooks/updatekey", response_model=Response, name="更新自动构建密钥")
async def update_key(request: Request,
                     serviceAlias: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     team=Depends(deps.get_current_team)) -> Any:
    try:
        data = await request.json()
        secret_key = data.get("secret_key", None)
        if not secret_key:
            code = 400
            result = general_message(code, "no secret_key", "请输入密钥")
            return JSONResponse(result, status_code=code)
        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        tenant_id = team.tenant_id
        service_alias = service.service_alias
        service_obj = team_component_repo.get_one_by_model(session=session,
                                                           query_model=TeamComponentInfo(tenant_id=tenant_id,
                                                                                         service_alias=service_alias))
        deploy_obj = deploy_repo.get_one_by_model(session=session,
                                                  query_model=DeployRelation(service_id=service_obj.service_id))
        pwd = base64.b64encode(pickle.dumps({"secret_key": secret_key}))
        if deploy_obj:
            deploy_obj.secret_key = pwd

            result = general_message(200, "success", "修改成功")
            return JSONResponse(result, 200)
        else:
            result = general_message(404, "not found", "没有该组件")
            return JSONResponse(result, 404)
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
    return JSONResponse(result, status_code=500)


@router.put("/teams/{team_name}/apps/{serviceAlias}/webhooks/trigger'", response_model=Response, name="更新自动部署触发方式")
async def update_deploy_mode(
        request: Request,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """镜像更新自动部署触发条件"""
    try:
        data = await request.json()
        service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
        service_webhook = service_webhooks_repo.get_or_create_service_webhook(session, service.service_id,
                                                                              "image_webhooks")
        trigger = data.get("trigger")
        if trigger:
            service_webhook.trigger = trigger
    except Exception as e:
        logger.exception(e)
        return error_message("failed")
    return JSONResponse(
        general_message(
            200,
            "success",
            "自动部署触发条件更新成功",
            bean={
                "url":
                    "{host}console/image/webhooks/{service_id}".format(
                        host=os.environ.get('DEFAULT_DOMAIN', request.headers.get("referer")),
                        service_id=service.service_id),
                "trigger":
                    service_webhook.trigger
            }),
        status_code=200)


@router.post("/image/webhooks/{service_id}", response_model=Response, name="镜像仓库webhooks回调")
async def update_deploy_mode(
        request: Request,
        service_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        data = await request.json()
        service_obj = service_info_repo.get_service_by_service_id(session, service_id)
        if not service_obj:
            result = general_message(400, "failed", "组件不存在")
            return JSONResponse(result, status_code=400)
        tenant_obj = env_services.get_team_by_team_id(session, service_obj.tenant_id)
        service_webhook = service_webhooks_repo.get_service_webhooks_by_service_id_and_type(
            session, service_obj.service_id, "image_webhooks")
        if not service_webhook.state:
            result = general_message(400, "failed", "组件关闭了自动构建")
            return JSONResponse(result, status_code=400)
        # 校验
        repository = data.get("repository")
        if not repository:
            logger.debug("缺少repository信息")
            result = general_message(400, "failed", "缺少repository信息")
            return JSONResponse(result, status_code=400)

        push_data = data.get("push_data")
        pusher = push_data.get("pusher")
        tag = push_data.get("tag")
        repo_name = repository.get("repo_name")
        if not repo_name:
            repository_namespace = repository.get("namespace")
            repository_name = repository.get("name")
            if repository_namespace and repository_name:
                # maybe aliyun repo add fake host
                repo_name = "fake.repo.aliyun.com/" + repository_namespace + "/" + repository_name
            else:
                repo_name = repository.get("repo_full_name")
        if not repo_name:
            result = general_message(400, "failed", "缺少repository名称信息")
            return JSONResponse(result, status_code=400)

        ref_repo_name, ref_tag = service_obj.image.split(":")
        if repo_name != ref_repo_name:
            result = general_message(400, "failed", "镜像名称与组件构建源不符")
            return JSONResponse(result, status_code=400)

        # 标签匹配
        if service_webhook.trigger:
            # 如果有正则表达式根据正则触发
            if not re.match(service_webhook.trigger, tag):
                result = general_message(400, "failed", "镜像tag与正则表达式不匹配")
                return JSONResponse(result, status_code=400)
        else:
            # 如果没有根据标签触发
            if tag != ref_tag:
                result = general_message(400, "failed", "镜像tag与组件构建源不符")
                return JSONResponse(result, status_code=400)

        service_info_repo.change_service_image_tag(session, service_obj, tag)
        # 获取组件状态
        status_map = application_service.get_service_status(session, tenant_obj, service_obj)
        status = status_map.get("status", None)
        user_obj = idaas_api.get_user_info(service_obj.creater)
        committer_name = pusher
        if status != "closed":
            return app_manage_service.deploy_service(
                session=session, tenant_obj=tenant_obj, service_obj=service_obj, user=user_obj, committer_name=committer_name)
        else:
            result = general_message(400, "failed", "组件状态处于关闭中，不支持自动构建")
            return JSONResponse(result, status_code=400)
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
        return JSONResponse(result, status_code=500)
