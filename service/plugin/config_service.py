import copy
import json

from sqlalchemy import select

from core.utils.constants import PluginMetaType
from database.session import SessionClass
from models.application.plugin import ComponentPluginConfigVar, TeamComponentPluginRelation
from repository.component.service_config_repo import port_repo
from service.plugin.plugin_config_service import plugin_config_service


class ConfigService:
    def get_service_plugin_relation(self, session: SessionClass, service_id, plugin_id):
        relations = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_id == plugin_id)).scalars().all()
        if relations:
            return relations[0]
        return None

    def get_service_plugin_config(self, session: SessionClass, tenant_env, service, plugin_id, build_version):
        config_groups = plugin_config_service.get_config_group(session=session, plugin_id=plugin_id,
                                                               build_version=build_version)
        service_plugin_vars = session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id,
            ComponentPluginConfigVar.service_id == service.service_id,
            ComponentPluginConfigVar.build_version == build_version)).scalars().all()
        result_bean = dict()

        undefine_env = dict()
        upstream_env_list = []
        downstream_env_list = []

        for config_group in config_groups:
            items = plugin_config_service.get_config_items(session=session, plugin_id=plugin_id,
                                                           build_version=build_version,
                                                           service_meta_type=config_group.service_meta_type)
            if config_group.service_meta_type == PluginMetaType.UNDEFINE:
                options = []
                normal_envs = []
                for service_plugin_var in service_plugin_vars:
                    if service_plugin_var.service_meta_type == PluginMetaType.UNDEFINE:
                        normal_envs.append(service_plugin_var)
                undefine_options = None
                if normal_envs:
                    normal_env = normal_envs[0]
                    undefine_options = json.loads(normal_env.attrs)
                for item in items:
                    item_option = {
                        "attr_info": item.attr_info,
                        "attr_name": item.attr_name,
                        "attr_value": item.attr_default_value,
                        "attr_alt_value": item.attr_alt_value,
                        "attr_type": item.attr_type,
                        "attr_default_value": item.attr_default_value,
                        "is_change": item.is_change
                    }
                    if undefine_options:
                        item_option["attr_value"] = undefine_options.get(item.attr_name, item.attr_default_value)
                    options.append(item_option)
                undefine_env.update({
                    "service_id": service.service_id,
                    "service_meta_type": config_group.service_meta_type,
                    "injection": config_group.injection,
                    "service_alias": service.service_alias,
                    "config": copy.deepcopy(options),
                    "config_group_name": config_group.config_name,
                })
            if config_group.service_meta_type == PluginMetaType.UPSTREAM_PORT:
                ports = port_repo.get_service_ports(session, service.tenant_env_id, service.service_id)
                for port in ports:
                    upstream_envs = []
                    for service_plugin_var in service_plugin_vars:
                        if service_plugin_var.service_meta_type == PluginMetaType.UPSTREAM_PORT \
                                and (service_plugin_var.container_port == port.container_port):
                            upstream_envs.append(service_plugin_var)
                    upstream_options = None
                    if upstream_envs:
                        upstream_env = upstream_envs[0]
                        upstream_options = json.loads(upstream_env.attrs)
                    options = []
                    for item in items:
                        item_option = {
                            "attr_info": item.attr_info,
                            "attr_name": item.attr_name,
                            "attr_value": item.attr_default_value,
                            "attr_alt_value": item.attr_alt_value,
                            "attr_type": item.attr_type,
                            "attr_default_value": item.attr_default_value,
                            "is_change": item.is_change
                        }
                        if upstream_options:
                            item_option["attr_value"] = upstream_options.get(item.attr_name, item.attr_default_value)
                        if item.protocol == "" or (port.protocol in item.protocol.split(",")):
                            options.append(item_option)
                    upstream_env_list.append({
                        "config_group_name": config_group.config_name,
                        "service_id": service.service_id,
                        "service_meta_type": config_group.service_meta_type,
                        "injection": config_group.injection,
                        "service_alias": service.service_alias,
                        "protocol": port.protocol,
                        "port": port.container_port,
                        "config": copy.deepcopy(options)
                    })
            if config_group.service_meta_type == PluginMetaType.DOWNSTREAM_PORT:
                dep_services = plugin_config_service.get_service_dependencies(session=session, tenant_env=tenant_env,
                                                                              service=service)
                for dep_service in dep_services:
                    ports = port_repo.list_inner_ports(session, dep_service.tenant_env_id, dep_service.service_id)
                    for port in ports:
                        downstream_envs = session.execute(select(ComponentPluginConfigVar).where(
                            ComponentPluginConfigVar.plugin_id == plugin_id,
                            ComponentPluginConfigVar.service_id == service.service_id,
                            ComponentPluginConfigVar.build_version == build_version,
                            ComponentPluginConfigVar.service_meta_type == PluginMetaType.DOWNSTREAM_PORT,
                            ComponentPluginConfigVar.dest_service_id == dep_service.service_id,
                            ComponentPluginConfigVar.container_port == port.container_port)).scalars().all()
                        downstream_options = None
                        if downstream_envs:
                            downstream_env = downstream_envs[0]
                            downstream_options = json.loads(downstream_env.attrs)
                        options = []
                        for item in items:
                            item_option = {
                                "attr_info": item.attr_info,
                                "attr_name": item.attr_name,
                                "attr_value": item.attr_default_value,
                                "attr_alt_value": item.attr_alt_value,
                                "attr_type": item.attr_type,
                                "attr_default_value": item.attr_default_value,
                                "is_change": item.is_change
                            }
                            if downstream_options:
                                item_option["attr_value"] = downstream_options.get(item.attr_name,
                                                                                   item.attr_default_value)
                            if item.protocol == "" or (port.protocol in item.protocol.split(",")):
                                options.append(item_option)
                        downstream_env_list.append({
                            "config_group_name": config_group.config_name,
                            "service_id": service.service_id,
                            "service_meta_type": config_group.service_meta_type,
                            "injection": config_group.injection,
                            "service_alias": service.service_alias,
                            "protocol": port.protocol,
                            "port": port.container_port,
                            "config": copy.deepcopy(options),
                            "dest_service_id": dep_service.service_id,
                            "dest_service_cname": dep_service.service_cname,
                            "dest_service_alias": dep_service.service_alias
                        })

        result_bean["undefine_env"] = undefine_env
        result_bean["upstream_env"] = upstream_env_list
        result_bean["downstream_env"] = downstream_env_list
        return result_bean


config_service = ConfigService()
