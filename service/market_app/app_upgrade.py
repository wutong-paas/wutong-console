# -*- coding: utf8 -*-
import json
import logging
import copy
from datetime import datetime

from loguru import logger

from clients.remote_plugin_client import remote_plugin_client
from core.enum.enterprise_enum import ActionType
from core.utils.crypt import make_uuid
from exceptions.bcode import ErrAppUpgradeDeployFailed
from exceptions.main import ServiceHandleException
from models.application.models import Application, ApplicationUpgradeRecord, ApplicationUpgradeStatus, \
    ServiceUpgradeRecord, \
    ApplicationConfigGroup, ApplicationUpgradeSnapshot, ConfigGroupItem, ConfigGroupService
from models.application.plugin import TeamComponentPluginRelation, ComponentPluginConfigVar, TeamPlugin, \
    PluginBuildVersion, PluginConfigItems, PluginConfigGroup
from models.relate.models import TeamComponentRelation
from models.teams import RegionConfig
from models.component.models import TeamComponentMountRelation
from repository.application.app_snapshot import app_snapshot_repo
from repository.application.config_group_repo import app_config_group_item_repo, app_config_group_service_repo
from repository.component.service_config_repo import app_config_group_repo
from service.component_group import ComponentGroup
from service.label_service import label_service
from service.market_app.component import Component
from service.market_app.market_app import MarketApp
from service.market_app.new_app import NewApp
from service.market_app.new_components import NewComponents
from service.market_app.original_app import OriginalApp
from service.market_app.plugin import Plugin
from service.market_app.property_changes import PropertyChanges
from service.market_app.update_components import UpdateComponents


class AppUpgrade(MarketApp):
    def __init__(self,
                 session,
                 enterprise_id,
                 tenant,
                 region: RegionConfig,
                 user,
                 app: Application,
                 version,
                 component_group,
                 app_template,
                 install_from_cloud,
                 market_name,
                 record: ApplicationUpgradeRecord = None,
                 component_keys=None,
                 is_deploy=False,
                 is_upgrade_one=False):
        """
        components_keys: component keys that the user select.
        """
        self.enterprise_id = enterprise_id
        self.tenant = tenant
        self.tenant_id = tenant.tenant_id
        self.region = region
        self.region_name = region.region_name
        self.user = user

        self.component_group = ComponentGroup(enterprise_id, component_group, version)
        self.record = record
        self.app = app
        self.app_id = app.app_id
        self.upgrade_group_id = self.component_group.upgrade_group_id
        self.app_model_key = self.component_group.app_model_key
        self.old_version = self.component_group.version
        self.version = version
        self.component_keys = component_keys if component_keys else None
        self.is_deploy = is_deploy
        self.is_upgrade_one = is_upgrade_one

        # app template
        self.app_template = app_template
        self.install_from_cloud = install_from_cloud
        self.market_name = market_name

        self.support_labels = label_service.list_available_labels(session, tenant, region.region_name)

        # original app
        self.original_app = OriginalApp(session, self.tenant, self.region, self.app, self.upgrade_group_id,
                                        self.support_labels)

        # plugins
        self.original_plugins = self.list_original_plugins(session)
        self.new_plugins = self._create_new_plugins()
        plugins = [plugin.plugin for plugin in self._plugins()]

        self.property_changes = PropertyChanges(session, self.original_app.components(), plugins, self.app_template,
                                                self.support_labels)

        self.new_app = self._create_new_app(session)
        self.property_changes.ensure_dep_changes(self.new_app, self.original_app)

        super(AppUpgrade, self).__init__(session, self.original_app, self.new_app)

    def install(self, session):
        # install plugins
        self.install_plugins(session)

        # Sync the new application to the data center first
        self.sync_new_app(session)

        try:
            # Save the application to the console
            self.save_new_app(session)
        except Exception as e:
            logger.exception(e)
            # rollback on failure
            self.rollback(session)
            raise ServiceHandleException("unexpected error", "安装遇到了故障, 暂无法执行, 请稍后重试")

        if self.is_deploy:
            self._install_deploy(session)

    def upgrade(self, session):
        # install plugins
        try:
            self.install_plugins(session)
        except Exception as e:
            self._update_upgrade_record(ApplicationUpgradeStatus.UPGRADE_FAILED.value)
            raise e

        # Sync the new application to the data center first
        try:
            self.sync_new_app(session)
        except Exception as e:
            self._update_upgrade_record(ApplicationUpgradeStatus.UPGRADE_FAILED.value)
            raise e

        try:
            # Save the application to the console
            self._save_app(session)
        except Exception as e:
            logger.exception(e)
            self._update_upgrade_record(ApplicationUpgradeStatus.UPGRADE_FAILED.value)
            # rollback on failure
            self.rollback(session)
            raise ServiceHandleException("unexpected error", "升级遇到了故障, 暂无法执行, 请稍后重试")

        self._deploy(session, self.record)

        return self.record

    def changes(self):
        templates = self.app_template.get("apps")
        templates = {tmpl["service_key"]: tmpl for tmpl in templates}

        result = []
        original_components = {cpt.component.component_id: cpt for cpt in self.original_app.components()}
        cpt_changes = {change["component_id"]: change for change in self.property_changes.changes}
        # upgrade components
        for cpt in self.new_app.update_components:
            component_id = cpt.component.component_id
            change = cpt_changes.get(component_id, {})
            if "component_id" in change.keys():
                change.pop("component_id")

            original_cpt = original_components.get(component_id)

            upgrade_info = cpt_changes.get(component_id, None)
            current_version = original_cpt.component_source.version
            result.append({
                "service": {
                    "service_id": cpt.component.component_id,
                    "service_cname": cpt.component.service_cname,
                    "service_key": cpt.component.service_key,
                    "type": "upgrade",
                    'current_version': current_version,
                    'can_upgrade': original_cpt is not None,
                    'have_change': True if upgrade_info and current_version != self.version else False
                },
                "upgrade_info": upgrade_info,
            })

        # new components
        for cpt in self.new_app.new_components:
            tmpl = templates.get(cpt.component.service_key)
            if not tmpl:
                continue
            result.append({
                "service": {
                    "service_id": "",
                    "service_cname": cpt.component.service_cname,
                    "service_key": cpt.component.service_key,
                    "type": "add",
                    "can_upgrade": True,
                },
                "upgrade_info": tmpl,
            })

        return result

    def install_plugins(self, session):
        # save plugins
        self.save_new_plugins(session)
        # sync plugins
        self._sync_plugins(session, self.new_app.new_plugins)
        # deploy plugins
        self._deploy_plugins(session, self.new_app.new_plugins)

    def _save_new_app(self, session):
        self.save_new_app(session)

    def _sync_plugins(self, session, plugins: [Plugin]):
        new_plugins = []
        for plugin in plugins:
            new_plugins.append({
                "build_model": plugin.plugin.build_source,
                "git_url": plugin.plugin.code_repo,
                "image_url": "{0}:{1}".format(plugin.plugin.image, plugin.build_version.image_tag),
                "plugin_id": plugin.plugin.plugin_id,
                "plugin_info": plugin.plugin.desc,
                "plugin_model": plugin.plugin.category,
                "plugin_name": plugin.plugin.plugin_name,
                "origin": plugin.plugin.origin
            })
        body = {
            "plugins": new_plugins,
        }
        remote_plugin_client.sync_plugins(session, self.tenant_name, self.region_name, body)

    def _install_deploy(self, session):
        try:
            _ = self.deploy(session)
        except Exception as e:
            logger.exception(e)
            raise ServiceHandleException(msg="install app failure", msg_show="安装应用发生异常，请稍后重试")

    def _deploy_plugins(self, session, plugins: [Plugin]):
        new_plugins = []
        for plugin in plugins:
            origin = plugin.plugin.origin
            if origin == "sys":
                plugin_from = "yb"
            elif origin == "market":
                plugin_from = "ys"
            else:
                plugin_from = None

            new_plugins.append({
                "plugin_id": plugin.plugin.plugin_id,
                "build_version": plugin.build_version.build_version,
                "event_id": plugin.build_version.event_id,
                "info": plugin.build_version.update_info,
                "operator": self.user.nick_name,
                "plugin_cmd": plugin.build_version.build_cmd,
                "plugin_memory": int(plugin.build_version.min_memory),
                "plugin_cpu": int(plugin.build_version.min_cpu),
                "repo_url": plugin.build_version.code_version,
                "username": plugin.plugin.username,  # git username
                "password": plugin.plugin.password,  # git password
                "tenant_id": self.tenant_id,
                "ImageInfo": plugin.plugin_image,
                "build_image": "{0}:{1}".format(plugin.plugin.image, plugin.build_version.image_tag),
                "plugin_from": plugin_from,
            })
        body = {
            "plugins": new_plugins,
        }
        remote_plugin_client.build_plugins(session, self.tenant_name, self.region_name, body)

    def _deploy(self, session, record):
        # Optimization: not all components need deploy
        try:
            events = self.deploy(session)
        except ServiceHandleException as e:
            self._update_upgrade_record(ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise ErrAppUpgradeDeployFailed(e.msg)
        except Exception as e:
            self._update_upgrade_record(ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise e
        self._create_component_record(session, record, events)

    def _create_component_record(self, session, app_record: ApplicationUpgradeRecord, events):
        if self.is_upgrade_one:
            return
        event_ids = {event["service_id"]: event["event_id"] for event in events}
        records = []
        for cpt in self.new_app.components():
            event_id = event_ids.get(cpt.component.component_id)
            record = ServiceUpgradeRecord(
                create_time=datetime.now(),
                app_upgrade_record=app_record,
                service_id=cpt.component.component_id,
                service_cname=cpt.component.service_cname,
                upgrade_type=ServiceUpgradeRecord.UpgradeType.UPGRADE.value,
                event_id=event_id,
                status=ApplicationUpgradeStatus.UPGRADING.value,
            )
            if cpt.action_type == ActionType.NOTHING.value:
                record.status = ApplicationUpgradeStatus.UPGRADED.value
                records.append(record)
                continue
            if not event_id:
                continue
            records.append(record)
        session.add_all(records)

    def _save_app(self, session):
        snapshot = self._take_snapshot(session)
        self.save_new_app(session)
        self._update_upgrade_record(ApplicationUpgradeStatus.UPGRADING.value, snapshot)

    def _create_new_app(self, session):
        # new components
        new_components = NewComponents(
            session,
            self.tenant,
            self.region,
            self.user,
            self.original_app,
            self.app_model_key,
            self.app_template,
            self.version,
            self.install_from_cloud,
            self.component_keys,
            self.market_name,
            self.is_deploy,
            support_labels=self.support_labels).components
        # components that need to be updated
        update_components = UpdateComponents(session, self.original_app, self.app_model_key, self.app_template,
                                             self.version,
                                             self.component_keys, self.property_changes).components

        components = new_components + update_components

        # component existing in the template.
        tmpl_components = self._tmpl_components(components)
        tmpl_component_ids = [cpt.component.component_id for cpt in tmpl_components]

        # create new component dependency from app_template
        new_component_deps = self._create_component_deps(components)
        component_deps = self.ensure_component_deps(new_component_deps, tmpl_component_ids, self.is_upgrade_one)

        # volume dependencies
        new_volume_deps = self._create_volume_deps(components)
        volume_deps = self.ensure_volume_deps(new_volume_deps, tmpl_component_ids, self.is_upgrade_one)

        # config groups
        config_groups = self._config_groups(session)
        config_group_items = self._config_group_items(session, config_groups)
        config_group_components = self._config_group_components(session, components, config_groups)

        # plugins
        new_plugin_deps, new_plugin_configs = self._new_component_plugins(components)
        plugin_deps = self.original_app.plugin_deps + new_plugin_deps
        plugin_configs = self.original_app.plugin_configs + new_plugin_configs

        new_component_group = copy.deepcopy(self.component_group.component_group)
        new_component_group.group_version = self.version

        return NewApp(
            session,
            self.tenant,
            self.region_name,
            self.app,
            ComponentGroup(self.enterprise_id, new_component_group, need_save=not self.is_upgrade_one),
            new_components,
            update_components,
            component_deps,
            volume_deps,
            plugins=self._plugins(),
            plugin_deps=plugin_deps,
            plugin_configs=plugin_configs,
            new_plugins=self.new_plugins,
            config_groups=config_groups,
            config_group_items=config_group_items,
            config_group_components=config_group_components,
            user=self.user)

    def _create_original_plugins(self, session):
        return self.list_original_plugins(session)

    def _plugins(self):
        return self.original_plugins + self.new_plugins

    def _create_component_deps(self, components):
        """
        组件唯一标识: cpt.component_source.service_share_uuid
        组件模板唯一标识: tmpl.get("service_share_uuid")
        被依赖组件唯一标识: dep["dep_service_key"]
        """
        components = {cpt.component_source.service_share_uuid: cpt.component for cpt in components}
        original_components = {cpt.component_source.service_share_uuid: cpt.component for cpt in
                               self.original_app.components()}

        deps = []
        for tmpl in self.app_template.get("apps", []):
            for dep in tmpl.get("dep_service_map_list", []):
                component_key = tmpl.get("service_share_uuid")
                component = components.get(component_key)
                if not component:
                    continue

                dep_component_key = dep["dep_service_key"]
                dep_component = components.get(dep_component_key) if components.get(
                    dep_component_key) else original_components.get(dep_component_key)
                if not dep_component:
                    logger.info("The component({}) cannot find the dependent component({})".format(
                        component_key, dep_component_key))
                    continue

                dep = TeamComponentRelation(
                    tenant_id=component.tenant_id,
                    service_id=component.service_id,
                    dep_service_id=dep_component.service_id,
                    dep_service_type="application",
                    dep_order=0,
                )
                deps.append(dep)
        return deps

    def _create_volume_deps(self, raw_components):
        """
        Create new volume dependencies with application template
        """
        volumes = []
        for cpt in raw_components:
            volumes.extend(cpt.volumes)
        components = {cpt.component_source.service_share_uuid: cpt.component for cpt in raw_components}
        original_components = {cpt.component_source.service_share_uuid: cpt.component for cpt in
                               self.original_app.components()}

        deps = []
        for tmpl in self.app_template.get("apps", []):
            component_key = tmpl.get("service_share_uuid")
            component = components.get(component_key)
            if not component:
                continue

            volume_deps = tmpl.get("mnt_relation_list")
            if not volume_deps:
                continue
            for dep in volume_deps:
                # check if the dependent component exists
                dep_component_key = dep["service_share_uuid"]
                dep_component = components.get(dep_component_key) if components.get(
                    dep_component_key) else original_components.get(dep_component_key)
                if not dep_component:
                    logger.info("dependent component({}) not found".format(dep_component_key))
                    continue

                # check if the dependent volume exists
                if not self._volume_exists(volumes, dep_component.service_id, dep["mnt_name"]):
                    logger.info("dependent volume({}/{}) not found".format(dep_component.service_id, dep["mnt_name"]))
                    continue

                dep = TeamComponentMountRelation(
                    tenant_id=component.tenant_id,
                    service_id=component.service_id,
                    dep_service_id=dep_component.service_id,
                    mnt_name=dep["mnt_name"],
                    mnt_dir=dep["mnt_dir"],
                )
                deps.append(dep)
        return deps

    @staticmethod
    def _volume_exists(volumes, component_id, volume_name):
        volumes = {vol.service_id + vol.volume_name: vol for vol in volumes}
        return True if volumes.get(component_id + volume_name) else False

    def _config_groups(self, session):
        """
        only add
        """
        config_groups = list(app_config_group_repo.list(session, self.region_name, self.app_id))
        config_group_names = [cg.config_group_name for cg in config_groups]
        tmpl = self.app_template.get("app_config_groups") if self.app_template.get("app_config_groups") else []
        for cg in tmpl:
            if cg["name"] in config_group_names:
                continue
            config_group = ApplicationConfigGroup(
                app_id=self.app_id,
                config_group_name=cg["name"],
                deploy_type=cg["injection_type"],
                enable=True,  # always true
                region_name=self.region_name,
                config_group_id=make_uuid(),
            )
            config_groups.append(config_group)
        return config_groups

    def _update_upgrade_record(self, status, snapshot=None):
        if self.is_upgrade_one:
            return
        self.record.status = status
        self.record.snapshot_id = snapshot.snapshot_id if snapshot else None
        self.record.version = self.version
        # self.record.save()

    def _take_snapshot(self, session):
        if self.is_upgrade_one:
            return

        new_components = {cpt.component.component_id: cpt for cpt in self.new_app.components()}

        components = []
        for cpt in self.original_app.components():
            # component snapshot
            csnap, _ = label_service.get_service_details(session, self.tenant, cpt.component)
            new_component = new_components.get(cpt.component.component_id)
            if new_component:
                csnap["action_type"] = new_component.action_type
            else:
                # no action for original component without changes
                csnap["action_type"] = ActionType.NOTHING.value
            components.append(csnap)
        if not components:
            return None
        snapshot = app_snapshot_repo.create(
            session,
            ApplicationUpgradeSnapshot(
                tenant_id=self.tenant_id,
                upgrade_group_id=self.upgrade_group_id,
                snapshot_id=make_uuid(),
                snapshot=json.dumps({
                    "components": components,
                    "component_group": self.component_group.component_group.to_dict(),
                }),
            ))
        return snapshot

    def _config_group_items(self, session, config_groups):
        """
        only add
        """
        config_groups = {cg.config_group_name: cg for cg in config_groups}
        config_group_items = list(app_config_group_item_repo.list_by_app_id(session, self.app_id))

        item_keys = [item.config_group_name + item.item_key for item in config_group_items]
        tmpl = self.app_template.get("app_config_groups") if self.app_template.get("app_config_groups") else []
        for cg in tmpl:
            config_group = config_groups.get(cg["name"])
            if not config_group:
                logger.warning("config group {} not found".format(cg["name"]))
                continue
            items = cg.get("config_items")
            if not items:
                continue
            for item_key in items:
                key = cg["name"] + item_key
                if key in item_keys:
                    # do not change existing items
                    continue
                item = ConfigGroupItem(
                    app_id=self.app_id,
                    config_group_name=cg["name"],
                    item_key=item_key,
                    item_value=items[item_key],
                    config_group_id=config_group.config_group_id,
                )
                config_group_items.append(item)
        return config_group_items

    def _config_group_components(self, session, components, config_groups):
        """
        only add
        """
        components = {cpt.component.service_key: cpt for cpt in components}

        config_groups = {cg.config_group_name: cg for cg in config_groups}

        config_group_components = list(app_config_group_service_repo.list_by_app_id(session, self.app_id))
        config_group_component_keys = [cgc.config_group_name + cgc.service_id for cgc in config_group_components]

        tmpl = self.app_template.get("app_config_groups") if self.app_template.get("app_config_groups") else []
        for cg in tmpl:
            config_group = config_groups.get(cg["name"])
            if not config_group:
                continue

            component_keys = cg.get("component_keys", [])
            for component_key in component_keys:
                cpt = components.get(component_key)
                if not cpt:
                    continue
                key = config_group.config_group_name + cpt.component.component_id
                if key in config_group_component_keys:
                    continue
                cgc = ConfigGroupService(
                    app_id=self.app_id,
                    config_group_name=config_group.config_group_name,
                    service_id=cpt.component.component_id,
                    config_group_id=config_group.config_group_id,
                )
                config_group_components.append(cgc)
        return config_group_components

    def _new_component_plugins(self, components: [Component]):
        plugins = {plugin.plugin.origin_share_id: plugin for plugin in self._plugins()}
        old_plugin_deps = [dep.service_id + dep.plugin_id for dep in self.original_app.plugin_deps]

        components = {cpt.component.service_key: cpt for cpt in components}
        component_keys = {tmpl["service_id"]: tmpl["service_key"] for tmpl in self.app_template.get("apps")}

        plugin_deps = []
        for component in self.app_template["apps"]:
            plugin_deps.extend(component.get("service_related_plugin_config", []))

        new_plugin_deps = []
        new_plugin_configs = []
        for plugin_dep in plugin_deps:
            # get component
            component_key = component_keys.get(plugin_dep["service_id"])
            if not component_key:
                logger.warning("component key {} not found".format(plugin_dep["service_id"]))
                continue
            component = components.get(component_key)
            if not component:
                logger.info("component {} not found".format(component_key))
                continue

            # get plugin
            plugin = plugins.get(plugin_dep["plugin_key"])
            if not plugin:
                logger.info("plugin {} not found".format(plugin_dep["plugin_key"]))
                continue

            if component.component.component_id + plugin.plugin.plugin_id in old_plugin_deps:
                continue

            # plugin configs
            plugin_configs, ignore_plugin = self._create_plugin_configs(component, plugin, plugin_dep["attr"],
                                                                        component_keys,
                                                                        components)
            if ignore_plugin:
                continue
            new_plugin_configs.extend(plugin_configs)

            new_plugin_deps.append(
                TeamComponentPluginRelation(
                    service_id=component.component.component_id,
                    plugin_id=plugin.plugin.plugin_id,
                    build_version=plugin.build_version.build_version,
                    service_meta_type=plugin_dep.get("service_meta_type"),
                    plugin_status=plugin_dep.get("plugin_status"),
                    min_memory=plugin_dep.get("min_memory", 128),
                    min_cpu=plugin_dep.get("min_cpu"),
                ))
        return new_plugin_deps, new_plugin_configs

    @staticmethod
    def _create_plugin_configs(component: Component, plugin: Plugin, plugin_configs, component_keys: [str], components):
        """
        return new_plugin_configs, ignore_plugin
        new_plugin_configs: new plugin configs created from app template
        ignore_plugin: ignore the plugin if the dependent component not found
        """
        new_plugin_configs = []
        for plugin_config in plugin_configs:
            new_plugin_config = ComponentPluginConfigVar(
                service_id=component.component.component_id,
                plugin_id=plugin.plugin.plugin_id,
                build_version=plugin.build_version.build_version,
                service_meta_type=plugin_config["service_meta_type"],
                injection=plugin_config["injection"],
                container_port=plugin_config["container_port"],
                attrs=plugin_config["attrs"],
                protocol=plugin_config["protocol"],
            )

            # dest_service_id, dest_service_alias
            dest_service_id = plugin_config.get("dest_service_id")
            if dest_service_id:
                dep_component_key = component_keys.get(dest_service_id)
                if not dep_component_key:
                    logger.info("dependent component key {} not found".format(dest_service_id))
                    return [], True
                dep_component = components.get(dep_component_key)
                if not dep_component:
                    logger.info("dependent component {} not found".format(dep_component_key))
                    return [], True
                new_plugin_config.dest_service_id = dep_component.component.component_id
                new_plugin_config.dest_service_alias = dep_component.component.service_alias
            new_plugin_configs.append(new_plugin_config)

        return new_plugin_configs, False

    def _create_new_plugins(self):
        plugin_templates = self.app_template.get("plugins")
        if not plugin_templates:
            return []

        original_plugins = {plugin.plugin.origin_share_id: plugin.plugin for plugin in self.original_plugins}
        plugins = []
        for plugin_tmpl in plugin_templates:
            original_plugin = original_plugins.get(plugin_tmpl.get("plugin_key"))
            if original_plugin:
                continue

            image = None
            username = None
            passwd = None
            plugin_image = None
            if "share_image" in plugin_tmpl:
                if plugin_tmpl["share_image"]:
                    image_and_tag = plugin_tmpl["share_image"].rsplit(":", 1)
                    image = image_and_tag[0]

            if "plugin_image" in plugin_tmpl:
                plugin_image = plugin_tmpl["plugin_image"]
                username = plugin_tmpl["plugin_image"]["hub_user"]
                passwd = plugin_tmpl["plugin_image"]["hub_password"]

            plugin = TeamPlugin(
                tenant_id=self.tenant.tenant_id,
                region=self.region_name,
                plugin_id=make_uuid(),
                create_user=self.user.user_id,
                desc=plugin_tmpl["desc"],
                plugin_alias=plugin_tmpl["plugin_alias"],
                category=plugin_tmpl["category"],
                build_source="image",
                image=image,
                code_repo=plugin_tmpl["code_repo"],
                username=username,
                password=passwd,
                origin="sys",
                origin_share_id=plugin_tmpl["plugin_key"],
                plugin_name=plugin_tmpl["plugin_name"])

            build_version = self._create_build_version(plugin.plugin_id, plugin_tmpl)
            config_groups, config_items = self._create_config_groups(plugin.plugin_id, build_version,
                                                                     plugin_tmpl.get("config_groups", []))
            plugins.append(Plugin(plugin, build_version, config_groups, config_items, plugin_image))

        return plugins

    def _create_build_version(self, plugin_id, plugin_tmpl):
        image_tag = None
        if "share_image" in plugin_tmpl:
            if plugin_tmpl["share_image"]:
                image_and_tag = plugin_tmpl["share_image"].rsplit(":", 1)
                if len(image_and_tag) > 1:
                    image_tag = image_and_tag[1]
                else:
                    image_tag = "latest"

        min_memory = plugin_tmpl.get('min_memory', 128)
        min_cpu = int(min_memory) / 128 * 20

        return PluginBuildVersion(
            plugin_id=plugin_id,
            tenant_id=self.tenant.tenant_id,
            region=self.region_name,
            user_id=self.user.user_id,
            event_id=make_uuid(),
            build_version=plugin_tmpl.get('build_version'),
            build_status="building",
            min_memory=min_memory,
            min_cpu=min_cpu,
            image_tag=image_tag,
            plugin_version_status="fixed",
            update_info=plugin_tmpl.get('desc')
        )

    @staticmethod
    def _create_config_groups(plugin_id, build_version, config_groups_tmpl):
        config_groups = []
        config_items = []
        for config in config_groups_tmpl:
            options = config["options"]
            plugin_config_meta = PluginConfigGroup(
                plugin_id=plugin_id,
                build_version=build_version.build_version,
                config_name=config["config_name"],
                service_meta_type=config["service_meta_type"],
                injection=config["injection"])
            config_groups.append(plugin_config_meta)

            for option in options:
                config_item = PluginConfigItems(
                    plugin_id=plugin_id,
                    build_version=build_version.build_version,
                    service_meta_type=config["service_meta_type"],
                    attr_name=option.get("attr_name", ""),
                    attr_alt_value=option.get("attr_alt_value", ""),
                    attr_type=option.get("attr_type", "string"),
                    attr_default_value=option.get("attr_default_value", None),
                    is_change=option.get("is_change", False),
                    attr_info=option.get("attr_info", ""),
                    protocol=option.get("protocol", ""))
                config_items.append(config_item)
        return config_groups, config_items

    def _tmpl_components(self, components: [Component]):
        component_keys = [tmpl.get("service_key") for tmpl in self.app_template.get("apps")]
        return [cpt for cpt in components if cpt.component.service_key in component_keys]
