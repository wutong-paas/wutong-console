import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette import status

from core import deps
from core.utils.reqparse import bool_argument, parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.users.perms_repo import perms_repo
from schemas.response import Response
from service.platform_config_service import platform_config_service
from service.region_service import region_services, EnterpriseConfigService
from service.task_guidance.base_task_guidance import base_task_guidance
from service.team_service import team_services

router = APIRouter()


@router.get("/config/info", response_model=Response, name="获取集群配置信息")
async def get_info(session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取集群配置信息
    :return:
    """
    initialize_info = perms_repo.initialize_permission_settings(session)
    register_config = platform_config_service.get_config_by_key(session, "IS_REGIST")
    data = platform_config_service.initialization_or_get_config(session=session)
    if data.get("enterprise_id", None) is None:
        data["enterprise_id"] = os.getenv('ENTERPRISE_ID', '')
    data["is_disable_logout"] = os.getenv('IS_DISABLE_LOGOUT', False)
    data["is_offline"] = os.getenv('IS_OFFLINE', False)
    data["is_regist"] = os.getenv('IS_REGIST', {"enable": register_config.enable,
                                                "value": register_config.value
                                                })
    result = general_message(200, "success", "查询成功", bean=data, initialize_info=initialize_info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/regions/{region_id}", response_model=Response, name="查询集群配置信息")
async def get_region_config(enterprise_id: Optional[str] = None,
                            region_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session)) -> Any:
    data = region_services.get_enterprise_region(session, enterprise_id, region_id, check_status=False)
    result = general_message(200, "success", "获取成功", bean=data)
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.put("/enterprise/{enterprise_id}/regions/{region_id}", response_model=Response, name="修改集群配置信息")
async def modify_region_config(request: Request,
                               enterprise_id: Optional[str] = None,
                               region_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    region = region_services.update_enterprise_region(session, enterprise_id, region_id, data)
    result = general_message(200, "success", "更新成功", bean=region)
    return JSONResponse(result, status_code=result.get("code", 200))


@router.get("/enterprise/{enterprise_id}/regions/{region_id}/tenants", response_model=Response, name="获取团队内存配置信息")
async def get_team_memory_config(request: Request,
                                 enterprise_id: Optional[str] = None,
                                 region_id: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session)) -> Any:
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("pageSize", 10)
    tenants, total = team_services.get_tenant_list_by_region(session, enterprise_id, region_id, page, page_size)
    result = general_message(
        200, "success", "获取成功", bean={
            "tenants": tenants,
            "total": total,
        })
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.post("/enterprise/{enterprise_id}/regions/{region_id}/tenants/{tenant_name}/limit",
             response_model=Response,
             name="设置团队内存限额")
async def set_team_memory_limit(request: Request,
                                enterprise_id: Optional[str] = None,
                                region_id: Optional[str] = None,
                                tenant_name: Optional[str] = None,
                                session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    team_services.set_tenant_memory_limit(session, enterprise_id, region_id, tenant_name, data)
    return JSONResponse({}, status_code=status.HTTP_200_OK)


@router.get("/enterprise/{enterprise_id}/base-guidance", response_model=Response, name="获取团队基础任务")
async def get_basic_task(enterprise_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    data = base_task_guidance.list_base_tasks(session, enterprise_id)
    result = general_message(200, "success", "请求成功", list=data)
    return JSONResponse(result, status_code=result["code"])


@router.put("/enterprise/{enterprise_id}/appstoreimagehub", response_model=Response, name="设置内部组件库镜像仓库")
async def set_internal_components_image(request: Request,
                                        enterprise_id: Optional[str] = None,
                                        session: SessionClass = Depends(deps.get_session)) -> Any:
    enable = bool_argument(await parse_item(request, "enable", required=True))
    hub_url = await parse_item(request, "hub_url", required=True)
    namespace = await parse_item(request, "namespace")
    hub_user = await parse_item(request, "hub_user")
    hub_password = await parse_item(request, "hub_password")

    ent_cfg_svc = EnterpriseConfigService(enterprise_id)
    ent_cfg_svc.update_config_enable_status(session, key="APPSTORE_IMAGE_HUB", enable=enable)
    ent_cfg_svc.update_config_value(
        session=session,
        key="APPSTORE_IMAGE_HUB",
        value={
            "hub_url": hub_url,
            "namespace": namespace,
            "hub_user": hub_user,
            "hub_password": hub_password,
        })
    return JSONResponse(status_code=status.HTTP_200_OK)


@router.put("/enterprise/{enterprise_id}/objectstorage", response_model=Response, name="配置云端备份对象存储")
async def set_object_storage(request: Request,
                             enterprise_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session)) -> Any:
    enable = bool_argument(await parse_item(request, "enable", required=True))
    provider = await parse_item(request, "provider", required=True)
    endpoint = await parse_item(request, "endpoint", required=True)
    bucket_name = await parse_item(request, "bucket_name", required=True)
    access_key = await parse_item(request, "access_key", required=True)
    secret_key = await parse_item(request, "secret_key", required=True)

    if provider not in ("alioss", "s3") and enable == "false":
        raise AbortRequest("provider {} not in (\"alioss\", \"s3\")".format(provider))

    ent_cfg_svc = EnterpriseConfigService(enterprise_id)
    ent_cfg_svc.update_config_enable_status(session=session, key="OBJECT_STORAGE", enable=enable)
    ent_cfg_svc.update_config_value(
        session=session,
        key="OBJECT_STORAGE",
        value={
            "provider": provider,
            "endpoint": endpoint,
            "bucket_name": bucket_name,
            "access_key": access_key,
            "secret_key": secret_key,
        })
    return JSONResponse(status_code=status.HTTP_200_OK)


@router.put("/enterprise/{enterprise_id}/visualmonitor", response_model=Response, name="监控配置")
async def set_visual_monitor(request: Request,
                             enterprise_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    enable = bool_argument(await parse_item(request, "enable", required=True))
    home_url = await parse_item(request, "home_url", required=True)
    cluster_monitor_suffix = data.get("cluster_monitor_suffix", "/d/cluster/ji-qun-jian-kong-ke-shi-hua")
    node_monitor_suffix = data.get("node_monitor_suffix", "/d/node/jie-dian-jian-kong-ke-shi-hua")
    component_monitor_suffix = data.get("component_monitor_suffix", "/d/component/zu-jian-jian-kong-ke-shi-hua")
    slo_monitor_suffix = data.get("slo_monitor_suffix", "/d/service/fu-wu-jian-kong-ke-shi-hua")

    ent_cfg_svc = EnterpriseConfigService(enterprise_id)
    ent_cfg_svc.update_config_enable_status(session=session, key="VISUAL_MONITOR", enable=enable)
    ent_cfg_svc.update_config_value(
        session=session,
        key="VISUAL_MONITOR",
        value={
            "home_url": home_url.strip('/'),
            "cluster_monitor_suffix": cluster_monitor_suffix,
            "node_monitor_suffix": node_monitor_suffix,
            "component_monitor_suffix": component_monitor_suffix,
            "slo_monitor_suffix": slo_monitor_suffix,
        })
    return JSONResponse(status_code=status.HTTP_200_OK)


@router.post("/enterprise/{enterprise_id}/regions", response_model=Response, name="集群配置")
async def set_region_config(request: Request,
                            enterprise_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    token = data.get("token")
    region_name = data.get("region_name")
    region_alias = data.get("region_alias")
    desc = data.get("desc")
    region_type = json.dumps(data.get("region_type", []))
    region_data = region_services.parse_token(token, region_name, region_alias, region_type)
    region_data["enterprise_id"] = enterprise_id
    region_data["desc"] = desc
    region_data["provider"] = data.get("provider", "")
    region_data["provider_cluster_id"] = data.get("provider_cluster_id", "")
    region_data["status"] = "1"
    region = region_services.add_region(session, region_data, user)
    if region:
        data = region_services.get_enterprise_region(session, enterprise_id, region.region_id, check_status=False)
        result = general_message(200, "success", "创建成功", bean=data)
        return JSONResponse(result, status_code=status.HTTP_200_OK)
    else:
        result = general_message(500, "failed", "创建失败")
        return JSONResponse(result, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
