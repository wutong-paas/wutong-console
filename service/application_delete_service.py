import datetime
from loguru import logger
from sqlalchemy import update
from service.alarm.alarm_strategy_service import alarm_strategy_service
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.application.models import Application, ComponentApplicationRelation
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_visit_service


async def logic_delete_application(request, session, app_id, region_name, user, env):
    # 停止当前组件
    await _stop_app(request=request, session=session, app_id=app_id, region_name=region_name, user=user, env=env)


async def _stop_app(request, session, app_id, region_name, user, env):

    app = application_repo.get_group_by_id(session, app_id)
    if not app:
        raise ServiceHandleException(msg="not found app", msg_show="应用不存在", status_code=400)

    app.is_delete = True
    app.delete_time = datetime.datetime.now()
    app.delete_operator = user.nick_name

    visit_app = application_visit_service.get_app_visit_record_by_user_app(session, user.user_id, app_id, False)
    if visit_app:
        visit_app.is_delete = True
        visit_app.delete_time = datetime.datetime.now()
        visit_app.delete_operator = user.nick_name

    services = session.query(ComponentApplicationRelation).filter(
        ComponentApplicationRelation.group_id == app_id).all()

    if not services:
        logger.info("当前应用无组件")
        return
    service_ids = [service.service_id for service in services]
    action = "stop"
    # 去除掉第三方组件
    for service_id in service_ids:
        service_obj = service_info_repo.delete_service_by_service_id(session, service_id)
        service_obj.is_delete = True
        service_obj.delete_time = datetime.datetime.now()
        service_obj.delete_operator = user.nick_name
        await alarm_strategy_service.update_alarm_strategy_service(request, session, env, service_obj)
        if service_obj and service_obj.service_source == "third_party":
            service_ids.remove(service_id)

        # 网关标记删除
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
