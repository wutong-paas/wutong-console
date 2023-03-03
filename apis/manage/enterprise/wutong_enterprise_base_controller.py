from typing import Optional, Any
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette import status
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from schemas.response import Response
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/enterprise/apps", response_model=Response, name="查询应用视图")
async def get_app_views(request: Request,
                        session: SessionClass = Depends(deps.get_session)) -> Any:
    data = []
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    tenant_ids = request.query_params.get("tenant_ids")
    enterprise_apps, apps_count = enterprise_repo.get_enterprise_app_list(session, tenant_ids, page, page_size)
    if enterprise_apps:
        for app in enterprise_apps:
            tenant = env_services.get_team_by_team_id(session, app.tenant_id)
            if not tenant:
                tenant_name = None
            else:
                tenant_name = tenant.tenant_name
            data.append({
                "ID": app.ID,
                "group_name": app.group_name,
                "tenant_id": app.tenant_id,
                "tenant_name": tenant_name,
                "region_name": app.region_name
            })
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(data), total_count=apps_count, page=page,
                             page_size=page_size)
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.get("/enterprise/apps/{app_id}/components", response_model=Response, name="查询组件视图")
async def get_components_views(request: Request,
                               app_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    data = []
    count = 0
    app = application_repo.get_group_by_id(session, app_id)
    if app:
        services, count = enterprise_repo.get_enterprise_app_component_list(session, app_id, page, page_size)
        if services:
            for service in services:
                data.append({
                    "service_alias": service.service_alias,
                    "service_id": service.service_id,
                    "tenant_id": app.tenant_id,
                    "region_name": service.service_region,
                    "service_cname": service.service_cname,
                    "service_key": service.service_key,
                })
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(data), total_count=count, page=page,
                             page_size=page_size)
    return JSONResponse(result, status_code=status.HTTP_200_OK)
