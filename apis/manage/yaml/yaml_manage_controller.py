import os
from typing import Any, Optional
from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse
from core.utils.return_message import general_message
from schemas.response import Response

router = APIRouter()


@router.get("/teams/apps/yaml", response_model=Response, name="获取yaml内容")
async def get_yaml_data(
        yaml_dir: Optional[str] = None
) -> Any:
    yaml_file = open(yaml_dir, "r", encoding='utf-8')
    file_data = yaml_file.read()
    yaml_file.close()
    context = {"context": file_data}
    return JSONResponse(general_message(200, "success", msg_show="获取成功", bean=context), status_code=200)


@router.put("/teams/apps/yaml", response_model=Response, name="修改yaml内容")
async def put_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_dir = data.get("yaml_dir")
    context = data.get("context")
    if not context or not yaml_dir:
        return JSONResponse(general_message(400, "failed", msg_show="参数错误"), status_code=400)

    yaml_file = open(yaml_dir, "w", encoding='utf-8')
    yaml_file.write(context)
    yaml_file.close()
    return JSONResponse(general_message(200, "success", msg_show="修改成功"), status_code=200)


@router.post("/teams/apps/yaml", response_model=Response, name="添加yaml文件")
async def put_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_dir = data.get("yaml_dir")
    context = data.get("context")
    if not context or not yaml_dir:
        return JSONResponse(general_message(400, "failed", msg_show="参数错误"), status_code=400)

    yaml_file = open(yaml_dir, "w+", encoding='utf-8')
    yaml_file.write(context)
    yaml_file.close()
    return JSONResponse(general_message(200, "success", msg_show="添加成功"), status_code=200)


@router.delete("/teams/apps/yaml", response_model=Response, name="删除yaml文件")
async def put_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_dir = data.get("yaml_dir")
    try:
        os.remove(yaml_dir)
    except Exception as e:
        logger.exception(e)
        return JSONResponse(general_message(400, "failed", msg_show="删除失败"), status_code=400)
    return JSONResponse(general_message(200, "success", msg_show="删除成功"), status_code=200)
