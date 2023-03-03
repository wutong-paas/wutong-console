from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.env_repo import env_repo
from schemas.response import Response
import subprocess

from service.market_app_service import market_app_service

router = APIRouter()


# 获取Helm市场应用列表
@router.get("/teams/{tenant_name}/env/{env_id}/region/{region_name}/helm/apps", response_model=Response, name="获取Helm市场应用列表")
async def get_helm_apps(
        request: Request,
        env_id: Optional[str] = None,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    helm_namespace = data.get("helm_namespace")
    helm_list = remote_component_client.get_helm_chart_apps(session,
                                                            region_name,
                                                            env,
                                                            {"helm_namespace": helm_namespace})

    return JSONResponse(general_message("0", "success", msg_show="查询成功", list=helm_list), status_code=200)

