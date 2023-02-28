import json

from fastapi.encoders import jsonable_encoder

from clients.remote_app_client import remote_app_client
from exceptions.bcode import ErrThirdComponentStartFailed
from models.application.models import Application
from models.teams import TeamEnvInfo
from repository.component.service_config_repo import service_endpoints_repo
from repository.region.region_app_repo import region_app_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service


class HelmAppService(object):
    def list_components(self, session, tenant_env: TeamEnvInfo, region_name: str, user, app: Application):
        # list kubernetes service
        services = self.list_services(session, tenant_env, region_name, app.app_id)
        # list components
        components = application_service.list_components(session, app.app_id)
        components = [jsonable_encoder(cpt) for cpt in components]
        # relations between components and services
        relations = self._list_component_service_relations(session, [cpt["service_id"] for cpt in components])

        # create third components for services
        orphan_services = [service for service in services if service["service_name"] not in relations.values()]
        for service in orphan_services:
            service["namespace"] = tenant_env.tenant_id
        error = {}
        try:
            app_manage_service.create_third_components(session, tenant_env, region_name, user, app, "kubernetes", orphan_services)
        except ErrThirdComponentStartFailed as e:
            error["code"] = e.error_code
            error["msg"] = e.msg

        # list components again
        components = application_service.list_components(session, app.app_id)
        components = [jsonable_encoder(cpt) for cpt in components]
        self._merge_component_service(components, services, relations)
        return components, error

    @staticmethod
    def list_services(session, tenant_env, region_name, app_id):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        services = remote_app_client.list_app_services(session, region_name, tenant_env, region_app_id)
        return services if services else []

    @staticmethod
    def _list_component_service_relations(session, component_ids):
        endpoints = service_endpoints_repo.list_by_component_ids(session, component_ids)
        relations = {}
        for endpoint in endpoints:
            ep = json.loads(endpoint.endpoints_info)
            service_name = ep.get("serviceName")
            relations[endpoint.service_id] = service_name
        return relations

    @staticmethod
    def _merge_component_service(components, services, relations):
        services = {service["service_name"]: service for service in services}
        for component in components:
            service_name = relations.get(component["service_id"])
            if not service_name:
                continue
            component["service"] = services.get(service_name)


helm_app_service = HelmAppService()
