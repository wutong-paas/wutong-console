from typing import Optional, Any
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
from starlette import status
from core import deps
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from models.region.models import EnvRegionInfo
from models.teams import PermRelTenant, EnvInfo, UserMessage
from models.teams.enterprise import TeamEnterprise
from repository.application.application_repo import application_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.env_service import env_services

router = APIRouter()


@router.get("/enterprises", response_model=Response, name="查询企业列表")
async def get_enterprise_list(session: SessionClass = Depends(deps.get_session),
                              user=Depends(deps.get_current_user)) -> Any:
    result_tenants_ids = session.execute(
        select(PermRelTenant.tenant_id).where(PermRelTenant.user_id == user.user_id)
    )
    tenants_ids = result_tenants_ids.scalars().all()
    result_team = session.execute(
        select(EnvInfo.env_id).where(EnvInfo.ID.in_(tenants_ids)).order_by(EnvInfo.create_time.desc())
    )
    tenant_ids = result_team.scalars().all()

    results_enterprise_ids = session.execute(
        select(EnvRegionInfo.enterprise_id).where(EnvRegionInfo.env_id.in_(tenant_ids))
    )
    enterprise_ids = results_enterprise_ids.scalars().all()
    enterprise_ids.append(user.enterprise_id)
    results = session.execute(
        select(TeamEnterprise).where(TeamEnterprise.enterprise_id.in_(enterprise_ids))
    )
    enterprises = results.scalars().all()
    if enterprises:
        enterprises_list = []
        for enterprise in enterprises:
            enterprises_list.append({
                "ID": enterprise.ID,
                "enterprise_alias": enterprise.enterprise_alias,
                "enterprise_name": enterprise.enterprise_name,
                "is_active": enterprise.is_active,
                "enterprise_id": enterprise.enterprise_id,
                "enterprise_token": enterprise.enterprise_token,
                "create_time": enterprise.create_time,
            })
        data = general_message(200, "success", "查询成功", list=enterprises_list)
        return data
    else:
        return JSONResponse(general_message(404, "failure", "未找到企业"), status_code=404)


@router.get("/enterprise/{enterprise_id}/apps", response_model=Response, name="查询应用视图")
async def get_app_views(request: Request,
                        enterprise_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user)) -> Any:
    data = []
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    enterprise_apps, apps_count = enterprise_repo.get_enterprise_app_list(session, enterprise_id,
                                                                          user, page, page_size)
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


@router.get("/enterprise/{enterprise_id}/apps/{app_id}/components", response_model=Response, name="查询组件视图")
async def get_components_views(request: Request,
                               app_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    data = []
    count = 0
    app = application_repo.get_group_by_id(session, app_id)
    if app:
        try:
            tenant = env_services.get_team_by_team_id(session, app.tenant_id)
            tenant_name = tenant.tenant_name
        except Exception:
            tenant_name = None
        services, count = enterprise_repo.get_enterprise_app_component_list(session, app_id, page, page_size)
        if services:
            for service in services:
                data.append({
                    "service_alias": service.service_alias,
                    "service_id": service.service_id,
                    "tenant_id": app.tenant_id,
                    "tenant_name": tenant_name,
                    "region_name": service.service_region,
                    "service_cname": service.service_cname,
                    "service_key": service.service_key,
                })
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(data), total_count=count, page=page,
                             page_size=page_size)
    return JSONResponse(result, status_code=status.HTTP_200_OK)
