import datetime

from loguru import logger
from sqlalchemy import update

from database.session import SessionClass
from models.application.models import Application, ComponentApplicationRelation
from repository.component.group_service_repo import service_info_repo
from service.app_actions.app_manage import app_manage_service


def logic_delete_application(session, app_id, region_name, user, env):
    # 停止当前组件
    _stop_app(session=session, app_id=app_id, region_name=region_name, user=user, env=env)

    # 逻辑删除当前组件
    _logic_delete_app(session=session, app_id=app_id)


def _stop_app(session, app_id, region_name, user, env):
    services = session.query(ComponentApplicationRelation).filter(
        ComponentApplicationRelation.group_id == app_id).all()

    if not services:
        logger.info("当前应用无组件")
        return
    service_ids = [service.service_id for service in services]
    action = "stop"
    # 去除掉第三方组件
    for service_id in service_ids:
        service_obj = service_info_repo.get_service_by_service_id(session, service_id)
        if service_obj and service_obj.service_source == "third_party":
            service_ids.remove(service_id)
    # 批量操作
    app_manage_service.batch_operations(tenant_env=env, region_name=region_name, user=user, action=action,
                                        service_ids=service_ids, session=session)


def _logic_delete_app(session: SessionClass, app_id):
    # 逻辑删除group
    update_data = {
        "is_delete": True,
        "delete_time": datetime.datetime.now(),
        "delete_operator": "system"
    }
    session.execute(update(Application).where(Application.ID == app_id).values(**update_data))
