import base64
import json
import os
import pickle
from typing import Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger

from core import deps
from core.utils.constants import AppConstants
from core.utils.return_message import general_message
from database.session import SessionClass
from models.component.models import TeamComponentInfo
from repository.component.component_repo import service_source_repo
from repository.component.deploy_repo import deploy_repo
from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import service_endpoints_repo
from repository.teams.team_component_repo import team_component_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.app_actions.app_log import ws_service, event_service
from service.application_service import application_service
from service.compose_service import compose_service
from service.market_app_service import market_app_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/status", response_model=Response, name="获取组件状态")
async def get_assembly_state(serviceAlias: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件状态
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
    """
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    bean = dict()
    bean["check_uuid"] = service.check_uuid
    status_map = application_service.get_service_status(session=session, tenant=team, service=service)
    bean.update(status_map)
    result = general_message(200, "success", "查询成功", bean=bean)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/detail", response_model=Response, name="应用详情")
async def get_app_detail(request: Request,
                         serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
     组件详情信息
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
     """
    bean = dict()
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    namespace = team.namespace
    service_model = jsonable_encoder(service)
    group_map = application_service.get_services_group_name(session=session, service_ids=[service.service_id])
    group_name = group_map.get(service.service_id)["group_name"]
    group_id = group_map.get(service.service_id)["group_id"]
    service_model["group_name"] = group_name
    service_model["group_id"] = group_id
    service_model["namespace"] = namespace
    bean.update({"service": service_model})
    event_websocket_url = ws_service.get_event_log_ws(session=session, request=request, region=service.service_region)
    bean.update({"event_websocket_url": event_websocket_url})
    if service.service_source == "market":
        service_source = service_source_repo.get_service_source(session, team.tenant_id, service.service_id)
        if not service_source:
            result = general_message(200, "success", "查询成功", bean=bean)
            return JSONResponse(result, status_code=result["code"])
        wutong_app, wutong_app_version = market_app_service.get_wutong_app_and_version(session=session,
                                                                                       enterprise_id=team.enterprise_id,
                                                                                       app_id=service_source.group_key,
                                                                                       app_version=service_source.version)
        if not wutong_app:
            result = general_message(200, "success", "当前组件安装源模版已删除", bean=bean)
            return JSONResponse(result, status_code=result["code"])

        bean.update({"rain_app_name": wutong_app.app_name})
        try:
            if wutong_app_version:
                apps_template = json.loads(wutong_app_version.app_template)
                apps_list = apps_template.get("apps")
                service_source = service_source_repo.get_service_source(session, service.tenant_id, service.service_id)
                if service_source and service_source.extend_info:
                    extend_info = json.loads(service_source.extend_info)
                    if extend_info:
                        for app in apps_list:
                            if "service_share_uuid" in app:
                                if app["service_share_uuid"] == extend_info["source_service_share_uuid"]:
                                    new_version = int(app["deploy_version"])
                                    old_version = int(extend_info["source_deploy_version"])
                                    if new_version > old_version:
                                        service.is_upgrate = True
                                        service.save()
                                        service_model["is_upgrade"] = True
                                        bean.update({"service": service_model})
                            elif "service_share_uuid" not in app and "service_key" in app:
                                if app["service_key"] == extend_info["source_service_share_uuid"]:
                                    new_version = int(app["deploy_version"])
                                    old_version = int(extend_info["source_deploy_version"])
                                    if new_version > old_version:
                                        service.is_upgrate = True
                                        service.save()
                                        service_model["is_upgrade"] = True
                                        bean.update({"service": service_model})
        except Exception as e:
            logger.exception(e)

    if service.service_source == AppConstants.DOCKER_COMPOSE:
        if service.create_status != "complete":
            compose_service_relation = compose_service.get_service_compose_id(session=session, service=service)
            if compose_service_relation:
                service_model["compose_id"] = compose_service_relation.compose_id
                bean.update({"service": service_model})
    bean["is_third"] = False
    if service.service_source == "third_party":
        bean["is_third"] = True
        service_endpoints = service_endpoints_repo.get_service_endpoints_by_service_id(session, service.service_id)
        if service_endpoints:
            bean["register_way"] = service_endpoints.endpoints_type
            bean["endpoints_type"] = service_endpoints.endpoints_type
            if service_endpoints.endpoints_type == "api":
                # 从环境变量中获取域名，没有在从请求中获取
                host = os.environ.get('DEFAULT_DOMAIN', "http://" + request.client.host)
                bean["api_url"] = host + "/console/" + "third_party/{0}".format(service.service_id)
                key_repo = deploy_repo.get_service_key_by_service_id(service_id=service.service_id)
                if key_repo:
                    bean["api_service_key"] = pickle.loads(base64.b64decode(key_repo.secret_key)).get("secret_key")
            if service_endpoints.endpoints_type == "discovery":
                # 返回类型和key
                endpoints_info_dict = json.loads(service_endpoints.endpoints_info)

                bean["discovery_type"] = endpoints_info_dict["type"]
                bean["discovery_key"] = endpoints_info_dict["key"]
            if service_endpoints.endpoints_type == "kubernetes":
                bean["kubernetes"] = json.loads(service_endpoints.endpoints_info)

    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/events", response_model=Response, name="获取作用对象的event事件")
async def get_events_info(request: Request,
                          session: SessionClass = Depends(deps.get_session),
                          team=Depends(deps.get_current_team)) -> Any:
    """
    获取作用对象的event事件

    """
    global result
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("page_size", 6)
    target = request.query_params.get("target", "")
    targetAlias = request.query_params.get("targetAlias", "")
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    if targetAlias == "":
        target = "team"
        targetAlias = team.tenant_name
    if target == "service":
        service = team_component_repo.get_one_by_model(session=session,
                                                       query_model=TeamComponentInfo(tenant_id=team.tenant_id,
                                                                                     service_alias=targetAlias))
        if service:
            target_id = service.service_id
            events, total, has_next = event_service.get_target_events(session=session, target=target,
                                                                      target_id=target_id,
                                                                      tenant=team, region=service.service_region,
                                                                      page=int(page),
                                                                      page_size=int(page_size))
            result = general_message(200, "success", "查询成功", list=events, total=total, has_next=has_next)
        else:
            result = general_message(200, "success", "查询成功", list=[], total=0, has_next=False)
    elif target == "team":
        target_id = team.tenant_id
        region = response_region
        events, total, has_next = event_service.get_target_events(session=session, target=target,
                                                                  target_id=target_id,
                                                                  tenant=team, region=region,
                                                                  page=int(page),
                                                                  page_size=int(page_size))
        result = general_message(200, "success", "查询成功", list=events, total=total, has_next=has_next)
    return JSONResponse(result, status_code=result["code"])
