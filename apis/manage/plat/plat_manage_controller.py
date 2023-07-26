from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from models.market.models import CenterAppTag
from repository.application.app_repository import app_tag_repo
from repository.market.center_app_tag_repo import center_app_tag_repo
from schemas.app_model_tag import PutTagParam, DeleteTagParam, AddTagParam
from schemas.response import Response
from service.application_service import application_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/plat/query/apps", response_model=Response, name="平台查询应用")
async def get_plat_apps(
        current: int = Query(default=1, ge=1, le=9999),
        size: int = Query(default=10, ge=-1, le=999),
        team_code: Optional[str] = None,
        env_id: Optional[str] = None,
        project_id: Optional[str] = None,
        app_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    apps = application_service.get_apps_by_plat(session, team_code, env_id, project_id, app_name)
    start = (current - 1) * size
    end = current * size
    if start >= len(apps):
        start = len(apps) - 1
        end = len(apps) - 1
    result = general_message("0", "success", "获取成功", list=jsonable_encoder(apps[start:end]), total=len(apps))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.get("/plat/query/envs", response_model=Response, name="平台查询环境")
async def get_plat_envs(
        tenant_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    if tenant_id:
        envs = env_services.get_envs_by_tenant_id(session, tenant_id)
    else:
        envs = env_services.get_all_envs(session)
    result = general_message("0", "success", "获取成功", list=jsonable_encoder(envs))
    return JSONResponse(result, status_code=status.HTTP_200_OK)


@router.post("/plat/app-models/tag", response_model=Response, name="新增tag")
async def add_tag(
        add_tag_param: AddTagParam = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    新增 tag
    :param name: 标签名
    :param desc: 标签描述
    :param sn: 标签排序号
    """

    name = add_tag_param.name
    desc = add_tag_param.desc
    sn = add_tag_param.sn
    result = general_message("0", "success", "创建成功")
    if not name:
        return JSONResponse(general_message(400, "fail", "参数不正确"), status_code=400)
    if len(desc) > 255:
        return JSONResponse(general_message(400, "label desc too long", "标签描述信息长度不能超过255"), status_code=400)
    try:
        rst = app_tag_repo.create_tag(session, name, sn, desc)
        if not rst:
            result = general_message(400, "fail", "标签已存在")
    except Exception as e:
        logger.debug(e)
        result = general_message(400, "fail", "创建失败")
    code = result.get("code", 200)
    if code == "0":
        code = 200
    return JSONResponse(result, status_code=code)


@router.get("/plat/app-models/tag", response_model=Response, name="获取tag")
async def get_tag(
        name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    获取 tag
    :param name: 标签名
    """

    app_tag_list = app_tag_repo.get_tag(session, name)
    app_tags = jsonable_encoder(app_tag_list)
    for app_tag in app_tags:
        app_tag.update({"tag_id": app_tag["ID"]})
        app_tag.pop("ID")
    result = general_message("0", "success", "获取成功", list=app_tags)
    return JSONResponse(result, status_code=200)


@router.put("/plat/app-models/tag", response_model=Response, name="修改tag")
async def update_tag(
        put_tag_params: PutTagParam = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    修改 tag
    :param tag_id: 标签ID
    :param name: 标签名
    :param desc: 标签描述
    :param sn: 标签排序号
    """

    tag_id = put_tag_params.tag_id
    name = put_tag_params.name
    desc = put_tag_params.desc
    sn = put_tag_params.sn

    result = general_message("0", "success", "修改成功")
    if not name or not tag_id:
        return JSONResponse(general_message(400, "fail", "参数错误"), status_code=400)
    if len(desc) > 255:
        return JSONResponse(general_message(400, "label desc too long", "标签描述信息长度不能超过255"), status_code=400)
    try:
        app_tag_repo.update_tag(session, tag_id, name, sn, desc)
    except Exception as e:
        logger.debug(e)
        result = general_message(400, "fail", "修改失败")
    code = result.get("code", 200)
    if code == "0":
        code = 200
    return JSONResponse(result, status_code=code)


@router.delete("/plat/app-models/tag", response_model=Response, name="删除tag")
async def delete_tag(
        delete_tag_param: DeleteTagParam = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除 tag
    :param name: 标签名
    """
    name = delete_tag_param.name
    result = general_message("0", "success", "删除成功")
    if not name:
        return JSONResponse(general_message(400, "fail", "标签名不能为空"), status_code=400)
    try:
        app_tag_repo.delete_tag(session, name)
    except Exception as e:
        logger.debug(e)
        result = general_message(400, "fail", "删除失败")
    code = result.get("code", 200)
    if code == "0":
        code = 200
    return JSONResponse(result, status_code=code)
