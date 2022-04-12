from exceptions.main import AbortRequest
from models.component.models import TeamApplication
from repository.component.component_repo import service_source_repo
from service.application_service import application_service


class ComponentGroup(object):
    def __init__(self, enterprise_id, component_group: TeamApplication, version=None, need_save=True):
        self.enterprise_id = enterprise_id
        self.component_group = component_group
        self.app_id = self.component_group.service_group_id
        self.app_model_key = self.component_group.group_key
        self.upgrade_group_id = self.component_group.ID
        self.version = version if version else component_group.group_version
        self.need_save = need_save

    def app_template_source(self, session):
        """
        Optimization: the component group should save the source of the app template itself.
        """
        components = application_service.get_wutong_services(session, self.app_id, self.app_model_key, self.upgrade_group_id)
        if not components:
            raise AbortRequest("components not found", "找不到组件", status_code=404, error_code=404)
        component = components[0]
        component_source = service_source_repo.get_service_source(session, component.tenant_id, component.service_id)
        return component_source

    def is_install_from_cloud(self, session):
        source = self.app_template_source(session)
        return source.is_install_from_cloud()

    def save(self):
        if not self.need_save:
            return
        # session.add(self.component_group)
