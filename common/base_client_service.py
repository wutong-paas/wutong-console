"""
base client service
"""
import http
from loguru import logger
from common.client_auth_service import client_auth_service
from exceptions.main import ServiceHandleException
from repository.region.region_config_repo import region_config_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.team_repo import team_repo


def get_region_access_info_by_enterprise_id(enterprise_id, region, session):
    """

    :param enterprise_id:
    :param region:
    :return:
    """
    url, token = client_auth_service.get_region_access_token_by_enterprise_id(session, enterprise_id, region)
    # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
    region_info = region_config_repo.get_region_config_by_region_name(session, region)
    if not region_info:
        raise ServiceHandleException("region not found")
    url = region_info.url
    if not token:
        token = region_info.token
    else:
        token = "Token {}".format(token)
    return url, token


def get_tenant_region_info(tenant_name, region_name, session):
    """

    :param tenant_name:
    :param region_name:
    :return:
    """
    # todo
    logger.info("查询团队信息,param-name:{},param-region:{}", tenant_name, region_name)
    tenant = team_repo.get_tenant_by_tenant_name(session=session, team_name=tenant_name)
    if tenant:
        tenant_region = team_region_repo.get_tenant_region_info_by_tenant_id_and_region_name(session,
                                                                                             tenant.tenant_id,
                                                                                             region_name)
        logger.info("")
        if not tenant_region:
            logger.error("tenant {0} is not in region {1}".format(tenant_name, region_name))
            raise http.HTTPStatus.NOT_FOUND
    else:
        logger.error("tenant {0} is not found!".format(tenant_name))
        raise http.HTTPStatus.NOT_FOUND
    return tenant_region


def get_region_access_info(tenant_name, region_name, session):
    """获取一个团队在指定数据中心的身份认证信息"""
    # 根据团队名获取其归属的企业在指定数据中心的访问信息
    token = None
    if tenant_name:
        url, token = client_auth_service.get_region_access_token_by_tenant(session, tenant_name, region_name)
    # 如果团队所在企业所属数据中心信息不存在则使用通用的配置(兼容未申请数据中心token的企业)
    # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
    region_config_info = region_config_repo.get_region_config_by_region_name(session, region_name)
    if region_config_info is None:
        raise ServiceHandleException("region not found", "数据中心不存在", 404, 404)
    url = region_config_info.url
    if not token:
        token = region_config_info.token
    else:
        token = "Token {}".format(token)
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
