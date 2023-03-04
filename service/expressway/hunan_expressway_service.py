from clients.remote_app_client import remote_app_client
from repository.expressway.hunan_expressway_repo import hunan_expressway_repo
from repository.region.region_app_repo import region_app_repo


class HunanExpresswayService(object):

    def get_all_app(self, session, region_name):
        return hunan_expressway_repo.get_all_app(session, region_name)

    def get_app_status(self, session, tenant_env, region_name, app_id):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        status = remote_app_client.get_app_status(session, region_name, tenant_env, region_app_id)
        if status.get("status") == "NIL":
            status["status"] = None
        overrides = status.get("overrides", [])
        if overrides:
            status["overrides"] = [{override.split("=")[0]: override.split("=")[1]} for override in overrides]
        return status

    def get_tenant_by_app_id(self, session, app_id):
        app = hunan_expressway_repo.get_app_by_app_id(session, app_id)
        tenant_env_id = app.tenant_env_id
        return hunan_expressway_repo.get_tenant_by_tenant_env_id(session, tenant_env_id)

    def get_groups_by_service_id(self, session, service_ids):
        return hunan_expressway_repo.get_groups_by_service_id(session, service_ids)

    def get_services_by_tenant_env_id(self, session, tenant_env_id):
        return hunan_expressway_repo.get_services_by_tenant_env_id(session, tenant_env_id)


hunan_expressway_service = HunanExpresswayService()
