from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status
from typing import Any, Optional

from clients.remote_node_client import remote_node_client_api
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.region.region_info_repo import region_repo
from schemas.node import NodeCordonParam
from schemas.response import Response

router = APIRouter()


@router.get("/plat/region/query/nodes", response_model=Response, name="查询节点列表")
async def get_plat_nodes(
        region_code: Optional[str] = None,
        query: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询节点列表
    """
    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群不存在"), status_code=200)
    nodes = remote_node_client_api.get_nodes(session, region_code, query)
    result = general_message(200, "success", "获取成功", list=jsonable_encoder(nodes))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.get("/plat/region/query/node/{node_name}", response_model=Response, name="查询某个节点详情")
async def get_plat_nodes(
        region_code: Optional[str] = None,
        node_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询某个节点详情
    """
    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)
    node = remote_node_client_api.get_node_by_name(session, region_code, node_name)
    result = general_message(200, "success", "获取成功", bean=jsonable_encoder(node))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.put("/plat/region/query/node/{node_name}/cordon", response_model=Response, name="设置节点调度")
async def set_plat_nodes(
        node_name: Optional[str] = None,
        params: Optional[NodeCordonParam] = NodeCordonParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    设置节点调度
    """
    region_code = params.region_code
    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    try:
        remote_node_client_api.set_node_cordon(session, region_code, node_name, params.cordon, params.evict_pods)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "set node cordon error", "设置节点调度失败"), status_code=200)

    return JSONResponse(general_message(200, "success", "设置成功"), status_code=200)
