from typing import Any, Optional

from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_repo
from schemas.response import Response
from service.app_actions.app_log import log_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/log", response_model=Response, name="获取组件的日志")
async def get_log(request: Request,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  team=Depends(deps.get_current_team)) -> Any:
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
    action = request.query_params.get("action", "service")
    lines = request.query_params.get("lines", 100)
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)

    code, msg, log_list = log_service.get_service_logs(session=session, tenant=team, service=service, action=action,
                                                       lines=int(lines))
    if code != 200:
        return JSONResponse(general_message(code, "query service log error", msg), status_code=code)
    result = general_message(200, "success", "查询成功", list=log_list)
    return JSONResponse(result, status_code=result["code"])
