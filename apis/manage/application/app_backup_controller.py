from typing import Any, Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import Params, paginate
from loguru import logger
from core import deps
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.backup_service import groupapp_backup_service
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/all/groupapp/backup", response_model=Response,
            name="查询当前团队 数据中心下所有备份信息")
async def get_team_backup_info(
        request: Request,
        env_id: Optional[str] = None,
        page: int = Query(default=1, ge=1, le=9999),
        page_size: int = Query(default=10, ge=1, le=500),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        backups = groupapp_backup_service.get_all_group_back_up_info(session, env, response_region)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(backups, params)
        total = event_paginator.total
        backup_records = event_paginator.items
        backup_list = list()
        if backup_records:
            for backup in backup_records:
                backup_dict = jsonable_encoder(backup)
                group_obj = application_repo.get_group_by_id(session, backup_dict["group_id"])
                if group_obj:
                    backup_dict["group_name"] = group_obj.group_name
                    backup_dict["is_delete"] = False
                else:
                    backup_dict["group_name"] = "应用已删除"
                    backup_dict["is_delete"] = True
                backup_list.append(backup_dict)
        result = general_message(200, "success", "查询成功", list=backup_list, total=total)
    except Exception as e:
        logger.exception(e)
        result = error_message("查询失败")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/env/{env_id}/groupapp/{group_id}/delete", response_model=Response,
               name="应用数据删除")
async def delete_team_app_info(request: Request,
                               env_id: Optional[str] = None,
                               group_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        data = await request.json()
        if not group_id:
            return JSONResponse(general_message(400, "group id is null", "请确认需要删除的组"), status_code=400)
        new_group_id = data.get("new_group_id", None)
        if not new_group_id:
            return JSONResponse(general_message(400, "new group id is null", "请确认新恢复的组"), status_code=400)
        if group_id == new_group_id:
            return JSONResponse(general_message(200, "success", "恢复到当前组无需删除"), status_code=200)
        group = application_repo.get_group_by_id(session, group_id)
        if not group:
            return JSONResponse(general_message(400, "group is delete", "该备份组已删除"), status_code=400)

        new_group = application_repo.get_group_by_id(session, new_group_id)
        if not new_group:
            return JSONResponse(general_message(400, "new group not exist", "组ID {0} 不存在".format(new_group_id)),
                                status_code=400)
        services = application_service.get_group_services(session, group_id)
        for service in services:
            try:
                app_manage_service.truncate_service(session, env, service)
            except Exception as le:
                logger.exception(le)

        application_repo.delete_group_by_id(session, group_id)
        result = general_message(200, "success", "操作成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=result["code"])
