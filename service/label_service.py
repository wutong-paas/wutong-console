import datetime

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from clients.remote_component_client import remote_component_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.component.models import ComponentLabels
from models.region.label import Labels
from repository.component.component_repo import service_source_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.graph_repo import component_graph_repo
from repository.component.service_config_repo import configuration_repo, auth_repo, \
    compile_env_repo, extend_repo, mnt_repo, volume_repo, port_repo, dep_relation_repo, service_endpoints_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_label_repo import service_label_repo, node_label_repo, label_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo, service_plugin_config_repo
from repository.region.region_info_repo import region_repo
from service.app_config.service_monitor_service import service_monitor_service


class LabelService(object):

    def get_service_os_name(self, session: SessionClass, service):
        os_label = (
            session.execute(select(Labels).where(Labels.label_name == "windows"))
        ).scalars().first()

        if os_label:
            service_label = (
                session.execute(
                    select(ComponentLabels).where(ComponentLabels.service_id == service.service_id,
                                                  ComponentLabels.label_id == os_label.label_id))
            ).scalars().first()

            if service_label:
                return "windows"
        return "linux"

    def get_service_labels(self, session: SessionClass, service):
        service_labels = service_label_repo.get_service_labels(session, service.service_id)
        service_label_ids = [service_label.label_id for service_label in service_labels]
        logger.debug('----------------->{0}'.format(service_label_ids))
        region_config = region_repo.get_region_by_region_name(session, service.service_region)
        node_label_ids = []
        # 判断标签是否被节点使用
        if region_config:
            node_labels = node_label_repo.get_node_label_by_region(
                session, region_config.region_id, service_label_ids)
            node_label_ids = [node_label.label_id for node_label in node_labels]
        used_labels = label_repo.get_labels_by_label_ids(session, service_label_ids)
        logger.debug('-----------used_labels------->{0}'.format(used_labels))
        unused_labels = []
        if node_label_ids:
            unused_labels = label_repo.get_labels_by_label_ids(session, node_label_ids)

        result = {
            "used_labels": [label.__dict__ for label in used_labels],
            "unused_labels": [label.__dict__ for label in unused_labels],
        }
        return result

    def set_service_os_label(self, session: SessionClass, tenant_env, service, os):
        os_label = (
            session.execute(select(Labels).where(Labels.label_name == os))
        ).scalars().first()

        if not os_label:
            label_id = make_uuid("labels")
            create_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            os_label = Labels(label_id=label_id, label_name=os, label_alias=os, create_time=create_time)
            session.add(os_label)

        return self.add_service_labels(session=session, tenant_env=tenant_env, service=service,
                                       label_ids=[os_label.label_id])

    def add_service_labels(self, session: SessionClass, tenant_env, service, label_ids, user_name=''):
        labels = (
            session.execute(select(Labels).where(Labels.label_id.in_(label_ids)))
        ).scalars().all()

        labels_list = list()
        body = dict()
        label_map = [label.label_name for label in labels]
        service_labels = list()
        for label_id in label_ids:
            service_label = ComponentLabels(
                tenant_env_id=tenant_env.env_id, service_id=service.service_id, label_id=label_id,
                region=service.service_region)
            service_labels.append(service_label)

        if service.create_status == "complete":
            for label_name in label_map:
                label_dict = dict()
                label_dict["label_key"] = "node-selector"
                label_dict["label_value"] = label_name
                labels_list.append(label_dict)
            body["labels"] = labels_list
            body["operator"] = user_name
            try:
                remote_component_client.addServiceNodeLabel(session,
                                                            service.service_region, tenant_env,
                                                            service.service_alias, body)
            except remote_component_client.CallApiError as e:
                if "is exist" not in e.body.get("msg"):
                    logger.exception(e)
                    return 507, "组件异常", None
        #         todo12qewtyrui12  98i
        session.add_all(service_labels)
        session.flush()
        return 200, "操作成功", None

    def get_region_labels(self, session: SessionClass, tenant_env, region_name):
        data = remote_component_client.get_region_labels(session, region_name, tenant_env)
        return data["list"]

    def _sync_labels(self, session: SessionClass, labels):
        label_names = [label.label_name for label in label_repo.get_all_labels(session)]

        new_labels = []
        for label_name in labels:
            if label_name in label_names:
                continue
            new_labels.append(
                Labels(
                    label_id=make_uuid(),
                    label_name=label_name,
                    label_alias=label_name,
                    create_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ))
        label_repo.bulk_create(session, new_labels)

    def get_service_details(self, session: SessionClass, tenant_env, service):
        service_base = jsonable_encoder(service)
        service_labels = service_label_repo.get_service_labels(session, service.service_id)
        service_domains = domain_repo.get_service_domains(session, service.service_id)
        http_rule_configs = configuration_repo.list_by_rule_ids(session, [sd.http_rule_id for sd in service_domains])
        service_tcpdomains = tcp_domain_repo.get_service_tcpdomains(session, service.service_id)
        service_probes = probe_repo.get_all_service_probe(session, service.service_id)
        service_source = service_source_repo.get_service_source(session,
                                                                tenant_env.env_id,
                                                                service.service_id)
        service_auths = auth_repo.get_service_auth(session, service.service_id)
        service_env_vars = env_var_repo.get_service_env_by_tenant_env_id_and_service_id(session=session,
                                                                                        tenant_env_id=tenant_env.env_id,
                                                                                        service_id=service.service_id)
        service_compile_env = compile_env_repo.get_service_compile_env(session, service.service_id)
        service_extend_method = extend_repo.get_extend_method_by_service(session, service)
        service_mnts = mnt_repo.get_service_mnts(session=session,
                                                 tenant_env_id=tenant_env.env_id,
                                                 service_id=service.service_id)
        service_volumes = volume_repo.get_service_volumes_with_config_file(session, service.service_id)
        service_config_file = volume_repo.get_service_config_files(session, service.service_id)
        service_ports = port_repo.get_service_ports(session=session, tenant_env_id=tenant_env.env_id,
                                                    service_id=service.service_id)
        service_relation = dep_relation_repo.get_service_dependencies(session=session,
                                                                      tenant_env_id=tenant_env.env_id,
                                                                      service_id=service.service_id)
        service_monitors = service_monitor_service.get_component_service_monitors(session=session,
                                                                                  tenant_env_id=tenant_env.env_id,
                                                                                  service_id=service.service_id)
        component_graphs = component_graph_repo.list(session, service.service_id)
        # plugin
        service_plugin_relation = app_plugin_relation_repo.get_service_plugin_relation_by_service_id(session,
                                                                                                     service.service_id)
        service_plugin_config = service_plugin_config_repo.get_service_plugin_all_config(session=session,
                                                                                         service_id=service.service_id)
        # third_party_service
        third_party_service_endpoints = service_endpoints_repo.get_all_service_endpoints_by_service_id(
            session, service.service_id)
        if service.service_source == "third_party":
            if not third_party_service_endpoints:
                raise ServiceHandleException(msg="third party service endpoints can't be null", msg_show="第三方组件实例不可为空")
        app_info = {
            "component_id": service.service_id,
            "service_base": service_base,
            "service_labels": [jsonable_encoder(label) for label in service_labels],
            "service_domains": [jsonable_encoder(domain) for domain in service_domains],
            "http_rule_configs": [jsonable_encoder(config) for config in http_rule_configs],
            "service_tcpdomains": [jsonable_encoder(tcpdomain) for tcpdomain in service_tcpdomains],
            "service_probes": [jsonable_encoder(probe) for probe in service_probes],
            "service_source": jsonable_encoder(service_source) if service_source else None,
            "service_auths": [jsonable_encoder(auth) for auth in service_auths],
            "service_env_vars": [jsonable_encoder(env_var) for env_var in service_env_vars],
            "service_compile_env": jsonable_encoder(service_compile_env) if service_compile_env else None,
            "service_extend_method": jsonable_encoder(service_extend_method) if service_extend_method else None,
            "service_mnts": [jsonable_encoder(mnt) for mnt in service_mnts],
            "service_plugin_relation": [jsonable_encoder(plugin_relation) for plugin_relation in
                                        service_plugin_relation],
            "service_plugin_config": [jsonable_encoder(config) for config in service_plugin_config],
            "service_relation": [jsonable_encoder(relation) for relation in service_relation],
            "service_volumes": [jsonable_encoder(volume) for volume in service_volumes],
            "service_config_file": [jsonable_encoder(config_file) for config_file in service_config_file],
            "service_ports": [jsonable_encoder(port) for port in service_ports],
            "third_party_service_endpoints": [jsonable_encoder(endpoint) for endpoint in third_party_service_endpoints],
            "service_monitors": [jsonable_encoder(monitor) for monitor in service_monitors],
            "component_graphs": [jsonable_encoder(graph) for graph in component_graphs]
        }
        plugin_ids = [pr.plugin_id for pr in service_plugin_relation]

        return app_info, plugin_ids

    def list_available_labels(self, session: SessionClass, tenant_env, region_name):
        try:
            labels = self.get_region_labels(session=session, tenant_env=tenant_env, region_name=region_name)
            if not labels:
                return

            self._sync_labels(session=session, labels=labels)

            label_names = [label_name for label_name in labels]
            return [label for label in label_repo.get_all_labels(session) if label.label_name in label_names]
        except Exception as e:
            logger.exception(e)
            return []

    def delete_service_label(self, session: SessionClass, tenant_env, service, label_id, user_name=''):
        label = label_repo.get_label_by_label_id(session, label_id)
        if not label:
            return 404, "指定标签不存在", None
        body = dict()
        # 组件标签删除
        label_dict = dict()
        label_list = list()
        label_dict["label_key"] = "node-selector"
        label_dict["label_value"] = label.label_name
        label_list.append(label_dict)
        body["labels"] = label_list
        body["operator"] = user_name
        logger.debug('-------------------->{0}'.format(body))
        try:
            remote_component_client.deleteServiceNodeLabel(session,
                                                           service.service_region, tenant_env,
                                                           service.service_alias, body)
            service_label_repo.delete_service_labels(session, service.service_id, label_id)
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            return 507, "组件异常", None

        return 200, "success", None


label_service = LabelService()
