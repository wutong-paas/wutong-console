from sqlalchemy import select, func, delete, not_, update

from clients.remote_build_client import remote_build_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.bcode import ErrServiceMonitorExists, ErrRepeatMonitoringTarget
from exceptions.main import ServiceHandleException
from models.component.models import ComponentMonitor
from repository.component.service_config_repo import port_repo
from service.app_config.port_service import port_service


class ComponentServiceMonitor(object):

    def overwrite_by_component_ids(self, session, component_ids, monitors):
        session.execute(delete(ComponentMonitor).where(
            ComponentMonitor.service_id.in_(component_ids)
        ))
        session.add_all(monitors)

    def delete_by_service_id(self, session, service_id):
        session.execute(
            delete(ComponentMonitor).where(ComponentMonitor.service_id == service_id)
        )

    def create_component_service_monitor(self, session: SessionClass, tenant, service, name, path, port,
                                         service_show_name, interval,
                                         user=None):
        sm_count = session.execute(select(func.count(ComponentMonitor.ID)).where(
            ComponentMonitor.tenant_id == tenant.tenant_id,
            ComponentMonitor.name == name
        )).first()[0]
        sm_port_count = session.execute(select(func.count(ComponentMonitor.ID)).where(
            ComponentMonitor.service_id == service.service_id,
            ComponentMonitor.port == port,
            ComponentMonitor.path == path,
        )).first()[0]
        if sm_count > 0:
            raise ErrServiceMonitorExists
        if sm_port_count > 0:
            raise ErrRepeatMonitoringTarget
        if not port_service.get_service_port_by_port(session=session, service=service, port=port):
            raise ServiceHandleException(msg="port not found", msg_show="配置的组件端口不存在", status_code=400, error_code=400)
        req = {"name": name, "path": path, "port": port, "service_show_name": service_show_name, "interval": interval,
               "operator": user.get_name() if user else None}
        if service.create_status == "complete":
            remote_build_client.create_service_monitor(session,
                                                       tenant.enterprise_id, service.service_region,
                                                       tenant.tenant_name,
                                                       service.service_alias, req)
        req.pop("operator")
        req["service_id"] = service.service_id
        req["tenant_id"] = tenant.tenant_id
        try:
            sm = ComponentMonitor(**req)
            session.add(sm)
            return sm
        except Exception as e:
            if service.create_status == "complete":
                remote_build_client.delete_service_monitor(session,
                                                           tenant.enterprise_id, service.service_region,
                                                           tenant.tenant_name,
                                                           service.service_alias, name, None)
            raise e

    def get_component_service_monitors(self, session: SessionClass, tenant_id, service_id):
        return (session.execute(select(ComponentMonitor).where(
            ComponentMonitor.service_id == service_id,
            ComponentMonitor.tenant_id == tenant_id))).scalars().all()

    def bulk_create_component_service_monitors(self, session: SessionClass, tenant, service, service_monitors):
        monitor_list = []
        for monitor in service_monitors:
            count = (session.execute(select(func.count(ComponentMonitor.ID)).where(
                ComponentMonitor.name == monitor["name"],
                ComponentMonitor.tenant_id == tenant.tenant_id))).first()[0]
            if count > 0:
                monitor["name"] = "-".join([monitor["name"], make_uuid()[-4:]])
            data = ComponentMonitor(
                name=monitor["name"],
                tenant_id=tenant.tenant_id,
                service_id=service.service_id,
                path=monitor["path"],
                port=monitor["port"],
                service_show_name=monitor["service_show_name"],
                interval=monitor["interval"])
            monitor_list.append(data)
        port_repo.bulk_all(session, monitor_list)

    def list_by_service_ids(self, session, tenant_id, service_ids):
        return (session.execute(select(ComponentMonitor).where(
            ComponentMonitor.service_id.in_(service_ids),
            ComponentMonitor.tenant_id == tenant_id))).scalars().all()

    def get_tenant_service_monitor(self, session, tenant_id, name):
        return (session.execute(select(ComponentMonitor).where(
            ComponentMonitor.name == name,
            ComponentMonitor.tenant_id == tenant_id))).scalars().all()

    def get_component_service_monitor(self, session, tenant_id, service_id, name):
        return session.execute(select(ComponentMonitor).where(
            ComponentMonitor.tenant_id == tenant_id,
            ComponentMonitor.service_id == service_id,
            ComponentMonitor.name == name
        )).scalars().first()

    def update_component_service_monitor(self, session, tenant, service, user, name, path, port, service_show_name,
                                         interval):
        sm = self.get_component_service_monitor(session, tenant.tenant_id, service.service_id, name)
        if not sm:
            raise ServiceHandleException(msg="service monitor is not found", msg_show="配置不存在", status_code=404)
        sm_count = session.execute(select(func.count(ComponentMonitor.ID)).where(
            ComponentMonitor.service_id == service.service_id,
            ComponentMonitor.port == port,
            ComponentMonitor.path == path,
            not_(ComponentMonitor.name == name)
        )).first()[0]
        if sm_count > 0:
            raise ServiceHandleException(msg="service monitor is exist", msg_show="重复的监控目标", status_code=400,
                                         error_code=400)
        if not port_service.get_service_port_by_port(session, service, port):
            raise ServiceHandleException(msg="port not found", msg_show="配置的组件端口不存在", status_code=400, error_code=400)
        req = {"path": path, "port": port, "service_show_name": service_show_name, "interval": interval,
               "operator": user.get_name()}
        remote_build_client.update_service_monitor(session,
                                                   tenant.enterprise_id, service.service_region, tenant.tenant_name,
                                                   service.service_alias, name, req)
        req.pop("operator")
        session.execute(update(ComponentMonitor).where(
            ComponentMonitor.tenant_id == tenant.tenant_id,
            ComponentMonitor.service_id == service.service_id,
            ComponentMonitor.name == name
        ).values(**req))
        return self.get_component_service_monitor(session, tenant.tenant_id, service.service_id, name)

    def delete_component_service_monitor(self, session, tenant, service, user, name):
        sm = self.get_component_service_monitor(session, tenant.tenant_id, service.service_id, name)
        if not sm:
            raise ServiceHandleException(msg="service monitor is not found", msg_show="配置不存在", status_code=404)
        body = {
            "operator": user.get_name(),
        }
        try:
            remote_build_client.delete_service_monitor(session,
                                                       tenant.enterprise_id, service.service_region, tenant.tenant_name,
                                                       service.service_alias, name, body)
        except ServiceHandleException as e:
            if e.error_code != 10101:
                raise e
        session.execute(delete(ComponentMonitor).where(
            ComponentMonitor.tenant_id == tenant.tenant_id,
            ComponentMonitor.service_id == service.service_id,
            ComponentMonitor.name == name
        ))
        return sm


service_monitor_service = ComponentServiceMonitor()
