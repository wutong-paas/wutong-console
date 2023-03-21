"""
env repository
"""
from loguru import logger
from sqlalchemy import select, delete
from clients.remote_build_client import remote_build_client
from models.teams import TeamEnvInfo, RegionConfig
from models.component.models import Component
from repository.base import BaseRepository


class EnvRepository(BaseRepository[TeamEnvInfo]):
    """
    TenantRepository
    """

    def get_envs_list_by_region(self, session, region_id, page=1, page_size=10):
        tenant_envs = self.get_all_envs(session)
        env_maps = {}
        if tenant_envs:
            for env in tenant_envs:
                env_maps[env.env_id] = env
        res, body = remote_build_client.list_envs(session, region_id, page, page_size)
        env_list = []
        total = 0
        if body.get("bean"):
            envs = body.get("bean").get("list")
            total = body.get("bean").get("total")
            if envs:
                for env in envs:
                    env_alias = env_maps.get(env["UUID"]).env_alias if env_maps.get(env["UUID"]) else ''
                    env_list.append({
                        "env_id": env["UUID"],
                        "env_name": env_alias,
                        "env_code": env["Name"],
                        "memory_request": env["memory_request"],
                        "cpu_request": env["cpu_request"],
                        "memory_limit": env["memory_limit"],
                        "cpu_limit": env["cpu_limit"],
                        "running_app_num": env["running_app_num"],
                        "running_app_internal_num": env["running_app_internal_num"],
                        "running_app_third_num": env["running_app_third_num"],
                        "set_limit_memory": env["LimitMemory"],
                    })
        else:
            logger.error(body)
        return env_list, total

    def get_all_envs(self, session):
        return session.execute(select(TeamEnvInfo)).scalars().all()

    def get_env_by_env_id(self, session, env_id, is_delete=False):
        return session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id,
                                      TeamEnvInfo.is_delete == is_delete)).scalars().first()

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

    def get_logic_delete_records(self, session, delete_date):
        return (
            session.execute(
                select(TeamEnvInfo).where(TeamEnvInfo.is_delete == True, TeamEnvInfo.delete_time < delete_date)
            )
        ).scalars().all()


env_repo = EnvRepository(TeamEnvInfo)
