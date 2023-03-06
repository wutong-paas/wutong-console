from typing import Any
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.team_plugin_repo import plugin_repo
from schemas.response import Response
from service.market_plugin_service import get_paged_plugins

router = APIRouter()


@router.get("/plugin/market/plugins", response_model=Response, name="插件市场")
async def market_plugins(page: int = 1,
                         limit: int = 10,
                         plugin_name: str = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    插件市场
    :param page:
    :param limit:
    :param plugin_name:
    :return:
    """
    # todo tenant_env_id
    total, plugins = get_paged_plugins(session=session, plugin_name=plugin_name, is_complete=True, page=page,
                                       limit=limit,
                                       order_by='is_complete', source='market', scope='goodrain', tenant_env=None)
    result = general_message("0", "success", "查询成功", list=plugins, total=total, next_page=int(page) + 1)
    return JSONResponse(result, status_code=200)


@router.get("/plugin/plugins", response_model=Response, name="内部插件市场插件列表")
async def internal_market_plugins(page: int = 1,
                                  limit: int = 10,
                                  plugin_name: str = None,
                                  scope: str = None,
                                  session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    内部插件市场插件列表
    :param page:
    :param limit:
    :param plugin_name:
    :param scope:
    :return:
    """
    # todo tenant_env_id
    total, plugins = get_paged_plugins(session=session, plugin_name=plugin_name, is_complete=True, scope=scope,
                                       tenant_env=None,
                                       page=page, limit=limit)
    result = general_message("0", "success", "查询成功", list=plugins, total=total, next_page=int(page) + 1)
    return JSONResponse(result, status_code=200)


@router.get("/plugin/plugins/installable", response_model=Response, name="插件列表")
async def installable_internal_plugins(page: int = 1,
                                       limit: int = 10,
                                       plugin_name: str = None,
                                       session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    插件列表
    :param page:
    :param limit:
    :param plugin_name:
    :return:
    """
    # todo tenant_env_id
    total, plugins = get_paged_plugins(session=session, plugin_name=plugin_name, is_complete=True, tenant_env=None,
                                       page=page,
                                       limit=limit)
    # todo tenant_env_id  region
    installed = plugin_repo.list_by_tenant_env_id(None, None).filter(origin__in=['sys', 'market'])
    for plugin in plugins:
        if installed.filter(origin_share_id=plugin["plugin_key"]).exists():
            plugin["is_installed"] = True
        else:
            plugin["is_installed"] = False
    result = general_message("0", "success", "查询成功", list=plugins, total=total, next_page=int(page) + 1)
    return JSONResponse(result, status_code=200)
