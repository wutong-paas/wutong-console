from typing import Optional
from fastapi import Request, Header, Depends
from loguru import logger
from core.idaasapi import idaas_api
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import TeamEnvInfo
from repository.enterprise.enterprise_repo import enterprise_repo
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


async def get_current_user(request: Request, authorization: Optional[str] = Header(None),
                           session: SessionClass = Depends(get_session)):
    try:
        idaas_api.set_token(authorization)
        from urllib import parse
        data = dict(request.headers.raw)
        enterprise = enterprise_repo.get_enterprise_first(session)
        user = {
            "user_id": data.get(b"userid"),
            "real_name": parse.unquote(str(data.get(b"userrealname"), "utf-8")),
            "nick_name": parse.unquote(str(data.get(b"usernickname"), "utf-8")),
            "email": data.get(b"useremail"),
            "phone": data.get(b"usermobile"),
            "enterprise_id": enterprise.enterprise_id
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
