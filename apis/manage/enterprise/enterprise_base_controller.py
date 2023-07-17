import json
import os
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_actions.app_deploy import RegionApiBaseHttpClient
from service.region_service import region_services
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/config/info", response_model=Response, name="获取集群配置信息")
async def get_info(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取集群配置信息
    :return:
    """
    data = {}
    data["is_disable_logout"] = os.getenv('IS_DISABLE_LOGOUT', False)
    data["is_offline"] = os.getenv('IS_OFFLINE', False)
    data["login_timeout"] = 15
    result = general_message("0", "success", "查询成功", bean=data, initialize_info=[])
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/regions/{region_id}", response_model=Response, name="查询集群配置信息")
async def get_region_config(
        region_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    data = region_services.get_enterprise_region(session, region_id, check_status=False)
    result = general_message("0", "success", "获取成功", bean=data)
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.put("/enterprise/regions/{region_name}/mavensettings/{name}", response_model=Response,
            name="修改Maven配置")
async def update_maven_settings(
        request: Request,
        region_name: Optional[str] = None,
        name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        data = await request.json()
        res, body = remote_build_client.update_maven_setting(session, region_name, name, data)
        result = general_message("0", 'update success', '修改成功', bean=body.get("bean"))
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


@router.delete("/enterprise/regions/{region_name}/mavensettings/{name}", response_model=Response,
               name="删除Maven配置")
async def delete_maven_settings(
        region_name: Optional[str] = None,
        name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        res, body = remote_build_client.delete_maven_setting(session, region_name, name)
        result = general_message("0", 'delete success', '删除成功', bean=body.get("bean"))
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


@router.post("/enterprise/regions/{region_name}/mavensettings", response_model=Response,
             name="添加Maven配置")
async def add_maven_settings(
        request: Request,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        data = await request.json()
        res, body = remote_build_client.add_maven_setting(session, region_name, data)
        result = general_message("0", 'query success', '添加成功', bean=body.get("bean"))
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


@router.get("/enterprise/regions/{region_name}/mavensettings", response_model=Response,
            name="获取构建源手动配置项")
async def get_mavens_ettings(
        request: Request,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    onlyname = request.query_params.get("onlyname", True)
    res, body = remote_build_client.list_maven_settings(session, region_name)
    redata = body.get("list")
    if redata and isinstance(redata, list) and (onlyname is True or onlyname == "true"):
        newdata = []
        for setting in redata:
            newdata.append({"name": setting["name"], "is_default": setting["is_default"]})
        redata = newdata
    result = general_message("0", 'query success', '数据中心Maven获取成功', list=redata)
    return JSONResponse(result, status_code=200)


@router.put("/enterprise/regions/{region_id}", response_model=Response, name="修改集群配置信息")
async def modify_region_config(request: Request,
                               region_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    region = region_services.update_enterprise_region(session, region_id, data)
    result = general_message("0", "success", "更新成功", bean=region)
    return JSONResponse(result, status_code=200)


@router.delete("/enterprise/regions/{region_id}", response_model=Response, name="删除集群")
async def delete_region(
        region_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    region = region_repo.get_region_by_region_id(session, region_id)
    if not region:
        raise ServiceHandleException(status_code=404, msg="集群已不存在")
    region_repo.del_by_enterprise_region_id(session, region_id)
    result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/regions/{region_id}/tenants/{tenant_name}/env/{env_id}/limit",
             response_model=Response,
             name="设置环境内存限额")
async def set_env_memory_limit(request: Request,
                               region_id: Optional[str] = None,
                               env_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    env_services.set_tenant_env_memory_limit(session, region_id, env, data)
    return JSONResponse({}, status_code=status.HTTP_200_OK)


@router.post("/enterprise/regions", response_model=Response, name="集群配置")
async def set_region_config(request: Request,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    token = data.get("token")
    region_name = data.get("region_name")
    region_alias = data.get("region_alias")
    desc = data.get("desc")
    region_type = json.dumps(data.get("region_type", []))
    region_data = region_services.parse_token(token, region_name, region_alias, region_type)
    region_data["desc"] = desc
    region_data["provider"] = data.get("provider", "")
    region_data["provider_cluster_id"] = data.get("provider_cluster_id", "")
    region_data["status"] = "1"
    region = region_services.add_region(session, region_data, user)
    if region:
        data = region_services.get_enterprise_region(session, region.region_id, check_status=False)
        result = general_message("0", "success", "创建成功", bean=data)
        return JSONResponse(result, status_code=status.HTTP_200_OK)
    else:
        result = general_message(500, "failed", "创建失败")
        return JSONResponse(result, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/enterprise/regions/{region_id}/tenants/envs", response_model=Response, name="获取环境内存配置信息")
async def get_team_memory_config(request: Request,
                                 region_id: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session)) -> Any:
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("pageSize", 10)
    team_code = request.query_params.get("team_code", None)
    env_id = request.query_params.get("env_id", None)
    envs, total = env_repo.get_envs_list_by_region(session, region_id, team_code, env_id, page, page_size)
    result = general_message(
        "0", "success", "获取成功", bean={
            "envs": envs,
            "total": total,
        })
    return JSONResponse(result, status_code=status.HTTP_200_OK)
