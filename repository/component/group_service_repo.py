from datetime import datetime

from sqlalchemy import select, delete, not_, text
from core.utils.status_translate import get_status_info_map
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.application.models import ComponentApplicationRelation
from models.component.models import Component, ComponentSourceInfo
from models.teams import ServiceDomain, ServiceTcpDomain
from repository.application.application_repo import application_repo
from repository.base import BaseRepository
from repository.region.region_info_repo import region_repo
from service.base_services import base_service


class ComponentRepository(BaseRepository[Component]):

    def get_service_by_tenant_and_alias(self, session, env_id, service_alias):
        services = session.execute(select(Component).where(
            Component.tenant_env_id == env_id,
            Component.service_alias == service_alias
        )).scalars().all()
        if services:
            return services[0]
        return None

    def get_services_by_service_ids_and_group_key(self, session, group_key, service_ids):
        """使用service_ids 和 group_key 查找一组云市应用下的组件"""
        service_source = session.execute(select(ComponentSourceInfo).where(
            ComponentSourceInfo.group_key == group_key,
            ComponentSourceInfo.service_id.in_(service_ids)
        )).scalars().all()
        service_ids = [service.service_id for service in service_source]
        return session.execute(select(Component).where(
            Component.service_id.in_(service_ids)
        )).scalars().all()

    def check_image_svc_by_eid(self, session):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_env_id = b.tenant_env_id
                AND a.create_status='complete'
                AND a.service_source IN ( 'docker_image', 'docker_compose', 'docker_run' )
                LIMIT 1"""
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def check_db_from_market_by_eid(self, session):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_env_id = b.tenant_env_id
                AND a.service_source = 'market'
                AND ( a.image LIKE "%mysql%" OR a.image LIKE "%postgres%" OR a.image LIKE "%mariadb%" )
                LIMIT 1"""
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def check_sourcecode_svc_by_eid(self, session):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_env_id = b.tenant_env_id
                AND a.service_source = 'source_code'
                AND a.create_status = 'complete'
                LIMIT 1"""
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def list_by_svc_share_uuids(self, session, group_id, dep_uuids):
        uuids = "'{}'".format("','".join(str(uuid) for uuid in dep_uuids))
        sql = """
            SELECT
                a.service_id,
                a.service_alias,
                a.service_cname,
                b.service_share_uuid
            FROM
                tenant_service a,
                service_source b,
                service_group_relation c
            WHERE
                a.tenant_env_id = b.tenant_env_id
                AND a.service_id = b.service_id
                AND b.service_share_uuid IN :uuids
                AND a.service_id = c.service_id
                AND c.group_id = :group_id
            """
        sql = text(sql).bindparams(group_id=group_id, uuids=tuple(uuids.split(",")))
        result = session.execute(sql).fetchall()
        return result

    def get_service_by_service_alias(self, session, service_alias):
        return (
            session.execute(
                select(Component).where(Component.service_alias == service_alias))
        ).scalars().first()

    def get_team_service_num_by_team_id(self, session, env_id, region_name, project_id=None):
        count = 0
        service_rels = session.execute(
            select(ComponentApplicationRelation).where(
                ComponentApplicationRelation.tenant_env_id == env_id,
                ComponentApplicationRelation.region_name == region_name)
        ).scalars().all()
        for rel in service_rels:
            service_id = rel.service_id
            group_id = rel.group_id
            app = application_repo.get_group_by_id_and_project_id(session, group_id, project_id)
            if app:
                service = service_info_repo.get_service_by_service_id(session, service_id)
                if service:
                    count += 1
        return count

    def get_hn_team_service_num_by_team_id(self, session, env_id):
        count = (session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.tenant_env_id == env_id))).scalars().all()
        return len(count)

    def get_services_in_multi_apps_with_app_info(self, session, group_ids):
        ids = "{0}".format(",".join(str(group_id) for group_id in group_ids))
        sql = """
        select svc.*, sg.id as group_id, sg.group_name, sg.region_name, sg.is_default, sg.note
        from tenant_service svc
            left join service_group_relation sgr on svc.service_id = sgr.service_id
            left join service_group sg on sg.id = sgr.group_id
        where sg.id in :ids and svc.is_delete=0;
        """
        sql = text(sql).bindparams(ids=tuple(ids.split(",")))

        return session.execute(sql).fetchall()

    def get_tenant_region_services(self, session, region, tenant_env_id):
        return (session.execute(select(Component).where(
            Component.service_region == region,
            Component.tenant_env_id == tenant_env_id))).scalars().all()

    def devops_get_tenant_region_services_by_service_id(self, session, tenant_env_id):
        return (session.execute(select(Component).where(
            Component.tenant_env_id == tenant_env_id))).scalars().all()

    def get_tenant_region_services_by_service_id(self, session, region, tenant_env_id, service_id):
        return (session.execute(select(Component).where(
            Component.service_region == region,
            Component.tenant_env_id == tenant_env_id,
            Component.is_delete == 0,
            not_(Component.service_id == service_id)))).scalars().all()

    def get_service(self, session, service_alias, env_id):
        service = session.execute(select(Component).where(
            Component.service_alias == service_alias,
            Component.tenant_env_id == env_id,
            Component.is_delete == 0)).scalars().first()
        if not service:
            raise ServiceHandleException(msg="not found service", msg_show="该组件不存在或已被删除", status_code=400)
        return service

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(Component).where(
            Component.service_id.in_(service_ids),
            Component.is_delete == 0)).scalars().all()

    def get_service_by_service_id(self, session, service_id, is_delete=False):
        return session.execute(select(Component).where(
            Component.service_id == service_id,
            Component.is_delete == is_delete)).scalars().first()

    def delete_service_by_service_id(self, session, service_id):
        return session.execute(select(Component).where(
            Component.service_id == service_id)).scalars().first()

    def get_group_service_by_group_id(self, session, group_id, region_name, tenant_env, query=""):
        # todo
        group_services_list = base_service.get_group_services_list(session=session, env_id=tenant_env.env_id,
                                                                   region_name=region_name, group_id=group_id,
                                                                   query=query)
        if not group_services_list:
            return []
        service_ids = [service.service_id for service in group_services_list]
        status_list = base_service.status_multi_service(session=session, region=region_name, tenant_env=tenant_env,
                                                        service_ids=service_ids)
        status_cache = {}
        statuscn_cache = {}
        for status in status_list:
            status_cache[status["service_id"]] = status["status"]
            statuscn_cache[status["service_id"]] = status["status_cn"]
        result = []
        for service in group_services_list:
            service = dict(service)
            service_obj = session.execute(select(Component).where(
                Component.service_id == service["service_id"])).scalars().first()
            if service_obj:
                service["service_source"] = service_obj.service_source

            service["service_domain"] = []
            # http服务
            service_domains = session.execute(select(ServiceDomain).where(
                ServiceDomain.service_id == service["service_id"])).scalars().all()
            if service_domains:
                for service_domain in service_domains:
                    service["service_domain"].append(service_domain.domain_name)
            # tcp服务
            service_tcp_domains = session.execute(select(ServiceTcpDomain).where(
                ServiceTcpDomain.service_id == service["service_id"])).scalars().all()
            if service_tcp_domains:
                for service_tcp_domain in service_tcp_domains:
                    end_point = service_tcp_domain.end_point
                    ip, port = end_point.split(":")
                    region = region_repo.get_region_by_region_name(session, region_name)
                    service["service_domain"].append(region.tcpdomain + ":" + port)

            service["status_cn"] = statuscn_cache.get(service["service_id"], "未知")
            status = status_cache.get(service["service_id"], "unknow")

            if status == "unknow" and service["create_status"] != "complete":
                service["status"] = "creating"
                service["status_cn"] = "创建中"
            else:
                service["status"] = status_cache.get(service["service_id"], "unknow")
            if service["status"] == "closed" or service["status"] == "undeploy":
                service["min_memory"] = 0
            status_map = get_status_info_map(service["status"])
            service.update(status_map)
            result.append(service)
        return result

    def get_services_by_env_and_region(self, session, env_id, region_name):
        return session.execute(select(Component).where(
            Component.service_region == region_name,
            Component.tenant_env_id == env_id),
            Component.is_delete == 0).scalars().all()

    def delete_services_by_team_and_region(self, session, env_id, region_name):
        session.execute(delete(Component).where(
            Component.service_region == region_name,
            Component.tenant_env_id == env_id))

    def get_services_by_service_group_ids(self, session, component_ids, service_group_ids):

        return (
            session.execute(
                select(Component).where(Component.service_id.in_(component_ids),
                                        Component.tenant_service_group_id.in_(service_group_ids),
                                        Component.is_delete == 0))
        ).scalars().all()

    def get_no_group_service_status_by_group_id(self, session, tenant_env, tenant_env_id, region_name):
        no_services = base_service.get_no_group_services_list(session=session, tenant_env_id=tenant_env_id,
                                                              region_name=region_name)
        if no_services:
            service_ids = [service.service_id for service in no_services]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name, tenant_env=tenant_env,
                                                            service_ids=service_ids)
            status_cache = {}
            statuscn_cache = {}
            for status in status_list:
                status_cache[status["service_id"]] = status["status"]
                statuscn_cache[status["service_id"]] = status["status_cn"]
            result = []
            for service in no_services:

                if service["group_name"] is None:
                    service["group_name"] = "未分组"
                service["status_cn"] = statuscn_cache.get(service["service_id"], "未知")
                status = status_cache.get(service["service_id"], "unknow")

                if status == "unknow" and service["create_status"] != "complete":
                    service["status"] = "creating"
                    service["status_cn"] = "创建中"
                else:
                    service["status"] = status_cache.get(service["service_id"], "unknow")
                if service["status"] == "closed" or service["status"] == "undeploy":
                    service["min_memory"] = 0

                status_map = get_status_info_map(service["status"])
                # todo
                service.update(status_map)
                result.append(service)

            return result
        else:
            return []

    def list_by_ids(self, session, service_ids):
        return (
            session.execute(
                select(Component).where(Component.service_id.in_(service_ids)))
        ).scalars().all()

    def list_by_ids_upgrade_group_id(self, session, service_ids, upgrade_group_id):
        return (
            session.execute(
                select(Component).where(
                    Component.service_id.in_(service_ids),
                    Component.tenant_service_group_id == upgrade_group_id))
        ).scalars().all()

    def get_services_by_service_ids(self, session, service_ids):
        return session.execute(
            select(Component).where(Component.service_id.in_(service_ids),
                                    Component.is_delete == 0)).scalars().all()

    def get_services_by_service_ids_tenant_env_id(self, session, service_ids, tenant_env_id):
        return session.execute(
            select(Component).where(
                Component.service_id.in_(service_ids),
                Component.tenant_env_id == tenant_env_id)).scalars().all()

    def delete_service(self, session, pk):
        session.execute(
            delete(Component).where(Component.ID == pk))

    def get_services_by_service_group_id(self, session, service_group_id):
        return (
            session.execute(
                select(Component).where(Component.tenant_service_group_id == service_group_id))
        ).scalars().all()

    def get_service_by_tenant_and_id(self, session, tenant_env_id, service_id):
        return (
            session.execute(
                select(Component).where(Component.tenant_env_id == tenant_env_id,
                                        Component.service_id == service_id))
        ).scalars().first()

    @staticmethod
    def change_service_image_tag(session, service, tag):
        """改变镜像标签"""
        ref_repo_name, ref_tag = service.image.split(":")
        service.image = "{}:{}".format(ref_repo_name, tag)
        service.version = tag
        session.flush()

    def get_logic_delete_records(self, session: SessionClass, delete_date: datetime):
        return (
            session.execute(
                select(Component).where(Component.delete_time < delete_date, Component.is_delete == True)
            )
        ).scalars().all()


service_info_repo = ComponentRepository(Component)
