import io
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.responses import StreamingResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup", response_model=Response, name="组件备份")
async def service_backup(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    组件备份
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    body = {
        "service_id": service.service_id
    }
    re = remote_component_client.service_backup(session,
                                                service.service_region, env,
                                                service.service_alias, body)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(400, "failed", "组件备份失败"), status_code=400)
    return JSONResponse(general_message(200, "success", "组件备份成功"), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/records", response_model=Response,
            name="获取组件备份列表")
async def get_service_backup(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件备份列表
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.get_service_backup_list(session,
                                                         service.service_region, env,
                                                         service.service_alias)
    return JSONResponse(general_message(200, "success", "获取组件备份成功", list=re), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/{backup_id}", response_model=Response,
               name="删除组件备份记录")
async def delete_service_backup(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件备份记录
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.delete_service_backup_records(session,
                                                               service.service_region, env,
                                                               service.service_alias,
                                                               backup_id)
    return JSONResponse(general_message(200, "success", "删除组件备份记录成功", list=re), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/{backup_id}", response_model=Response,
             name="组件恢复")
async def service_restore(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    组件恢复
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    body = {
        "service_id": service.service_id,
        "backup_id": backup_id
    }
    re = remote_component_client.service_restore(session,
                                                 service.service_region, env,
                                                 service.service_alias, body)
    if re and re.get("bean") and re.get("bean").get("status") != "success":
        logger.error("deploy component failure {}".format(re))
        return JSONResponse(general_message(400, "failed", "组件恢复失败"), status_code=400)
    return JSONResponse(general_message(200, "success", "组件恢复成功"), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/records", response_model=Response,
            name="获取组件恢复列表")
async def get_service_backup(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件恢复列表
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.get_service_restore_list(session,
                                                          service.service_region, env,
                                                          service.service_alias)
    return JSONResponse(general_message(200, "success", "获取组件恢复列表", list=re), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/restore/{restore_id}", response_model=Response,
               name="删除组件恢复记录")
async def delete_service_restore(
        service_alias: Optional[str] = None,
        restore_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件恢复记录
    """
    service = service_info_repo.get_service(session, service_alias, env.env_id)

    re = remote_component_client.delete_service_restore_records(session,
                                                                service.service_region, env,
                                                                service.service_alias,
                                                                restore_id)
    return JSONResponse(general_message(200, "success", "删除组件恢复记录成功", list=re), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/backup/{backup_id}/download",
            response_model=Response,
            name="下载组件备份")
async def get_service_backup(
        service_alias: Optional[str] = None,
        backup_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    下载组件备份
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
