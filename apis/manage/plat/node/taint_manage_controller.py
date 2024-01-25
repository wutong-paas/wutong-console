from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger

from clients.remote_node_client import remote_node_client_api
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.region.region_info_repo import region_repo
from schemas.node import AddNodeTaintParam, DeleteNodeTaintParam
from schemas.response import Response

router = APIRouter()


@router.get("/plat/region/node/{node_name}/taint", response_model=Response, name="查询节点污点")
async def get_node_taint(
        node_name: Optional[str] = None,
        region_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询节点污点
    """

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    try:
        annotations = remote_node_client_api.get_node_taint(session, region_code, node_name)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "get node annotation error", "查询节点污点失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "查询成功", list=annotations), status_code=200)


@router.post("/plat/region/node/{node_name}/taint", response_model=Response, name="新增节点污点")
async def add_node_taint(
        node_name: Optional[str] = None,
        params: Optional[AddNodeTaintParam] = AddNodeTaintParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    新增节点污点
    """
    key = params.taint_key
    value = params.taint_value
    region_code = params.region_code
    effect = params.effect

    if not effect:
        return JSONResponse(
            general_message(400, "effect not null", "效果不能为空"),
            status_code=200,
        )

    if effect not in ["NoSchedule", "PreferNoSchedule", "NoExecute"]:
        return JSONResponse(general_message(400, "error params", "效果只支持NoSchedule、PreferNoSchedule、NoExecute"),
                            status_code=200)

    if not key:
        return JSONResponse(general_message(500, "not found key", "污点键不能为空"), status_code=200)

    if len(key) > 64:
        return JSONResponse(general_message(400, "error params", "污点键不能超过64个字符"), status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "taint_key": key,
        "taint_value": value,
        "effect": effect
    }
    try:
        remote_node_client_api.add_node_taint(session, region_code, node_name, body)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "add node annotation error", "新增节点污点失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "新增成功"), status_code=200)


@router.delete("/plat/region/node/{node_name}/taint", response_model=Response, name="删除节点污点")
async def delete_node_taint(
        node_name: Optional[str] = None,
        params: Optional[DeleteNodeTaintParam] = DeleteNodeTaintParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除节点污点
    """
    key = params.taint_key
    region_code = params.region_code
    if not key:
        return JSONResponse(general_message(500, "not found key", "污点键不能为空"), status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "taint_key": key
    }
    try:
        remote_node_client_api.delete_node_taint(session, region_code, node_name, body)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "delete node annotation error", "删除节点污点失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "删除成功"), status_code=200)
