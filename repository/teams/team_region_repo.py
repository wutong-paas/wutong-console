from loguru import logger
from sqlalchemy import select

from database.session import SessionClass
from models.region.models import EnvRegionInfo
from models.teams import RegionConfig, TeamEnvInfo
from repository.base import BaseRepository


class TeamRegionRepository(BaseRepository[EnvRegionInfo]):
    """
    TenantRegionRepository
    """

    def get_env_region_info_by_env_id_and_region_name(self, session: SessionClass, env_id, region_name):
        """

        :param tenant_id:
        :param region_name:
        :return:
        """

        logger.info("get_env_region_info_by_tenant_id_and_region,param-tenant_id:{},param-region:{}", env_id,
                    region_name)
        sql = select(EnvRegionInfo).where(EnvRegionInfo.env_id == env_id,
                                          EnvRegionInfo.region_name == region_name)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_active_region_by_tenant_name(self, session: SessionClass, tenant_name):
        """

        :param tenant_name:
        :return:
        """
        tenant_results = session.execute(select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == tenant_name))
        tenant = tenant_results.scalars().first()
        if not tenant:
            return None
        regions_result = session.execute(
            select(EnvRegionInfo).where(EnvRegionInfo.tenant_id == tenant.tenant_id,
                                        EnvRegionInfo.is_active == 1, EnvRegionInfo.is_init == 1))
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
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.tenant_id == tenant_id)).scalars().first()


team_region_repo = TeamRegionRepository(EnvRegionInfo)
