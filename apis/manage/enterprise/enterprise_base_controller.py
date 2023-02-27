import json
import os
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
from starlette import status
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.reqparse import bool_argument, parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest, ServiceHandleException
from models.teams import PermRelTenant, EnvInfo
from models.teams.enterprise import TeamEnterprise
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_enterprise_repo import tenant_enterprise_repo
from repository.users.perms_repo import perms_repo
from schemas.response import Response
from service.app_actions.app_deploy import RegionApiBaseHttpClient
from service.platform_config_service import platform_config_service
from service.region_service import region_services, EnterpriseConfigService, get_region_list_by_team_name
from service.task_guidance.base_task_guidance import base_task_guidance
from service.env_service import env_services

router = APIRouter()


@router.get("/config/info", response_model=Response, name="获取集群配置信息")
async def get_info(
        session: SessionClass = Depends(deps.get_session)) -> Any:
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
    if register_config:
        data["is_regist"] = os.getenv('IS_REGIST', {"enable": register_config.enable,
                                                    "value": register_config.value
                                                    })
    else:
        data["is_regist"] = os.getenv('IS_REGIST', {"enable": 1,
                                                    "value": ""
                                                    })
    data["login_timeout"] = 15
    result = general_message(200, "success", "查询成功", bean=data, initialize_info=initialize_info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/regions/{region_id}", response_model=Response, name="查询集群配置信息")
async def get_region_config(enterprise_id: Optional[str] = None,
                            region_id: Optional[str] = None,
                            user=Depends(deps.get_current_user),
                            session: SessionClass = Depends(deps.get_session)) -> Any:
    data = region_services.get_enterprise_region(session, enterprise_id, region_id, check_status=False)
    result = general_message(200, "success", "获取成功", bean=data)
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.put("/enterprise/{enterprise_id}/regions/{region_name}/mavensettings/{name}", response_model=Response,
            name="修改Maven配置")
async def update_maven_settings(
        request: Request,
        enterprise_id: Optional[str] = None,
        region_name: Optional[str] = None,
        name: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        data = await request.json()
        res, body = remote_build_client.update_maven_setting(session, enterprise_id, region_name, name, data)
        result = general_message(200, 'update success', '修改成功', bean=body.get("bean"))
    except RegionApiBaseHttpClient.CallApiError as exc:
        if exc.message.get("httpcode") == 404:
            result = general_message(404, 'maven setting is not exist', '配置不存在')
        else:
            logger.exception(exc)
            result = general_message(500, 'update maven setting failure', '更新配置失败')
    except ServiceHandleException as e:
        if e.status_code == 404:
            result = general_message(404, 'maven setting is not exist', '配置不存在')
        else:
            logger.exception(e)
            result = general_message(500, 'update maven setting failure', '更新配置失败')
    return JSONResponse(result, status_code=result["code"])


@router.delete("/enterprise/{enterprise_id}/regions/{region_name}/mavensettings/{name}", response_model=Response,
               name="删除Maven配置")
async def delete_maven_settings(
        enterprise_id: Optional[str] = None,
        region_name: Optional[str] = None,
        name: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        res, body = remote_build_client.delete_maven_setting(session, enterprise_id, region_name, name)
        result = general_message(200, 'delete success', '删除成功', bean=body.get("bean"))
    except RegionApiBaseHttpClient.CallApiError as exc:
        if exc.message.get("httpcode") == 404:
            result = general_message(404, 'maven setting is not exist', '配置不存在')
        else:
            logger.exception(exc)
            result = general_message(500, 'add maven setting failure', '删除配置失败')
    except ServiceHandleException as e:
        if e.status_code == 404:
            result = general_message(404, 'maven setting is not exist', '配置不存在')
        else:
            logger.exception(e)
            result = general_message(500, 'add maven setting failure', '删除配置失败')
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/regions/{region_name}/mavensettings", response_model=Response,
             name="添加Maven配置")
async def add_maven_settings(
        request: Request,
        enterprise_id: Optional[str] = None,
        region_name: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        data = await request.json()
        res, body = remote_build_client.add_maven_setting(session, enterprise_id, region_name, data)
        result = general_message(200, 'query success', '添加成功', bean=body.get("bean"))
    except RegionApiBaseHttpClient.CallApiError as exc:
        if exc.message.get("httpcode") == 400:
            result = general_message(400, 'maven setting name is exist', '配置名称已存在')
        else:
            logger.exception(exc)
            result = general_message(500, 'add maven setting failure', '配置添加失败')
    except ServiceHandleException as e:
        if e.status_code == 400:
            result = general_message(400, 'maven setting name is exist', '配置名称已存在')
        else:
            logger.exception(e)
            result = general_message(500, 'add maven setting failure', '配置添加失败')
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/regions/{region_name}/mavensettings", response_model=Response,
            name="获取构建源手动配置项")
async def get_mavens_ettings(
        request: Request,
        enterprise_id: Optional[str] = None,
        region_name: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    onlyname = request.query_params.get("onlyname", True)
    res, body = remote_build_client.list_maven_settings(session, enterprise_id, region_name)
    redata = body.get("list")
    if redata and isinstance(redata, list) and (onlyname is True or onlyname == "true"):
        newdata = []
        for setting in redata:
            newdata.append({"name": setting["name"], "is_default": setting["is_default"]})
        redata = newdata
    result = general_message(200, 'query success', '数据中心Maven获取成功', list=redata)
    return JSONResponse(result, status_code=200)


@router.put("/enterprise/{enterprise_id}/regions/{region_id}", response_model=Response, name="修改集群配置信息")
async def modify_region_config(request: Request,
                               enterprise_id: Optional[str] = None,
                               region_id: Optional[str] = None,
                               user=Depends(deps.get_current_user),
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    region = region_services.update_enterprise_region(session, enterprise_id, region_id, data)
    result = general_message(200, "success", "更新成功", bean=region)
    return JSONResponse(result, status_code=result.get("code", 200))


@router.delete("/enterprise/{enterprise_id}/regions/{region_id}", response_model=Response, name="删除集群")
async def delete_region(request: Request,
                        enterprise_id: Optional[str] = None,
                        region_id: Optional[str] = None,
                        user=Depends(deps.get_current_user),
                        session: SessionClass = Depends(deps.get_session)) -> Any:
    region = region_repo.get_region_by_region_id(session, region_id)
    if not region:
        raise ServiceHandleException(status_code=404, msg="集群已不存在")
    region_repo.del_by_enterprise_region_id(session, enterprise_id, region_id)
    result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result.get("code", 200))


@router.get("/enterprise/{enterprise_id}/regions/{region_id}/tenants", response_model=Response, name="获取团队内存配置信息")
async def get_team_memory_config(request: Request,
                                 enterprise_id: Optional[str] = None,
                                 region_id: Optional[str] = None,
                                 user=Depends(deps.get_current_user),
                                 session: SessionClass = Depends(deps.get_session)) -> Any:
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("pageSize", 10)
    tenants, total = env_services.get_tenant_list_by_region(session, enterprise_id, region_id, page, page_size)
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
                                user=Depends(deps.get_current_user),
                                session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    env_services.set_tenant_memory_limit(session, enterprise_id, region_id, tenant_name, data)
    return JSONResponse({}, status_code=status.HTTP_200_OK)


@router.get("/enterprise/{enterprise_id}/base-guidance", response_model=Response, name="获取团队基础任务")
async def get_basic_task(enterprise_id: Optional[str] = None,
                         user=Depends(deps.get_current_user),
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    data = base_task_guidance.list_base_tasks(session, enterprise_id)
    result = general_message(200, "success", "请求成功", list=data)
    return JSONResponse(result, status_code=result["code"])


@router.put("/enterprise/{enterprise_id}/appstoreimagehub", response_model=Response, name="设置内部组件库镜像仓库")
async def set_internal_components_image(request: Request,
                                        enterprise_id: Optional[str] = None,
                                        user=Depends(deps.get_current_user),
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
                             user=Depends(deps.get_current_user),
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
                             user=Depends(deps.get_current_user),
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


@router.put("/enterprise/{enterprise_id}/log_query", response_model=Response, name="配置日志查询开关")
async def set_log_query(request: Request,
                        enterprise_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user)) -> Any:
    enable = bool_argument(await parse_item(request, "enable", required=True))
    admin = enterprise_user_perm_repo.is_admin(session, user_id=user.user_id, eid=enterprise_id)
    if admin:
        if enable is False:
            # 修改全局配置
            platform_config_service.update_config(session, "LOG_QUERY", {"enable": False, "value": None})
            return JSONResponse(general_message(200, "close log_query", "关闭日志查询"), status_code=200)
        else:
            platform_config_service.update_config(session, "LOG_QUERY", {"enable": True, "value": None})
            return JSONResponse(general_message(200, "open log_query", "开启日志查询"), status_code=200)
    else:
        return JSONResponse(general_message(400, "no jurisdiction", "没有权限"), status_code=400)


@router.put("/enterprise/{enterprise_id}/call_link", response_model=Response, name="配置调用链路查询开关")
async def set_call_link(request: Request,
                        enterprise_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user)) -> Any:
    enable = bool_argument(await parse_item(request, "enable", required=True))
    admin = enterprise_user_perm_repo.is_admin(session, user_id=user.user_id, eid=enterprise_id)
    if admin:
        if enable is False:
            # 修改全局配置
            platform_config_service.update_config(session, "CALL_LINK_QUERY", {"enable": False, "value": None})
            return JSONResponse(general_message(200, "close call_link_query", "关闭调用链路查询"), status_code=200)
        else:
            platform_config_service.update_config(session, "CALL_LINK_QUERY", {"enable": True, "value": None})
            return JSONResponse(general_message(200, "open call_link_query", "开启调用链路查询"), status_code=200)
    else:
        return JSONResponse(general_message(400, "no jurisdiction", "没有权限"), status_code=400)


@router.get("/users/details", response_model=Response, name="获取用户详情")
async def get_user_details(session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user)) -> Any:
    # 查询企业信息
    enterprise = tenant_enterprise_repo.get_one_by_model(session=session,
                                                         query_model=TeamEnterprise(enterprise_id=user.enterprise_id))

    user_detail = dict()
    user_detail["user_id"] = user.user_id
    user_detail["user_name"] = user.nick_name
    user_detail["real_name"] = user.real_name
    user_detail["email"] = user.email
    user_detail["enterprise_id"] = user.enterprise_id
    user_detail["phone"] = user.phone

    user_detail["roles"] = ["admin"]
    user_detail["is_sys_admin"] = False
    user_detail["git_user_id"] = 0

    if enterprise:
        user_detail["is_enterprise_active"] = enterprise.is_active
    # todo is_enterprise_admin
    # user_detail["is_enterprise_admin"] = self.is_enterprise_admin
    user_detail["is_enterprise_admin"] = True
    tenant_list = []
    # 查询团队信息
    # tenant_ids_results = session.execute(
    #     select(PermRelTenant.tenant_id).where(PermRelTenant.user_id == user.user_id))
    # tenant_ids = tenant_ids_results.scalars().all()
    # if len(tenant_ids) > 0:
    #     tenants_results = session.execute(
    #         select(EnvInfo).where(EnvInfo.ID.in_(tenant_ids)).order_by(EnvInfo.create_time.desc()))
    #     tenants = tenants_results.scalars().all()
    #     for tenant in tenants:
    #         tenant_info = dict()
    #         is_team_owner = False
    #         team_region_list = get_region_list_by_team_name(session=session, team_name=tenant.tenant_name)
    #         tenant_info["team_id"] = tenant.ID
    #         tenant_info["team_name"] = tenant.tenant_name
    #         tenant_info["team_alias"] = tenant.tenant_alias
    #         tenant_info["limit_memory"] = tenant.limit_memory
    #         tenant_info["pay_level"] = tenant.pay_level
    #         tenant_info["region"] = team_region_list
    #         tenant_info["creater"] = tenant.creater
    #         tenant_info["create_time"] = tenant.create_time
    #         tenant_info["namespace"] = tenant.namespace
    #
    #         if tenant.creater == user.user_id:
    #             is_team_owner = True
    #         tenant_info["is_team_owner"] = is_team_owner
    #         tenant_list.append(tenant_info)
    user_detail["teams"] = tenant_list
    result = general_message(200, "Obtain my details to be successful.", "获取我的详情成功", bean=jsonable_encoder(user_detail))

    return JSONResponse(result, status_code=result["code"])
