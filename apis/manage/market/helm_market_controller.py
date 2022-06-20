import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.enum.component_enum import Kind
from core.utils.return_message import general_message
from database.session import SessionClass
from models.users.users import Users
from schemas.response import Response
from jsonpath import jsonpath

from service.market_app_service import market_app_service

router = APIRouter()


# 获取Helm市场应用列表
@router.get("/teams/{tenant_name}/region/{region_name}/helm/apps", response_model=Response, name="获取Helm市场应用列表")
async def get_helm_apps(
        request: Request,
        tenant_name: Optional[str] = None,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    helm_namespace = data.get("helm_namespace")
    helm_list = remote_component_client.get_helm_chart_apps(session,
                                                            region_name,
                                                            tenant_name,
                                                            {"helm_namespace": helm_namespace})

    return JSONResponse(general_message(200, "success", msg_show="查询成功", list=helm_list), status_code=200)


# 获取Helm市场应用安装
@router.post("/teams/{team_name}/region/{region_name}/helm/install", response_model=Response,
             name="Helm市场应用安装")
async def helm_app_install(
        request: Request,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    helm_namespace = data.get("helm_namespace")
    helm_name = data.get("helm_name")
    group_id = data.get("group_id")
    app_version = data.get("app_version")
    is_deploy = data.get("is_deploy")
    install_from_cloud = data.get("install_from_cloud")
    market_app_service.install_helm_app(session=session,
                                        user=user,
                                        tenant=team,
                                        app_id=group_id,
                                        version=app_version,
                                        region_name=region_name,
                                        is_deploy=is_deploy,
                                        install_from_cloud=install_from_cloud,
                                        helm_name=helm_name,
                                        helm_namespace=helm_namespace)

    return JSONResponse(general_message(200, "success", msg_show="安装成功"), status_code=200)
