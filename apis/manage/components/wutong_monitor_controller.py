from typing import Any, Optional
from urllib.parse import urlencode
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.promql_service import promql_service

router = APIRouter()


def get_sufix_path(request, query=""):
    """获取get请求参数路径部分的数据"""
    full_url = request.url.path
    index = full_url.find("?")
    sufix = ""
    if index != -1:
        sufix = full_url[index:]

    if query:
        params = {
            "query": query,
            "start": request.query_params.get("start"),
            "end": request.query_params.get("end"),
            "step": request.query_params.get("step"),
        }
        sufix = urlencode(params)

    return sufix


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/monitor/query", response_model=Response,
            name="查询组件监控信息")
async def get_monitor_info(request: Request,
                           env_id: Optional[str] = None,
                           serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    """
     监控信息查询
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
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        query = request.query_params.get("query", "")
        service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
        if "service_id" not in query:
            query = promql_service.add_or_update_label(service.service_id, query)
        sufix = "?" + get_sufix_path(request, query)
        res, body = remote_build_client.get_query_data(session, service.service_region, env, sufix)
        result = general_message(200, "success", "查询成功", bean=body["data"])
    except Exception as e:
        logger.debug(e)
        result = general_message(200, "success", "查询成功", bean=[])
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/monitor/query_range", response_model=Response,
            name="查询组件监控信息范围")
async def get_monitor_info(request: Request,
                           env_id: Optional[str] = None,
                           serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    """
     监控信息范围查询
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
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        query = request.query_params.get("query", "")
        disable_auto_label = request.query_params.get("disable_auto_label", "false")
        service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
        if "service_id" not in query and disable_auto_label == "false":
            query = promql_service.add_or_update_label(service.service_id, query)
        sufix = "?" + get_sufix_path(request, query)
        res, body = remote_build_client.get_query_range_data(session, service.service_region, env, sufix)
        result = general_message(200, "success", "查询成功", bean=body["data"])
    except Exception as e:
        logger.exception(e)
        result = general_message(200, "success", "查询成功", bean=[])
    return JSONResponse(result, status_code=result["code"])
