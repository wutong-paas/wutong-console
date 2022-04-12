from loguru import logger
from sqlalchemy import select

from database.session import SessionClass
from models.region.models import TeamRegionInfo
from models.teams import RegionConfig, TeamInfo
from repository.base import BaseRepository


class TeamRegionRepository(BaseRepository[TeamRegionInfo]):
    """
    TenantRegionRepository
    """

    def get_tenant_region_info_by_tenant_id_and_region_name(self, session: SessionClass, tenant_id, region_name):
        """

        :param tenant_id:
        :param region_name:
        :return:
        """
        
        logger.info("get_tenant_region_info_by_tenant_id_and_region,param-tenant_id:{},param-region:{}", tenant_id,
                    region_name)
        sql = select(TeamRegionInfo).where(TeamRegionInfo.tenant_id == tenant_id,
                                           TeamRegionInfo.region_name == region_name)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_active_region_by_tenant_name(self, session: SessionClass, tenant_name):
        """

        :param tenant_name:
        :return:
        """
        tenant_results = session.execute(select(TeamInfo).where(TeamInfo.tenant_name == tenant_name))
        tenant = tenant_results.scalars().first()
        if not tenant:
            return None
        regions_result = session.execute(
            select(TeamRegionInfo).where(TeamRegionInfo.tenant_id == tenant.tenant_id,
                                         TeamRegionInfo.is_active == 1, TeamRegionInfo.is_init == 1))
        regions = regions_result.scalars().all()
        if regions:
            return regions
        return None

    def get_region_by_region_name(self, session: SessionClass, region_name):
        """
        查询数据中心信息
        :param region_name:
        :return:
        """
        results = session.execute(select(RegionConfig).where(RegionConfig.region_name == region_name))
        region_config = results.scalars().first()
        return region_config

    def get_regions_by_enterprise_id(self, session: SessionClass, eid, status=None):
        if status:
            data = (
                session.execute(
                    select(RegionConfig).where(RegionConfig.enterprise_id == eid, RegionConfig.status == status))
            ).scalars().all()

            return data
        result = (
            session.execute(select(RegionConfig).where(RegionConfig.enterprise_id == eid))
        ).scalars().all()

        return result

    def get_region_by_tenant_id(self, session: SessionClass, tenant_id):
        return session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.tenant_id == tenant_id)).scalars().first()


team_region_repo = TeamRegionRepository(TeamRegionInfo)
