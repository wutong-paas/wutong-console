from typing import Any, Optional

from fastapi import APIRouter, Depends, Body
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from clients.wutong_market_client import wutong_market_client
from core import deps
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.market.wutong_market_repo import wutong_market_repo
from schemas.market import MarketCreateParam, MarketAppQueryParam, MarketAppInstallParam, MarketAppQueryVO
from service.market import wutong_market_service
from service.market_app_service import market_app_service

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/cloud/wutong-markets", name="梧桐商店列表")
async def wutong_markets(enterprise_id: str = None,
                         user=Depends(deps.get_current_user),
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    markets = wutong_market_service.get_wutong_markets(session=session, enterprise_id=enterprise_id,
                                                       user=user)
    return JSONResponse(general_message(200, "success", "查询成功", list=jsonable_encoder(markets)), status_code=200)


@router.post("/enterprise/{enterprise_id}/cloud/bind-markets", name="新增梧桐应用商店")
async def bind_wutong_market(params: Optional[MarketCreateParam] = MarketCreateParam(),
                             enterprise_id: str = None,
                             session: SessionClass = Depends(deps.get_session)) -> Any:
    wutong_market_service.bind_wutong_market(session=session, enterprise_id=enterprise_id, params=params)
    return JSONResponse(general_message(200, "success", "操作成功"), status_code=200)


@router.put("/enterprise/{enterprise_id}/markets/{market_id}", name="更新梧桐应用商店名称")
async def update_wutong_market(enterprise_id: str = None, market_id: str = None, market_name: str = None,
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    wutong_market_service.update_wutong_market(session=session, enterprise_id=enterprise_id, market_id=market_id,
                                               market_name=market_name)
    return JSONResponse(general_message(200, "success", "操作成功"), status_code=200)


@router.post("/enterprise/{enterprise_id}/market-apps/{market_id}", name="商店应用列表")
async def get_cloud_market_apps(market_id: int = None,
                                current: int = Body(default=1, ge=1, le=99999, embed=True),
                                size: int = Body(default=10, ge=1, le=500, embed=True),
                                queryVO: MarketAppQueryVO = Body(default=MarketAppQueryVO(), embed=True),
                                session: SessionClass = Depends(deps.get_session)) -> Any:
    market = wutong_market_repo.get_by_primary_key(session=session, primary_key=market_id)
    result = wutong_market_client.get_market_apps(
        session=session, body=MarketAppQueryParam(current=current, size=size, queryVO=queryVO).dict(), market=market)
    return JSONResponse(general_message(200, "success", "操作成功", bean=jsonable_encoder(result)), status_code=200)


@router.get("/enterprise/{enterprise_id}/market/{market_id}/apps/{app_id}", name="商店应用详情")
async def get_cloud_market_app_detail(market_id: int = None, app_id: str = None,
                                      session: SessionClass = Depends(deps.get_session)) -> Any:
    market = wutong_market_repo.get_by_primary_key(session=session, primary_key=market_id)
    result = wutong_market_client.get_market_app_detail(session=session, market=market, app_id=app_id)
    return JSONResponse(general_message(200, "success", "操作成功", bean=jsonable_encoder(result)), status_code=200)


@router.post("/enterprise/{enterprise_id}/market/create_template", name="创建应用模版")
async def create_cloud_app_template(name: str = Body(default="", embed=True), enterprise_id: str = None,
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
    market_app_service.create_wutong_app(session, enterprise_id, app_info, make_uuid())
    return JSONResponse(general_message(200, "success", "操作成功", status_code=200))


@router.get("/enterprise/{enterprise_id}/market/{market_id}/apps/{app_id}/versions", name="查询应用版本列表")
async def get_cloud_app_versions(market_id: int = None, app_id: str = None,
                                 session: SessionClass = Depends(deps.get_session)) -> Any:
    market = wutong_market_repo.get_by_primary_key(session=session, primary_key=market_id)
    query_body = {
        "current": 1,
        "size": 100,
        "queryVO": {
            "app_id": app_id
        }
    }
    app_versions = wutong_market_client.get_market_app_versions(session=session, market=market, query_body=query_body)
    return JSONResponse(general_message(200, "success", "操作成功", list=jsonable_encoder(app_versions)), status_code=200)


@router.post("/enterprise/{enterprise_id}/market-apps/{market_id}/install_cloud_app", name="安装商店应用")
async def install_cloud_market_app(enterprise_id: str, market_id: str,
                                   params: Optional[MarketAppInstallParam] = MarketAppInstallParam(),
                                   user=Depends(deps.get_current_user),
                                   session: SessionClass = Depends(deps.get_session)) -> Any:
    wutong_market_service.install_cloud_market_app(session=session, user=user, enterprise_id=enterprise_id,
                                                   market_id=market_id, params=params)
    return JSONResponse(general_message(200, "success", "操作成功", status_code=200))


@router.get("/enterprise/{enterprise_id}/store-list", name="获取店铺下拉列表")
async def get_store_list(enterprise_id: str, session: SessionClass = Depends(deps.get_session)) -> Any:
    store_list = wutong_market_service.get_store_list(session=session, enterprise_id=enterprise_id)
    return JSONResponse(general_message(200, "success", "操作成功", list=jsonable_encoder(store_list), status_code=200))
