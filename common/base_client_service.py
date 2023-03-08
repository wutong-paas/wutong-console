"""
base client service
"""
import http
from loguru import logger
from exceptions.main import ServiceHandleException
from repository.region.region_config_repo import region_config_repo
from repository.teams.team_region_repo import team_region_repo


def get_region_access_info(region, session):
    """
    :param session:
    :param region:
    :return:
    """
    # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
    region_info = region_config_repo.get_region_config_by_region_name(session, region)
    if not region_info:
        raise ServiceHandleException("region not found")
    url = region_info.url
    token = region_info.token
    return url, token


def get_enterprise_region_info(region, session):
    """

    :param region:
    :return:
    """
    region_config = region_config_repo.get_region_config_by_region_name(session=session, region_name=region)
    if region_config:
        return region_config
    else:
        region_config = region_config_repo.get_region_config_by_region_id(session=session, region_id=region)
        if region_config:
            return region_config
    return None
