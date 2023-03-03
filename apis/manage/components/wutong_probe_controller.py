from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.probe_service import probe_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/probe", response_model=Response, name="获取组件指定模式的探针")
async def get_probe(request: Request,
                    serviceAlias: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件指定模式的探针
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
        - name: mode
          description: 不健康处理方式（readiness|liveness|ignore）
          required: true
          type: string
          paramType: query
    """
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    if service.service_source == "third_party":
        code, msg, probe = probe_service.get_service_probe(session=session, service=service)
        if code != 200:
            return JSONResponse(general_message(code, "get probe error", msg))
        result = general_message("0", "success", "查询成功", bean=jsonable_encoder(probe))
    else:
        mode = request.query_params.get("mode", None)
        if not mode:
            code, msg, probe = probe_service.get_service_probe(session=session, service=service)
            if code != 200:
                return JSONResponse(general_message(code, "get probe error", msg))
            result = general_message("0", "success", "查询成功", bean=jsonable_encoder(probe))
        else:
            code, msg, probe = probe_service.get_service_probe_by_mode(session=session, service=service, mode=mode)
            if code != 200:
                return JSONResponse(general_message(code, "get probe error", msg))
            if not mode:
                result = general_message("0", "success", "查询成功", list=probe)
            else:
                result = general_message("0", "success", "查询成功", bean=jsonable_encoder(probe))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/probe", response_model=Response, name="添加组件探针")
async def add_probe(request: Request,
                    env_id: Optional[str] = None,
                    serviceAlias: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    添加组件探针
    ---
    serializer: ProbeSerilizer
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()

    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)

    params = jsonable_encoder(data)
    code, msg, probe = probe_service.add_service_probe(session=session, tenant_env=env, service=service, data=params)
    if code != 200:
        return JSONResponse(general_message(code, "add probe error", msg))
    result = general_message("0", "success", "添加成功", bean=jsonable_encoder(jsonable_encoder(probe) if probe else probe))
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/probe", response_model=Response, name="修改组件探针")
async def modify_probe(request: Request,
                       env_id: Optional[str] = None,
                       serviceAlias: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       user=Depends(deps.get_current_user)) -> Any:
    """
    修改组件探针,包括启用停用 mode参数必填
    ---
    serializer: ProbeSerilizer
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)

    data = await request.json()

    probe = probe_service.update_service_probea(session=session,
                                                tenant_env=env, service=service, data=data, user_name=user.nick_name)
    result = general_message("0", "success", "修改成功", bean=jsonable_encoder(probe.__dict__ if probe else probe))
    return JSONResponse(result, status_code=200)
