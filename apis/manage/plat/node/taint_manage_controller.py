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
from schemas.response import Response
from schemas.node import AddNodeTaintParam, DeleteNodeTaintParam
from core.utils.validation import node_validate_name

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
    key = params.key
    value = params.value
    region_code = params.region_code
    effect = params.effect

    if effect not in ["NoSchedule", "PreferNoSchedule", "NoExecute"]:
        return JSONResponse(general_message(400, "error params", "效果只支持NoSchedule、PreferNoSchedule、NoExecute"),
                            status_code=200)

    if not key:
        return JSONResponse(general_message(500, "not found key", "污点键不能为空"), status_code=200)

    if len(key) > 32:
        return JSONResponse(general_message(400, "error params", "污点键不能超过32个字符”“值不能超过32个字符"), status_code=200)

    if not node_validate_name(key):
        return JSONResponse(general_message(400, "error params", "污点键只支持英文、数字、中横线、下划线组合，只能以英文开头且中横线、下划线不能位于首尾"),
                            status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "key": key,
        "value": value,
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
    key = params.key
    region_code = params.region_code
    if not key:
        return JSONResponse(general_message(500, "not found key", "污点键不能为空"), status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "key": key
    }
    try:
        remote_node_client_api.delete_node_taint(session, region_code, node_name, body)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "delete node annotation error", "删除节点污点失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "删除成功"), status_code=200)
