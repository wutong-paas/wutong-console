import pickle
from typing import Optional

from fastapi import Request, Header, Depends
from jose import jwt
from loguru import logger

from core.setting import settings
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import TeamInfo
from models.users.users import Users
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo


async def get_session() -> SessionClass:
    """
    get session
    """
    session = SessionClass()
    try:
        yield session
        session.commit()
        session.expunge_all()
    except Exception as e:
        logger.exception(e)
        session.rollback()
        raise
    finally:
        session.close()


async def get_current_user(request: Request, authorization: Optional[str] = Header(None),
                           session: SessionClass = Depends(get_session)) -> Users:
    try:
        logger.info("token:{}", authorization)
        if not authorization:
            raise ServiceHandleException(msg="parse token failed", msg_show="访问令牌解析失败")
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        result = request.app.state.redis.get("user_" + str(payload["user_id"]))
        if not result:
            user = user_repo.get_by_primary_key(session=session, primary_key=payload["user_id"])
            if user:
                request.app.state.redis.set("user_%d" % user.user_id, pickle.dumps(user), settings.REDIS_CACHE_TTL)
        else:
            user = pickle.loads(result)
        return user
    except ServiceHandleException as token_err:
        logger.exception("ServiceHandleException", token_err)
        raise token_err
    except Exception as e:
        logger.exception("catch exception", e)


async def get_current_team(request: Request, team_name: str, session: SessionClass = Depends(get_session)) -> TeamInfo:
    # team_repo
    logger.info("查询团队信息,团队名称:{}", team_name)
    if not team_name:
        raise ServiceHandleException(msg="team_name not found", msg_show="团队名称不存在")
    team_cache = request.app.state.redis.get("team_%s" % team_name)
    if not team_cache:
        team_db = team_repo.get_one_by_model(session=session, query_model=TeamInfo(tenant_name=team_name))
        if not team_db:
            logger.error("未找到团队信息,团队名称:{}", team_name)
            raise ServiceHandleException(msg="team not found", msg_show="团队不存在")
        request.app.state.redis.set("team_%s" % team_name, pickle.dumps(team_db), settings.REDIS_CACHE_TTL)
        return team_db
    team_cache_info = pickle.loads(team_cache)
    return team_cache_info
