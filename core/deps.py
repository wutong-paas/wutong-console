from typing import Optional
from fastapi import Request, Header, Depends
from loguru import logger
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import TeamEnvInfo
from repository.teams.env_repo import env_repo
from schemas.user import UserInfo


async def get_session() -> SessionClass:
    """
    get session
    """
    session = SessionClass()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.exception(e)
        session.rollback()
        raise
    finally:
        session.expunge_all()
        session.close()


async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> UserInfo:
    try:
        from urllib import parse
        data = dict(request.headers.raw)
        # user = {
        #     "user_id": str(data.get(b"userid"), "utf-8"),
        #     "user_name": str(data.get(b"username"), "utf-8"),
        #     "real_name": parse.unquote(str(data.get(b"userrealname", b''), "utf-8")),
        #     "nick_name": parse.unquote(str(data.get(b"usernickname"), "utf-8")),
        #     "email": str(data.get(b"useremail"), "utf-8"),
        #     "phone": str(data.get(b"usermobile", b''), "utf-8"),
        #     "token": authorization
        # }
        user = {
            "user_id": "1",
            "user_name": "zdl",
            "real_name": "zdl",
            "nick_name": "zdl",
            "email": "test",
            "phone": "1333333333",
            "token": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1aWQiOiI4MWYzMjhmMjU2NmM2NjViNGZmODZjMjM0YmMxMWU3NCIsInN1YiI6IjkwNTI4IiwiYXVkIjoidGVuYW50IiwidW5hbWUiOiI5MDUyOCIsImlzcyI6ImN1YmUiLCJybmQiOiI4endlNTdxMyIsImV4cCI6MTcwNDA2OTc0NiwiaWF0IjoxNzAzNDY0OTQ2fQ.iLdPCQXH22KCtOTJ4QTutLXCpPFW8R_esNsDPwW2prI"
        }
        user = UserInfo(**user)
        return user
    except ServiceHandleException as token_err:
        logger.exception("ServiceHandleException", token_err)
        raise token_err
    except Exception as e:
        logger.exception("catch exception", e)


async def get_current_team_env(
        env_id: Optional[str] = None,
        session: SessionClass = Depends(get_session)) -> TeamEnvInfo:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        raise ServiceHandleException(msg="not found env", msg_show="环境不存在", status_code=400)
    return env
