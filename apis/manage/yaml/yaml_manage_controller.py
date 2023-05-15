import os
from typing import Any, Optional

from fastapi import APIRouter, Request, UploadFile, File
from loguru import logger
from starlette.responses import JSONResponse

from core.setting import settings
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from schemas.response import Response
from service.upload_service import upload_service

router = APIRouter()


@router.post("/yaml-files/upload", response_model=Response, name="文件上传")
async def file_upload(file: UploadFile = File(...)) -> Any:
    """
    文件上传

    :param file:
    :return:
    """
    if not file:
        return JSONResponse(general_message(400, "param error", "请指定需要上传的文件"), status_code=400)
    suffix = file.filename.split('.')[-1]
    file_url = await upload_service.upload_yaml_file(file, suffix)

    if not file_url:
        result = general_message(400, "upload file error", "上传失败")
    else:
        result = general_message("0", "file upload success", "上传成功", bean={"file_url": file_url})
    return JSONResponse(result, status_code=200)


@router.get("/teams/apps/yaml", response_model=Response, name="获取yaml内容")
async def get_yaml_data(
        yaml_name: Optional[str] = None
) -> Any:
    filename = 'yamls/{0}'.format(yaml_name)
    save_filename = os.path.join(settings.YAML_ROOT, filename)
    yaml_file = open(save_filename, "r", encoding='utf-8')
    file_data = yaml_file.read()
    yaml_file.close()
    context = {"context": file_data}
    return JSONResponse(general_message(200, "success", msg_show="获取成功", bean=context), status_code=200)


@router.put("/teams/apps/yaml", response_model=Response, name="修改yaml内容")
async def put_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_name = data.get("yaml_name")
    context = data.get("context")
    if not context or not yaml_name:
        return JSONResponse(general_message(400, "failed", msg_show="参数错误"), status_code=400)

    filename = 'yamls/{0}'.format(yaml_name)
    save_filename = os.path.join(settings.YAML_ROOT, filename)
    with open(save_filename, "w", encoding='utf-8') as file:
        file.write(context)
        file.close()
    return JSONResponse(general_message(200, "success", msg_show="修改成功"), status_code=200)


@router.post("/teams/apps/yaml", response_model=Response, name="添加yaml文件")
async def add_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_name = data.get("yaml_name")
    context = data.get("context")
    if not context or not yaml_name:
        return JSONResponse(general_message(400, "failed", msg_show="参数错误"), status_code=400)

    filename = 'yamls/{0}.{1}'.format(make_uuid(), "yaml")
    save_filename = os.path.join(settings.YAML_ROOT, filename)
    query_filename = os.path.join(settings.YAML_URL, filename)
    yaml_file = open(save_filename, "w+", encoding='utf-8')
    yaml_file.write(context)
    yaml_file.close()
    return JSONResponse(general_message(200, "success", msg_show="添加成功", bean={"file_url": query_filename}), status_code=200)


@router.delete("/teams/apps/yaml", response_model=Response, name="删除yaml文件")
async def delete_yaml_data(
        request: Request
) -> Any:
    data = await request.json()
    yaml_name = data.get("yaml_name")
    try:
        filename = 'yamls/{0}'.format(yaml_name)
        save_filename = os.path.join(settings.YAML_ROOT, filename)
        os.remove(save_filename)
    except Exception as e:
        logger.exception(e)
        return JSONResponse(general_message(400, "failed", msg_show="删除失败"), status_code=400)
    return JSONResponse(general_message(200, "success", msg_show="删除成功"), status_code=200)
