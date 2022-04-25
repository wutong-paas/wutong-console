from loguru import logger
from sqlalchemy import select, delete, or_, and_

from database.session import SessionClass
from models.application.plugin import PluginBuildVersion, TeamPlugin, PluginConfigGroup, PluginConfigItems
from repository.base import BaseRepository


class TenantPluginRepository(BaseRepository[TeamPlugin]):
    """
    TenantPluginRepository

    """

    def list_by_tenant_id(self, session: SessionClass, tenant_id, region_name):
        """
        查询插件列表

        :param tenant_id:
        :param region_name:
        :return:
        """
        sql = select(TeamPlugin).where(TeamPlugin.tenant_id == tenant_id, TeamPlugin.region == region_name)
        results = session.execute(sql)
        data = results.scalars().all()
        logger.info("list tenant plugin list by tenant id and region,param-tenant_id:{},param-region:{}", tenant_id,
                    region_name)
        return data

    def get_plugin_detail_by_plugin_id(self, session: SessionClass, plugin_id):
        """
        查询插件信息

        :param plugin_id: 插件ID
        :return: 插件详情
        """
        sql = select(TeamPlugin).where(TeamPlugin.plugin_id == plugin_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_plugin_by_plugin_id(self, session: SessionClass, tenant_id, plugin_id):
        """
        根据租户和插件id查询插件元信息
        :param tenant_id: 租户信息
        :param plugin_id: 插件ID列表
        :return: 插件信息
        """
        sql = select(TeamPlugin).where(TeamPlugin.tenant_id == tenant_id, TeamPlugin.plugin_id == plugin_id)
        results = session.execute(sql)
        data = results.scalars().first()
        logger.info("get plugin detail by tenant id and plugin id,param-tenant_id:{},param-plugin_id:{}", tenant_id,
                    plugin_id)
        return data

    def get_plugin_by_plugin_ids(self, session: SessionClass, plugin_ids):
        """
        批量查询插件信息
        :param plugin_ids:
        :return:
        """
        data = (session.execute(select(TeamPlugin).where(
            TeamPlugin.plugin_id.in_(plugin_ids)))).scalars().all()
        return data

    def get_plugin_build_version(self, session: SessionClass, plugin_id, version):
        """

        :param plugin_id:
        :param version:
        :return:
        """
        sql = select(PluginBuildVersion).where(PluginBuildVersion.plugin_id == plugin_id,
                                               PluginBuildVersion.build_version == version)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_plugin_config_groups(self, session: SessionClass, plugin_id, version):
        """

        :param plugin_id:
        :param version:
        :return:
        """
        sql = select(PluginConfigGroup).where(PluginConfigGroup.plugin_id == plugin_id,
                                              PluginConfigGroup.build_version == version)
        results = session.execute(sql)
        data = results.all()
        return data

    def get_plugin_config_items(self, session: SessionClass, plugin_id, version):
        """

        :param plugin_id:
        :param version:
        :return:
        """
        sql = select(PluginConfigItems).where(PluginConfigItems.plugin_id == plugin_id,
                                              PluginConfigItems.build_version == version)
        results = session.execute(sql)
        data = results.all()
        return data

    def get_plugins_by_service_ids(self, session: SessionClass, service_ids):
        # todo 多表查询
        return None

    def create_plugin(self, session: SessionClass, **plugin_args):
        """
        创建插件
        :param plugin_args:
        """
        add_plugin = TeamPlugin(**plugin_args)
        session.add(add_plugin)
        return add_plugin

    def delete_by_plugin_id(self, session: SessionClass, tenant_id, plugin_id):
        """
        删除插件
        :param tenant_id:
        :param plugin_id:
        """
        session.execute(
            delete(TeamPlugin).where(TeamPlugin.tenant_id == tenant_id, TeamPlugin.plugin_id == plugin_id))

    def get_plugin_by_origin_share_id(self, session: SessionClass, tenant_id, origin_share_id):
        """

        :param tenant_id:
        :param origin_share_id:
        :return:
        """
        sql = select(TeamPlugin).where(TeamPlugin.tenant_id == tenant_id,
                                       TeamPlugin.origin_share_id == origin_share_id)
        results = session.execute(sql)
        data = results.all()
        return data

    def create_if_not_exist(self, session: SessionClass, **plugin):
        """
        创建插件

        :param plugin:
        """
        sql = select(TeamPlugin).where(TeamPlugin.tenant_id == plugin["tenant_id"],
                                       TeamPlugin.plugin_id == plugin["plugin_id"],
                                       TeamPlugin.region == plugin["region"])
        results = session.execute(sql)
        data = results.all()
        if data:
            session.execute(delete(TeamPlugin).where(TeamPlugin.tenant_id == plugin["tenant_id"],
                                                     TeamPlugin.plugin_id == plugin["plugin_id"],
                                                     TeamPlugin.region == plugin["region"]))
        add_plugin = TeamPlugin(**plugin)
        session.add(add_plugin)
        

    def bulk_create(self, session: SessionClass, plugins):
        """
        批量新增插件
        :param plugins:
        """
        session.add_all(plugins)

    def list_by_plugin_ids(self, session: SessionClass, plugin_ids):
        """
        批量查询插件版本记录
        :param plugin_ids:
        :return:
        """
        data = session.execute(
            select(PluginBuildVersion).where(PluginBuildVersion.plugin_id.in_(plugin_ids))).all()
        return data

    def get_tenant_plugin_newest_versions(self, session: SessionClass, region_name, tenant, plugin_id):
        """
        获取指定租户的指定插件的最新版本信息
        :param region_name: region
        :param tenant: 租户
        :param plugin_id: 插件id
        :return: 指定插件的所有版本信息
        """
        plugin_build_version = session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.region == region_name,
            PluginBuildVersion.tenant_id == tenant.tenant_id,
            PluginBuildVersion.plugin_id == plugin_id,
            PluginBuildVersion.build_status == "build_success").order_by(PluginBuildVersion.ID.desc())).all()

        return plugin_build_version

    def get_tenant_plugins(self, session: SessionClass, tenant_id, region):
        return session.execute(select(TeamPlugin).where(
            TeamPlugin.tenant_id == tenant_id,
            TeamPlugin.region == region)).scalars().all()

    def get_def_tenant_plugins(self, session: SessionClass, tenant_id, region, origin_share_ids):
        return session.execute(select(TeamPlugin).where(
            TeamPlugin.tenant_id == tenant_id,
            TeamPlugin.region == region,
            TeamPlugin.origin_share_id.in_(origin_share_ids))).scalars().all()

    def get_default_tenant_plugins(self, session: SessionClass, tenant_id, region, pluginImage, IMAGE_REPO):
        return session.execute(select(TeamPlugin).where(
            TeamPlugin.tenant_id == tenant_id,
            TeamPlugin.region == region,
            or_(and_(TeamPlugin.category == "analyst-plugin:perf",
                     TeamPlugin.image == pluginImage.RUNNER),
                (and_(TeamPlugin.category == "analyst-plugin:perf",
                      TeamPlugin.image == IMAGE_REPO))))).scalars().first()

    def get_by_plugin_id(self, session: SessionClass, tenant_id, plugin_id):
        return (session.execute(select(TeamPlugin).where(
            TeamPlugin.tenant_id == tenant_id,
            TeamPlugin.plugin_id == plugin_id))).scalars().first()


plugin_repo = TenantPluginRepository(TeamPlugin)
