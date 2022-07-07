from sqlalchemy import delete, select, not_

from models.application.plugin import PluginConfigGroup, PluginConfigItems
from repository.base import BaseRepository


class PluginConfigGroupRepository(BaseRepository[PluginConfigGroup]):

    def create_if_not_exist(self, session, **plugin_config_group):
        result = session.execute(select(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_config_group["plugin_id"],
            PluginConfigGroup.build_version == plugin_config_group["build_version"],
            PluginConfigGroup.config_name == plugin_config_group["config_name"]
        )).scalars().first()
        if not result:
            pcg = PluginConfigGroup(**plugin_config_group)
            session.add(pcg)
            session.flush()

    def delete_config_group_by_meta_type(self, session, plugin_id, build_version, service_meta_type):
        session.execute(delete(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_id,
            PluginConfigGroup.build_version == build_version,
            PluginConfigGroup.service_meta_type == service_meta_type))
        session.flush()

    def get_config_group_by_pk(self, session, pk):
        return session.execute(select(PluginConfigGroup).where(
            PluginConfigGroup.ID == pk)).scalars().first()

    def delete_config_group_by_plugin_id(self, session, plugin_id):
        session.execute(delete(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_id))

    def bulk_create_plugin_config_group(self, session, plugin_config_meta_list):
        """批量创建插件配置组信息"""
        session.add_all(plugin_config_meta_list)
        session.flush()

    def get_config_group_by_id_and_version(self, session, plugin_id, build_version):
        return (session.execute(select(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_id,
            PluginConfigGroup.build_version == build_version))).scalars().all()

    def get_config_group_by_id_and_version_pk(self, session, plugin_id, build_version, pk):
        return (session.execute(select(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_id,
            PluginConfigGroup.build_version == build_version,
            not_(PluginConfigGroup.ID == pk)))).scalars().all()

    def list_by_plugin_id(self, session, plugin_id):
        return (session.execute(select(PluginConfigGroup).where(
            PluginConfigGroup.plugin_id == plugin_id))).scalars().all()


class PluginConfigItemsRepository(BaseRepository[PluginConfigItems]):

    def create_if_not_exist(self, session, **plugin_config_item):
        result = session.execute(select(PluginConfigItems).where(
            PluginConfigItems.plugin_id == plugin_config_item["plugin_id"],
            PluginConfigItems.build_version == plugin_config_item["build_version"],
            PluginConfigItems.attr_name == plugin_config_item["attr_name"]
        )).scalars().first()
        if not result:
            pci = PluginConfigItems(**plugin_config_item)
            session.add(pci)
            session.flush()

    def delete_config_items(self, session, plugin_id, build_version, service_meta_type):
        session.execute(delete(PluginConfigItems).where(
            PluginConfigItems.plugin_id == plugin_id,
            PluginConfigItems.build_version == build_version,
            PluginConfigItems.service_meta_type == service_meta_type))

    def delete_config_items_by_plugin_id(self, session, plugin_id):
        session.execute(delete(PluginConfigItems).where(
            PluginConfigItems.plugin_id == plugin_id))

    def bulk_create_items(self, session, config_items_list):
        session.add_all(config_items_list)
        session.flush()

    def get_config_items_by_unique_key(self, session, plugin_id, build_version, service_meta_type):
        return (session.execute(select(PluginConfigItems).where(
            PluginConfigItems.plugin_id == plugin_id,
            PluginConfigItems.build_version == build_version,
            PluginConfigItems.service_meta_type == service_meta_type))).scalars().all()

    def list_by_plugin_id(self, session, plugin_id):
        return (session.execute(select(PluginConfigItems).where(
            PluginConfigItems.plugin_id == plugin_id))).scalars().all()


config_item_repo = PluginConfigItemsRepository(PluginConfigItems)
config_group_repo = PluginConfigGroupRepository(PluginConfigGroup)
