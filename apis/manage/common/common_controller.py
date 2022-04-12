from typing import Any

# from PIL import Image, ImageDraw, ImageFont
from fastapi import APIRouter, Depends
from fastapi import UploadFile, File
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import JSONResponse

from core.utils.return_message import general_message
from core import deps
from database.session import SessionClass
from models.base.err_log import Errorlog
from repository.users.perms_repo import perms_repo
from schemas.response import Response
from schemas.wutong_errlog import ErrLogCreate
from service.upload_service import upload_service

router = APIRouter()


@router.post("/errlog", response_model=Response, name="错误日志")
async def create_error_log(
        *,
        params: ErrLogCreate,
        db: SessionClass = Depends(deps.get_session)
) -> Any:
    """
        :param params:
        :param db:
        :return:
        """
    logger.info("创建错误日志,params:{}", params)
    model = params.dict()
    add = Errorlog(**model)
    db.add(add)
    db.flush()

    return {
        "code": 200
    }


@router.post("/files/upload", response_model=Response, name="文件上传")
async def file_upload(file: UploadFile = File(...)) -> Any:
    """
    文件上传

    :param file:
    :return:
    """
    if not file:
        return general_message(400, "param error", "请指定需要上传的文件")
    # if file.spool_max_size > 1048576 * 2:
    #     return general_message(400, "file is too large", "图片大小不能超过2M")
    suffix = file.filename.split('.')[-1]
    file_url = await upload_service.upload_file(file, suffix)
    if not file_url:
        result = general_message(400, "upload file error", "上传失败")
    else:
        result = general_message(200, "file upload success", "上传成功", bean={"file_url": file_url})
    return JSONResponse(result, status_code=result["code"])


@router.get("/perms", response_model=Response, name="获取权限列表")
async def get_perms_info() -> Any:
    perms = perms_repo.get_perms_info()
    result = general_message(200, None, None, bean=jsonable_encoder(perms))
    return JSONResponse(result, status_code=200)
