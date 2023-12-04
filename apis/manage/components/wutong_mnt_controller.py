import json
from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from core import deps
from core.utils.reqparse import parse_argument
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.application.app_repository import app_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.mnt_service import mnt_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/mnt", response_model=Response, name="获取组件挂载的组件")
async def get_mnt(request: Request,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  env=Depends(deps.get_current_team_env)) -> Any:
    """
     获取组件挂载的组件
     ---
     parameters:
         - name: tenantName
           description: 租户名
           required: true
           type: string
           paramType: path
         - name: serviceAlias
           description: 组件别名
           required: true
           type: string
           paramType: path
         - name: type
           description: 查询的类别 mnt（已挂载的,默认）| unmnt (未挂载的)
           required: false
           type: string
           paramType: query
         - name: page
           description: 页号（默认第一页）
           required: false
           type: integer
           paramType: query
         - name: page_size
           description: 每页大小(默认10)
           required: false
           type: integer
           paramType: query

     """
    query = request.query_params.get("query", "")
    if query == "undefined":
        query = ""
    query_type = request.query_params.get("type", "mnt")
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("page_size", 10)
    volume_types = parse_argument(request, 'volume_types', value_type=list)
    is_config = parse_argument(request, 'is_config', value_type=bool, default=False)

    service = service_info_repo.get_service(session, serviceAlias, env.env_id)

    if query == "undefined":
        query = ""
    if volume_types is not None and ('config-file' in volume_types):
        is_config = True

    if query_type == "mnt":
        mnt_list, total = mnt_service.get_service_mnt_details(session=session, tenant_env=env, service=service,
                                                              volume_types=volume_types)
    elif query_type == "unmnt":
        services = app_repo.get_app_list(session, env.env_id, service.service_region, query)
        services_ids = [s.service_id for s in services]
        mnt_list, total = mnt_service.get_service_unmount_volume_list(session=session, tenant_env=env, service=service,
                                                                      service_ids=services_ids, page=page,
                                                                      page_size=page_size, is_config=is_config)
    else:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)
    result = general_message("0", "success", "查询成功", list=mnt_list, total=total)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/mnt", response_model=Response, name="获取组件挂载的组件")
async def set_mnt(request: Request,
                  env_id: Optional[str] = None,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user)) -> Any:
    """
    为组件添加挂载依赖
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: body
          description: 批量添加挂载[{"id":49,"path":"/add"},{"id":85,"path":"/dadd"}]
          required: true
          type: string
          paramType: body

    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    data = await request.json()
    dep_vol_data = data["body"]
    dep_vol_data = json.loads(dep_vol_data)
    mnt_service.batch_mnt_serivce_volume(session=session, tenant_env=env, service=service, dep_vol_data=dep_vol_data,
                                         user_name=user.nick_name)
    result = general_message("0", "success", "操作成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/mnt/{dep_vol_id}", response_model=Response,
               name="取消挂载共享配置文件")
async def delete_mnt(
        env_id: Optional[str] = None,
        dep_vol_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    code, msg = mnt_service.delete_service_mnt_relation(session, env, service, dep_vol_id, user.nick_name)

    if code != 200:
        return JSONResponse(general_message(code, "add error", msg), status_code=code)

    result = general_message("0", "success", "操作成功")
    return JSONResponse(result, status_code=200)
