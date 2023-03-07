# -*- coding: utf8 -*-
import json
import logging
import copy
from datetime import datetime

from core.enum.app import ApplicationUpgradeStatus
from core.enum.enterprise_enum import ActionType
from exceptions.bcode import ErrAppUpgradeDeployFailed
from exceptions.main import ServiceHandleException
from models.application.models import ApplicationUpgradeRecord, Application, ServiceUpgradeRecord
from models.application.plugin import TeamComponentPluginRelation, ComponentPluginConfigVar
from models.component.models import TeamApplication, Component, ComponentSourceInfo, ComponentEnvVar, \
    TeamComponentPort, ComponentExtendMethod, TeamComponentVolume, TeamComponentConfigurationFile, ComponentProbe, \
    ComponentMonitor, ComponentGraph, ComponentLabels, TeamComponentMountRelation
from models.relate.models import TeamComponentRelation
from models.teams import RegionConfig
from repository.application.app_snapshot import app_snapshot_repo
from repository.application.app_upgrade_repo import upgrade_repo
from service.component_group import ComponentGroup
from service.label_service import label_service
from service.market_app.component import Component
from service.market_app.market_app import MarketApp
from service.market_app.new_app import NewApp
from service.market_app.original_app import OriginalApp

logger = logging.getLogger('django.contrib.gis')


class AppRestore(MarketApp):
    """
    AppRestore is responsible for restore an upgrade.
    1. AppRestore will use the snapshot to overwrite the components.
    2. AppRestore will not delete new components in the upgrade.
    3. AppRestore will not restore components that were deleted after the upgrade.
    """

    def __init__(self, session, tenant_env, region: RegionConfig, user, app: Application, component_group: TeamApplication,
                 app_upgrade_record: ApplicationUpgradeRecord):
        self.tenant_env = tenant_env
        self.region = region
        self.region_name = region.region_name
        self.user = user
        self.app = app
        self.upgrade_group_id = component_group.ID
        self.upgrade_record = app_upgrade_record
        self.rollback_record = None
        self.component_group = component_group

        self.support_labels = label_service.list_available_labels(session, tenant_env, region.region_name)

        self.original_app = OriginalApp(session, tenant_env, region, app, component_group.ID, self.support_labels)
        self.snapshot = self._get_snapshot(session)
        self.new_app = self._create_new_app(session)
        super(AppRestore, self).__init__(session, self.original_app, self.new_app)

    def restore(self, session):
        # Sync the new application to the data center first
        # TODO(huangrh): rollback on api timeout
        self.sync_new_app(session)
        try:
            # Save the application to the console
            self._save_new_app(session)
        except Exception as e:
            logger.exception(e)
            self._update_rollback_record(ApplicationUpgradeStatus.ROLLBACK_FAILED.value)
            self.rollback(session)
            raise ServiceHandleException("unexpected error", "升级遇到了故障, 暂无法执行, 请稍后重试")

        self._deploy(session)

        return self.rollback_record, self.component_group

    def _save_new_app(self, session):
        # save new app
        self.save_new_app(session)
        # update record
        self.create_rollback_record(session)

    def create_rollback_record(self, session):
        rollback_record = self.upgrade_record.to_dict()
        rollback_record.pop("ID")
        rollback_record.pop("can_rollback")
        rollback_record.pop("is_finished")
        rollback_record["status"] = ApplicationUpgradeStatus.ROLLING.value
        rollback_record["record_type"] = ApplicationUpgradeStatus.ROLLBACK.value
        rollback_record["parent_id"] = self.upgrade_record.ID
        rollback_record["version"] = self.upgrade_record.old_version
        rollback_record["old_version"] = self.upgrade_record.version
        self.rollback_record = upgrade_repo.create_app_upgrade_record(session, **rollback_record)

    def _update_upgrade_record(self, status):
        self.upgrade_record.status = status

    def _update_rollback_record(self, status):
        self.rollback_record.status = status

    def _deploy(self, session):
        try:
            events = self.deploy(session)
        except ServiceHandleException as e:
            self._update_rollback_record(ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise ErrAppUpgradeDeployFailed(e.msg)
        except Exception as e:
            self._update_rollback_record(ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise e
        self._create_component_record(session, events)

    def _create_component_record(self, session, events=list):
        event_ids = {event["service_id"]: event["event_id"] for event in events}
        records = []
        for cpt in self.new_app.components():
            event_id = event_ids.get(cpt.component.component_id)
            record = ServiceUpgradeRecord(
                create_time=datetime.now(),
                app_upgrade_record=self.rollback_record,
                service_id=cpt.component.component_id,
                service_cname=cpt.component.service_cname,
                upgrade_type=ServiceUpgradeRecord.UpgradeType.UPGRADE.value,
                event_id=event_id,
                status=ApplicationUpgradeStatus.ROLLING.value,
                update="",
            )
            if cpt.action_type == ActionType.NOTHING.value:
                record.status = ApplicationUpgradeStatus.ROLLBACK.value
                records.append(record)
                continue
            if not event_id:
                continue
            records.append(record)
        session.add_all(records)
        session.flush()

    def _get_snapshot(self, session):
        snap = app_snapshot_repo.get_by_snapshot_id(session, self.upgrade_record.snapshot_id)
        snap = json.loads(snap.snapshot)
        # filter out components that are in the snapshot but not in the application
        component_ids = [cpt.component.component_id for cpt in self.original_app.components()]
        snap["components"] = [snap for snap in snap["components"] if snap["component_id"] in component_ids]
        return snap

    def _create_new_app(self, session):
        """
        create new app from the snapshot
        """
        components = []
        for snap in self.snapshot["components"]:
            components.append(self._create_component(snap))
        component_ids = [cpt.component.component_id for cpt in components]

        # component dependencies
        new_deps = self._create_component_deps(component_ids)
        component_deps = self.ensure_component_deps(new_deps)

        # volume dependencies
        new_volume_deps = self._create_volume_deps(component_ids)
        volume_deps = self.ensure_volume_deps(new_volume_deps)

        # plugins
        plugins = self.list_original_plugins(session)

        return NewApp(
            session=session,
            tenant_env=self.tenant_env,
            region_name=self.region_name,
            app=self.app,
            component_group=self._create_component_group(),
            new_components=[],
            update_components=components,
            component_deps=component_deps,
            volume_deps=volume_deps,
            plugins=plugins,
            plugin_deps=self._create_plugins_deps(),
            plugin_configs=self._create_plugins_configs(),
        )

    def _create_component(self, snap):
        # component
        component = Component(**snap["service_base"])
        # component source
        component_source = ComponentSourceInfo(**snap["service_source"])
        # environment
        envs = [ComponentEnvVar(**env) for env in snap["service_env_vars"]]
        # ports
        ports = [TeamComponentPort(**port) for port in snap["service_ports"]]
        # service_extend_method
        extend_info = None
        if snap.get("service_extend_method"):
            extend_info = ComponentExtendMethod(**snap.get("service_extend_method"))
        # volumes
        volumes = [TeamComponentVolume(**volume) for volume in snap["service_volumes"]]
        # configuration files
        config_files = [TeamComponentConfigurationFile(**config_file) for config_file in snap["service_config_file"]]
        # probe
        probes = [ComponentProbe(**probe) for probe in snap["service_probes"]]
        # monitors
        monitors = [ComponentMonitor(**monitor) for monitor in snap["service_monitors"]]
        # graphs
        graphs = [ComponentGraph(**graph) for graph in snap["component_graphs"]]
        service_labels = [ComponentLabels(**label) for label in snap["service_labels"]]
        cpt = Component(
            component=component,
            component_source=component_source,
            envs=envs,
            ports=ports,
            volumes=volumes,
            config_files=config_files,
            probes=probes,
            extend_info=extend_info,
            monitors=monitors,
            graphs=graphs,
            plugin_deps=[],
            labels=service_labels,
            support_labels=self.support_labels,
        )
        cpt.action_type = snap.get("action_type", ActionType.BUILD.value)
        return cpt

    def _create_component_deps(self, component_ids):
        component_deps = []
        for snap in self.snapshot["components"]:
            component_deps.extend([TeamComponentRelation(**dep) for dep in snap["service_relation"]])
        # filter out the component dependencies which dep_service_id does not belong to the components
        return [dep for dep in component_deps if dep.dep_service_id in component_ids]

    def _create_volume_deps(self, component_ids):
        volume_deps = []
        for snap in self.snapshot["components"]:
            volume_deps.extend([TeamComponentMountRelation(**dep) for dep in snap["service_mnts"]])
        # filter out the component dependencies which dep_service_id does not belong to the components
        return [dep for dep in volume_deps if dep.dep_service_id in component_ids]

    def _create_component_group(self):
        component_group = self.snapshot["component_group"]
        version = component_group["group_version"]
        component_group = copy.deepcopy(self.component_group)
        component_group.group_version = version
        return ComponentGroup(component_group)

    def _create_plugins_deps(self):
        plugin_deps = []
        for component in self.snapshot["components"]:
            for plugin_dep in component["service_plugin_relation"]:
                plugin_deps.append(TeamComponentPluginRelation(**plugin_dep))
        return plugin_deps

    def _create_plugins_configs(self):
        plugin_configs = []
        for component in self.snapshot["components"]:
            for plugin_config in component["service_plugin_config"]:
                plugin_configs.append(ComponentPluginConfigVar(**plugin_config))
        return plugin_configs
