from sqlalchemy import select
from core.idaasapi import idaas_api
from models.teams.enterprise import TeamEnterprise
from models.teams import PermRelTenant, TeamEnvInfo
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import  service_info_repo
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo


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
            users = idaas_api.get_all_user_infos()
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

    def get_enterprise_app_list(self, session, tenant_ids, page=1, page_size=10):
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
                    select(TeamEnvInfo).where(TeamEnvInfo.ID == tenant_id, TeamEnvInfo.tenant_alias.contains(name))
                )
                tn = result_tenant.scalars().first()
                if tn:
                    tenants.append(tn)
        else:
            for tenant_id in tenant_ids:
                result_tenant = session.execute(
                    select(TeamEnvInfo).where(TeamEnvInfo.ID == tenant_id)
                )
                tn = result_tenant.scalars().first()
                if tn:
                    tenants.append(tn)
        return tenants


enterprise_repo = EnterpriseRepository()
