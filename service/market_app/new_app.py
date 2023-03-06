# -*- coding: utf8 -*-

from models.application.models import Application
from repository.application.app_repository import config_file_repo
from repository.application.config_group_repo import app_config_group_item_repo, app_config_group_service_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.graph_repo import component_graph_repo
from repository.component.service_config_repo import port_repo, volume_repo, \
    extend_repo, dep_relation_repo, mnt_repo, app_config_group_repo
from repository.component.service_label_repo import service_label_repo
from repository.component.service_probe_repo import probe_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo, service_plugin_config_repo
from repository.region.region_app_repo import region_app_repo
from service.app_config.service_monitor_service import service_monitor_service
from service.component_group import ComponentGroup
from service.market_app.plugin import Plugin


class NewApp(object):
    """
    A new application formed by template application in existing application
    """

    def __init__(self,
                 session,
                 tenant_env,
                 region_name,
                 app: Application,
                 component_group: ComponentGroup,
                 new_components,
                 update_components,
                 component_deps,
                 volume_deps,
                 plugins: [Plugin],
                 plugin_deps,
                 plugin_configs,
                 new_plugins: [Plugin] = None,
                 config_groups=None,
                 config_group_items=None,
                 config_group_components=None,
                 user=None):
        self.user = user
        self.tenant_env = tenant_env
        self.tenant_env_id = tenant_env.env_id
        self.region_name = region_name
        self.app_id = app.app_id
        self.app = app
        self.component_group = component_group
        self.upgrade_group_id = component_group.upgrade_group_id
        self.version = component_group.version
        self.region_app_id = region_app_repo.get_region_app_id(session, self.region_name, self.app_id)
        self.governance_mode = app.governance_mode
        self.new_components = new_components
        self.update_components = update_components
        self.component_ids = [cpt.component.component_id for cpt in self._components()]

        # plugins
        self.plugins = plugins
        self.new_plugins = new_plugins
        self.plugin_deps = plugin_deps
        self.plugin_configs = plugin_configs

        # component dependencies
        self.component_deps = component_deps if component_deps else []
        # volume dependencies
        self.volume_deps = volume_deps if volume_deps else []
        # config groups
        self.config_groups = config_groups if config_groups else []
        self.config_group_items = config_group_items if config_group_items else []
        self.config_group_components = config_group_components if config_group_components else []

    def save(self, session):
        # component
        self._save_components(session)
        self._update_components(session)

        # plugins
        self._save_plugin_deps(session)
        self._save_plugin_configs(session)

        # dependency
        self._save_component_deps(session)
        self._save_volume_deps(session)
        # component group
        self.component_group.save(session)

    def components(self):
        return self._ensure_components(self._components())

    def list_update_components(self):
        return self._ensure_components(self.update_components)

    def _ensure_components(self, components):
        # component dependency
        component_deps = {}
        for dep in self.component_deps:
            deps = component_deps.get(dep.service_id, [])
            deps.append(dep)
            component_deps[dep.service_id] = deps
        # volume dependency
        volume_deps = {}
        for dep in self.volume_deps:
            deps = volume_deps.get(dep.service_id, [])
            deps.append(dep)
            volume_deps[dep.service_id] = deps
        # application config groups
        config_group_components = {}
        for cgc in self.config_group_components:
            cgcs = config_group_components.get(cgc.service_id, [])
            cgcs.append(cgc)
            config_group_components[cgc.service_id] = cgcs
        # plugins
        plugin_deps = {}
        for plugin_dep in self.plugin_deps:
            pds = plugin_deps.get(plugin_dep.service_id, [])
            pds.append(plugin_dep)
            plugin_deps[plugin_dep.service_id] = pds
        plugin_configs = {}
        for plugin_config in self.plugin_configs:
            pcs = plugin_configs.get(plugin_config.service_id, [])
            pcs.append(plugin_config)
            plugin_configs[plugin_config.service_id] = pcs
        for cpt in components:
            cpt.component_deps = component_deps.get(cpt.component.component_id)
            cpt.volume_deps = volume_deps.get(cpt.component.component_id)
            cpt.app_config_groups = config_group_components.get(cpt.component.component_id)
            cpt.plugin_deps = plugin_deps.get(cpt.component.component_id)
            cpt.plugin_configs = plugin_configs.get(cpt.component.component_id)
        return components

    def _components(self):
        return self.new_components + self.update_components

    def _save_components(self, session):
        """
        create new components
        """
        component_sources = []
        envs = []
        ports = []
        http_rules = []
        http_rule_configs = []
        volumes = []
        config_files = []
        probes = []
        extend_infos = []
        monitors = []
        graphs = []
        service_group_rels = []
        labels = []
        for cpt in self.new_components:
            component_sources.append(cpt.component_source)
            envs.extend(cpt.envs)
            ports.extend(cpt.ports)
            http_rules.extend(cpt.http_rules)
            http_rule_configs.extend(cpt.http_rule_configs)
            volumes.extend(cpt.volumes)
            config_files.extend(cpt.config_files)
            if cpt.probes:
                probes.extend(cpt.probes)
            if cpt.extend_info:
                extend_infos.append(cpt.extend_info)
            monitors.extend(cpt.monitors)
            graphs.extend(cpt.graphs)
            service_group_rels.append(cpt.service_group_rel)
            labels.extend(cpt.labels)
        components = [cpt.component for cpt in self.new_components]

        session.add_all(components)
        session.add_all(component_sources)
        session.add_all(envs)
        session.add_all(ports)
        session.add_all(http_rules)
        session.add_all(http_rule_configs)
        session.add_all(volumes)
        session.add_all(config_files)
        session.add_all(probes)
        session.add_all(extend_infos)
        session.add_all(monitors)
        session.add_all(graphs)
        session.add_all(service_group_rels)
        session.add_all(labels)

    def _update_components(self, session):
        """
        update existing components
        """
        if not self.update_components:
            return

        sources = []
        envs = []
        ports = []
        volumes = []
        config_files = []
        probes = []
        extend_infos = []
        monitors = []
        graphs = []
        labels = []
        for cpt in self.update_components:
            sources.append(cpt.component_source)
            envs.extend(cpt.envs)
            ports.extend(cpt.ports)
            volumes.extend(cpt.volumes)
            config_files.extend(cpt.config_files)
            if cpt.probes:
                probes.extend(cpt.probes)
            if cpt.extend_info:
                extend_infos.append(cpt.extend_info)
            monitors.extend(cpt.monitors)
            graphs.extend(cpt.graphs)
            labels.extend(cpt.labels)

        components = [cpt.component for cpt in self.update_components]
        component_ids = [cpt.component_id for cpt in components]
        for component in components:
            session.merge(component)
        for source in sources:
            session.merge(source)
        session.flush()
        env_var_repo.overwrite_by_component_ids(session, component_ids, envs)
        port_repo.overwrite_by_component_ids(session, component_ids, ports)
        volume_repo.overwrite_by_component_ids(session, component_ids, volumes)
        config_file_repo.overwrite_by_component_ids(session, component_ids, config_files)
        probe_repo.overwrite_by_component_ids(session, component_ids, probes)
        service_monitor_service.overwrite_by_component_ids(session, component_ids, monitors)
        component_graph_repo.overwrite_by_component_ids(session, component_ids, graphs)
        service_label_repo.overwrite_by_component_ids(session, component_ids, labels)

    def _save_component_deps(self, session):
        dep_relation_repo.overwrite_by_component_id(session, self.component_ids, self.component_deps)

    def _save_volume_deps(self, session):
        mnt_repo.overwrite_by_component_id(session, self.component_ids, self.volume_deps)

    def _existing_volume_deps(self, session):
        components = self._components()
        volume_deps = mnt_repo.list_mnt_relations_by_service_ids(session,
                                                                 self.tenant_env_id,
                                                                 [cpt.component.component_id for cpt in components])
        return {dep.key(): dep for dep in volume_deps}

    def _save_plugin_deps(self, session):
        app_plugin_relation_repo.overwrite_by_component_ids(session, self.component_ids, self.plugin_deps)

    def _save_plugin_configs(self, session):
        service_plugin_config_repo.overwrite_by_component_ids(session, self.component_ids, self.plugin_configs)
