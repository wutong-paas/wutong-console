import datetime

from loguru import logger
from sqlalchemy import update

from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.application.models import Application, ComponentApplicationRelation
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_visit_service


def logic_delete_application(session, app_id, region_name, user, env):
    # 停止当前组件
    _stop_app(session=session, app_id=app_id, region_name=region_name, user=user, env=env)


def _stop_app(session, app_id, region_name, user, env):

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
        if service_obj and service_obj.service_source == "third_party":
            service_ids.remove(service_id)
    # 批量操作
    app_manage_service.batch_operations(tenant_env=env, region_name=region_name, user=user, action=action,
                                        service_ids=service_ids, session=session)
