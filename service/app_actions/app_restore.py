import json

from loguru import logger

from models.application.plugin import TeamComponentPluginRelation
from models.relate.models import TeamComponentRelation
from models.component.models import ComponentEnvVar, TeamComponentPort, TeamComponentMountRelation
from repository.component.component_repo import service_source_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import port_repo, volume_repo, dep_relation_repo, mnt_repo
from repository.component.service_probe_repo import probe_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo


class AppRestore(object):
    def __init__(self, tenant, service):
        self.tenant = tenant
        self.service = service

    def svc(self, session, service_base):
        if not service_base:
            logger.warning("service id: {}; service base not found while \
                restoring service".format(self.service.service_id))
            return
        service_repo.del_by_sid(session=session, sid=self.service.service_id)
        service_base.pop("ID")
        service_repo.base_create(session=session, add_model=service_base)

    def svc_source(self, session, service_source):
        if not service_source:
            logger.warning("service id: {}; service source data not found while \
                restoring service source".format(self.service.service_id))
            return
        service_source_repo.delete_service_source(session=session, team_id=self.tenant.tenant_id,
                                                  service_id=self.service.service_id)
        service_source.pop("ID")
        if "service" in service_source:
            service_source["service_id"] = service_source.pop("service")
        logger.debug("service_source: {}".format(json.dumps(service_source)))
        service_source_repo.create_service_source(session, **service_source)

    def envs(self, session, service_env_vars):
        env_var_repo.delete_service_env(session, self.tenant.tenant_id, self.service.service_id)
        if service_env_vars:
            envs = []
            for item in service_env_vars:
                item.pop("ID")
                envs.append(ComponentEnvVar(**item))
            env_var_repo.bulk_create(envs)

    def ports(self, session, service_ports):
        port_repo.delete_service_port(session, self.tenant.tenant_id, self.service.service_id)
        if service_ports:
            ports = []
            for item in service_ports:
                item.pop("ID")
                ports.append(TeamComponentPort(**item))
            port_repo.bulk_create(ports)

    def volumes(self, session, service_volumes, service_config_file):
        volume_repo.delete_service_volumes(session, self.service.service_id)
        volume_repo.delete_config_files(session, self.service.service_id)
        id_cfg = {item["volume_id"]: item for item in service_config_file}
        for item in service_volumes:
            if isinstance(item, dict):
                item_id = item.get("ID", None)
            else:
                item_id = item.ID

            item.pop("ID")
            v = volume_repo.add_service_volume(**item)
            if v.volume_type != "config-file":
                continue
            cfg = id_cfg.get(item_id, None)
            if cfg is None:
                continue
            cfg["volume_id"] = v.ID
            cfg.pop("ID")
            _ = volume_repo.add_service_config_file(**cfg)

    def probe(self, session, probe):
        probe_repo.delete_service_probe(session, self.service.service_id)
        if not probe:
            return
        probe.pop("ID")
        probe_repo.add_service_probe(**probe)

    def dep_services(self, session, service_relation):
        dep_relation_repo.delete_service_relation(session, self.tenant.tenant_id, self.service.service_id)
        if not service_relation:
            return
        relations = []
        for relation in service_relation:
            relation.pop("ID")
            new_service_relation = TeamComponentRelation(**relation)
            relations.append(new_service_relation)
        TeamComponentRelation.objects.bulk_create(relations)

    def dep_volumes(self, session, service_mnts):
        mnt_repo.delete_mnt(session, self.service.service_id)
        if not service_mnts:
            return
        mnts = []
        for item in service_mnts:
            item.pop("ID")
            mnt = TeamComponentMountRelation(**item)
            mnts.append(mnt)
        mnt_repo.bulk_create(mnts)

    def plugins(self, session, service_plugin_relation):
        app_plugin_relation_repo.delete_by_sid(session, self.service.service_id)
        plugin_relations = []
        for item in service_plugin_relation:
            item.pop("ID")
            plugin_relations.append(TeamComponentPluginRelation(**item))
        app_plugin_relation_repo.bulk_create(plugin_relations)
