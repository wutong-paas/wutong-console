import datetime

from loguru import logger

from clients.remote_build_client import remote_build_client
from clients.remote_tenant_client import remote_tenant_client
from exceptions.main import ServiceHandleException
from models.application.models import ComponentApplicationRelation
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.app_actions.app_manage import app_manage_service
from service.base_services import base_service
from service.plugin_service import plugin_service
from service.region_service import region_services
from service.tenant_env_service import env_services


def logic_delete_by_env_id(session, user, env, region_name):
    # 查询环境下全部应用，停用全部组件
    stop_env_resource(session=session, env=env, region_name=region_name, user=user)
    # 环境、应用、组件 标记为逻辑删除
    logic_delete_env(session=session, env=env, user_nickname=user_nickname)
    logger.info("逻辑删除环境资源")


def stop_env_resource(session, env, region_name, user):

    action = "stop"
    apps = application_repo.get_tenant_region_groups(session, env.env_id, region_name)
    for app in apps:
        group_id = app.ID
        services = session.query(ComponentApplicationRelation).filter(
            ComponentApplicationRelation.group_id == group_id).all()
        if not services:
            raise ServiceHandleException(400, "not service", "当前组内无组件，无法操作")
        service_ids = [service.service_id for service in services]
        # 去除掉第三方组件
        for service_id in service_ids:
            service_obj = service_info_repo.get_service_by_service_id(session, service_id)
            service_obj.is_delete = True
            service_obj.delete_time = datetime.datetime.now()
            service_obj.delete_operator = user.nick_name
            if service_obj and service_obj.service_source == "third_party":
                service_ids.remove(service_id)

            tcp_domains = tcp_domain_repo.get_service_tcpdomains(session, service_id)
            for tcp_domain in tcp_domains:
                tcp_domain.is_delete = True
                tcp_domain.delete_time = datetime.datetime.now()
                tcp_domain.delete_operator = user.nick_name
            service_domains = domain_repo.get_service_domains(session, service_id)
            for service_domain in service_domains:
                service_domain.is_delete = True
                service_domain.delete_time = datetime.datetime.now()
                service_domain.delete_operator = user.nick_name

        # 批量操作
        app_manage_service.batch_operations(tenant_env=env, region_name=region_name, user=user, action=action,
                                            service_ids=service_ids, session=session)
        app.is_delete = True
        app.delete_time = datetime.datetime.now()
        app.delete_operator = user.nick_name
    env.is_delete = True
    env.delete_time = datetime.datetime.now()
    env.delete_operator = user.nick_name



def logic_delete_env(session, env, user_nickname):
    # start delete
    region_config = region_repo.get_enterprise_region_by_region_name(session, env.region_name)
    ignore_cluster_resource = True
