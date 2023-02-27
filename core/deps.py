from typing import Optional
from fastapi import Request, Header, Depends
from loguru import logger
from core.idaasapi import idaas_api
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.enterprise.enterprise_repo import enterprise_repo
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
        # user = {
        #     "user_id": data.get(b"userid"),
        #     "real_name": parse.unquote(str(data.get(b"userrealname"), "utf-8")),
        #     "nick_name": parse.unquote(str(data.get(b"usernickname"), "utf-8")),
        #     "email": data.get(b"useremail"),
        #     "phone": data.get(b"usermobile"),
        #     "enterprise_id": enterprise.enterprise_id
        # }
        user = {
            "user_id": "f75939fe51fa01980d7afd1e9cfb1d66",
            "real_name": "王少鹏",
            "nick_name": "王少鹏",
            "email": "wangshaopeng@talkweb.com.cn",
            "phone": "13787256706",
            "token": authorization,
            "enterprise_id": enterprise.enterprise_id
        }
        user = UserInfo(**user)
        return user
    except ServiceHandleException as token_err:
        logger.exception("ServiceHandleException", token_err)
        raise token_err
    except Exception as e:
        logger.exception("catch exception", e)


async def get_current_team(request: Request, team_name: str, session: SessionClass = Depends(get_session)):
    # team_repo
    logger.info("查询团队信息,团队名称:{}", team_name)
    if not team_name:
        raise ServiceHandleException(msg="team_name not found", msg_show="团队名称不存在")
    team_db = None
    if not team_db:
        logger.error("未找到团队信息,团队名称:{}", team_name)
        raise ServiceHandleException(msg="team not found", msg_show="团队不存在")
    return team_db
