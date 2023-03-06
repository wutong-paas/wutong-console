from loguru import logger
from sqlalchemy import select
from clients.remote_build_client import remote_build_client
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import TeamEnvInfo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from service.app_actions.app_deploy import RegionApiBaseHttpClient
from service.region_service import region_services


class TenantEnvService(object):

    @staticmethod
    def check_resource_name(session, tenant_env, region_name: str, rtype: str, name: str):
        return remote_build_client.check_resource_name(session, tenant_env, region_name, rtype, name)

    def set_tenant_env_memory_limit(self, session, region_id, tenant_env, limit):
        try:
            remote_build_client.set_tenant_env_limit_memory(session, tenant_env, region_id, body=limit)
        except RegionApiBaseHttpClient.CallApiError as e:
            logger.exception(e)
            raise ServiceHandleException(status_code=500, msg="", msg_show="设置租户限额失败")

    def get_tenant_env_list_by_region(self, session, region_id, page=1, page_size=10):
        envs = env_repo.get_all_envs(session)
        env_maps = {}
        if envs:
            for env in envs:
                env_maps[env.env_id] = env
        res, body = remote_build_client.list_tenant_envs(session, region_id, page, page_size)
        env_list = []
        total = 0
        if body.get("bean"):
            region_envs = body.get("bean").get("list")
            total = body.get("bean").get("total")
            if region_envs:
                for env in region_envs:
                    env_alias = env_maps.get(env["UUID"]).tenant_alias if env_maps.get(env["UUID"]) else ''
                    env_list.append({
                        "tenant_env_id": env["UUID"],
                        "env_alias": env_alias,
                        "env_name": env["Name"],
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

    def devops_get_tenant(self, session, tenant_name):
        tenant = session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == tenant_name)).scalars().first()
        return tenant

    def get_env_by_env_id(self, session: SessionClass, env_id) -> TeamEnvInfo:
        env = env_repo.get_env_by_env_id(session=session, env_id=env_id)
        return env

    def get_env_by_env_name(self, session: SessionClass, env_name) -> TeamEnvInfo:
        env = env_repo.get_env_by_env_name(session=session, env_name=env_name)
        return env

    def get_envs_by_tenant_name(self, session, tenant_name):
        envs = session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == tenant_name)).scalars().all()
        return envs

    def get_envs_by_tenant_env_id(self, session, tenant_env_id):
        envs = session.execute(
            select(TeamEnvInfo).where(
                TeamEnvInfo.env_id == tenant_env_id)).scalars().all()
        return envs

    def get_all_envs(self, session: SessionClass):
        envs = session.execute(
            select(TeamEnvInfo)).scalars().all()
        return envs

    def delete_by_env_id(self, session: SessionClass, user, env):
        env_regions = region_repo.get_env_regions_by_envid(session, env.env_id)
        for region in env_regions:
            try:
                region_services.delete_env_on_region(session=session,
                                                     env=env, region_name=region.region_name,
                                                     user=user)
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(
                    msg_show="{}集群自动卸载失败，请手动卸载后重新删除团队".format(region.region_name), msg="delete tenant failure")
        env_repo.delete_by_env_id(session=session, env_id=env.env_id)

    def check_and_get_user_team_by_name_and_region(self, session, env_name, region_name):
        tenant_env = env_repo.get_env_by_env_name(session, env_name)
        if not tenant_env:
            return tenant_env
        if not env_repo.get_team_region_by_name(session, tenant_env.env_id, region_name):
            return None
        else:
            return tenant_env


env_services = TenantEnvService()
