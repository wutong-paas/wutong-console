from loguru import logger
from sqlalchemy import select, Constraint, or_

from database.session import SessionClass
from models.teams import RegionConfig
from repository.base import BaseRepository


class RegionConfigRepository(BaseRepository[RegionConfig]):
    """
    RegionConfigRepository

    """

    def get_region_config_by_region_code(self, session: SessionClass, region_code):
        """
        get_region_config_by_region_code
        :param session:
        :param region_code:
        :return:
        """
        logger.info("get_region_config_by_region_code,param:{}", region_code)
        sql = select(RegionConfig).where(RegionConfig.region_name == region_code)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_region_config_by_region_id(self, session: SessionClass, region_id):
        """
        get_region_config_by_region_id
        :param session:
        :param region_id:
        :return:
        """
        logger.info("get_region_config_by_region_id,param:{}", region_id)
        sql = select(RegionConfig).where(RegionConfig.region_id == region_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_all_regions(self, session: SessionClass, query=""):
        if query:
            return session.execute(select(RegionConfig).where(
                or_(Constraint(RegionConfig.region_name == query),
                    RegionConfig.region_alias == query))).scalars().all()
        res = session.execute(select(RegionConfig))
        res = res.scalars().all()
        return res


region_config_repo = RegionConfigRepository(RegionConfig)
