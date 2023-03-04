# -*- coding: utf8 -*-
from models.application.models import Application
from models.teams import RegionConfig
from repository.application.application_repo import application_repo
from repository.application.config_group_repo import app_config_group_item_repo, app_config_group_service_repo
from repository.component.component_repo import service_source_repo
from repository.component.graph_repo import component_graph_repo
from repository.component.service_config_repo import dep_relation_repo, port_repo, volume_repo, \
    mnt_repo, app_config_group_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_label_repo import label_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo, service_plugin_config_repo
from repository.teams.team_service_env_var_repo import env_var_repo
from service.app_config.service_monitor_service import service_monitor_service
from service.application_service import application_service
from service.market_app.component import Component


class OriginalApp(object):
    def __init__(self, session, tenant, region: RegionConfig, app: Application, upgrade_group_id, support_labels=None):
        self.tenant = tenant
        self.tenant_env_id = tenant.tenant_env_id
        self.region = region
        self.region_name = region.region_name
        self.app_id = app.app_id
        self.upgrade_group_id = upgrade_group_id
        self.app = application_repo.get_by_primary_key(session=session, primary_key=app.app_id)
        self.governance_mode = app.governance_mode

        self.support_labels = support_labels

        self._component_ids = self._component_ids(session)
        self._components = self._create_components(session, app.app_id, upgrade_group_id)

        # dependency
        component_deps = dep_relation_repo.list_by_component_ids(session,
                                                                 self.tenant_env_id,
                                                                 [cpt.component.component_id for cpt in
                                                                  self._components])
        self.component_deps = list(component_deps) if component_deps else []
        self.volume_deps = self._volume_deps(session)

        # plugins
        self.plugin_deps = self._plugin_deps(session)
        self.plugin_configs = self._plugin_configs(session)

        # config groups
        self.config_groups = self._config_groups(session)
        self.config_group_items = self._config_group_items(session)
        self.config_group_components = self._config_group_components(session)

        # labels
        self.labels = list(label_repo.get_all_labels(session))

    def components(self):
        return self._components

    def _component_ids(self, session):
        components = application_service.list_components_by_upgrade_group_id(session, self.app_id,
                                                                             self.upgrade_group_id)
        return [cpt.component_id for cpt in components]

    def _create_components(self, session, app_id, upgrade_group_id):
        components = application_service.list_components_by_upgrade_group_id(session, app_id, upgrade_group_id)
        component_ids = [cpt.component_id for cpt in components]

        http_rules = self._list_http_rules(session, component_ids)
        tcp_rules = self._list_tcp_rules(session, component_ids)

        result = []
        for cpt in components:
            component_source = service_source_repo.get_service_source(session, cpt.tenant_env_id, cpt.service_id)
            envs = env_var_repo.get_service_env(session, cpt.tenant_env_id, cpt.service_id)
            ports = port_repo.get_service_ports(session, cpt.tenant_env_id, cpt.service_id)
            volumes = volume_repo.get_service_volumes_with_config_file(session, cpt.service_id)
            config_files = volume_repo.get_service_config_files(session, cpt.service_id)
            probes = probe_repo.list_probes(session, cpt.service_id)
            monitors = service_monitor_service.list_by_service_ids(session, cpt.tenant_env_id, [cpt.service_id])
            graphs = component_graph_repo.list(session, cpt.service_id)
            plugin_deps = app_plugin_relation_repo.list_by_component_ids(session, [cpt.service_id])
            component = Component(
                cpt,
                component_source,
                envs,
                ports,
                volumes,
                config_files,
                probes,
                None,
                monitors,
                graphs,
                plugin_deps,
                http_rules=http_rules.get(cpt.component_id),
                tcp_rules=tcp_rules.get(cpt.component_id),
                support_labels=self.support_labels)
            result.append(component)
        return result

    @staticmethod
    def _list_http_rules(session, component_ids):
        http_rules = domain_repo.list_by_component_ids(session, component_ids)
        result = {}
        for rule in http_rules:
            rules = result.get(rule.service_id, [])
            rules.append(rule)
            result[rule.service_id] = rules
        return result

    @staticmethod
    def _list_tcp_rules(session, component_ids):
        tcp_rules = tcp_domain_repo.list_by_component_ids(session, component_ids)
        result = {}
        for rule in tcp_rules:
            rules = result.get(rule.service_id, [])
            rules.append(rule)
            result[rule.service_id] = rules
        return result

    def _volume_deps(self, session):
        component_ids = [cpt.component.component_id for cpt in self._components]
        return list(mnt_repo.list_mnt_relations_by_service_ids(session, self.tenant_env_id, component_ids))

    def _config_groups(self, session):
        return list(app_config_group_repo.list(session, self.region_name, self.app_id))

    def _config_group_items(self, session):
        return list(app_config_group_item_repo.list_by_app_id(session, self.app_id))

    def _config_group_components(self, session):
        return list(app_config_group_service_repo.list_by_app_id(session, self.app_id))

    def _plugin_deps(self, session):
        return app_plugin_relation_repo.list_by_component_ids(session, self._component_ids)

    def _plugin_configs(self, session):
        return service_plugin_config_repo.list_by_component_ids(session, self._component_ids)
