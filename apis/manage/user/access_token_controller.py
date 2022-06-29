import hashlib
import os
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from pymysql import IntegrityError

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.users.users import UserAccessKey
from repository.users.user_repo import user_access_key_repo
from schemas.response import Response
from schemas.user import CreateAccessTokenParam

router = APIRouter()


@router.get("/users/access-token", response_model=Response, name="访问令牌")
async def get_access_token_list(
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    access_key_dict = []
    access_key_list = user_access_key_repo.list_by_model(session=session,
                                                         query_model=UserAccessKey(user_id=user.user_id))
    for access_key in access_key_list:
        access_dict = jsonable_encoder(access_key)
        if access_dict["expire_time"]:
            time_array = time.strptime(access_dict["expire_time"], "%Y-%m-%dT%H:%M:%S")
            access_dict["expire_time"] = int(time.mktime(time_array))
        access_key_dict.append(access_dict)
    result = general_message(200, "success", None, list=access_key_dict)
    return JSONResponse(result, status_code=result["code"])


@router.post("/users/access-token", response_model=Response, name="颁发令牌")
async def create_access_token(
        params: Optional[CreateAccessTokenParam] = CreateAccessTokenParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    if not params.note:
        raise ServiceHandleException(msg="note can't be null", msg_show="注释不能为空")
    try:
        key = hashlib.sha1(os.urandom(24)).hexdigest()
        if params.age:
            expire_time = time.time() + float(params.age)
            tiem_struct = time.localtime(expire_time)
            expire_time = time.strftime("%Y-%m-%d %H:%M:%S", tiem_struct)
        else:
            expire_time = None
        add_model: UserAccessKey = UserAccessKey(note=params.note, user_id=user.user_id,
                                                 expire_time=expire_time, access_key=key)
        session.add(add_model)
        session.flush()
        return JSONResponse(general_message(200, None, None, bean=jsonable_encoder(add_model)), status_code=200)
    except ValueError as e:
        logger.exception(e)
        raise ServiceHandleException(msg="params error", msg_show="请检查参数是否合法")
    except IntegrityError:
        raise ServiceHandleException(msg="note duplicate", msg_show="令牌用途不能重复")


@router.get("/users/access-token/{token_id}", response_model=Response, name="访问令牌详情")
async def get_access_token_detail(session: SessionClass = Depends(deps.get_session),
                                  token_id: Optional[int] = None) -> Any:
    access_key = user_access_key_repo.get_by_primary_key(session=session, primary_key=token_id)
    if not access_key:
        return general_message(404, "no found access key", "未找到该凭证")
    return general_message(200, "success", None, bean=access_key)


@router.put("/users/access-token/{token_id}", response_model=Response, name="更新访问令牌")
async def update_access_token(session: SessionClass = Depends(deps.get_session), token_id: Optional[int] = None) -> Any:
    try:
        new_access_key = hashlib.sha1(os.urandom(24)).hexdigest()
        user_access_key = user_access_key_repo.get_by_primary_key(session=session, primary_key=token_id)
        if user_access_key:
            user_access_key.access_key = new_access_key
            session.merge(user_access_key)
    except IntegrityError as e:
        logger.exception(e)
        raise ServiceHandleException(msg="access key duplicate", msg_show="刷新失败，请重试")
    if not user_access_key:
        return general_message(404, "no found access key", "未找到该凭证")
    return general_message(200, "success", None, bean=jsonable_encoder(user_access_key))


@router.delete("/users/access-token/{token_id}", response_model=Response, name="删除访问令牌")
async def delete_access_token(session: SessionClass = Depends(deps.get_session), token_id: Optional[int] = None) -> Any:
    user_access_key_repo.delete_by_primary_key(session=session, primary_key=token_id)
    return general_message(200, "success", None)
