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
from schemas.virtual import (CreateVirtualImageParam, UpdateVirtualImageParam)

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


@router.delete(
    "/plat/virtual/image",
    response_model=Response,
    name="删除虚拟机镜像",
)
async def delete_virtual_image(
        image_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    删除虚拟机镜像
    """
    if not image_name:
        return JSONResponse(
            general_message(400, "param error", "参数错误"), status_code=400
        )

    virtual_image_repo.delete_virtual_imagever_by_image_name(session, image_name)
    return JSONResponse(
        general_message(200, "create virtual machine success", "删除虚拟机镜像成功"),
        status_code=200
    )


@router.put(
    "/plat/virtual/image",
    response_model=Response,
    name="更新虚拟机镜像",
)
async def update_virtual_image(
        param: UpdateVirtualImageParam = UpdateVirtualImageParam(),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    更新虚拟机镜像
    """

    id_image = virtual_image_repo.get_virtual_imagever_by_id(session, param.image_id)
    name_image = virtual_image_repo.get_virtual_image_by_name(session, param.image_name)
    version_image = virtual_image_repo.get_virtual_image_by_os_name(session, id_image.os_name, param.version)
    if name_image and name_image.ID != id_image.ID:
        return JSONResponse(
            general_message(500, "image name is already exists", "镜像名称已存在"),
            status_code=501,
        )
    if version_image and version_image.ID != id_image.ID:
        return JSONResponse(
            general_message(500, "version is already exists", "镜像版本已存在"),
            status_code=501,
        )
    id_image.image_name = param.image_name
    id_image.image_type = param.image_type
    id_image.image_address = param.image_address
    id_image.version = param.version
    id_image.desc = param.desc

    return JSONResponse(
        general_message(200, "create virtual machine success", "更新虚拟机镜像成功"),
        status_code=200
    )


@router.get(
    "/virtual/image",
    response_model=Response,
    name="创建虚拟机获取虚拟机镜像地址",
)
async def create_virtual_image(
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    创建虚拟机获取虚拟机镜像地址
    """
    image_info = {}
    images = virtual_image_repo.get_all_virtual_image(session)
    os_names = [image.os_name for image in images]
    for os_name in os_names:

        image_info[os_name] = {}
        versions = virtual_image_repo.get_virtual_imagever_by_os_name(session, os_name)
        for version in versions:
            image = virtual_image_repo.get_virtual_image_by_os_name(session, os_name, version)
            image_info[os_name].update({version: image.image_address})

    return JSONResponse(
        general_message(200, "create virtual machine success", "获取虚拟机镜像成功", bean=image_info),
        status_code=200
    )
