from fastapi_pagination import Params, paginate
from loguru import logger
from sqlalchemy import select, delete

from clients.remote_build_client import remote_build_client
from core.idaasapi import idaas_api
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import EnvInfo, PermRelTenant, UserRole
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from repository.users.role_repo import role_repo
from service.app_actions.app_deploy import RegionApiBaseHttpClient
from service.region_service import region_services


class EnvService(object):

    @staticmethod
    def check_resource_name(session, tenant_name: str, region_name: str, rtype: str, name: str):
        return remote_build_client.check_resource_name(session, tenant_name, region_name, rtype, name)

    def update_tenant_alias(self, session, tenant_name, new_team_alias):
        tenant = env_repo.get_tenant_by_tenant_name(session=session, team_name=tenant_name, exception=True)
        tenant.tenant_alias = new_team_alias
        return tenant

    def list_user_teams(self, session, enterprise_id, user, name):
        # User joined team
        teams = self.get_teams_region_by_user_id(session, enterprise_id, user, name, get_region=False)
        # The team that the user did not join
        user_id = user.user_id if user else ""
        nojoin_teams = env_repo.get_user_notjoin_teams(session, enterprise_id, user_id, name)
        for nojoin_team in nojoin_teams:
            team = self.team_with_region_info(session, nojoin_team, get_region=False)
            teams.append(team)
        return teams

    def set_tenant_memory_limit(self, session, eid, region_id, tenant_name, limit):
        try:
            remote_build_client.set_tenant_limit_memory(session, eid, tenant_name, region_id, body=limit)
        except RegionApiBaseHttpClient.CallApiError as e:
            logger.exception(e)
            raise ServiceHandleException(status_code=500, msg="", msg_show="设置租户限额失败")

    def get_tenant_list_by_region(self, session, eid, region_id, page=1, page_size=10):
        teams = env_repo.get_team_by_enterprise_id(session, eid)
        team_maps = {}
        if teams:
            for team in teams:
                team_maps[team.tenant_id] = team
        res, body = remote_build_client.list_tenants(session, eid, region_id, page, page_size)
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

    def get_teams_region_by_user_id(self, session: SessionClass, enterprise_id, user, name=None, get_region=True):
        teams_list = list()
        tenants = enterprise_repo.get_enterprise_user_teams(session, enterprise_id, user.user_id, name)
        if tenants:
            for tenant in tenants:
                team = self.env_with_region_info(session=session, env=tenant, request_user=user,
                                                  get_region=get_region)
                teams_list.append(team)
        return teams_list

    def env_with_region_info(self, session: SessionClass, env, request_user=None, get_region=True):
        user = idaas_api.get_user_info(env.creater)

        info = {
            "team_name": env.env_name,
            "team_alias": env.env_alias,
            "team_id": env.env_id,
            "create_time": env.create_time,
            "enterprise_id": env.enterprise_id,
            "owner": env.creater,
            "owner_name": user.nick_name,
            "namespace": env.namespace
        }

        if get_region:
            region_info_map = []
            region_name_list = env_repo.get_team_region_names(session, env.env_id)
            if region_name_list:
                region_infos = region_repo.get_region_by_region_names(session, region_name_list)
                if region_infos:
                    for region in region_infos:
                        region_info_map.append({"region_name": region.region_name, "region_alias": region.region_alias})
            info["region"] = region_info_map[0]["region_name"] if len(region_info_map) > 0 else ""
            info["region_list"] = region_info_map

        return info

    def devops_get_tenant(self, session, tenant_name):
        tenant = session.execute(
            select(EnvInfo).where(EnvInfo.tenant_name == tenant_name)).scalars().first()
        return tenant

    def get_env_by_env_id(self, session: SessionClass, env_id) -> EnvInfo:
        env = env_repo.get_env_by_env_id(session=session, env_id=env_id)
        return env

    def get_envs_by_tenant_name(self, session, tenant_name):
        envs = session.execute(
            select(EnvInfo).where(EnvInfo.tenant_name == tenant_name)).scalars().all()
        return envs

    def update_or_create(self, session: SessionClass, user_id, tenant_id, enterprise_id):
        perm_rel_tenant = session.execute(
            select(PermRelTenant).where(PermRelTenant.user_id == user_id,
                                        PermRelTenant.tenant_id == tenant_id,
                                        PermRelTenant.enterprise_id == enterprise_id))
        perm_rel_tenant = perm_rel_tenant.scalars().first()
        if not perm_rel_tenant:
            session.add(PermRelTenant(user_id=user_id, tenant_id=tenant_id, enterprise_id=enterprise_id))

    def get_enterprise_teams(self, session: SessionClass, enterprise_id, query=None, page=None, page_size=None,
                             user=None):
        tall = env_repo.get_teams_by_enterprise_id(session, enterprise_id, query=query)
        total = len(tall)
        if page is not None and page_size is not None:
            if page_size > 100:
                page_size = 100
            params = Params(page=page, size=page_size)
            pg = paginate(tall, params)
            total = pg.total
            raw_tenants = pg.items
        else:
            raw_tenants = tall
        tenants = []
        for tenant in raw_tenants:
            tenants.append(self.env_with_region_info(session=session, env=tenant, request_user=user))
        return tenants, total

    def get_enterprise_tenant_by_tenant_name(self, session: SessionClass, enterprise_id, tenant_name):
        return (session.execute(
            select(EnvInfo).where(EnvInfo.tenant_name == tenant_name,
                                  EnvInfo.enterprise_id == enterprise_id))).scalars().first()

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

    def get_not_join_users(self, session: SessionClass, enterprise, tenant, query):
        return env_repo.get_not_join_users(session, enterprise, tenant, query)

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


env_services = EnvService()
