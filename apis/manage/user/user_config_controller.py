from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.config.config_repo import console_config_repo
from schemas.response import Response
from service.custom_configs import custom_configs_service

router = APIRouter()


@router.get("/custom_configs", response_model=Response, name="获取用户配置")
async def get_custom_configs(session: SessionClass = Depends(deps.get_session)) -> Any:
    configs = console_config_repo.get_all(session=session)
    result = general_message(200, "success", msg_show="操作成功", list=jsonable_encoder(configs))
    return JSONResponse(result, status_code=result["code"])


@router.put("/custom_configs", response_model=Response, name="更新用户配置")
async def update_custom_configs(request: Request, session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    if type(data) != list:
        raise AbortRequest(msg="The request parameter must be a list", msg_show="请求参数必须为列表")
    custom_configs_service.bulk_create_or_update(session, data)
    result = general_message(200, "success", msg_show="操作成功", list=data)
    return JSONResponse(result, status_code=result["code"])
