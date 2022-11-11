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
from exceptions.main import ServiceHandleException
from models.region.models import TeamRegionInfo
from models.teams import PermRelTenant, TeamInfo, UserMessage
from models.teams.enterprise import TeamEnterprise
from repository.application.application_repo import application_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from repository.teams.team_applicants_repo import apply_repo
from repository.teams.team_repo import team_repo
from schemas.response import Response
from service.apply_service import apply_service
from service.platform_config_service import platform_config_service
from service.team_service import team_services

router = APIRouter()


# 用户加入团队，给管理员发送站内信
def send_user_message_to_tenantadmin(session, admins, team_name, nick_name):
    tenant = team_repo.get_tenant_by_tenant_name(session=session, team_name=team_name)
    logger.debug('---------admin---------->{0}'.format(admins))
    for admin in admins:
        message_id = make_uuid()
        content = '{0}用户申请加入{1}团队'.format(nick_name, tenant.tenant_alias)
        ums = UserMessage(
            message_id=message_id, receiver_id=admin.user_id, content=content, msg_type="warn", title="团队加入信息")
        session.add(ums)


@router.get("/enterprises", response_model=Response, name="查询企业列表")
async def get_enterprise_list(session: SessionClass = Depends(deps.get_session),
                              user=Depends(deps.get_current_user)) -> Any:
    result_tenants_ids = session.execute(
        select(PermRelTenant.tenant_id).where(PermRelTenant.user_id == user.user_id)
    )
    tenants_ids = result_tenants_ids.scalars().all()
    result_team = session.execute(
        select(TeamInfo.tenant_id).where(TeamInfo.ID.in_(tenants_ids)).order_by(TeamInfo.create_time.desc())
    )
    tenant_ids = result_team.scalars().all()

    results_enterprise_ids = session.execute(
        select(TeamRegionInfo.enterprise_id).where(TeamRegionInfo.tenant_id.in_(tenant_ids))
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


@router.get("/enterprise/registerstatus", response_model=Response, name="查询用户注册开启状态")
async def get_register_status(session: SessionClass = Depends(deps.get_session)) -> Any:
    register_config = platform_config_service.get_config_by_key(session, "IS_REGIST")
    if register_config.enable is False:
        return JSONResponse(general_message(200, "status is close", "注册关闭状态", bean={"is_regist": False}),
                            status_code=200)
    else:
        return JSONResponse(general_message(200, "status is open", "注册开启状态", bean={"is_regist": True}), status_code=200)


@router.put("/enterprise/registerstatus", response_model=Response, name="修改用户注册开启状态")
async def update_register_status(request: Request,
                                 session: SessionClass = Depends(deps.get_session),
                                 user=Depends(deps.get_current_user)) -> Any:
    admin = enterprise_user_perm_repo.is_admin(session, user_id=user.user_id, eid=user.enterprise_id)
    data = await request.json()
    is_regist = data.get("is_regist")
    if admin:
        if is_regist is False:
            # 修改全局配置
            platform_config_service.update_config(session, "IS_REGIST", {"enable": False, "value": None})

            return JSONResponse(general_message(200, "close register", "关闭注册"), status_code=200)
        else:
            platform_config_service.update_config(session, "IS_REGIST", {"enable": True, "value": None})
            return JSONResponse(general_message(200, "open register", "开启注册"), status_code=200)
    else:
        return JSONResponse(general_message(400, "no jurisdiction", "没有权限"), status_code=400)


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
            tenant = team_services.get_team_by_team_id(session, app.tenant_id)
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
            tenant = team_services.get_team_by_team_id(session, app.tenant_id)
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


@router.get("/enterprise/{enterprise_id}/jointeams", response_model=Response, name="查询可加入的团队")
async def get_join_teams(enterprise_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user)) -> Any:
    """指定用户可以加入哪些团队"""
    tenants = team_repo.get_tenants_by_user_id(session=session, user_id=user.user_id)
    # 已加入的团队
    team_name_list = [tenant.tenant_name for tenant in tenants]
    team_list = team_repo.get_teams_by_enterprise_id(session, enterprise_id)
    apply_team = apply_repo.get_append_applicants_team(session=session, user_id=user.user_id)
    # 已申请过的团队
    applied_team = [team_name.team_name for team_name in apply_team]
    can_join_team_list = []
    for join_team in team_list:
        if join_team.tenant_name not in applied_team and join_team.tenant_name not in team_name_list:
            can_join_team_list.append(join_team.tenant_name)
    join_list = [{
        "team_name": j_team.tenant_name,
        "team_alias": j_team.tenant_alias,
        "team_id": j_team.tenant_id
    } for j_team in team_repo.get_team_by_team_names(session, can_join_team_list)]
    result = general_message(200, "success", "查询成功", list=jsonable_encoder(join_list))
    return JSONResponse(result, status_code=result["code"])


@router.post("/user/applicants/join", response_model=Response, name="指定用户加入指定团队")
async def join_team(request: Request,
                    session: SessionClass = Depends(deps.get_session),
                    user=Depends(deps.get_current_user)) -> Any:
    """指定用户加入指定团队"""
    try:
        data = await request.json()
        user_id = user.user_id
        team_name = data.get("team_name")
        tenant = team_repo.get_one_by_model(session=session, query_model=TeamInfo(tenant_name=team_name))
        info = apply_service.create_applicants(session=session, user_id=user_id, team_name=team_name)
        result = general_message(200, "apply success", "申请加入")
        if info:
            admins = team_repo.get_tenant_admin_by_tenant_id(session, tenant)
            send_user_message_to_tenantadmin(session=session, admins=admins, team_name=team_name,
                                             nick_name=user.get_name())
        return JSONResponse(result, status_code=result["code"])
    except ServiceHandleException as e:
        JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.put("/user/applicants/join", response_model=Response, name="撤销申请")
async def cancellation_application(request: Request,
                                   session: SessionClass = Depends(deps.get_session),
                                   user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    team_name = data.get("team_name")
    apply_service.delete_applicants(session=session, user_id=user.user_id, team_name=team_name)
    result = general_message(200, "success", None)
    return JSONResponse(result, status_code=200)
