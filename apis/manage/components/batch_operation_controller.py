from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from starlette.requests import Request
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from schemas.components import BatchActionParam
from schemas.response import Response
from service.app_actions.app_manage import app_manage_service
from service.region_service import region_services

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/batch_actions", response_model=Response, name="批量操作")
async def batch_actions(
        request: Request,
        params: Optional[BatchActionParam] = BatchActionParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    批量操作组件
    """
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name

    if params.action not in ("stop", "start", "restart", "move", "upgrade", "deploy"):
        return JSONResponse(general_message(400, "param error", "操作类型错误"), status_code=400)

    perm_action = params.action
    if params.action == "upgrade":
        perm_action = "update"
    if params.action == "deploy":
        perm_action = "construct"

    service_id_list = params.service_ids.split(",")
    code, msg = app_manage_service.batch_action(session=session, region_name=region_name, tenant_env=env, user=user,
                                                action=params.action, service_ids=service_id_list,
                                                move_group_id=params.move_group_id)
    if code != 200:
        result = general_message(code, "batch manage error", msg)
    else:
        result = general_message(200, "success", "操作成功")
    return JSONResponse(result, status_code=result["code"])
