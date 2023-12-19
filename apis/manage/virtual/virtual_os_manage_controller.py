from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.virtual.virtual_os_repo import virtual_os_repo
from schemas.response import Response
from schemas.virtual import CreateImageOSParam

router = APIRouter()


@router.post(
    "/plat/virtual/os",
    response_model=Response,
    name="创建虚拟机操作系统",
)
async def create_virtual_os(
        param: CreateImageOSParam = CreateImageOSParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    创建虚拟机操作系统
    """

    os_name = param.os_name
    logo = param.logo
    if not os_name:
        return JSONResponse(
            general_message(400, "param error", "操作系统名不能为空"), status_code=400
        )

    os_info = virtual_os_repo.get_os_info_by_os_name(session, os_name)
    if os_info:
        return JSONResponse(
            general_message(400, "os already exists", "操作系统已存在"), status_code=400
        )

    os_info = {
        "os_name": os_name,
        "logo": logo,
        "operator": user.nick_name,
    }
    try:
        virtual_os_repo.create_virtual_os(session, os_info)
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "create os error", "创建操作系统失败"), status_code=501
        )

    return JSONResponse(
        general_message(200, "create os success", "创建操作系统成功"), status_code=200
    )


@router.get(
    "/plat/virtual/os",
    response_model=Response,
    name="查询虚拟机操作系统",
)
async def get_virtual_os_info(
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    查询虚拟机操作系统
    """

    try:
        os_infos = virtual_os_repo.get_all_os_info(session)
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "create os error", "查询操作系统失败"), status_code=501
        )

    return JSONResponse(
        general_message(200, "create os success", "查询虚拟机操作系统成功", list=jsonable_encoder(os_infos)), status_code=200
    )


@router.delete(
    "/plat/virtual/os",
    response_model=Response,
    name="删除虚拟机操作系统",
)
async def delete_virtual_os(
        os_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    删除虚拟机操作系统
    """

    try:
        virtual_os_repo.delete_os_info_by_os_name(session, os_name)
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "delete os error", "删除操作系统失败"), status_code=501
        )

    return JSONResponse(
        general_message(200, "delete os success", "删除虚拟机操作系统成功"), status_code=200
    )
