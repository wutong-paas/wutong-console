import datetime
from models.application.models import ComponentApplicationRelation, Application
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_visit_service


def logic_delete_by_env_id(session, user, env, region_code):
    # 查询环境下全部应用，停用全部组件
    # 环境、应用、组件 标记为逻辑删除
    stop_env_resource(session=session, env=env, region_code=region_code, user=user)


def stop_env_resource(session, env, region_code, user):
    action = "stop"
    apps = application_repo.get_tenant_region_groups(session, env.env_id, region_code)
    for app in apps:
        app = Application(**app)
        group_id = app.ID

        # 应用访问记录删除
        app_vists = application_visit_service.get_app_visit_record_by_app_id(session, group_id)
        if app_vists:
            for app_vist in app_vists:
                app_vist.is_delete = True
                app_vist.delete_time = datetime.datetime.now()
                app_vist.delete_operator = user.nick_name

        services = session.query(ComponentApplicationRelation).filter(
            ComponentApplicationRelation.group_id == group_id).all()
        if not services:
            app.is_delete = True
            app.delete_time = datetime.datetime.now()
            app.delete_operator = user.nick_name
            session.merge(app)
            continue
        service_ids = [service.service_id for service in services]
        # 去除掉第三方组件
        for service_id in service_ids:
            service_obj = service_info_repo.delete_service_by_service_id(session, service_id)
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
        session.merge(app)
    env.is_delete = True
    env.delete_time = datetime.datetime.now()
    env.delete_operator = user.nick_name
