"""
tenant repository
"""
import random
import string
from loguru import logger
from sqlalchemy import select, delete
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.region.models import EnvRegionInfo
from models.teams import TeamEnvInfo, RegionConfig
from models.component.models import Component
from repository.base import BaseRepository


class EnvRepository(BaseRepository[TeamEnvInfo]):
    """
    TenantRepository
    """

    def get_all_envs(self, session):
        return session.execute(select(TeamEnvInfo)).scalars().all()

    def get_tenant_by_env_name(self, session: SessionClass, env_name, exception=True):
        """
        get_tenant_by_tenant_name

        :param session:
        :return:
        """
        logger.info("get_tenant_by_tenant_name,param:{}", env_name)
        env = session.execute(select(TeamEnvInfo).where(TeamEnvInfo.env_name == env_name)).scalars().first()
        if not env and exception:
            return None
        return env

    def get_env_by_env_id(self, session, env_id):
        return session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id)).scalars().first()

    def get_env_by_env_name(self, session, env_name):
        return session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_name == env_name)).scalars().first()

    def delete_by_env_id(self, session, env_id):
        row = session.execute(
            delete(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id))
        return row.rowcount > 0

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(Component).where(
            Component.service_id.in_(service_ids))).scalars().all()

    def save_tenant_service_info(self, session, ts):
        session.add(ts)
        session.flush()

    def env_is_exists_by_env_name(self, session, team_id, env_alias):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.env_alias == env_alias,
            TeamEnvInfo.tenant_id == team_id)).scalars().first()

    def env_is_exists_by_namespace(self, session, team_id, env_name):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.env_name == env_name,
            TeamEnvInfo.tenant_id == team_id)).scalars().first()

    def create_env(self, session, user, region_name, region_code, env_name, env_alias, team_id, team_name, namespace="",
                   desc=""):
        if not env_alias:
            env_alias = "{0}的环境".format(user.nick_name)
        params = {
            "env_name": env_name,
            "region_name": region_name,
            "region_code": region_code,
            "creater": user.user_id,
            "env_alias": env_alias,
            "limit_memory": 0,
            "namespace": namespace,
            "tenant_id": team_id,
            "tenant_name": team_name,
            "desc": desc
        }
        add_team = TeamEnvInfo(**params)
        session.add(add_team)
        session.flush()
        return add_team

    def get_team_by_env_name(self, session, env_name):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.env_name == env_name)).scalars().first()

    def get_region_alias(self, session, region_name):
        try:
            results = session.execute(select(RegionConfig).where(
                RegionConfig.region_name == region_name))
            region = results.scalars().all()
            if region:
                region = region[0]
                region_alias = region.region_alias
                return region_alias
            else:
                return None
        except Exception as e:
            logger.exception(e)
            return "测试Region"


env_repo = EnvRepository(TeamEnvInfo)
