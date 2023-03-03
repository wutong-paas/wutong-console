from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import  service_info_repo


class EnterpriseRepository:

    def get_enterprise_app_component_list(self, session, app_id, page=1, page_size=10):
        group_relation_services = app_component_relation_repo.get_services_by_group(session, app_id)
        if not group_relation_services:
            return [], 0
        service_ids = [group_relation_service.service_id for group_relation_service in group_relation_services]
        services = service_info_repo.list_by_component_ids(session, service_ids)
        return services[(page - 1) * page_size:page * page_size], len(services)

    def get_enterprise_app_list(self, session, tenant_ids, page=1, page_size=10):
        enterprise_apps = application_repo.get_groups_by_tenant_ids(session, tenant_ids)
        if not enterprise_apps:
            return [], 0
        return enterprise_apps[(page - 1) * page_size:page * page_size], len(enterprise_apps)


enterprise_repo = EnterpriseRepository()
