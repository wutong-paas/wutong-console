from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_actions.app_log import log_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/log", response_model=Response, name="获取组件的日志")
async def get_log(request: Request,
                  env_id: Optional[str] = None,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取组件的日志
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
        - name: action
          description: 日志类型（目前只有一个 service）
          required: false
          type: string
          paramType: query
        - name: lines
          description: 日志数量，默认为100
          required: false
          type: integer
          paramType: query

    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    action = request.query_params.get("action", "service")
    lines = request.query_params.get("lines", 100)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)

    code, msg, log_list = log_service.get_service_logs(session=session, tenant_env=env, service=service, action=action,
                                                       lines=int(lines))
    if code != 200:
        return JSONResponse(general_message(code, "query service log error", msg), status_code=code)
    result = general_message("0", "success", "查询成功", list=log_list)
    return JSONResponse(result, status_code=200)
