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

    def set_tenant_env_memory_limit(self, session, eid, region_id, tenant_env, limit):
        try:
            remote_build_client.set_tenant_env_limit_memory(session, eid, tenant_env, region_id, body=limit)
        except RegionApiBaseHttpClient.CallApiError as e:
            logger.exception(e)
            raise ServiceHandleException(status_code=500, msg="", msg_show="设置租户限额失败")

    def get_tenant_env_list_by_region(self, session, eid, region_id, page=1, page_size=10):
        teams = env_repo.get_team_by_enterprise_id(session, eid)
        team_maps = {}
        if teams:
            for team in teams:
                team_maps[team.tenant_id] = team
        res, body = remote_build_client.list_tenant_envs(session, eid, region_id, page, page_size)
        tenant_list = []
        total = 0
        if body.get("bean"):
            tenants = body.get("bean").get("list")
            total = body.get("bean").get("total")
            if tenants:
                for tenant in tenants:
                    tenant_alias = team_maps.get(tenant["UUID"]).tenant_alias if team_maps.get(tenant["UUID"]) else ''
                    tenant_list.append({
                        "tenant_id": tenant["UUID"],
                        "team_name": tenant_alias,
                        "tenant_name": tenant["Name"],
                        "memory_request": tenant["memory_request"],
                        "cpu_request": tenant["cpu_request"],
                        "memory_limit": tenant["memory_limit"],
                        "cpu_limit": tenant["cpu_limit"],
                        "running_app_num": tenant["running_app_num"],
                        "running_app_internal_num": tenant["running_app_internal_num"],
                        "running_app_third_num": tenant["running_app_third_num"],
                        "set_limit_memory": tenant["LimitMemory"],
                    })
        else:
            logger.error(body)
        return tenant_list, total

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

    def get_all_envs(self, session: SessionClass):
        envs = session.execute(
            select(TeamEnvInfo)).scalars().all()
        return envs

    def delete_by_env_id(self, session: SessionClass, user, env):
        env_regions = region_repo.get_env_regions_by_envid(session, env.env_id)
        for region in env_regions:
            try:
                region_services.delete_env_on_region(session=session, enterprise_id=env.enterprise_id,
                                                     env=env, region_name=region.region_name,
                                                     user=user)
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(
                    msg_show="{}集群自动卸载失败，请手动卸载后重新删除团队".format(region.region_name), msg="delete tenant failure")
        env_repo.delete_by_env_id(session=session, env_id=env.env_id)

    def get_tenant_by_tenant_name(self, session: SessionClass, tenant_name, exception=True):
        return env_repo.get_tenant_by_tenant_name(session=session, team_name=tenant_name, exception=exception)

    def check_and_get_user_team_by_name_and_region(self, session, user_id, tenant_name, region_name):
        tenant = env_repo.get_user_tenant_by_name(session, user_id, tenant_name)
        if not tenant:
            return tenant
        if not env_repo.get_team_region_by_name(session, tenant.tenant_id, region_name):
            return None
        else:
            return tenant


env_services = TenantEnvService()
