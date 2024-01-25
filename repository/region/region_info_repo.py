from sqlalchemy import select, delete, not_
from database.session import SessionClass
from exceptions.main import RegionNotFound
from models.region.models import EnvRegionInfo
from models.teams import RegionConfig
from repository.base import BaseRepository
from repository.teams.env_repo import env_repo


class RegionRepo(BaseRepository[RegionConfig]):

    def del_by_enterprise_region_id(self, session, region_id):
        session.execute(delete(RegionConfig).where(
            RegionConfig.region_id == region_id
        ))

    def create_region(self, session, region_data):
        region_config = RegionConfig(**region_data)
        session.add(region_config)
        session.flush()
        return region_config

    def get_region(self, session):
        return session.execute(select(RegionConfig).where(
        )).scalars().first()

    def get_region_by_region_id(self, session, region_id):
        return session.execute(select(RegionConfig).where(
            RegionConfig.region_id == region_id
        )).scalars().first()

    def update_enterprise_region(self, session, region_id, data):
        region = self.get_region_by_id(session, region_id)
        if not region:
            raise RegionNotFound("region no found")
        region.region_alias = data.get("region_alias")
        region.url = data.get("url")
        region.wsurl = data.get("wsurl")
        region.httpdomain = data.get("httpdomain")
        region.tcpdomain = data.get("tcpdomain")
        if data.get("scope"):
            region.scope = data.get("scope")
        region.ssl_ca_cert = data.get("ssl_ca_cert")
        region.cert_file = data.get("cert_file")
        region.desc = data.get("desc")
        region.key_file = data.get("key_file")
        return region

    def get_region_by_id(self, session, region_id):
        return session.execute(select(RegionConfig).where(
            RegionConfig.region_id == region_id
        )).scalars().first()

    def get_region_by_region_names(self, session: SessionClass, region_names):
        results = session.execute(select(RegionConfig).where(RegionConfig.region_name.in_(region_names)))
        data = results.scalars().all()
        return data

    def get_team_opened_region(self, session: SessionClass, env_namespace, is_init=None):
        """获取团队已开通的数据中心"""
        tenant_env = env_repo.get_env_by_env_namespace(session, env_namespace)
        if not tenant_env:
            return None
        if not is_init:
            results = session.execute(select(EnvRegionInfo).where(
                EnvRegionInfo.region_env_id == tenant_env.env_id))
        else:
            results = session.execute(select(EnvRegionInfo).where(
                EnvRegionInfo.region_env_id == tenant_env.env_id,
                EnvRegionInfo.is_init == is_init))
        return results.scalars().all()

    def get_env_region_by_env_and_region(self, session: SessionClass, env_id, region):
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.region_env_id == env_id,
            EnvRegionInfo.region_name == region)).scalars().first()

    def delete_team_region_by_tenant_and_region(self, session: SessionClass, tenant_env_id, region):
        session.execute(delete(EnvRegionInfo).where(
            EnvRegionInfo.region_env_id == tenant_env_id,
            EnvRegionInfo.region_name == region))
        session.flush()

    def create_tenant_region(self, session: SessionClass, **params):
        tenant_region_info = EnvRegionInfo(**params)
        session.add(tenant_region_info)
        session.flush()
        return tenant_region_info

    def get_env_regions_by_envid(self, session: SessionClass, env_id):
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.region_env_id == env_id)).scalars().all()

    def get_usable_regions(self, session: SessionClass, opened_regions_name):
        """获取可使用的数据中心"""
        return (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1",
            not_(RegionConfig.region_name.in_(opened_regions_name))))).scalars().all()

    def get_usable_cert_regions(self, session: SessionClass):
        """获取可使用的数据中心"""
        return (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1"))).scalars().all()

    def get_new_usable_regions(self, session: SessionClass):
        """获取可使用的数据中心"""
        regions = (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1"))).scalars().all()
        return regions if regions else []

    def get_by_region_name(self, session: SessionClass, region_name):
        return (
            session.execute(select(RegionConfig).where(RegionConfig.region_name == region_name))
        ).scalars().first()

    def get_region_by_region_name(self, session: SessionClass, region_name):
        return session.execute(select(RegionConfig).where(RegionConfig.region_name == region_name)).scalars().first()

    def get_region_tcpdomain(self, session: SessionClass, region_name):
        region = self.get_region_by_region_name(session, region_name)
        if region:
            return region.tcpdomain
        return ""

    def get_region_httpdomain(self, session: SessionClass, region_name):
        region = self.get_region_by_region_name(session, region_name)
        if region:
            return region.httpdomain
        return ""


region_repo = RegionRepo(RegionConfig)
