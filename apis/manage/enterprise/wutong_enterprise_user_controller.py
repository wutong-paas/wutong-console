from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from core import deps
from core.idaasapi import idaas_api
from core.utils.return_message import general_message
from database.session import SessionClass
from schemas.response import Response
from service.env_service import env_services

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/user/{user_id}/teams", response_model=Response, name="查询用户列表")
async def get_users_team(request: Request,
                         enterprise_id: Optional[str] = None,
                         user_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    name = request.query_params.get("name", None)
    user = idaas_api.get_user_info(user_id)
    teams = env_services.list_user_teams(session, enterprise_id, user, name)
    result = general_message(200, "team query success", "查询成功", list=jsonable_encoder(teams))
    return JSONResponse(result, status_code=200)