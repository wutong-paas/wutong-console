from fastapi.encoders import jsonable_encoder

from core.utils.constants import PluginMetaType
from database.session import SessionClass
from models.application.plugin import PluginConfigItems, PluginConfigGroup
from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import dep_relation_repo
from repository.plugin.plugin_config_repo import config_group_repo, config_item_repo


class PluginConfigService(object):

    def delete_config_group_by_meta_type(self, session, plugin_id, build_version, service_meta_type):
        config_group_repo.delete_config_group_by_meta_type(session, plugin_id, build_version, service_meta_type)
        config_item_repo.delete_config_items(session, plugin_id, build_version, service_meta_type)

    def create_config_groups(self, session, plugin_id, build_version, config_group):
        plugin_config_meta_list = []
        config_items_list = []
        if config_group:
            for config in config_group:
                options = config["options"]
                plugin_config_meta = PluginConfigGroup(
                    plugin_id=plugin_id,
                    build_version=build_version,
                    config_name=config["config_name"],
                    service_meta_type=config["service_meta_type"],
                    injection=config["injection"])
                plugin_config_meta_list.append(plugin_config_meta)

                for option in options:
                    config_item = PluginConfigItems(
                        plugin_id=plugin_id,
                        build_version=build_version,
                        service_meta_type=config["service_meta_type"],
                        attr_name=option.get("attr_name", ""),
                        attr_alt_value=option.get("attr_alt_value", ""),
                        attr_type=option.get("attr_type", "string"),
                        attr_default_value=option.get("attr_default_value", None),
                        is_change=option.get("is_change", False),
                        attr_info=option.get("attr_info", ""),
                        protocol=option.get("protocol", ""))
                    config_items_list.append(config_item)

        config_group_repo.bulk_create_plugin_config_group(session, plugin_config_meta_list)
        config_item_repo.bulk_create_items(session, config_items_list)

    def get_config_group(self, session: SessionClass, plugin_id, build_version):
        return config_group_repo.get_config_group_by_id_and_version(session=session, plugin_id=plugin_id,
                                                                    build_version=build_version)

    def get_config_group_by_pk_build_version(self, session: SessionClass, plugin_id, build_version, config_group_pk):
        return config_group_repo.get_config_group_by_id_and_version_pk(session=session, plugin_id=plugin_id,
                                                                       build_version=build_version, pk=config_group_pk)

    def get_config_items(self, session: SessionClass, plugin_id, build_version, service_meta_type):
        return config_item_repo.get_config_items_by_unique_key(session=session, plugin_id=plugin_id,
                                                               build_version=build_version,
                                                               service_meta_type=service_meta_type)

    def __get_dep_service_ids(self, session: SessionClass, tenant, service):
        service_dependencies = dep_relation_repo.get_service_dependencies(session, tenant.tenant_id, service.service_id)
        return [service_dep.dep_service_id for service_dep in service_dependencies]

    def get_service_dependencies(self, session: SessionClass, tenant, service):
        dep_ids = self.__get_dep_service_ids(session=session, tenant=tenant, service=service)
        services = service_repo.get_services_by_service_ids(session, dep_ids)
        return services

    def get_config_details(self, session, plugin_id, build_version):
        config_groups = config_group_repo.get_config_group_by_id_and_version(session=session, plugin_id=plugin_id,
                                                                             build_version=build_version)
        config_group = []
        for conf in config_groups:
            config_dict = jsonable_encoder(conf)
            items = config_item_repo.get_config_items_by_unique_key(session=session, plugin_id=conf.plugin_id,
                                                                    build_version=conf.build_version,
                                                                    service_meta_type=conf.service_meta_type)
            options = [jsonable_encoder(item) for item in items]
            config_dict["options"] = options
            config_group.append(config_dict)
        return config_group

    def check_group_config(self, service_meta_type, injection, config_groups):
        if injection == "env":
            if service_meta_type == PluginMetaType.UPSTREAM_PORT or service_meta_type == PluginMetaType.DOWNSTREAM_PORT:
                return False, "基于上游端口或下游端口的配置只能使用主动发现"
        for config_group in config_groups:
            if config_group.service_meta_type == service_meta_type:
                return False, "配置组配置类型不能重复"
        return True, "检测成功"

    def get_config_group_by_pk(self, session, config_group_pk):
        return config_group_repo.get_config_group_by_pk(session, config_group_pk)

    def update_config_group_by_pk(self, session, config_group_pk, config_name, service_meta_type, injection):
        pcg = self.get_config_group_by_pk(session, config_group_pk)
        if not pcg:
            return 404, "配置不存在"
        pcg.service_meta_type = service_meta_type
        pcg.injection = injection
        pcg.config_name = config_name
        # pcg.save()
        return 404, pcg

    def delet_config_items(self, session, plugin_id, build_version, service_meta_type):
        config_item_repo.delete_config_items(session, plugin_id, build_version, service_meta_type)

    def create_config_items(self, session, plugin_id, build_version, service_meta_type, *options):
        config_items_list = []
        for option in options:
            config_item = PluginConfigItems(
                plugin_id=plugin_id,
                build_version=build_version,
                service_meta_type=service_meta_type,
                attr_name=option["attr_name"],
                attr_alt_value=option["attr_alt_value"],
                attr_type=option.get("attr_type", "string"),
                attr_default_value=option.get("attr_default_value", None),
                is_change=option.get("is_change", False),
                attr_info=option.get("attr_info", ""),
                protocol=option.get("protocol", ""))
            config_items_list.append(config_item)
        config_item_repo.bulk_create_items(session, config_items_list)


plugin_config_service = PluginConfigService()
