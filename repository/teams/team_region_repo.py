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

        :param tenant_env_id:
        :param region_name:
        :return:
        """

        logger.info("get_env_region_info_by_tenant_env_id_and_region,param-tenant_env_id:{},param-region:{}", env_id,
                    region_name)
        sql = select(EnvRegionInfo).where(EnvRegionInfo.region_env_id == env_id,
                                          EnvRegionInfo.region_name == region_name)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_active_region_by_env_name(self, session: SessionClass, env_name):
        """

        :param tenant_name:
        :return:
        """
        env_results = session.execute(select(TeamEnvInfo).where(TeamEnvInfo.env_name == env_name))
        tenant_env = env_results.scalars().first()
        if not tenant_env:
            return None
        regions_result = session.execute(
            select(EnvRegionInfo).where(EnvRegionInfo.region_env_id == tenant_env.env_id,
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

    def get_regions(self, session: SessionClass, status=None):
        if status:
            data = (
                session.execute(
                    select(RegionConfig).where(RegionConfig.status == status))
            ).scalars().all()

            return data
        result = (
            session.execute(select(RegionConfig))
        ).scalars().all()

        return result

    def get_region_by_env_id(self, session: SessionClass, env_id):
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.region_env_id == env_id)).scalars().first()


team_region_repo = TeamRegionRepository(EnvRegionInfo)
