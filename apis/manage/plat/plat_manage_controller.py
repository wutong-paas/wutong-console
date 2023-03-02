from typing import Any, Optional
from fastapi import APIRouter, Depends
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
async def get_env_memory_config(
        tenant_id: Optional[str] = None,
        env_id: Optional[str] = None,
        project_id: Optional[str] = None,
        app_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    apps = application_service.get_apps_by_plat(session, tenant_id, env_id, project_id, app_name)
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(apps))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.get("/plat/query/envs", response_model=Response, name="平台查询环境")
async def get_env_memory_config(
        tenant_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    if tenant_id:
        envs = env_services.get_envs_by_tenant_id(session, tenant_id)
    else:
        envs = env_services.get_all_envs(session)
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(envs))
    return JSONResponse(result, status_code=status.HTTP_200_OK)
