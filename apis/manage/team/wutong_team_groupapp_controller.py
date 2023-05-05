from typing import Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import Params, paginate
from loguru import logger
from common.api_base_http_client import ApiBaseHttpClient
from core import deps
from core.utils.constants import StorageUnit
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.application.app_migration_repo import migrate_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.backup_service import groupapp_backup_service
from service.groupapps_migrate_service import migrate_service
from service.groupcopy_service import groupapp_copy_service
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/groupapp/backup", response_model=Response, name="查询备份信息")
async def get_backup_info(request: Request,
                          session: SessionClass = Depends(deps.get_session),
                          env=Depends(deps.get_current_team_env)) -> Any:
    """
    查询备份信息
    """
    group_id = request.query_params.get("group_id", None)
    if not group_id:
        return JSONResponse(general_message(400, "group id is not found", "请指定需要查询的组"), status_code=400)
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name

    backups = groupapp_backup_service.get_group_back_up_info(session=session, tenant_env=env, region=region_name,
                                                             group_id=group_id)
    params = Params(page=page, size=page_size)
    event_paginator = paginate(backups, params)
    total = event_paginator.total
    backup_records = event_paginator.items
    bean = {"is_configed": False}
    result = general_message(
        "0", "success", "查询成功", bean=jsonable_encoder(bean),
        list=[jsonable_encoder(backup) for backup in backup_records], total=total)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/backup", response_model=Response, name="应用备份")
async def get_backup_info(request: Request,
                          env_id: Optional[str] = None,
                          group_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user)) -> Any:
    """
    应用备份
    ---
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if not group_id:
        return JSONResponse(general_message(400, "group id is null", "请选择需要备份的组"), status_code=400)
    data = await request.json()
    note = data.get("note", None)
    if not note:
        return JSONResponse(general_message(400, "note is null", "请填写备份信息"), status_code=400)
    mode = data.get("mode", None)
    if not mode:
        return JSONResponse(general_message(400, "mode is null", "请选择备份模式"), status_code=400)

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    force = data.get("force", False)
    if not force:
        # state service can't backup while it is running
        code, running_state_services = groupapp_backup_service.check_backup_condition(session=session,
                                                                                      tenant_env=env,
                                                                                      region=region_name,
                                                                                      group_id=group_id)
        if running_state_services:
            return JSONResponse(
                general_message(
                    code=4121, msg="state service is running", msg_show="有状态组件未关闭", list=running_state_services),
                status_code=412)
        # if service use custom service, can't backup
        use_custom_svc = groupapp_backup_service.check_backup_app_used_custom_volume(session=session, group_id=group_id)
        if use_custom_svc:
            logger.info("use custom volume: {}".format(use_custom_svc))
            return JSONResponse(
                general_message(code=4122, msg="use custom volume", msg_show="组件使用了自定义存储", list=use_custom_svc),
                status_code=412)

    try:
        back_up_record = groupapp_backup_service.backup_group_apps(session=session, tenant_env=env, user=user,
                                                                   region_name=region_name, group_id=group_id,
                                                                   mode=mode,
                                                                   note=note, force=force)
        bean = jsonable_encoder(back_up_record)
        result = general_message("0", "success", "操作成功，正在备份中", bean=bean)
    except ServiceHandleException as e:
        code = 500
        result = general_message(code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/backup", response_model=Response,
            name="根据应用备份ID查询备份状态")
async def backup_app(request: Request,
                     env_id: Optional[str] = None,
                     group_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    根据应用备份ID查询备份状态
    """
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        if not group_id:
            return JSONResponse(general_message(400, "group id is null", "请选择需要备份的组"), status_code=400)
        backup_id = request.query_params.get("backup_id", None)
        if not backup_id:
            return JSONResponse(general_message(400, "backup id is null", "请指明当前组的具体备份项"), status_code=400)
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        code, msg, backup_record = groupapp_backup_service.get_groupapp_backup_status_by_backup_id(session=session,
                                                                                                   tenant_env=env,
                                                                                                   region=response_region,
                                                                                                   backup_id=backup_id)
        if code != 200:
            return JSONResponse(general_message(code, "get backup status error", msg), status_code=code)
        bean = jsonable_encoder(backup_record)
        bean.pop("backup_server_info")

        result = general_message("0", "success", "查询成功", bean=bean)

    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/backup", response_model=Response, name="删除应用备份")
async def delete_backup_app(request: Request,
                            env_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    backup_id = data.get("backup_id", None)
    if not backup_id:
        return JSONResponse(general_message(400, "backup id is null", "请指明当前组的具体备份项"), status_code=400)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    groupapp_backup_service.delete_group_backup_by_backup_id(session=session, tenant_env=env, region=response_region,
                                                             backup_id=backup_id)
    result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/migrate/record", response_model=Response,
            name="查询当前用户是否有未完成的恢复和迁移")
async def get_migrate_record(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询当前用户是否有未完成的恢复和迁移
    ---
        name: group_id
        description: 应用id
        required: true
        type: string
        paramType: path

    """
    group_uuid = request.query_params.get("group_uuid", None)
    if not group_uuid:
        return JSONResponse(general_message(400, "parameters are missing", "参数缺失"), status_code=400)
    unfinished_migrate_records = migrate_repo.get_user_unfinished_migrate_record(session=session, group_uuid=group_uuid)
    is_finished = True
    data = None
    if unfinished_migrate_records:
        r = unfinished_migrate_records[0]
        data = {
            "status": r.status,
            "event_id": r.event_id,
            "migrate_type": r.migrate_type,
            "restore_id": r.restore_id,
            "backup_id": r.backup_id,
            "group_id": r.group_id,
        }
        is_finished = False

    bean = {"is_finished": is_finished, "data": data}
    return JSONResponse(general_message("0", "success", "查询成功", bean=bean), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/migrate", response_model=Response, name="应用迁移")
async def app_migrate(request: Request,
                      env_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      user=Depends(deps.get_current_user)) -> Any:
    """
    应用迁移
    ---
    """
    data = await request.json()
    migrate_region = data.get("region", None)
    migrate_env_id = data.get("migrate_env_id", None)
    backup_id = data.get("backup_id", None)
    migrate_type = data.get("migrate_type", "migrate")
    event_id = data.get("event_id", None)
    restore_id = data.get("restore_id", None)
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    if not migrate_env_id:
        return JSONResponse(general_message(400, "team is null", "请指明要迁移的环境"), status_code=400)
    migrate_env = env_repo.get_env_by_env_id(session, migrate_env_id)
    if not migrate_env:
        return JSONResponse(general_message(404, "team is not found", "需要迁移的环境不存在"), status_code=404)

    try:
        migrate_record = migrate_service.start_migrate(session=session, user=user, tenant_env=env,
                                                       current_region=response_region, migrate_env=migrate_env,
                                                       migrate_region=migrate_region,
                                                       backup_id=backup_id, migrate_type=migrate_type,
                                                       event_id=event_id,
                                                       restore_id=restore_id)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    result = general_message("0", "success", "操作成功，开始迁移应用", bean=jsonable_encoder(migrate_record))
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/migrate", response_model=Response, name="查询应用迁移状态")
async def get_app_migrate_state(request: Request,
                                env_id: Optional[str] = None,
                                session: SessionClass = Depends(deps.get_session),
                                user=Depends(deps.get_current_user)) -> Any:
    restore_id = request.query_params.get("restore_id", None)
    if not restore_id:
        return JSONResponse(general_message(400, "restore id is null", "请指明查询的备份ID"), status_code=400)

    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    migrate_record = migrate_service.get_and_save_migrate_status(session=session,
                                                                 migrate_env=env,
                                                                 user=user, restore_id=restore_id,
                                                                 current_env_name=env.env_name,
                                                                 current_region=response_region)
    if not migrate_record:
        return JSONResponse(general_message(404, "not found record", "记录不存在"), status_code=404)
    result = general_message("0", "success", "查询成功", bean=jsonable_encoder(migrate_record))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/backup/import", response_model=Response, name="导入备份")
async def set_backup_info(request: Request,
                          env_id: Optional[str] = None,
                          group_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        form_data = await request.form()
        if not group_id:
            return JSONResponse(general_message(400, "group id is null", "请选择需要导出备份的组"), status_code=400)
        if not form_data or not form_data.get('file'):
            return JSONResponse(general_message(400, "param error", "请指定需要导入的备份信息"), status_code=400)
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        upload_file = form_data.get('file')
        file_data = await upload_file.read()
        if len(file_data) > StorageUnit.ONE_MB * 2:
            return JSONResponse(general_message(400, "file is too large", "文件大小不能超过2M"), status_code=400)

        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        code, msg, record = groupapp_backup_service.import_group_backup(session, env, response_region,
                                                                        group_id,
                                                                        file_data)
        if code != 200:
            return JSONResponse(general_message(code, "backup import failed", msg), status_code=code)
        result = general_message("0", "success", "导入成功", bean=jsonable_encoder(record))
    except Exception as e:
        logger.exception(e)
        result = error_message("导入失败")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/copy", response_model=Response, name="获取应用复制信息")
async def get_app_copy(
        request: Request,
        group_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    group_services = groupapp_copy_service.get_group_services_with_build_source(session, env, region_name, group_id)
    result = general_message("0", "success", "获取成功", list=jsonable_encoder(group_services))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/copy", response_model=Response, name="应用复制")
async def app_copy(request: Request,
                   group_id: Optional[str] = None,
                   user=Depends(deps.get_current_user),
                   env=Depends(deps.get_current_team_env),
                   session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    services = data.get("services", [])
    tar_env_id = data.get("tar_env_id")
    tar_region_name = data.get("tar_region_name")
    tar_group_id = data.get("tar_group_id")

    if not tar_env_id or not tar_region_name or not tar_group_id:
        raise ServiceHandleException(msg_show="缺少复制目标参数", msg="not found copy target parameters", status_code=404)

    tar_env = env_repo.get_env_by_env_id(session, tar_env_id)
    if not tar_env:
        raise ServiceHandleException(msg_show="目标环境不存在", msg="not found tar env", status_code=404)
    tar_group = groupapp_copy_service.check_and_get_env_group(session, tar_env_id, tar_group_id)
    try:
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        region_name = region.region_name
        groupapp_copy_service.copy_group_services(session, user, env, region_name, tar_env,
                                                  tar_region_name,
                                                  tar_group, group_id, services)
        result = general_message(
            200,
            "success",
            "复制成功",
            bean={
                "tar_team_name": tar_env.tenant_name,
                "tar_env_id": tar_env_id,
                "tar_region_name": tar_region_name,
                "tar_group_id": tar_group_id
            })
        status = 200
    except ApiBaseHttpClient.CallApiError as e:
        logger.exception(e)
        if e.status == 403:
            result = general_message(10407, "no cloud permission", e.message)
            status = e.status
        elif e.status == 400:
            if "is exist" in e.message.get("body", ""):
                result = general_message(400, "the service is exist in region", "组件名称在数据中心已存在")
            else:
                result = general_message(400, "call cloud api failure", e.message)
            status = e.status
        else:
            result = general_message(500, "call cloud api failure", e.message)
            status = 500
    return JSONResponse(result, status_code=status)
