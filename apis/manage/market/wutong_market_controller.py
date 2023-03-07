from typing import Any
from fastapi import APIRouter, Depends, Body
from starlette.responses import JSONResponse
from core import deps
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from service.market_app_service import market_app_service

router = APIRouter()


@router.post("/enterprise/market/create_template", name="创建应用模版")
async def create_cloud_app_template(name: str = Body(default="", embed=True),
                                    user=Depends(deps.get_current_user),
                                    session: SessionClass = Depends(deps.get_session)) -> Any:
    app_info = {
        "app_name": name,
        "describe": "",
        "pic": "",
        "details": "",
        "dev_status": "",
        "tag_ids": "",
        "scope": "market",
        "scope_target": "",
        "source": "",
        "create_team": "",
        "create_user": user.user_id,
        "create_user_name": user.nick_name
    }
    market_app_service.create_wutong_app(session, app_info, make_uuid())
    return JSONResponse(general_message("0", "success", "操作成功", status_code=200))
