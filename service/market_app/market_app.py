# -*- coding: utf8 -*-
import json

from fastapi.encoders import jsonable_encoder

from clients.remote_app_client import remote_app_client
from clients.remote_build_client import remote_build_client
from core.enum.enterprise_enum import ActionType
from core.utils.constants import PluginMetaType, PluginInjection
from models.teams import ServiceDomain
from repository.component.service_label_repo import label_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.market_app.new_app import NewApp
from service.market_app.original_app import OriginalApp
from service.market_app.plugin import Plugin


class MarketApp(object):
    def __init__(self, session, original_app: OriginalApp, new_app: NewApp):
        self.original_app = original_app
        self.new_app = new_app

        self.tenant_name = self.new_app.tenant.tenant_name
        self.region_name = self.new_app.region_name

        self.labels = {label.label_id: label for label in label_repo.get_all_labels(session)}

    def save_new_app(self, session):
        self.new_app.save(session)

    def sync_new_app(self, session):
        self._sync_new_components(session)
        self._sync_app_config_groups(session, self.new_app)

    def rollback(self, session):
        self._rollback_components(session)
        self._sync_app_config_groups(session, self.original_app)

    def deploy(self, session):
        builds = self._generate_builds()
        upgrades = self._generate_upgrades()

        # Region do not support different operation in one API.
        # We have to call build, then upgrade.
        res = []
        if builds:
            body = {
                "operation": "build",
                "build_infos": builds,
            }
            _, body = remote_build_client.batch_operation_service(session, self.new_app.region_name,
                                                                  self.new_app.tenant.tenant_name, body)
            res += body["bean"]["batch_result"]

        if upgrades:
            body = {
                "operation": "upgrade",
                "upgrade_infos": upgrades,
            }
            _, body = remote_build_client.batch_operation_service(session,
                                                                  self.new_app.region_name,
                                                                  self.new_app.tenant.tenant_name, body)
            res += body["bean"]["batch_result"]

        return res

    def ensure_component_deps(self, new_deps, tmpl_component_ids=[], is_upgrade_one=False):
        """
        确保组件依赖关系的正确性.
        根据已有的依赖关系, 新的依赖关系计算出最终的依赖关系, 计算规则如下:
        只处理同一应用下, 同一 upgrade_group_id 的组件的依赖关系, 即
        情况 1: 覆盖 app_id 和 upgrade_group_id 依赖关系
        情况 2: 保留 app_id 和 upgrade_group_id 都不同的依赖关系
        """
        # 保留 app_id 和 upgrade_group_id 都不同的依赖关系
        # component_ids 是相同 app_id 和 upgrade_group_id 下的组件, 所以 dep_service_id 不属于 component_ids 的依赖关系属于'情况2'
        if is_upgrade_one:
            # If the dependency of the component has changed with other components (existing in the template
            # and installed), then update it.
            new_deps.extend(self.original_app.component_deps)
            return self._dedup_deps(new_deps)
        component_ids = [cpt.component.component_id for cpt in self.original_app.components()]
        if tmpl_component_ids:
            component_ids = [component_id for component_id in component_ids if component_id in tmpl_component_ids]
        deps = []
        for dep in self.original_app.component_deps:
            if dep.dep_service_id not in component_ids:
                deps.append(dep)
                continue
            if tmpl_component_ids and dep.service_id not in tmpl_component_ids:
                deps.append(dep)
        deps.extend(new_deps)
        return self._dedup_deps(deps)

    def ensure_volume_deps(self, new_deps, tmpl_component_ids=[], is_upgrade_one=False):
        """
        确保存储依赖关系的正确性.
        根据已有的依赖关系, 新的依赖关系计算出最终的依赖关系, 计算规则如下:
        只处理同一应用下, 同一 upgrade_group_id 的存储的依赖关系, 即
        情况 1: 覆盖 app_id 和 upgrade_group_id 存储依赖关系
        情况 2: 保留 app_id 和 upgrade_group_id 都不同的存储依赖关系
        """
        # 保留 app_id 和 upgrade_group_id 都不同的依赖关系
        # component_ids 是相同 app_id 和 upgrade_group_id 下的组件, 所以 dep_service_id 不属于 component_ids 的依赖关系属于'情况2'
        if is_upgrade_one:
            # If the dependency of the component has changed with other components (existing in the template
            # and installed), then update it.
            new_deps.extend(self.original_app.volume_deps)
            return self._dedup_deps(new_deps)
        component_ids = [cpt.component.component_id for cpt in self.original_app.components()]
        if tmpl_component_ids:
            component_ids = [component_id for component_id in component_ids if component_id in tmpl_component_ids]
        deps = []
        for dep in self.original_app.volume_deps:
            if dep.dep_service_id not in component_ids:
                deps.append(dep)
                continue
            if tmpl_component_ids and dep.service_id not in tmpl_component_ids:
                deps.append(dep)
        deps.extend(new_deps)
        return self._dedup_deps(deps)

    def _sync_new_components(self, session):
        """
        synchronous components to the application in region
        """
        body = {
            "components": self._create_component_body(self.new_app),
        }
        remote_app_client.sync_components(session, self.tenant_name, self.region_name, self.new_app.region_app_id, body)

    def _rollback_components(self, session):
        body = {
            "components": self._create_component_body(self.original_app),
            "delete_component_ids": [cpt.component.component_id for cpt in self.new_app.new_components]
        }
        remote_app_client.sync_components(session, self.tenant_name, self.region_name, self.new_app.region_app_id, body)

    def _create_component_body(self, app):
        components = app.components()
        plugin_bodies = self._create_plugin_body(components)
        new_components = []
        for cpt in components:
            component_base = jsonable_encoder(cpt.component)
            component_base["component_id"] = component_base["service_id"]
            component_base["component_name"] = component_base["service_cname"]
            component_base["component_alias"] = component_base["service_alias"]
            component_base["container_cpu"] = cpt.component.min_cpu
            component_base["container_memory"] = cpt.component.min_memory
            component_base["replicas"] = cpt.component.min_node
            probes = [jsonable_encoder(probe) for probe in cpt.probes]
            for probe in probes:
                probe["is_used"] = 1 if probe["is_used"] else 0
            component = {
                "component_base": component_base,
                "envs": [jsonable_encoder(env) for env in cpt.envs],
                "ports": [jsonable_encoder(port) for port in cpt.ports],
                "config_files": [jsonable_encoder(cf) for cf in cpt.config_files],
                "probes": probes,
                "monitors": [jsonable_encoder(monitor) for monitor in cpt.monitors],
                "http_rules": self._create_http_rules(cpt.http_rules),
                "http_rule_configs": [json.loads(config.value) for config in cpt.http_rule_configs],
            }
            volumes = [jsonable_encoder(volume) for volume in cpt.volumes]
            # todo allow_expansion
            for volume in volumes:
                try:
                    volume["allow_expansion"] = True if volume["allow_expansion"] == 1 else False
                except:
                    volume["allow_expansion"] = False
            component["volumes"] = volumes
            # labels
            labels = []
            for cl in cpt.labels:
                label = self.labels.get(cl.label_id)
                if not label:
                    continue
                labels.append({"label_key": "node-selector", "label_value": label.label_name})
            component["labels"] = labels
            # volume dependency
            deps = []
            if cpt.volume_deps:
                for dep in cpt.volume_deps:
                    new_dep = jsonable_encoder(dep)
                    new_dep["dep_volume_name"] = dep.mnt_name
                    new_dep["mount_path"] = dep.mnt_dir
                    deps.append(new_dep)
            component["volume_relations"] = deps
            # component dependency
            if cpt.component_deps:
                component["relations"] = [jsonable_encoder(dep) for dep in cpt.component_deps]
            if cpt.app_config_groups:
                component["app_config_groups"] = [{
                    "config_group_name": config_group.config_group_name
                } for config_group in cpt.app_config_groups]
            # plugin
            plugin_body = plugin_bodies.get(cpt.component.component_id, [])
            component["plugins"] = plugin_body
            new_components.append(component)
        return new_components

    def _create_plugin_body(self, components):
        components = {cpt.component.component_id: cpt for cpt in components}
        plugins = {plugin.plugin.plugin_id: plugin for plugin in self.new_app.plugins}
        plugin_configs = {}
        for plugin_config in self.new_app.plugin_configs:
            pcs = plugin_configs.get(plugin_config.service_id, [])
            pcs.append(plugin_config)
            plugin_configs[plugin_config.service_id] = pcs

        new_plugin_deps = {}
        for plugin_dep in self.new_app.plugin_deps:
            plugin = plugins.get(plugin_dep.plugin_id)
            if not plugin:
                continue
            component = components.get(plugin_dep.service_id)
            if not component:
                continue

            cpt_plugin_configs = plugin_configs.get(plugin_dep.service_id, [])
            normal_envs = []
            base_normal = {}
            base_ports = []
            base_services = []
            for plugin_config in cpt_plugin_configs:
                if plugin_config.service_meta_type == PluginMetaType.UNDEFINE:
                    if plugin_config.injection == PluginInjection.EVN:
                        attr_map = json.loads(plugin_config.attrs)
                        for k, v in list(attr_map.items()):
                            normal_envs.append({"env_name": k, "env_value": v})
                    else:
                        base_normal["options"] = json.loads(plugin_config.attrs)
                if plugin_config.service_meta_type == PluginMetaType.UPSTREAM_PORT:
                    base_ports.append({
                        "service_id": plugin_config.service_id,
                        "options": json.loads(plugin_config.attrs),
                        "protocol": plugin_config.protocol,
                        "port": plugin_config.container_port,
                        "service_alias": component.component.service_alias
                    })
                if plugin_config.service_meta_type == PluginMetaType.DOWNSTREAM_PORT:
                    base_services.append({
                        "depend_service_alias": plugin_config.dest_service_alias,
                        "protocol": plugin_config.protocol,
                        "service_alias": component.component.service_alias,
                        "options": json.loads(plugin_config.attrs),
                        "service_id": component.component.service_id,
                        "depend_service_id": plugin_config.dest_service_id,
                        "port": plugin_config.container_port,
                    })
            new_plugin_dep = {
                "plugin_id": plugin_dep.plugin_id,
                "version_id": plugin.build_version.build_version,
                "plugin_model": plugin.plugin.category,
                "container_cpu": plugin_dep.min_cpu,
                "container_memory": plugin_dep.min_memory,
                "switch": plugin_dep.plugin_status == 1,
                "config_envs": {
                    "normal_envs": normal_envs,
                    "complex_envs": {
                        "base_ports": base_ports,
                        "base_services": base_services,
                        "base_normal": base_normal,
                    }
                },
            }
            pds = new_plugin_deps.get(plugin_dep.service_id, [])
            pds.append(new_plugin_dep)
            new_plugin_deps[plugin_dep.service_id] = pds
        return new_plugin_deps

    @staticmethod
    def _create_http_rules(gateway_rules: [ServiceDomain]):
        rules = []
        for gateway_rule in gateway_rules:
            rule = jsonable_encoder(gateway_rule)
            rule["domain"] = gateway_rule.domain_name
            try:
                rule.pop("certificate_id")
            except:
                print("certificate is null")

            rule_extensions = []
            for ext in gateway_rule.rule_extensions.split(";"):
                kvs = ext.split(":")
                if len(kvs) != 2 or kvs[0] == "" or kvs[1] == "":
                    continue
                rule_extensions.append({
                    "key": kvs[0],
                    "value": kvs[1],
                })
            rule["rule_extensions"] = rule_extensions
            rules.append(rule)
        return rules

    def _sync_app_config_groups(self, session, app):
        config_group_items = dict()
        for item in app.config_group_items:
            items = config_group_items.get(item.config_group_name, [])
            new_item = jsonable_encoder(item)
            items.append(new_item)
            config_group_items[item.config_group_name] = items
        config_group_components = dict()
        for cgc in app.config_group_components:
            cgcs = config_group_components.get(cgc.config_group_name, [])
            new_cgc = jsonable_encoder(cgc)
            cgcs.append(new_cgc)
            config_group_components[cgc.config_group_name] = cgcs
        config_groups = list()
        for config_group in app.config_groups:
            cg = jsonable_encoder(config_group)
            cg["config_items"] = config_group_items.get(config_group.config_group_name)
            cg["config_group_services"] = config_group_components.get(config_group.config_group_name)
            config_groups.append(cg)

        body = {
            "app_config_groups": config_groups,
        }
        remote_app_client.sync_config_groups(session, self.tenant_name, self.region_name, self.new_app.region_app_id,
                                             body)

    def list_original_plugins(self, session):
        plugins = plugin_repo.list_by_tenant_id(session, self.original_app.tenant_id, self.region_name)
        plugin_ids = [plugin.plugin_id for plugin in plugins]
        plugin_versions = self._list_plugin_versions(session, plugin_ids)

        new_plugins = []
        for plugin in plugins:
            plugin_version = plugin_versions.get(plugin.plugin_id)
            new_plugins.append(Plugin(plugin, plugin_version))
        return new_plugins

    @staticmethod
    def _list_plugin_versions(session, plugin_ids):
        plugin_versions = plugin_version_repo.list_by_plugin_ids(session, plugin_ids)
        return {plugin_version.plugin_id: plugin_version for plugin_version in plugin_versions}

    def save_new_plugins(self, session):
        plugins = []
        build_versions = []
        config_groups = []
        config_items = []
        for plugin in self.new_app.new_plugins:
            plugins.append(plugin.plugin)
            build_versions.append(plugin.build_version)
            config_groups.extend(plugin.config_groups)
            config_items.extend(plugin.config_items)

        plugin_repo.bulk_create(session, plugins)
        session.add_all(build_versions)
        session.add_all(config_groups)
        session.add_all(config_items)

    def _generate_builds(self):
        builds = []
        for cpt in self.new_app.components():
            if cpt.action_type != ActionType.BUILD.value:
                continue
            build = dict()
            build["service_id"] = cpt.component.component_id
            build["action"] = 'deploy'
            if cpt.component.build_upgrade:
                build["action"] = 'upgrade'
            build["kind"] = "build_from_market_image"
            extend_info = json.loads(cpt.component_source.extend_info)
            build["image_info"] = {
                "image_url": cpt.component.image,
                "user": extend_info.get("hub_user"),
                "password": extend_info.get("hub_password"),
                "cmd": cpt.component.cmd,
            }
            builds.append(build)
        return builds

    def _generate_upgrades(self):
        upgrades = []
        for cpt in self.new_app.components():
            if cpt.action_type != ActionType.UPDATE.value:
                continue
            upgrade = dict()
            upgrade["service_id"] = cpt.component.component_id
            upgrades.append(upgrade)
        return upgrades

    def _dedup_deps(self, deps):
        result = []
        if not deps:
            return []

        exists = []
        for dep in deps:
            if dep.service_id + dep.dep_service_id in exists:
                continue
            result.append(dep)
            exists.append(dep.service_id + dep.dep_service_id)
        return result
