import copy
import json
import random
import string

from addict import Dict
from fastapi_pagination import Params, paginate
from jsonpath import jsonpath
from loguru import logger
from sqlalchemy import select, delete

from clients.remote_plugin_client import remote_plugin_client
from core.utils.constants import PluginCategoryConstants, PluginMetaType, PluginInjection
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.bcode import ErrServiceMonitorExists, ErrRepeatMonitoringTarget, ErrInternalGraphsNotFound
from exceptions.main import ServiceHandleException
from models.application.plugin import ComponentPluginConfigVar
from models.component.models import ComponentEnvVar
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import port_repo, volume_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.plugin.service_plugin_repo import service_plugin_config_repo, app_plugin_relation_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.app_config.component_graph import component_graph_service
from service.app_config.port_service import port_service
from service.app_config.service_monitor_service import service_monitor_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.plugin.plugin_config_service import plugin_config_service
from service.plugin.plugin_service import plugin_service
from service.plugin.plugin_version_service import plugin_version_service
from core.setting import settings

has_the_same_category_plugin = ServiceHandleException(msg="params error", msg_show="该组件已存在相同功能插件", status_code=400)


class AppPluginService(object):
    def update_config_if_have_export_plugin(self, session, tenant, service):
        plugins = self.get_service_abled_plugin(session, service)
        for plugin in plugins:
            if PluginCategoryConstants.OUTPUT_NET == plugin.category or \
                    PluginCategoryConstants.OUTPUT_INPUT_NET == plugin.category:
                pbv = plugin_version_service.get_newest_usable_plugin_version(session, tenant.tenant_id,
                                                                              plugin.plugin_id)
                if pbv:
                    configs = self.get_service_plugin_config(session, tenant, service, plugin.plugin_id,
                                                             pbv.build_version)
                    self.update_service_plugin_config(session, tenant, service, plugin.plugin_id, pbv.build_version,
                                                      configs,
                                                      service.service_region)

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
                ports = port_repo.get_service_ports(session, service.tenant_id, service.service_id)
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
                dep_services = plugin_config_service.get_service_dependencies(session=session, tenant=tenant,
                                                                              service=service)
                for dep_service in dep_services:
                    ports = port_repo.list_inner_ports(session, dep_service.tenant_id, dep_service.service_id)
                    for port in ports:
                        downstream_envs = service_plugin_config_repo.get_service_plugin_downstream_envs(
                            session=session,
                            service_id=service.service_id,
                            plugin_id=plugin_id,
                            build_version=build_version,
                            service_meta_type=PluginMetaType.DOWNSTREAM_PORT,
                            dest_service_id=dep_service.service_id,
                            container_port=port.container_port
                        )
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

    def update_config_if_have_entrance_plugin(self, session: SessionClass, tenant, service):
        plugins = self.get_service_abled_plugin(session=session, service=service)
        for plugin in plugins:
            if PluginCategoryConstants.INPUT_NET == plugin.category:
                pbv = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                              tenant_id=tenant.tenant_id,
                                                                              plugin_id=plugin.plugin_id)
                if pbv:
                    configs = self.get_service_plugin_config(session=session, tenant=tenant, service=service,
                                                             plugin_id=plugin.plugin_id,
                                                             build_version=pbv.build_version)
                    self.update_service_plugin_config(session=session, tenant=tenant, service=service,
                                                      plugin_id=plugin.plugin_id, build_version=pbv.build_version,
                                                      config=configs,
                                                      response_region=service.service_region)

    def delete_service_plugin_config(self, session: SessionClass, service, plugin_id):
        service_plugin_config_repo.delete_service_plugin_config_var(session=session, service_id=service.service_id,
                                                                    plugin_id=plugin_id)

    def delete_filemanage_service_plugin_port(self, session: SessionClass, team, service, response_region, user,
                                              container_port, plugin_id):
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
        if plugin_info:
            if plugin_info.origin_share_id == "filebrowser_plugin" or plugin_info.origin_share_id == "redis_dbgate_plugin" \
                    or plugin_info.origin_share_id == "mysql_dbgate_plugin":
                port = port_service.get_port_by_container_port(session, service, container_port)
                if not port:
                    return
                code, msg, data = port_service.manage_port(session=session, tenant=team, service=service,
                                                           region_name=response_region, container_port=container_port,
                                                           action="close_inner",
                                                           protocol="http", port_alias=None,
                                                           k8s_service_name="", user_name=user.nick_name)

                if code != 200:
                    logger.debug("close file manager inner error", msg)

                port_service.delete_port_by_container_port(session=session, tenant=team, service=service,
                                                           container_port=container_port,
                                                           user_name=user.nick_name)

    def update_java_agent_plugin_env(self, session: SessionClass, team, service, plugin_id, user):
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
        if plugin_info:
            if plugin_info.origin_share_id == "java_agent_plugin":
                env_name = "JAVA_TOOL_OPTIONS"
                env = session.execute(select(ComponentEnvVar).where(
                    ComponentEnvVar.attr_name == env_name,
                    ComponentEnvVar.service_id == service.service_id
                )).scalars().first()

                if env:
                    old_attr_value = env.attr_value
                    if "-javaagent" in env.attr_value:
                        start_index = old_attr_value.find("-javaagent")
                        end_index = old_attr_value.find(service.k8s_component_name) + len(service.k8s_component_name)
                        repl_value = old_attr_value[:start_index] + "" + old_attr_value[end_index:]
                    else:
                        return
                    if repl_value == '':
                        env_var_service.delete_env_by_env_id(session=session, tenant=team, service=service,
                                                             env_id=env.ID,
                                                             user_name=user.nick_name)
                    else:
                        env_var_service.update_env_by_env_id(session=session, tenant=team,
                                                             service=service,
                                                             env_id=str(env.ID), name=env_name,
                                                             attr_value=repl_value,
                                                             user_name=user.nick_name)

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
        region_env_config["tenant_id"] = service.tenant_id
        region_env_config["config_envs"] = config_envs
        region_env_config["service_id"] = service.service_id
        region_env_config["operator"] = user.nick_name if user else None

        return region_env_config

    def update_service_plugin_config(self, session: SessionClass, tenant, service, plugin_id, build_version, config,
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
                                                          response_region, tenant.tenant_name,
                                                          service.service_alias, plugin_id,
                                                          region_config)

    def check_the_same_plugin(self, session: SessionClass, plugin_id, tenant_id, service_id):
        plugin_ids = []
        categories = []
        service_plugins = app_plugin_relation_repo.get_service_plugin_relation_by_service_id(session,
                                                                                             service_id)
        if not service_plugins:
            """ component has not installed plugin"""
            return
        """ filter the same category plugin"""
        for i in service_plugins:
            plugin_ids.append(i.plugin_id)
        plugins = plugin_repo.get_plugin_by_plugin_ids(session, plugin_ids)
        for i in plugins:
            categories.append(i.category)

        # the trend to install plugin
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, tenant_id, plugin_id)

        category_info = plugin_info.category.split(":")
        if category_info[0] == "net-plugin":
            if plugin_info.category in categories:
                raise has_the_same_category_plugin
            if category_info[1] == "in-and-out" and ("net-plugin:up" in categories or "net-plugin:down" in categories):
                raise has_the_same_category_plugin

    def __check_ports_for_config_items(self, session: SessionClass, ports, items):
        for item in items:
            if item.protocol == "":
                return True
            else:
                protocols = item.protocol.split(",")
                for port in ports:
                    if port.protocol in protocols:
                        return True
        return False

    def save_default_plugin_config(self, session: SessionClass, tenant, service, plugin_id, build_version):
        """console层保存默认的数据"""
        config_groups = plugin_config_service.get_config_group(session=session, plugin_id=plugin_id,
                                                               build_version=build_version)
        service_plugin_var = []
        for config_group in config_groups:
            items = plugin_config_service.get_config_items(session=session, plugin_id=plugin_id,
                                                           build_version=build_version,
                                                           service_meta_type=config_group.service_meta_type)
            if config_group.service_meta_type == PluginMetaType.UNDEFINE:
                attrs_map = {item.attr_name: item.attr_default_value for item in items}
                service_plugin_var.append(
                    ComponentPluginConfigVar(
                        service_id=service.service_id,
                        plugin_id=plugin_id,
                        build_version=build_version,
                        service_meta_type=config_group.service_meta_type,
                        injection=config_group.injection,
                        dest_service_id="",
                        dest_service_alias="",
                        container_port=0,
                        attrs=json.dumps(attrs_map),
                        protocol=""))

            if config_group.service_meta_type == PluginMetaType.UPSTREAM_PORT:
                ports = port_repo.get_service_ports(session, service.tenant_id, service.service_id)
                if not self.__check_ports_for_config_items(session=session, ports=ports, items=items):
                    raise ServiceHandleException(msg="do not support protocol", status_code=409,
                                                 msg_show="插件支持的协议与组件端口协议不一致")
                for port in ports:
                    attrs_map = dict()
                    for item in items:
                        if item.protocol == "" or (port.protocol in item.protocol.split(",")):
                            attrs_map[item.attr_name] = item.attr_default_value
                    service_plugin_var.append(
                        ComponentPluginConfigVar(
                            service_id=service.service_id,
                            plugin_id=plugin_id,
                            build_version=build_version,
                            service_meta_type=config_group.service_meta_type,
                            injection=config_group.injection,
                            dest_service_id="",
                            dest_service_alias="",
                            container_port=port.container_port,
                            attrs=json.dumps(attrs_map),
                            protocol=port.protocol))

            if config_group.service_meta_type == PluginMetaType.DOWNSTREAM_PORT:
                dep_services = plugin_service.get_service_dependencies(session=session, tenant=tenant, service=service)
                if not dep_services:
                    session.rollback()
                    raise ServiceHandleException(msg="can't use this plugin", status_code=409,
                                                 msg_show="组件没有依赖其他组件，不能安装此插件")
                for dep_service in dep_services:
                    ports = port_repo.get_service_ports(session, dep_service.tenant_id, dep_service.service_id)
                    if not self.__check_ports_for_config_items(session=session, ports=ports, items=items):
                        raise ServiceHandleException(
                            msg="do not support protocol", status_code=409, msg_show="该组件依赖的组件的端口协议与插件支持的协议不一致")
                    for port in ports:
                        attrs_map = dict()
                        for item in items:
                            if item.protocol == "" or (port.protocol in item.protocol.split(",")):
                                attrs_map[item.attr_name] = item.attr_default_value
                        service_plugin_var.append(
                            ComponentPluginConfigVar(
                                service_id=service.service_id,
                                plugin_id=plugin_id,
                                build_version=build_version,
                                service_meta_type=config_group.service_meta_type,
                                injection=config_group.injection,
                                dest_service_id=dep_service.service_id,
                                dest_service_alias=dep_service.service_alias,
                                container_port=port.container_port,
                                attrs=json.dumps(attrs_map),
                                protocol=port.protocol))
        # 保存数据
        service_plugin_config_repo.create_bulk_service_plugin_config_var(session=session,
                                                                         service_plugin_var=service_plugin_var)

    def __create_service_monitor(self, session: SessionClass, tenant_env, service, plugin_name, user=None):
        user_name = user.nick_name if user else ''
        path = "/metrics"
        if plugin_name == "mysqld_exporter":
            port = 9104
            show_name = "MySQL-Metrics"
        else:
            return
        # create internal port
        port_service.create_internal_port(session=session, tenant=tenant_env, component=service, container_port=port,
                                          user_name=user_name)
        try:
            service_monitor_service.create_component_service_monitor(session=session, tenant_env=tenant_env, service=service,
                                                                     name="mysqldexporter-" + make_uuid()[0:4],
                                                                     path=path,
                                                                     port=port, service_show_name=show_name,
                                                                     interval="10s", user=user)
        except ErrRepeatMonitoringTarget as e:
            logger.debug(e)

    def __create_component_graphs(self, session: SessionClass, component_id, plugin_name):
        try:
            component_graph_service.create_internal_graphs(session=session, component_id=component_id,
                                                           graph_name=plugin_name)
        except ErrInternalGraphsNotFound as e:
            logger.warning("plugin name '{}': {}", plugin_name, e)

    def create_monitor_resources(self, session: SessionClass, tenant_env, service, plugin_name, user=None):
        # service monitor
        try:
            self.__create_service_monitor(session, tenant_env, service, plugin_name, user)
        except ErrServiceMonitorExists:
            # try again
            self.__create_service_monitor(session, tenant_env, service, plugin_name, user)

        # component graphs
        self.__create_component_graphs(session=session, component_id=service.service_id, plugin_name=plugin_name)

    def create_service_plugin_relation(self, session: SessionClass,
                                       tenant_id,
                                       service_id,
                                       plugin_id,
                                       build_version,
                                       service_meta_type="",
                                       plugin_status=True):
        sprs = app_plugin_relation_repo.get_relation_by_service_and_plugin(session=session, service_id=service_id,
                                                                           plugin_id=plugin_id)
        if sprs:
            raise ServiceHandleException(msg="plugin has installed", status_code=409, msg_show="组件已安装该插件")
        plugin_version_info = plugin_version_repo.get_by_id_and_version(session, plugin_id, build_version)
        min_memory = plugin_version_info.min_memory
        min_cpu = plugin_version_info.min_cpu
        params = {
            "service_id": service_id,
            "build_version": build_version,
            "service_meta_type": service_meta_type,
            "plugin_id": plugin_id,
            "plugin_status": plugin_status,
            "min_memory": min_memory,
            "min_cpu": min_cpu,
        }
        return app_plugin_relation_repo.create_service_plugin_relation(session, **params)

    def install_new_plugin(self, session: SessionClass, region, tenant_env, service, plugin_id, plugin_version=None,
                           user=None):
        if not plugin_version:
            plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                                     tenant_id=tenant_env.tenant_id,
                                                                                     plugin_id=plugin_id)
            plugin_version = plugin_version.build_version
        logger.debug("start install plugin ! plugin_id {0}  plugin_version {1}".format(plugin_id, plugin_version))
        # 1.生成console数据，存储
        self.save_default_plugin_config(session=session, tenant=tenant_env, service=service, plugin_id=plugin_id,
                                        build_version=plugin_version)
        # 2.从console数据库取数据生成region数据
        region_config = self.get_region_config_from_db(session, service, plugin_id, plugin_version, user)

        # 3. create monitor resources, such as: service monitor, component graphs
        plugin = plugin_repo.get_by_plugin_id(session, plugin_id)
        self.create_monitor_resources(session, tenant_env, service, plugin.origin_share_id, user)

        data = dict()
        data["plugin_id"] = plugin_id
        data["switch"] = True
        data["version_id"] = plugin_version
        data["operator"] = user.nick_name if user else None
        data.update(region_config)
        plugin_rel = self.create_service_plugin_relation(session=session, tenant_id=tenant_env.tenant_id,
                                                         service_id=service.service_id, plugin_id=plugin_id,
                                                         build_version=plugin_version)
        data["plugin_cpu"] = plugin_rel.min_cpu
        data["plugin_memory"] = plugin_rel.min_memory
        try:
            remote_plugin_client.install_service_plugin(session, region, tenant_env.tenant_name, service.service_alias,
                                                        data)
        except remote_plugin_client.CallApiError as e:
            if "body" in e.message and "msg" in e.message["body"] \
                    and "a same kind plugin has been linked" in e.message["body"]["msg"]:
                raise ServiceHandleException(msg="install plugin fail", msg_show="相同类插件已开通不能重复安装", status_code=409)

    def add_filemanage_port(self, session: SessionClass, tenant, service, plugin_id, container_port, user=None):
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, tenant.tenant_id, plugin_id)

        if plugin_info:
            if plugin_info.origin_share_id == "filebrowser_plugin" \
                    or plugin_info.origin_share_id == "redis_dbgate_plugin" \
                    or plugin_info.origin_share_id == "mysql_dbgate_plugin":
                if plugin_info.origin_share_id == "filebrowser_plugin":
                    container_port = "6173"
                else:
                    container_port = "3000"
                port_num = container_port
                protocol = "http"
                port_alias = service.service_alias.upper().replace("-", "_") + str(port_num)
                port = port_service.get_port_by_container_port(session, service, port_num)
                if port:
                    return
                port_service.add_service_port(session=session, tenant=tenant, service=service,
                                              container_port=port_num, protocol=protocol,
                                              port_alias=port_alias,
                                              is_inner_service=True,
                                              is_outer_service=False,
                                              k8s_service_name=None,
                                              user_name=user.nick_name)

    def add_filemanage_mount(self, session: SessionClass, tenant, service, plugin_id, plugin_version, user=None):
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, tenant.tenant_id, plugin_id)
        volume_name = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        if plugin_info:
            if plugin_info.origin_share_id == "filebrowser_plugin":
                result_bean = app_plugin_service.get_service_plugin_config(session=session, tenant=tenant,
                                                                           service=service,
                                                                           plugin_id=plugin_id,
                                                                           build_version=plugin_version)
                config = jsonpath(result_bean, '$.undefine_env..config')[0][1]
                attr_value = config["attr_value"]

                volumes = volume_service.get_service_volumes(session=session, tenant=tenant, service=service,
                                                             is_config_file=False)

                for volume in volumes:
                    if volume["volume_path"] == attr_value:
                        return

                settings = {'volume_capacity': 1, 'provider_name': '',
                            'access_mode': '',
                            'share_policy': '', 'backup_policy': '',
                            'reclaim_policy': '',
                            'allow_expansion': False}
                volume_service.add_service_volume(
                    session=session,
                    tenant=tenant,
                    service=service,
                    volume_path=attr_value,
                    volume_type="share-file",
                    volume_name=volume_name,
                    file_content="",
                    settings=settings,
                    user_name=user.nick_name,
                    mode=None)

    def add_init_agent_mount(self, session: SessionClass, tenant, service, plugin_id, plugin_version, user=None):
        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, tenant.tenant_id, plugin_id)
        volume_name = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        if plugin_info:
            if plugin_info.origin_share_id == "java_agent_plugin":

                volumes = volume_service.get_service_volumes(session=session, tenant=tenant, service=service,
                                                             is_config_file=False)

                for volume in volumes:
                    if volume["volume_path"] == "/agent":
                        return

                settings = {'volume_capacity': 1, 'provider_name': '',
                            'access_mode': '',
                            'share_policy': '', 'backup_policy': '',
                            'reclaim_policy': '',
                            'allow_expansion': False}
                volume_service.add_service_volume(
                    session=session,
                    tenant=tenant,
                    service=service,
                    volume_path="/agent",
                    volume_type="share-file",
                    volume_name=volume_name,
                    file_content="",
                    settings=settings,
                    user_name=user.nick_name,
                    mode=None)

    def modify_init_agent_env(self, session: SessionClass, tenant, service, plugin_id, user=None):

        plugin_info = plugin_repo.get_plugin_by_plugin_id(session, tenant.tenant_id, plugin_id)
        if plugin_info:
            if plugin_info.origin_share_id == "java_agent_plugin":
                env_name = "JAVA_TOOL_OPTIONS"
                env = session.execute(select(ComponentEnvVar).where(
                    ComponentEnvVar.attr_name == env_name,
                    ComponentEnvVar.service_id == service.service_id
                )).scalars().first()

                if not env:
                    env_var_service.add_service_env_var(session=session, tenant=tenant, service=service,
                                                        container_port=0, name=env_name, attr_name=env_name,
                                                        attr_value=settings.INIT_AGENT_PLUGIN_ENV + service.k8s_component_name,
                                                        is_change=True, scope="inner",
                                                        user_name=user.nick_name)
                else:
                    attr_value = settings.INIT_AGENT_PLUGIN_ENV + service.k8s_component_name + " " + env.attr_value
                    env.attr_value = attr_value

    def delete_service_plugin_relation(self, session: SessionClass, service, plugin_id):
        app_plugin_relation_repo.delete_service_plugin(session=session, service_id=service.service_id,
                                                       plugin_id=plugin_id)

    def get_service_plugin_relation(self, session: SessionClass, service_id, plugin_id):
        relations = app_plugin_relation_repo.get_relation_by_service_and_plugin(session=session, service_id=service_id,
                                                                                plugin_id=plugin_id)
        if relations:
            return relations[0]
        return None

    def start_stop_service_plugin(self, session: SessionClass, service_id, plugin_id, is_active, cpu, memory):
        """启用停用插件"""
        app_plugin_relation_repo.update_service_plugin_status(session=session, service_id=service_id,
                                                              plugin_id=plugin_id, is_active=is_active, cpu=cpu,
                                                              memory=memory)

    def get_plugin_used_services(self, session, plugin_id, tenant_id, page, page_size):
        aprr = app_plugin_relation_repo.get_used_plugin_services(session=session, plugin_id=plugin_id)
        service_ids = [r.service_id for r in aprr]
        service_plugin_version_map = {r.service_id: r.build_version for r in aprr}
        services = service_info_repo.get_services_by_service_ids_tenant_id(session, service_ids, tenant_id)
        params = Params(page=page, size=page_size)
        paginator = paginate(services, params)
        show_apps = paginator.items
        total = paginator.total
        result_list = []
        for s in show_apps:
            data = dict()
            data["service_id"] = s.service_id
            data["service_alias"] = s.service_alias
            data["service_cname"] = s.service_cname
            data["build_version"] = service_plugin_version_map[s.service_id]
            result_list.append(data)
        return result_list, total


app_plugin_service = AppPluginService()
