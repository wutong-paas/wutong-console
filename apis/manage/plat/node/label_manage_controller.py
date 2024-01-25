from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger

from clients.remote_node_client import remote_node_client_api
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.region.region_info_repo import region_repo
from schemas.node import AddNodeLabelParam, DeleteNodeLabelParam
from schemas.response import Response

router = APIRouter()


@router.post("/plat/region/node/{node_name}/label", response_model=Response, name="新增节点标签")
async def add_node_label(
        node_name: Optional[str] = None,
        params: Optional[AddNodeLabelParam] = AddNodeLabelParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    新增节点标签
    """
    key = params.label_key
    value = params.label_value
    region_code = params.region_code
    label_type = params.label_type
    if not key:
        return JSONResponse(general_message(500, "not found key", "标签键不能为空"), status_code=200)

    if len(key) > 64:
        return JSONResponse(general_message(400, "error params", "标签键不能超过64个字符"), status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "label_key": key,
        "label_value": value
    }
    try:
        if label_type == "common_label":
            remote_node_client_api.add_node_label(session, region_code, node_name, body)
        elif label_type == "vm_label":
            remote_node_client_api.add_node_vm_label(session, region_code, node_name, body)
        else:
            return JSONResponse(general_message(500, "not found label_type", "标签类型错误"), status_code=200)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "add node label error", "新增节点标签失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "新增成功"), status_code=200)


@router.delete("/plat/region/node/{node_name}/label", response_model=Response, name="删除节点标签")
async def delete_node_label(
        node_name: Optional[str] = None,
        params: Optional[DeleteNodeLabelParam] = DeleteNodeLabelParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除节点标签
    """
    key = params.label_key
    region_code = params.region_code
    label_type = params.label_type
    if not key:
        return JSONResponse(general_message(500, "not found key", "标签键不能为空"), status_code=200)

    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    body = {
        "label_key": key,
    }
    try:
        if label_type == "common_label":
            remote_node_client_api.delete_node_label(session, region_code, node_name, body)
        elif label_type == "vm_label":
            remote_node_client_api.delete_node_vm_label(session, region_code, node_name, body)
        else:
            return JSONResponse(general_message(500, "not found label_type", "标签类型错误"), status_code=200)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "add node label error", "删除节点标签失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "删除成功"), status_code=200)


@router.get("/plat/region/node/{node_name}/label", response_model=Response, name="查询节点标签")
async def get_node_label(
        node_name: Optional[str] = None,
        region_code: Optional[str] = None,
        label_type: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询节点标签
    """
    region = region_repo.get_region_by_region_name(session, region_code)
    if not region:
        return JSONResponse(general_message(500, "not found region", "集群 {0} 不存在".format(region_code)), status_code=200)

    try:
        if label_type == "common_label":
            labels = remote_node_client_api.get_node_label(session, region_code, node_name)
        elif label_type == "vm_label":
            labels = remote_node_client_api.get_node_vm_label(session, region_code, node_name)
        else:
            return JSONResponse(general_message(500, "not found label_type", "标签类型错误"), status_code=200)
    except Exception as e:
        logger.error(e)
        return JSONResponse(general_message(500, "add node label error", "查询节点标签失败"), status_code=200)
    return JSONResponse(general_message(200, "success", "查询成功", list=labels), status_code=200)
