import copy
import json

from addict import Dict

from clients.remote_plugin_client import remote_plugin_client
from core.utils.constants import PluginCategoryConstants, PluginMetaType, PluginInjection
from database.session import SessionClass
from models.application.plugin import ComponentPluginConfigVar
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import port_repo, dep_relation_repo
from repository.plugin.service_plugin_repo import service_plugin_config_repo, app_plugin_relation_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.plugin.plugin_config_service import plugin_config_service
from service.plugin.plugin_version_service import plugin_version_service


class PluginService(object):
    def get_service_plugin_config(self, session: SessionClass, tenant, service, plugin_id, build_version):
        config_groups = plugin_config_service.get_config_group(session=session, plugin_id=plugin_id,
                                                               build_version=build_version)
        service_plugin_vars = service_plugin_config_repo.get_service_plugin_config_var(session=session,
                                                                                       service_id=service.service_id,
                                                                                       plugin_id=plugin_id,
                                                                                       build_version=build_version)
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
                normal_envs = service_plugin_vars.filter(service_meta_type=PluginMetaType.UNDEFINE)
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
                ports = port_repo.get_service_ports(service.tenant_env_id, service.service_id)
                for port in ports:
                    upstream_envs = service_plugin_vars.filter(
                        service_meta_type=PluginMetaType.UPSTREAM_PORT, container_port=port.container_port)
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
                dep_services = plugin_config_service.get_service_dependencies(session=session, tenant=tenant,
                                                                              service=service)
                for dep_service in dep_services:
                    ports = port_repo.list_inner_ports(dep_service.tenant_env_id, dep_service.service_id)
                    for port in ports:
                        downstream_envs = service_plugin_vars.filter(
                            service_meta_type=PluginMetaType.DOWNSTREAM_PORT,
                            dest_service_id=dep_service.service_id,
                            container_port=port.container_port)
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

    def get_service_abled_plugin(self, session: SessionClass, service):
        plugins = app_plugin_relation_repo.get_service_plugin_relation_by_service_id(
            session, service.service_id)
        plugin_ids = [p.plugin_id for p in plugins]
        base_plugins = plugin_repo.get_plugin_by_plugin_ids(session, plugin_ids)
        return base_plugins

    def update_config_if_have_entrance_plugin(self, session: SessionClass, tenant_env, service):
        plugins = self.get_service_abled_plugin(session=session, service=service)
        for plugin in plugins:
            if PluginCategoryConstants.INPUT_NET == plugin.category:
                pbv = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                              tenant_env_id=tenant_env.env_id,
                                                                              plugin_id=plugin.plugin_id)
                if pbv:
                    configs = self.get_service_plugin_config(session=session, tenant=tenant_env, service=service,
                                                             plugin_id=plugin.plugin_id,
                                                             build_version=pbv.build_version)
                    self.update_service_plugin_config(session=session, tenant_env=tenant_env, service=service,
                                                      plugin_id=plugin.plugin_id, build_version=pbv.build_version,
                                                      config=configs,
                                                      response_region=service.service_region)

    def delete_service_plugin_config(self, session: SessionClass, service, plugin_id):
        service_plugin_config_repo.delete_service_plugin_config_var(session=session, service_id=service.service_id,
                                                                    plugin_id=plugin_id)

    def __update_service_plugin_config(self, session: SessionClass, service, plugin_id, build_version, config_bean):
        config_bean = Dict(config_bean)
        service_plugin_var = []
        undefine_env = config_bean.undefine_env
        if undefine_env:
            attrs_map = {c.attr_name: c.attr_value for c in undefine_env.config}
            service_plugin_var.append(
                ComponentPluginConfigVar(
                    service_id=service.service_id,
                    plugin_id=plugin_id,
                    build_version=build_version,
                    service_meta_type=undefine_env.service_meta_type,
                    injection=undefine_env.injection,
                    dest_service_id="",
                    dest_service_alias="",
                    container_port=0,
                    attrs=json.dumps(attrs_map),
                    protocol=""))
        upstream_config_list = config_bean.upstream_env
        for upstream_config in upstream_config_list:
            attrs_map = {c.attr_name: c.attr_value for c in upstream_config.config}
            service_plugin_var.append(
                ComponentPluginConfigVar(
                    service_id=service.service_id,
                    plugin_id=plugin_id,
                    build_version=build_version,
                    service_meta_type=upstream_config.service_meta_type,
                    injection=upstream_config.injection,
                    dest_service_id="",
                    dest_service_alias="",
                    container_port=upstream_config.port,
                    attrs=json.dumps(attrs_map),
                    protocol=upstream_config.protocol))
        dowstream_config_list = config_bean.downstream_env
        for dowstream_config in dowstream_config_list:
            attrs_map = {c.attr_name: c.attr_value for c in dowstream_config.config}
            service_plugin_var.append(
                ComponentPluginConfigVar(
                    service_id=service.service_id,
                    plugin_id=plugin_id,
                    build_version=build_version,
                    service_meta_type=dowstream_config.service_meta_type,
                    injection=dowstream_config.injection,
                    dest_service_id=dowstream_config.dest_service_id,
                    dest_service_alias=dowstream_config.dest_service_alias,
                    container_port=dowstream_config.port,
                    attrs=json.dumps(attrs_map),
                    protocol=dowstream_config.protocol))

        service_plugin_config_repo.create_bulk_service_plugin_config_var(session=session,
                                                                         service_plugin_var=service_plugin_var)

    def get_region_config_from_db(self, session: SessionClass, service, plugin_id, build_version, user=None):
        attrs = service_plugin_config_repo.get_service_plugin_config_var(session=session, service_id=service.service_id,
                                                                         plugin_id=plugin_id,
                                                                         build_version=build_version)
        normal_envs = []
        base_normal = dict()
        # 上游组件
        base_ports = []
        # 下游组件
        base_services = []
        region_env_config = dict()
        for attr in attrs:
            if attr.service_meta_type == PluginMetaType.UNDEFINE:
                if attr.injection == PluginInjection.EVN:
                    attr_map = json.loads(attr.attrs)
                    for k, v in list(attr_map.items()):
                        normal_envs.append({"env_name": k, "env_value": v})
                else:
                    base_normal["options"] = json.loads(attr.attrs)
            if attr.service_meta_type == PluginMetaType.UPSTREAM_PORT:
                base_ports.append({
                    "service_id": service.service_id,
                    "options": json.loads(attr.attrs),
                    "protocol": attr.protocol,
                    "port": attr.container_port,
                    "service_alias": service.service_alias
                })
            if attr.service_meta_type == PluginMetaType.DOWNSTREAM_PORT:
                base_services.append({
                    "depend_service_alias": attr.dest_service_alias,
                    "protocol": attr.protocol,
                    "service_alias": service.service_alias,
                    "options": json.loads(attr.attrs),
                    "service_id": service.service_id,
                    "depend_service_id": attr.dest_service_id,
                    "port": attr.container_port,
                })

        config_envs = dict()
        complex_envs = dict()
        config_envs["normal_envs"] = normal_envs
        complex_envs["base_ports"] = base_ports
        complex_envs["base_services"] = base_services
        complex_envs["base_normal"] = base_normal
        config_envs["complex_envs"] = complex_envs
        region_env_config["tenant_env_id"] = service.tenant_env_id
        region_env_config["config_envs"] = config_envs
        region_env_config["service_id"] = service.service_id
        region_env_config["operator"] = user.nick_name if user else None

        return region_env_config

    def update_service_plugin_config(self, session: SessionClass, tenant_env, service, plugin_id, build_version, config,
                                     response_region):
        # delete old config
        self.delete_service_plugin_config(session=session, service=service, plugin_id=plugin_id)
        # 全量插入新配置
        self.__update_service_plugin_config(session=session, service=service, plugin_id=plugin_id,
                                            build_version=build_version, config_bean=config)
        # 更新数据中心配置
        region_config = self.get_region_config_from_db(session=session, service=service, plugin_id=plugin_id,
                                                       build_version=build_version)
        remote_plugin_client.update_service_plugin_config(session,
                                                          response_region, tenant_env,
                                                          service.service_alias, plugin_id,
                                                          region_config)

    def __get_dep_service_ids(self, session: SessionClass, tenant, service):
        service_dependencies = dep_relation_repo.get_service_dependencies(session, tenant.tenant_env_id, service.service_id)
        return [service_dep.dep_service_id for service_dep in service_dependencies]

    def get_service_dependencies(self, session: SessionClass, tenant, service):
        dep_ids = self.__get_dep_service_ids(session=session, tenant=tenant, service=service)
        services = service_info_repo.get_services_by_service_ids(session, dep_ids)
        return services


plugin_service = PluginService()
