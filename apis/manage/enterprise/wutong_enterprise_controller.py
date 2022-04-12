import pickle
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select, distinct
from starlette.requests import Request
from starlette.responses import StreamingResponse

from clients.remote_build_client import remote_build_client
from core import deps
from core.enum.enterprise_enum import EnterpriseRolesEnum
from core.utils.perms import ENTERPRISE
from core.utils.reqparse import parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.bcode import ErrEnterpriseNotFound, ErrUserNotFound
from exceptions.exceptions import UserNotExistError, TenantNotExistError, ErrAdminUserDoesNotExist, \
    ErrCannotDelLastAdminUser
from exceptions.main import ServiceHandleException, AbortRequest
from models.market.models import CenterApp
from models.teams import RegionConfig, TeamInfo
from models.teams.enterprise import TeamEnterprise
from models.users.users import Users
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_config_repo import region_config_repo
from repository.teams.team_enterprise_repo import tenant_enterprise_repo
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo
from repository.users.user_role_repo import user_role_repo
from schemas.response import Response
from service.backup_data_service import platform_data_services
from service.enterprise_service import enterprise_services
from service.region_service import EnterpriseConfigService, region_services
from service.team_service import team_services
from service.user_service import user_svc

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/info", response_model=Response, name="查询企业信息")
async def get_enterprise_info(enterprise_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询企业信息
    :param enterprise_id:
    :param session:
    :return:
    """
    enterprise: TeamEnterprise = tenant_enterprise_repo.get_one_by_model(session=session, query_model=TeamEnterprise(
        enterprise_id=enterprise_id))
    enterprise_dict = jsonable_encoder(enterprise)

    if enterprise_dict:
        enterprise_config = EnterpriseConfigService(enterprise_id).initialization_or_get_config(session=session)
        enterprise_dict.update(enterprise_config)
    regions = region_config_repo.list_by_model(session=session, query_model=RegionConfig(enterprise_id=enterprise_id))
    enterprise_dict["disable_install_cluster_log"] = False
    if regions:
        enterprise_dict["disable_install_cluster_log"] = True
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(enterprise_dict))
    return JSONResponse(result, status_code=result["code"])


@router.put("/enterprise/{enterprise_id}/info", response_model=Response, name="修改企业信息")
async def update_enterprise_info(request: Request,
                                 key: Optional[str] = None,
                                 enterprise_id: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session)) -> Any:
    if not key:
        result = general_message(404, "no found config key {0}".format(key), "更新失败")
        return JSONResponse(result, status_code=result["code"])
    form_data = await request.json()
    value = form_data[key]
    if not value:
        result = general_message(404, "no found config value", "更新失败")
        return JSONResponse(result, status_code=result["code"])
    enterprise_config_service = EnterpriseConfigService(enterprise_id)
    key = key.upper()
    if key in enterprise_config_service.base_cfg_keys + enterprise_config_service.cfg_keys:
        try:
            data = enterprise_config_service.update_config(session, key, value)
            result = general_message(200, "success", "更新成功", bean=data)
            return JSONResponse(result, status_code=result["code"])
        except Exception as e:
            logger.error(e)
            raise ServiceHandleException(msg="update enterprise config failed", msg_show="更新失败")
    else:
        result = general_message(404, "no found config key", "更新失败")
        return JSONResponse(result, status_code=result["code"])


@router.delete("/enterprise/{enterprise_id}/info", response_model=Response, name="删除企业信息")
async def delete_enterprise_info(request: Request,
                                 key: Optional[str] = None,
                                 enterprise_id: Optional[str] = None) -> Any:
    if not key:
        result = general_message(404, "no found config key {0}".format(key), "重置失败")
        return JSONResponse(result, status_code=result["code"])
    form_data = await request.form()
    value = form_data[key]
    if not value:
        result = general_message(404, "no found config value", "重置失败")
        return JSONResponse(result, status_code=result["code"])
    enterprise_config_service = EnterpriseConfigService(enterprise_id)
    key = key.upper()
    if key in enterprise_config_service.cfg_keys:
        data = enterprise_config_service.delete_config(key)
        try:
            result = general_message(200, "success", "重置成功", bean=data)
            return JSONResponse(result, status_code=result["code"])
        except Exception as e:
            logger.debug(e)
            raise ServiceHandleException(msg="update enterprise config failed", msg_show="重置失败")
    else:
        result = general_message(404, "can not delete key value", "该配置不可重置")
        return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/myteams", response_model=Response, name="查询我的团队列表")
async def my_teams(name: Optional[str] = None,
                   enterprise_id: Optional[str] = None,
                   session: SessionClass = Depends(deps.get_session),
                   user=Depends(deps.get_current_user)) -> Any:
    tenants = team_services.get_teams_region_by_user_id(session=session, enterprise_id=enterprise_id, user=user,
                                                        name=name)
    result = general_message(200, "team query success", "查询成功", list=jsonable_encoder(tenants))
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/overview", response_model=Response, name="总览-集群信息")
async def overview(enterprise_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    users = user_repo.list_by_model(session=session, query_model=Users(enterprise_id=enterprise_id))
    user_nums = len(users)
    team = (
        session.execute(
            select(TeamInfo).where(TeamInfo.enterprise_id == enterprise_id, TeamInfo.is_active == True).order_by(
                TeamInfo.create_time.desc()))
    ).scalars().all()
    team_nums = len(team)
    shared_app_nums = len(
        (session.execute(
            select(distinct(CenterApp.app_id)).where(CenterApp.enterprise_id == enterprise_id))
        ).scalars().all()
    )
    data = {"shared_apps": shared_app_nums, "total_teams": team_nums, "total_users": user_nums}
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/{enterprise_id}/overview/app", response_model=Response, name="总览-应用信息")
async def overview_app(enterprise_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    usable_regions = region_config_repo.list_by_model(session=session,
                                                      query_model=RegionConfig(enterprise_id=enterprise_id, status="1"))
    if not usable_regions:
        result = general_message(404, "no found regions", "查询成功")
        return JSONResponse(result, status_code=200)
    data = enterprise_services.get_enterprise_runing_service(session=session, enterprise_id=enterprise_id,
                                                             regions=usable_regions)
    result = general_message(200, "success", "查询成功", bean=data)
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/overview/team", response_model=Response, name="总览-团队信息")
async def overview_team(enterprise_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user)) -> Any:
    new_join_team = []
    request_join_team = []
    try:
        tenants = enterprise_repo.get_enterprise_user_teams(session, enterprise_id, user.user_id)
        join_tenants = enterprise_repo.get_enterprise_user_join_teams(session, enterprise_id, user.user_id)
        active_tenants = enterprise_repo.get_enterprise_user_active_teams(session, enterprise_id, user.user_id)
        request_tenants = enterprise_repo.get_enterprise_user_request_join(session, enterprise_id, user.user_id)
        if tenants:
            for tenant in tenants[:3]:
                region_name_list = team_repo.get_team_region_names(session, tenant.tenant_id)
                user_role_list = user_role_repo.get_user_roles(
                    session=session, kind="team", kind_id=tenant.tenant_id, user=user)
                roles = [x["role_name"] for x in user_role_list["roles"]]
                if tenant.creater == user.user_id:
                    roles.append("owner")
                owner = user_repo.get_by_primary_key(session=session, primary_key=tenant.creater)

                if len(region_name_list) > 0:
                    team_item = {
                        "team_name": tenant.tenant_name,
                        "team_alias": tenant.tenant_alias,
                        "team_id": tenant.tenant_id,
                        "create_time": tenant.create_time,
                        "region": region_name_list[0],  # first region is default
                        "region_list": region_name_list,
                        "enterprise_id": tenant.enterprise_id,
                        "owner": tenant.creater,
                        "owner_name": (owner.get_name() if owner else None),
                        "roles": roles,
                        "is_pass": True,
                    }
                    new_join_team.append(team_item)
        if join_tenants:
            for tenant in join_tenants:
                region_name_list = team_repo.get_team_region_names(session, tenant.team_id)
                tenant_info = team_repo.get_team_by_team_id(session, tenant.team_id)
                try:
                    user = user_repo.get_by_primary_key(session=session, primary_key=tenant_info.creater)
                    if not user:
                        raise UserNotExistError("用户{}不存在".format(tenant.creater))
                    nick_name = user.nick_name
                except UserNotExistError:
                    nick_name = None
                if len(region_name_list) > 0:
                    team_item = {
                        "team_name": tenant.team_name,
                        "team_alias": tenant.team_alias,
                        "team_id": tenant.team_id,
                        "create_time": tenant_info.create_time,
                        "region": region_name_list[0],
                        "region_list": region_name_list,
                        "enterprise_id": tenant_info.enterprise_id,
                        "owner": tenant_info.creater,
                        "owner_name": nick_name,
                        "role": None,
                        "is_pass": tenant.is_pass,
                    }
                    new_join_team.append(team_item)
        if request_tenants:
            for request_tenant in request_tenants:
                region_name_list = team_repo.get_team_region_names(session, request_tenant.team_id)
                tenant_info = team_repo.get_one_by_model(session=session,
                                                         query_model=TeamInfo(tenant_id=request_tenant.team_id))
                if not tenant_info:
                    raise TenantNotExistError
                try:
                    user = user_repo.get_by_primary_key(session=session, primary_key=tenant_info.creater)
                    if not user:
                        raise UserNotExistError("用户{}不存在".format(tenant_info.creater))
                    nick_name = user.nick_name
                except UserNotExistError:
                    nick_name = None
                if len(region_name_list) > 0:
                    team_item = {
                        "team_name": request_tenant.team_name,
                        "team_alias": request_tenant.team_alias,
                        "team_id": request_tenant.team_id,
                        "apply_time": request_tenant.apply_time,
                        "user_id": request_tenant.user_id,
                        "user_name": request_tenant.user_name,
                        "region": region_name_list[0],
                        "region_list": region_name_list,
                        "enterprise_id": enterprise_id,
                        "owner": tenant_info.creater,
                        "owner_name": nick_name,
                        "role": "viewer",
                        "is_pass": request_tenant.is_pass,
                    }
                    request_join_team.append(team_item)
        data = {
            "active_teams": active_tenants,
            "new_join_team": new_join_team,
            "request_join_team": request_join_team,
        }
        result = general_message(200, "success", None, bean=jsonable_encoder(data))
    except Exception as e:
        logger.exception(e)
        code = 400
        result = general_message(code, "failed", "请求失败")
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/monitor", response_model=Response, name="集群监控信息")
async def monitor(enterprise_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    usable_regions = region_config_repo.list_by_model(session=session,
                                                      query_model=RegionConfig(enterprise_id=enterprise_id, status="1"))
    region_memory_total = 0
    region_memory_used = 0
    region_cpu_total = 0
    region_cpu_used = 0
    if not usable_regions:
        result = general_message(404, "no found", None)
        return JSONResponse(result, status_code=200)
    region_num = len(usable_regions)
    for region in usable_regions:
        try:
            res, body = remote_build_client.get_region_resources(session, enterprise_id, region=region.region_name)
            if res.get("status") == 200:
                region_memory_total += body["bean"]["cap_mem"]
                region_memory_used += body["bean"]["req_mem"]
                region_cpu_total += body["bean"]["cap_cpu"]
                region_cpu_used += body["bean"]["req_cpu"]
        except Exception as e:
            logger.debug(e)
            continue
    data = {
        "total_regions": region_num,
        "memory": {
            "used": region_memory_used,
            "total": region_memory_total
        },
        "cpu": {
            "used": region_cpu_used,
            "total": region_cpu_total
        }
    }
    result = general_message(200, "success", None, bean=data)
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/regions", response_model=Response, name="获取企业列表")
async def regions(status: Optional[str] = "", check_status: Optional[str] = "",
                  enterprise_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    data = region_services.get_enterprise_regions(session=session, enterprise_id=enterprise_id, level="safe",
                                                  status=status,
                                                  check_status=check_status)
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(data))
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/teams", response_model=Response, name="获取企业团队列表")
async def get_enterprise_teams(request: Request,
                               enterprise_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               user=Depends(deps.get_current_user)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    name = request.query_params.get("name", None)
    teams, total = team_services.get_enterprise_teams(session=session, enterprise_id=enterprise_id, query=name,
                                                      page=page,
                                                      page_size=page_size, user=user)
    data = {"total_count": total, "page": page, "page_size": page_size, "list": teams}
    return JSONResponse(general_message(200, "success", None, bean=jsonable_encoder(data)), status_code=200)


@router.post("/enterprise/admin/join-team", response_model=Response, name="企业管理员添加用户")
async def enterprise_admin_join_team(request: Request,
                                     session: SessionClass = Depends(deps.get_session),
                                     user=Depends(deps.get_current_user)) -> Any:
    nojoin_user_ids = []
    team_name = (await request.json()).get("team_name")
    team = team_services.get_enterprise_tenant_by_tenant_name(session=session, enterprise_id=user.enterprise_id,
                                                              tenant_name=team_name)
    if not team:
        raise ServiceHandleException(msg="no found team", msg_show="团队不存在", status_code=404)
    request.app.state.redis.set("team_%s" % team_name, pickle.dumps(team), 24 * 60 * 60)

    users = team_services.get_team_users(session=session, team=team)
    if users:
        nojoin_user_ids = [user.user_id for user in users]
    if user.user_id not in nojoin_user_ids:
        team_services.add_user_role_to_team(session=session, tenant=team, user_ids=[user.user_id], role_ids=[])
    return general_message(200, "success", None)


@router.get("/enterprise/{enterprise_id}/admin/user", response_model=Response, name="获取企业管理员列表")
async def get_enterprise_admin_list(enterprise_id: Optional[str] = None,
                                    session: SessionClass = Depends(deps.get_session)) -> Any:
    users = user_svc.get_admin_users(session, enterprise_id)
    result = general_message(200, "success", "获取企业管理员列表成功", list=jsonable_encoder(users))
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/{enterprise_id}/admin/roles", response_model=Response, name="获取企业管理员角色")
async def get_enterprise_admin_roles() -> Any:
    roles = list()
    for role in ENTERPRISE:
        roles.append(role)
    result = general_message(200, "success", None, list=roles)
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/{enterprise_id}/admin/user", response_model=Response, name="企业添加管理员")
async def add_enterprise_admin(
        request: Request,
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    roles = await parse_item(request, "roles", required=True, error="at least one role needs to be specified")
    if not set(roles).issubset(EnterpriseRolesEnum.names()):
        raise AbortRequest("invalid roles", msg_show="角色不正确")

    data = await request.json()
    user_id = data.get("user_id")
    if user_id == user.user_id:
        raise AbortRequest("cannot edit your own role", msg_show="不可操作自己的角色")

    ent = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    if ent is None:
        raise ErrEnterpriseNotFound

    user = user_repo.get_user_by_user_id(session, user_id)
    if not user:
        raise ErrUserNotFound

    user_svc.create_admin_user(session, user, ent, roles)
    return JSONResponse(general_message(201, "success", None), status_code=201)


@router.delete("/enterprise/{enterprise_id}/admin/user/{user_id}", response_model=Response, name="删除企业管理员")
async def delete_enterprise_admin(user_id: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  user=Depends(deps.get_current_user)) -> Any:
    if str(user.user_id) == user_id:
        result = general_message(400, "fail", "不可删除自己")
        return JSONResponse(result, status_code=400)
    try:
        user_svc.delete_admin_user(session, user_id)
        result = general_message(200, "success", None)
        return JSONResponse(result, 200)
    except ErrAdminUserDoesNotExist as e:
        logger.debug(e)
        result = general_message(400, "用户'{}'不是企业管理员".format(user_id), None)
        return JSONResponse(result, 400)
    except ErrCannotDelLastAdminUser as e:
        logger.debug(e)
        result = general_message(400, "fail", None)
        return JSONResponse(result, 400)


@router.put("/enterprise/{enterprise_id}/admin/user/{user_id}", response_model=Response, name="修改企业管理员")
async def modify_enterprise_admin(request: Request,
                                  enterprise_id: Optional[str] = None,
                                  user_id: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  user=Depends(deps.get_current_user)) -> Any:
    roles = await parse_item(request, "roles", required=True, error="at least one role needs to be specified")
    if not set(roles).issubset(EnterpriseRolesEnum.names()):
        raise AbortRequest("invalid roles", msg_show="角色不正确")
    if str(user.user_id) == user_id:
        raise AbortRequest("changing your role is not allowed", "不可修改自己的角色")
    user_svc.update_roles(session, enterprise_id, user_id, roles)
    result = general_message(200, "success", None)
    return JSONResponse(result, 200)


@router.get("/enterprise/{enterprise_id}/backups", response_model=Response, name="获取备份信息")
async def get_enterprise_backup_info() -> Any:
    backups = platform_data_services.list_backups()
    result = general_message(200, "success", "数据上传成功", list=backups)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/backups", response_model=Response, name="增加备份")
async def add_enterprise_backup() -> Any:
    platform_data_services.create_backup()
    result = general_message(200, "success", "备份成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/enterprise/{enterprise_id}/backups", response_model=Response, name="删除备份")
async def delete_enterprise_backup(request: Request) -> Any:
    data = await request.json()
    name = data.get("name")
    if not name:
        result = general_message(200, "backup file can not be empty", "备份文件名称不能为空")
    else:
        platform_data_services.remove_backup(name)
        result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/upload-backups", response_model=Response, name="导入备份")
async def import_enterprise_backup(request: Request) -> Any:
    form_data = await request.form()
    if not form_data or not form_data.get('file'):
        return JSONResponse(general_message(400, "param error", "请指定需要上传的文件"), status_code=400)

    upload_file = form_data.get('file')
    suffix = upload_file.filename.split('.')[-1]
    if suffix != "gz":
        return JSONResponse(general_message(400, "param error", "请上传以 tar.gz 结尾的数据备份文件"), status_code=400)
    # upload file
    await platform_data_services.upload_file(upload_file)
    result = general_message(200, "success", "数据上传成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/backups/{backup_name}", response_model=Response, name="下载备份")
async def down_enterprise_backup(backup_name: Optional[str] = None) -> Any:
    response = StreamingResponse(platform_data_services.download_file(backup_name))
    return response
    # ===================================================================
    # file_path = os.path.join(settings.DATA_DIR, "backups", backup_name)
    # return FileResponse(file_path)


@router.post("/enterprise/{enterprise_id}/recover", response_model=Response, name="恢复备份")
async def recovery_enterprise_backup(request: Request,
                                     user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    name = data.get("name")
    password = data.get("password")
    if not user.check_password(password):
        return JSONResponse(general_message(400, "param error", "输入密码不正确"), status_code=400)
    if not name:
        result = general_message(200, "backup file can not be empty", "备份文件名称不能为空")
    else:
        platform_data_services.recover_platform_data(name)
        result = general_message(200, "success", "恢复成功")
    return JSONResponse(result, status_code=result["code"])
