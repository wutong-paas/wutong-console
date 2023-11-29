from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import JSONResponse

from clients.remote_virtual_client import remote_virtual_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.team_region_repo import team_region_repo
from repository.virtual.virtual_image_repo import virtual_image_repo
from schemas.response import Response
from schemas.virtual import (CreateVirtualImageParam)

router = APIRouter()


@router.post(
    "/plat/virtual/image",
    response_model=Response,
    name="创建虚拟机镜像",
)
async def create_virtual_image(
        param: CreateVirtualImageParam = CreateVirtualImageParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    创建虚拟机镜像
    """

    if not param.image_name or not param.image_address or not param.os_name or not param.version \
            or not param.image_type:
        return JSONResponse(
            general_message(400, "param error", "参数错误"), status_code=400
        )

    image = virtual_image_repo.get_virtual_image_by_name(session, param.image_name)
    if image:
        return JSONResponse(
            general_message(500, "image name is already exists", "镜像名称已存在"),
            status_code=501,
        )

    image_info = {
        "image_name": param.image_name,
        "image_type": param.image_type,
        "image_address": param.image_address,
        "os_name": param.os_name,
        "version": param.version,
        "desc": param.desc,
        "operator": user.nick_name
    }

    try:
        virtual_image_repo.create_virtual_image(session, image_info)
    except Exception as err:
        logger.error(err)
        return JSONResponse(
            general_message(500, "create virtual machine success", "创建虚拟机镜像失败"),
            status_code=501,
        )

    return JSONResponse(
        general_message(200, "create virtual machine success", "创建虚拟机镜像成功"),
        status_code=200,
    )


@router.get(
    "/plat/virtual/image",
    response_model=Response,
    name="获取虚拟机镜像",
)
async def create_virtual_image(
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    获取虚拟机镜像
    """
    images = virtual_image_repo.get_all_virtual_image(session)
    return JSONResponse(
        general_message(200, "create virtual machine success", "获取虚拟机镜像成功", list=jsonable_encoder(images)),
        status_code=200
    )
