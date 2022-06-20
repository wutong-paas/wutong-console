from sqlalchemy import delete, select

from models.application.plugin import PluginBuildVersion
from repository.base import BaseRepository


class PluginVersionRepository(BaseRepository[PluginBuildVersion]):

    def list_by_plugin_ids(self, session, plugin_ids):
        return session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.plugin_id.in_(plugin_ids)
        )).scalars().all()

    def create_plugin_build_version(self, session, **params):
        add_plugin = PluginBuildVersion(**params)
        session.add(add_plugin)
        session.flush()
        return add_plugin

    def delete_build_version_by_plugin_id(self, session, tenant_id, plugin_id):
        session.execute(delete(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id))

    def get_plugin_versions(self, session, tenant_id, plugin_id):
        return session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id).order_by(
            PluginBuildVersion.ID.desc())).scalars().all()

    def get_by_id_and_version(self, session, tenant_id, plugin_id, build_version):
        return session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id,
            PluginBuildVersion.build_version == build_version)).scalars().first()

    def get_plugin_version_by_id(self, session, tenant_id, plugin_id):
        return session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id)).scalars().first()

    def get_last_ok_one(self, session, plugin_id, tenant_id):
        return (session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id,
            PluginBuildVersion.build_status == "build_success").order_by(
            PluginBuildVersion.build_time.desc()))).scalars().first()

    def delete_build_version(self, session, tenant_id, plugin_id, build_version):
        session.execute(delete(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id,
            PluginBuildVersion.build_version == build_version))

    def get_plugin_build_version_by_tenant_and_region(self, session, tenant_id, region):
        return session.execute(select(PluginBuildVersion).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.region == region,
            PluginBuildVersion.build_status.in_(["building", "timeout", "time_out"]))).scalars().all()

    def get_plugin_build_version(self, session, plugin_id, tenant_id):
        return session.execute(select(PluginBuildVersion.build_version).where(
            PluginBuildVersion.tenant_id == tenant_id,
            PluginBuildVersion.plugin_id == plugin_id)).scalars().first()


plugin_version_repo = PluginVersionRepository(PluginBuildVersion)
