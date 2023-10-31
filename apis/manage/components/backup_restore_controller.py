import io
from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.responses import StreamingResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from schemas.components import BackupScheduleParam, ServiceBackupParam
from common.api_base_http_client import ApiBaseHttpClient

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup", response_model=Response, name="组件存储备份")
async def service_backup(
        service_alias: Optional[str] = None,
        service_backup_param: ServiceBackupParam = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    组件存储备份
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    body = {
        "ttl": service_backup_param.ttl,
        "operator": user.nick_name,
        "desc": service_backup_param.desc
    }
    re = remote_component_client.service_backup(session,
                                                service.service_region, env,
                                                service.service_alias, body)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(400, "failed", "组件存储备份失败"), status_code=400)
    return JSONResponse(general_message("0", "success", "组件存储备份成功"), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/records", response_model=Response,
            name="获取组件存储备份列表")
async def get_service_backup(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件存储备份列表
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    data = remote_component_client.get_service_backup_list(session,
                                                           service.service_region, env,
                                                           service.service_alias)

    all_backup_stauts = True
    if data:
        for backup in data:
            if backup["status"] == "InProgress" or backup["status"] == "Deleting":
                all_backup_stauts = False

    return JSONResponse(
        general_message("0", "success", "获取组件存储备份成功", list=data, bean={"all_backup_stauts": all_backup_stauts}),
        status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/{backup_id}", response_model=Response,
               name="删除组件存储备份记录")
async def delete_service_backup(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件存储备份记录
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    remote_component_client.delete_service_backup_records(session,
                                                          service.service_region, env,
                                                          service.service_alias,
                                                          backup_id)
    return JSONResponse(general_message("0", "success", "删除组件存储备份记录成功"), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/{backup_id}", response_model=Response,
             name="组件存储恢复")
async def service_restore(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    组件存储恢复
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    body = {
        "service_id": service.service_id,
        "backup_id": backup_id,
        "operator": user.nick_name
    }
    try:
        remote_component_client.service_restore(session,
                                                service.service_region, env,
                                                service.service_alias, body)
    except ApiBaseHttpClient.CallApiError as exc:
        logger.error(exc)
        return JSONResponse(general_message(500, exc.body.msg, exc.body.msg),
                            status_code=200)
    return JSONResponse(general_message(200, "success", "组件存储恢复成功"), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/records", response_model=Response,
            name="获取组件存储恢复列表")
async def get_service_backup(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件存储恢复列表
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.get_service_restore_list(session,
                                                          service.service_region, env,
                                                          service.service_alias)
    return JSONResponse(general_message("0", "success", "获取组件存储恢复列表", list=re), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/{restore_id}", response_model=Response,
               name="删除组件存储恢复记录")
async def delete_service_restore(
        service_alias: Optional[str] = None,
        restore_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件存储恢复记录
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    remote_component_client.delete_service_restore_records(session,
                                                           service.service_region, env,
                                                           service.service_alias,
                                                           restore_id)
    return JSONResponse(general_message("0", "success", "删除组件存储恢复记录成功"), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/{backup_id}/download",
            response_model=Response,
            name="下载组件存储备份")
async def get_service_backup(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    下载组件存储备份
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.download_service_backup(session,
                                                         service.service_region, env,
                                                         service.service_alias,
                                                         backup_id)
    file = io.BytesIO(re)
    response = StreamingResponse(file, media_type="application/gzip")
    response.init_headers({"Content-Disposition": "attchment; filename={0}.tar.gz".format(backup_id)})
    return response


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/schedule", response_model=Response,
            name="获取组件存储备份计划")
async def get_service_backup_schedule(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件存储备份计划
    """
    data = {"enable": True}
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.get_service_backup_schedule(session,
                                                             service.service_region, env,
                                                             service.service_alias)
    if not re:
        data.update({"enable": False})
    else:
        try:
            data.update(re)
            cron_list = data.get("cron").split(" ")
            if cron_list[4] == "*":
                sync_freq = "day"
            else:
                sync_freq = "week"
            sync_time = int(cron_list[1]) + 8
            if sync_time > 24:
                sync_time = sync_time - 24

            data.update({"sync_freq": sync_freq,
                         "sync_time": sync_time,
                         "sync_week": int(cron_list[4]) if cron_list[4] != "*" else 1})
        except Exception as err:
            logger.error(err)
            return JSONResponse(general_message(500, "failed", "获取组件存储备份计划失败"), status_code=500)

    return JSONResponse(general_message("0", "success", "获取组件存储备份计划成功", bean=data), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/schedule", response_model=Response,
             name="新增组件存储备份计划")
async def service_backup_schedule(
        service_alias: Optional[str] = None,
        param: Optional[BackupScheduleParam] = BackupScheduleParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    新增组件存储备份计划
    """
    if not param.sync_time:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    sync_time = int(param.sync_time)
    if sync_time - 8 < 0:
        sync_time = 24 + sync_time - 8
    else:
        sync_time = sync_time - 8

    cron = "0 {0} * * {1}".format(str(sync_time), param.sync_week)

    body = {
        "cron": cron,
        "ttl": param.ttl,
        "operator": user.nick_name,
        "desc": param.desc
    }
    re = remote_component_client.service_backup_schedule(session,
                                                         service.service_region, env,
                                                         service.service_alias, body)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(500, "failed", "新增组件存储备份计划失败"), status_code=500)
    return JSONResponse(general_message("0", "success", "新增组件存储备份计划成功"), status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/schedule", response_model=Response,
            name="修改组件存储备份计划")
async def put_service_backup_schedule(
        service_alias: Optional[str] = None,
        param: Optional[BackupScheduleParam] = BackupScheduleParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    修改组件存储备份计划
    """
    if not param.sync_time:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    sync_time = int(param.sync_time)
    if sync_time - 8 < 0:
        sync_time = 24 + sync_time - 8
    else:
        sync_time = sync_time - 8

    cron = "0 {0} * * {1}".format(str(sync_time), param.sync_week)

    body = {
        "cron": cron,
        "ttl": param.ttl,
        "operator": user.nick_name,
        "desc": param.desc
    }
    re = remote_component_client.put_service_backup_schedule(session,
                                                             service.service_region, env,
                                                             service.service_alias, body)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(500, "failed", "修改组件存储备份计划失败"), status_code=500)
    return JSONResponse(general_message("0", "success", "修改组件存储备份计划成功"), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/schedule/delete",
               response_model=Response,
               name="删除组件存储备份计划")
async def delete_service_backup_schedule(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件存储备份计划
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.delete_service_backup_schedule(session,
                                                                service.service_region, env,
                                                                service.service_alias)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(500, "failed", "删除组件存储备份计划失败"), status_code=500)
    return JSONResponse(general_message("0", "success", "删除组件存储备份计划成功"), status_code=200)
