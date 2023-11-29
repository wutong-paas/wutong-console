from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.requests import Request
from starlette.responses import StreamingResponse
from clients.remote_build_client import remote_build_client
from core import deps
from core.api.team_api import team_api
from core.utils.return_message import general_message
from database.session import SessionClass
from models.teams import RegionConfig
from repository.application.application_repo import application_repo
from repository.region.region_config_repo import region_config_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.backup_data_service import platform_data_services
from service.common_services import common_services
from service.enterprise_service import enterprise_services
from service.region_service import region_services

router = APIRouter()


@router.get("/enterprise/overview/app", response_model=Response, name="总览-应用信息")
async def overview_app(
        request: Request,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    tenant_env_ids = request.query_params.get("tenant_env_ids", None)
    usable_regions = region_config_repo.list_by_model(session=session,
                                                      query_model=RegionConfig(status="1"))
    if not usable_regions:
        result = general_message(404, "no found regions", "查询成功")
        return JSONResponse(result, status_code=200)
    data = enterprise_services.get_enterprise_runing_service(session=session, regions=usable_regions,
                                                             tenant_env_ids=tenant_env_ids)
    result = general_message("0", "success", "查询成功", bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/monitor", response_model=Response, name="集群监控信息")
async def monitor(session: SessionClass = Depends(deps.get_session)) -> Any:
    usable_regions = region_config_repo.list_by_model(session=session,
                                                      query_model=RegionConfig(status="1"))
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
            res, body = remote_build_client.get_region_resources(session, region=region.region_name)
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
    result = general_message("0", "success", None, bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/regions", response_model=Response, name="获取集群列表")
async def regions(status: Optional[str] = "", check_status: Optional[str] = "",
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user)) -> Any:
    data = region_services.get_enterprise_regions(session=session, level="safe",
                                                  status=status,
                                                  check_status=check_status)
    region_infos = jsonable_encoder(data)
    for region_info in region_infos:
        region_code = region_info["region_name"]
        envs = env_repo.get_envs_by_region_code(session, region_code)
        region_use_info = {}
        for env in envs:
            team_code = env.tenant_name
            team_name = env.team_alias
            current_team_info = region_use_info.get(team_code, {})
            current_use_cpu = 0
            current_use_memory = 0
            if current_team_info:
                current_use_cpu = current_team_info.get("use_cpu", 0)
                current_use_memory = current_team_info.get("use_memory", 0)
            env_info = common_services.get_current_region_used_resource(session, env, region_code)
            if env_info:
                use_cpu = env_info.get("cpu", 0)
                use_memory = env_info.get("memory", 0)
                region_use_info.update({team_code: {
                    "use_cpu": round(current_use_cpu + use_cpu, 2),
                    "use_memory": round(current_use_memory + use_memory, 2),
                    "team_name": team_name
                }})
        region_info.update({"region_team_info": region_use_info})
    result = general_message("0", "success", "获取成功", list=region_infos)
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/backups", response_model=Response, name="获取备份信息")
async def get_enterprise_backup_info() -> Any:
    backups = platform_data_services.list_backups()
    result = general_message("0", "success", "数据上传成功", list=backups)
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/backups", response_model=Response, name="增加备份")
async def add_enterprise_backup() -> Any:
    platform_data_services.create_backup()
    result = general_message("0", "success", "备份成功")
    return JSONResponse(result, status_code=200)


@router.delete("/enterprise/backups", response_model=Response, name="删除备份")
async def delete_enterprise_backup(request: Request) -> Any:
    data = await request.json()
    name = data.get("name")
    if not name:
        result = general_message("0", "backup file can not be empty", "备份文件名称不能为空")
    else:
        platform_data_services.remove_backup(name)
        result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/upload-backups", response_model=Response, name="导入备份")
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
    result = general_message("0", "success", "数据上传成功")
    return JSONResponse(result, status_code=200)


@router.get("/enterprise/backups/{backup_name}", response_model=Response, name="下载备份")
async def down_enterprise_backup(backup_name: Optional[str] = None) -> Any:
    response = StreamingResponse(platform_data_services.download_file(backup_name))
    return response
    # ===================================================================
    # file_path = os.path.join(settings.DATA_DIR, "backups", backup_name)
    # return FileResponse(file_path)


@router.post("/enterprise/recover", response_model=Response, name="恢复备份")
async def recovery_enterprise_backup(request: Request,
                                     user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    name = data.get("name")
    password = data.get("password")
    if not user.check_password(password):
        return JSONResponse(general_message(400, "param error", "输入密码不正确"), status_code=400)
    if not name:
        result = general_message("0", "backup file can not be empty", "备份文件名称不能为空")
    else:
        platform_data_services.recover_platform_data(name)
        result = general_message("0", "success", "恢复成功")
    return JSONResponse(result, status_code=200)
