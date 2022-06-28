from sqlalchemy import select, func

from exceptions.exceptions import UserRoleNotFoundException
from models.application.models import Application
from models.teams.enterprise import TeamEnterprise
from models.region.models import TeamRegionInfo
from models.teams import PermRelTenant, TeamInfo, Applicants
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import  service_info_repo
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo
from repository.users.user_role_repo import user_role_repo


class EnterpriseRepository:

    def get_enterprise_app_component_list(self, session, app_id, page=1, page_size=10):
        group_relation_services = app_component_relation_repo.get_services_by_group(session, app_id)
        if not group_relation_services:
            return [], 0
        service_ids = [group_relation_service.service_id for group_relation_service in group_relation_services]
        services = service_info_repo.list_by_component_ids(session, service_ids)
        return services[(page - 1) * page_size:page * page_size], len(services)

    def is_user_admin_in_enterprise(self, session, user, enterprise_id):
        """判断用户在该企业下是否为管理员"""
        if user.enterprise_id != enterprise_id:
            return False
        if not enterprise_user_perm_repo.is_admin(session, enterprise_id, user.user_id):
            users = user_repo.get_enterprise_users(session, enterprise_id)
            if users:
                admin_user = users[0]
                # 如果有，判断用户最开始注册的用户和当前用户是否为同一人，如果是，添加数据返回true
                if admin_user.user_id == user.user_id:
                    enterprise_user_perm_repo.create_enterprise_user_perm(session, user.user_id, enterprise_id, "admin")
                    return True
                else:
                    return False
        else:
            return True

    def get_enterprise_tenant_ids(self, session, enterprise_id, user=None):
        if user is None or self.is_user_admin_in_enterprise(session, user, enterprise_id):
            teams = session.execute(select(TeamInfo).where(
                TeamInfo.enterprise_id == enterprise_id)).scalars().all()
            if not teams:
                return None
            team_ids = [team.tenant_id for team in teams]
        else:
            enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
            if not enterprise:
                return None
            user_teams_perm = session.execute(select(PermRelTenant).where(
                PermRelTenant.enterprise_id == enterprise.ID,
                PermRelTenant.user_id == user.user_id)).scalars().all()
            if not user_teams_perm:
                return None
            tenant_auto_ids = [user_team.tenant_id for user_team in user_teams_perm]
            teams = session.execute(select(TeamInfo).where(
                TeamInfo.ID.in_(tenant_auto_ids))).scalars().all()
            if not teams:
                return None
            team_ids = [team.tenant_id for team in teams]
        tenants = session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id.in_(team_ids))).scalars().all()
        if not tenants:
            return None
        else:
            return [tenant.region_tenant_id for tenant in tenants]

    def get_enterprise_app_list(self, session, enterprise_id, user, page=1, page_size=10):
        tenant_ids = self.get_enterprise_tenant_ids(session, enterprise_id, user)
        if not tenant_ids:
            return [], 0
        enterprise_apps = application_repo.get_groups_by_tenant_ids(session, tenant_ids)
        if not enterprise_apps:
            return [], 0
        return enterprise_apps[(page - 1) * page_size:page * page_size], len(enterprise_apps)

    def get_enterprise_by_enterprise_id(self, session, enterprise_id):
        return session.execute(select(TeamEnterprise).where(
            TeamEnterprise.enterprise_id == enterprise_id)).scalars().first()

    def get_enterprise_first(self, session):
        q = session.execute(select(TeamEnterprise))
        return q.scalars().first()

    def get_enterprise_user_teams(self, session, enterprise_id, user_id, name=None):
        tenants = []
        result_enterprise = session.execute(select(TeamEnterprise).where(
            TeamEnterprise.enterprise_id == enterprise_id))

        enterprise = result_enterprise.scalars().first()

        if not enterprise:
            return enterprise

        result_tenant_ids = session.execute(
            select(PermRelTenant.tenant_id).where(
                PermRelTenant.enterprise_id == enterprise.ID,
                PermRelTenant.user_id == user_id).order_by(PermRelTenant.ID.desc())
        )
        tenant_ids = result_tenant_ids.scalars().all()
        tenant_ids = list(tenant_ids)
        tenant_ids = sorted(set(tenant_ids), key=tenant_ids.index)
        if name:
            for tenant_id in tenant_ids:
                result_tenant = session.execute(
                    select(TeamInfo).where(TeamInfo.ID == tenant_id, TeamInfo.tenant_alias.contains(name))
                )
                tn = result_tenant.scalars().first()
                if tn:
                    tenants.append(tn)
        else:
            for tenant_id in tenant_ids:
                result_tenant = session.execute(
                    select(TeamInfo).where(TeamInfo.ID == tenant_id)
                )
                tn = result_tenant.scalars().first()
                if tn:
                    tenants.append(tn)
        return tenants

    def get_enterprise_user_join_teams(self, session, enterprise_id, user_id):
        teams = self.get_enterprise_user_teams(session, enterprise_id, user_id)
        if not teams:
            return teams
        team_ids = [team.tenant_id for team in teams]
        result_applicants = session.execute(
            select(Applicants).where(Applicants.user_id == user_id,
                                     Applicants.is_pass == 1,
                                     Applicants.team_id.in_(team_ids)
                                     ).order_by(Applicants.apply_time.desc()))
        applicants = result_applicants.scalars().all()
        return applicants

    def get_enterprise_user_active_teams(self, session, enterprise_id, user_id):
        tenants = self.get_enterprise_user_teams(session, enterprise_id, user_id)
        if not tenants:
            return None
        active_tenants_list = []
        for tenant in tenants:
            role = None
            owner = None
            try:
                owner = user_repo.get_user_by_user_id(session, tenant.creater)
                role = user_role_repo.get_role_names(session=session, user_id=user_id, tenant_id=tenant.tenant_id)
            except UserRoleNotFoundException:
                if tenant.creater == user_id:
                    role = "owner"
            region_name_list = team_repo.get_team_region_names(session, tenant.tenant_id)
            if len(region_name_list) > 0:
                total = (session.execute(
                    select(func.count(Application.ID)).where(Application.tenant_id == tenant.tenant_id))).first()[0]
                team_item = {
                    "tenant_id": tenant.tenant_id,
                    "team_alias": tenant.tenant_alias,
                    "owner": tenant.creater,
                    "owner_name": owner.get_name() if owner else "",
                    "enterprise_id": tenant.enterprise_id,
                    "create_time": tenant.create_time,
                    "team_name": tenant.tenant_name,
                    "region": region_name_list if region_name_list else "",
                    "region_list": region_name_list,
                    "num": total,
                    "role": role
                }
                if not team_item["region"] and len(region_name_list) > 0:
                    team_item["region"] = region_name_list
                active_tenants_list.append(team_item)
        active_tenants_list.sort(key=lambda x: x["num"], reverse=True)
        active_tenants_list = active_tenants_list[:3]
        return active_tenants_list

    def get_enterprise_user_request_join(self, session, enterprise_id, user_id):
        team_ids = session.execute(
            select(TeamInfo.tenant_id).where(TeamInfo.enterprise_id == enterprise_id, TeamInfo.is_active == True).order_by(
                TeamInfo.create_time.desc())).scalars().all()
        data = session.execute(
                select(Applicants).where(Applicants.user_id == user_id, Applicants.team_id.in_(team_ids)).order_by(
                    Applicants.is_pass.asc(), Applicants.apply_time.desc())).scalars().all()
        return data

    def get_enterprise_teams(self, session, enterprise_id, name=None):
        if name:
            return (
                session.execute(
                    select(TeamInfo).where(TeamInfo.enterprise_id == enterprise_id, TeamInfo.is_active == True,
                                           TeamInfo.tenant_alias.contains(name)).order_by(TeamInfo.create_time.desc()))
            ).scalars().all()
        else:
            return (
                session.execute(
                    select(TeamInfo).where(TeamInfo.enterprise_id == enterprise_id, TeamInfo.is_active == True).order_by(
                        TeamInfo.create_time.desc()))
            ).scalars().all()


enterprise_repo = EnterpriseRepository()
