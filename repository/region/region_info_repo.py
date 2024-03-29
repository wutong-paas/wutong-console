from sqlalchemy import select, delete, not_

from core.utils.crypt import make_tenant_id
from database.session import SessionClass
from exceptions.main import ServiceHandleException, RegionNotFound
from models.region.models import TeamRegionInfo
from models.teams import RegionConfig, TeamInfo
from repository.base import BaseRepository
from repository.teams.team_repo import team_repo


class RegionRepo(BaseRepository[RegionConfig]):

    def del_by_enterprise_region_id(self, session, enterprise_id, region_id):
        session.execute(delete(RegionConfig).where(
            RegionConfig.enterprise_id == enterprise_id,
            RegionConfig.region_id == region_id
        ))

    def create_region(self, session, region_data):
        region_config = RegionConfig(**region_data)
        session.add(region_config)
        session.flush()
        return region_config

    def get_region_by_enterprise_id(self, session, enterprise_id):
        return session.execute(select(RegionConfig).where(
            RegionConfig.enterprise_id == enterprise_id
        )).scalars().first()

    def get_region_by_region_id(self, session, region_id):
        return session.execute(select(RegionConfig).where(
            RegionConfig.region_id == region_id
        )).scalars().first()

    def update_enterprise_region(self, session, eid, region_id, data):
        region = self.get_region_by_id(session, eid, region_id)
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

    def get_region_by_id(self, session, eid, region_id):
        return session.execute(select(RegionConfig).where(
                RegionConfig.enterprise_id == eid,
                RegionConfig.region_id == region_id
        )).scalars().first()

    def get_region_by_region_names(self, session: SessionClass, region_names):
        results = session.execute(select(RegionConfig).where(RegionConfig.region_name.in_(region_names)))
        data = results.scalars().all()
        return data

    def get_team_opened_region(self, session: SessionClass, team_name, is_init=None):
        """获取团队已开通的数据中心"""
        tenant = team_repo.get_team_by_team_name(session, team_name)
        if not tenant:
            return None
        if not is_init:
            results = session.execute(select(TeamRegionInfo).where(
                TeamRegionInfo.tenant_id == tenant.tenant_id))
        else:
            results = session.execute(select(TeamRegionInfo).where(
                TeamRegionInfo.tenant_id == tenant.tenant_id,
                TeamRegionInfo.is_init == is_init))
        return results.scalars().all()

    def get_team_opened_region_name(self, session: SessionClass, team_name, region_names, is_init=None):
        """获取团队已开通的数据中心"""
        tenant = team_repo.get_team_by_team_name(session, team_name)
        if not tenant:
            return None
        if not is_init:
            results = session.execute(select(TeamRegionInfo).where(
                TeamRegionInfo.tenant_id == tenant.tenant_id,
                TeamRegionInfo.region_name.in_(region_names),
                TeamRegionInfo.is_init == 1))
        else:
            results = session.execute(select(TeamRegionInfo).where(
                TeamRegionInfo.tenant_id == tenant.tenant_id,
                TeamRegionInfo.is_init == is_init))
        return results.scalars().all()

    def get_region_by_tenant_name(self, session: SessionClass, tenant_name):
        tenant = team_repo.get_tenant_by_tenant_name(session=session, team_name=tenant_name, exception=True)
        results = session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id == tenant.tenant_id))
        return results.scalars().all()

    def get_region_desc_by_region_name(self, session: SessionClass, region_name):
        results = session.execute(select(RegionConfig).where(
            RegionConfig.region_name == region_name))
        regions = results.scalars().all()
        if regions:
            region_desc = regions[0].desc
            return region_desc
        else:
            return None

    def get_enterprise_region_by_region_name(self, session: SessionClass, enterprise_id, region_name):
        return session.execute(select(RegionConfig).where(
            RegionConfig.enterprise_id == enterprise_id,
            RegionConfig.region_name == region_name)).scalars().first()

    def get_team_region_by_tenant_and_region(self, session: SessionClass, tenant_id, region):
        return session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id == tenant_id,
            TeamRegionInfo.region_name == region)).scalars().first()

    def delete_team_region_by_tenant_and_region(self, session: SessionClass, tenant_id, region):
        session.execute(delete(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id == tenant_id,
            TeamRegionInfo.region_name == region))
        session.flush()

    def create_tenant_region(self, session: SessionClass, **params):
        tenant_region_info = TeamRegionInfo(**params)
        session.add(tenant_region_info)
        session.flush()
        return tenant_region_info

    def get_tenant_regions_by_teamid(self, session: SessionClass, team_id):
        return session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id == team_id)).scalars().all()

    def get_usable_regions(self, session: SessionClass, enterprise_id, opened_regions_name):
        """获取可使用的数据中心"""
        return (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1",
            RegionConfig.enterprise_id == enterprise_id,
            not_(RegionConfig.region_name.in_(opened_regions_name))))).scalars().all()

    def get_usable_cert_regions(self, session: SessionClass, enterprise_id):
        """获取可使用的数据中心"""
        return (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1",
            RegionConfig.enterprise_id == enterprise_id))).scalars().all()

    def get_usable_regions_by_enterprise_id(self, session: SessionClass, enterprise_id):
        """获取可使用的数据中心"""
        return (session.execute(select(RegionConfig).where(
            RegionConfig.status == "1",
            RegionConfig.enterprise_id == enterprise_id))).scalars().all()

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
