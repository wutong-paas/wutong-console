from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette import status
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from schemas.response import Response
from service.application_service import application_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/plat/query/apps", response_model=Response, name="平台查询应用")
async def get_plat_apps(
        current: int = Query(default=1, ge=1, le=9999),
        size: int = Query(default=10, ge=-1, le=999),
        team_code: Optional[str] = None,
        env_id: Optional[str] = None,
        project_id: Optional[str] = None,
        app_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    apps = application_service.get_apps_by_plat(session, team_code, env_id, project_id, app_name)
    start = (current - 1) * size
    end = current * size
    if start >= len(apps):
        start = len(apps) - 1
        end = len(apps) - 1
    result = general_message("0", "success", "获取成功", list=jsonable_encoder(apps[start:end]), total=len(apps))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.get("/plat/query/envs", response_model=Response, name="平台查询环境")
async def get_plat_envs(
        tenant_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    if tenant_id:
        envs = env_services.get_envs_by_tenant_id(session, tenant_id)
    else:
        envs = env_services.get_all_envs(session)
    result = general_message("0", "success", "获取成功", list=jsonable_encoder(envs))
    return JSONResponse(result, status_code=status.HTTP_200_OK)
