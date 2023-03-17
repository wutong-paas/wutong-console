from loguru import logger

from clients.remote_build_client import remote_build_client
from clients.remote_tenant_client import remote_tenant_client
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.app_actions.app_manage import app_manage_service
from service.base_services import base_service
from service.plugin_service import plugin_service
from service.region_service import region_services


def logic_delete_by_env_id(session, user_nickname, env):
    # 查询环境下全部应用，停用全部组件
    stop_env_resource()
    # 环境、应用、组件 标记为逻辑删除
    logic_delete_env()
    logger.info("逻辑删除环境资源")


def stop_env_resource():
    logger.info("")


def logic_delete_env(session, env, region_name, user_nickname):
    # start delete
    region_config = region_repo.get_enterprise_region_by_region_name(session, region_name)
    ignore_cluster_resource = True
