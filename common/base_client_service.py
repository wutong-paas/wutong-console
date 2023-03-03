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


def get_env_region_info(env, region_name, session):
    """

    :param tenant_name:
    :param region_name:
    :return:
    """
    if env:
        env_region = team_region_repo.get_env_region_info_by_env_id_and_region_name(session,
                                                                                    env.env_id,
                                                                                    region_name)
        logger.info("")
        if not env_region:
            logger.error("env {0} is not in region {1}".format(env.env_name, region_name))
            raise http.HTTPStatus.NOT_FOUND
    else:
        logger.error("env {0} is not found!".format(env.env_name))
        raise http.HTTPStatus.NOT_FOUND
    return env_region


def get_region_access_info(env_name, region_name, session):
    """获取一个团队在指定数据中心的身份认证信息"""
    # 如果团队所在企业所属数据中心信息不存在则使用通用的配置(兼容未申请数据中心token的企业)
    # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
    region_config_info = region_config_repo.get_region_config_by_region_name(session, region_name)
    if region_config_info is None:
        raise ServiceHandleException("region not found", "数据中心不存在", 404, 404)
    url = region_config_info.url
    token = region_config_info.token
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
