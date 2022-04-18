from fastapi_pagination import Params, paginate
from loguru import logger
from sqlalchemy import select, delete

from clients.remote_build_client import remote_build_client
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import TeamInfo, PermRelTenant, UserRole
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_repo import team_repo
from repository.users.role_repo import role_repo
from repository.users.user_role_repo import user_role_repo
from repository.users.user_repo import user_repo
from service.app_actions.app_deploy import RegionApiBaseHttpClient
from service.region_service import region_services


class TeamService(object):

    def list_user_teams(self, session, enterprise_id, user, name):
        # User joined team
        teams = self.get_teams_region_by_user_id(session, enterprise_id, user, name, get_region=False)
        # The team that the user did not join
        user_id = user.user_id if user else ""
        nojoin_teams = team_repo.get_user_notjoin_teams(session, enterprise_id, user_id, name)
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
        teams = team_repo.get_team_by_enterprise_id(session, eid)
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
                team = self.team_with_region_info(session=session, tenant=tenant, request_user=user,
                                                  get_region=get_region)
                teams_list.append(team)
        return teams_list

    def team_with_region_info(self, session: SessionClass, tenant, request_user=None, get_region=True):
        user = user_repo.get_user_by_user_id(session=session, user_id=tenant.creater)
        owner_name = user.get_name()

        info = {
            "team_name": tenant.tenant_name,
            "team_alias": tenant.tenant_alias,
            "team_id": tenant.tenant_id,
            "create_time": tenant.create_time,
            "enterprise_id": tenant.enterprise_id,
            "owner": tenant.creater,
            "owner_name": owner_name,
        }

        if request_user:
            user_role_list = user_role_repo.get_user_roles(session=session, kind="team", kind_id=tenant.tenant_id,
                                                           user=request_user)
            roles = [x["role_name"] for x in user_role_list["roles"]]
            if tenant.creater == request_user.user_id:
                roles.append("owner")
            info["roles"] = roles

        if get_region:
            region_info_map = []
            region_name_list = team_repo.get_team_region_names(session, tenant.tenant_id)
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
            select(TeamInfo).where(TeamInfo.tenant_name == tenant_name)).scalars().first()
        return tenant

    def get_team_by_team_id(self, session: SessionClass, team_id):
        team = team_repo.get_team_by_team_id(session=session, team_id=team_id)
        if team:
            user = user_repo.get_user_by_user_id(session=session, user_id=team.creater)
            team.creater_name = user.get_name()
        return team

    def update_or_create(self, session: SessionClass, user_id, tenant_id, enterprise_id):
        perm_rel_tenant = session.execute(
            select(PermRelTenant).where(PermRelTenant.user_id == user_id,
                                        PermRelTenant.tenant_id == tenant_id,
                                        PermRelTenant.enterprise_id == enterprise_id))
        perm_rel_tenant = perm_rel_tenant.scalars().first()
        if not perm_rel_tenant:
            session.add(PermRelTenant(user_id=user_id, tenant_id=tenant_id, enterprise_id=enterprise_id))

    def add_user_role_to_team(self, session: SessionClass, tenant, user_ids, role_ids):
        """在团队中添加一个用户并给用户分配一个角色"""
        enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session=session,
                                                                     enterprise_id=tenant.enterprise_id)
        if enterprise:
            for user_id in user_ids:
                # for role_id in role_ids:
                user = user_repo.get_user_by_user_id(session=session, user_id=user_id)
                user_role_repo.update_user_roles(session=session,
                                                 kind="team",
                                                 kind_id=tenant.tenant_id,
                                                 user=user,
                                                 role_ids=role_ids)
                self.update_or_create(session=session, user_id=user_id, tenant_id=tenant.ID,
                                      enterprise_id=enterprise.ID)

    def user_is_exist_in_team(self, session: SessionClass, user_list, tenant_name):
        """判断一个用户是否存在于一个团队中"""
        team = team_repo.get_one_by_model(session=session, query_model=TeamInfo(tenant_name=tenant_name))
        if not team:
            team = self.get_team_by_team_id(session=session, team_id=tenant_name)
            if team is None:
                return None
        enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session=session,
                                                                     enterprise_id=team.enterprise_id)
        for user_id in user_list:
            obj = session.execute(
                select(PermRelTenant).where(PermRelTenant.user_id == user_id,
                                            PermRelTenant.tenant_id == team.ID,
                                            PermRelTenant.enterprise_id == enterprise.ID))
            obj = obj.scalars().first()
            if obj:
                return obj.user_id
        return False

    def batch_delete_users(self, request, session: SessionClass, tenant_name, user_id_list):
        team = team_repo.get_one_by_model(session=session, query_model=TeamInfo(tenant_name=tenant_name))
        if not team:
            team = team_services.get_team_by_team_id(session=session, team_id=tenant_name)
        if not team:
            raise ServiceHandleException(msg="team not exist", msg_show="{}团队不存在".format(tenant_name))

        session.execute(
            delete(PermRelTenant).where(PermRelTenant.user_id.in_(user_id_list),
                                        PermRelTenant.tenant_id == team.ID))

        role_ids = []
        roles = role_repo.get_roles_by_kind(session=session, kind="team", kind_id=team.tenant_id)
        if roles:
            for rw in roles:
                role_ids.append(rw.ID)

            session.execute(
                delete(UserRole).where(UserRole.user_id.in_(user_id_list),
                                       UserRole.role_id.in_(role_ids)))

    def get_team_users(self, session: SessionClass, team, name=None):
        users = team_repo.get_tenant_users_by_tenant_ID(session, team.ID)
        if users and name:
            users = team_repo.get_tenant_users_by_tenant_ID_name(session, team.ID, name)
        return users

    def get_enterprise_teams(self, session: SessionClass, enterprise_id, query=None, page=None, page_size=None,
                             user=None):
        tall = team_repo.get_teams_by_enterprise_id(session, enterprise_id, query=query)
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
            tenants.append(self.team_with_region_info(session=session, tenant=tenant, request_user=user))
        return tenants, total

    def get_enterprise_tenant_by_tenant_name(self, session: SessionClass, enterprise_id, tenant_name):
        return (session.execute(
            select(TeamInfo).where(TeamInfo.tenant_name == tenant_name,
                                   TeamInfo.enterprise_id == enterprise_id))).scalars().first()

    def add_user_to_team(self, session: SessionClass, tenant, user_id, role_ids=None):
        user = user_repo.get_user_by_user_id(session=session, user_id=user_id)
        if not user:
            raise ServiceHandleException(msg="user not found", msg_show="用户不存在", status_code=404)
        exist_team_user = (session.execute(
            select(PermRelTenant).where(PermRelTenant.user_id == user.user_id,
                                        PermRelTenant.tenant_id == tenant.ID))).scalars().first()
        enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session=session,
                                                                     enterprise_id=tenant.enterprise_id)
        if exist_team_user:
            raise ServiceHandleException(msg="user exist", msg_show="用户已经加入此团队", status_code=400)
        session.add(PermRelTenant(tenant_id=tenant.ID, user_id=user.user_id,
                                  identity="", enterprise_id=enterprise.ID))

        if role_ids:
            user_role_repo.update_user_roles(session=session, kind="team", kind_id=tenant.tenant_id, user=user,
                                             role_ids=role_ids)

    def delete_by_tenant_id(self, session: SessionClass, user, tenant):
        tenant_regions = region_repo.get_tenant_regions_by_teamid(session, tenant.tenant_id)
        for region in tenant_regions:
            try:
                region_services.delete_tenant_on_region(session=session, enterprise_id=tenant.enterprise_id,
                                                        team_name=tenant.tenant_name, region_name=region.region_name,
                                                        user=user)
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(
                    msg_show="{}集群自动卸载失败，请手动卸载后重新删除团队".format(region.region_name), msg="delete tenant failure")
        team_repo.delete_by_tenant_id(session=session, tenant_id=tenant.tenant_id)

    def get_not_join_users(self, session: SessionClass, enterprise, tenant, query):
        return team_repo.get_not_join_users(session, enterprise, tenant, query)

    def get_tenant_by_tenant_name(self, session: SessionClass, tenant_name, exception=True):
        return team_repo.get_tenant_by_tenant_name(session=session, team_name=tenant_name, exception=exception)

    def exit_current_team(self, session: SessionClass, team_name, user_id):
        # s_id = transaction.savepoint()
        try:
            tenant = self.get_tenant_by_tenant_name(session=session, tenant_name=team_name)
            team_repo.delete_user_perms_in_permtenant(session=session, user_id=user_id, tenant_id=tenant.ID)
            user = user_repo.get_by_primary_key(session=session, primary_key=user_id)
            user_role_repo.delete_user_roles(session=session, kind="team", kind_id=tenant.tenant_id, user=user)
            # transaction.savepoint_commit(s_id)
            return 200, "退出团队成功"
        except Exception as e:
            logger.exception(e)
            # transaction.savepoint_rollback(s_id)
            return 400, "退出团队失败"

    def check_and_get_user_team_by_name_and_region(self, session, user_id, tenant_name, region_name):
        tenant = team_repo.get_user_tenant_by_name(session, user_id, tenant_name)
        if not tenant:
            return tenant
        if not team_repo.get_team_region_by_name(session, tenant.tenant_id, region_name):
            return None
        else:
            return tenant


team_services = TeamService()
