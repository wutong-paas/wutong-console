from sqlalchemy import select, func, delete, not_

from core.utils.status_translate import get_status_info_map
from models.application.models import ComponentApplicationRelation, Application
from models.component.models import TeamComponentInfo, ComponentSourceInfo
from repository.base import BaseRepository
from service.base_services import base_service


class GroupServiceRelationRepository(BaseRepository[ComponentApplicationRelation]):

    def get_group_info_by_service_id(self, session, service_id):
        sgrs = session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.service_id == service_id
        )).scalars().all()
        if not sgrs:
            return None
        relation = sgrs[0]
        return session.execute(select(Application).where(
            Application.ID == relation.group_id
        )).scalars().first()

    def delete_relation_by_group_id(self, session, group_id):
        session.execute(delete(ComponentApplicationRelation).where(
            ComponentApplicationRelation.group_id == group_id))

    def add_service_group_relation(self, session, group_id, service_id, tenant_id, region_name):
        sgr = ComponentApplicationRelation(
            service_id=service_id, group_id=group_id, tenant_id=tenant_id, region_name=region_name)
        session.add(sgr)
        session.flush()
        return sgr

    def get_service_group_relation_by_groups(self, session, group_ids):
        return (
            session.execute(
                select(ComponentApplicationRelation).where(ComponentApplicationRelation.group_id.in_(group_ids)))
        ).scalars().all()

    def get_group_by_service_id(self, session, service_id):
        return session.execute(
            select(ComponentApplicationRelation).where(ComponentApplicationRelation.service_id == service_id)).scalars().first()

    def count_service_by_app_id(self, session, app_id):
        """
        统计应用下组件数量
        :param app_id:
        :return:
        """
        return (session.execute(
            select(func.count(ComponentApplicationRelation.ID)).where(ComponentApplicationRelation.group_id == app_id)
        )).first()[0]

    def list_serivce_ids_by_app_id(self, session, tenant_id, region_name, app_id):
        service_ids = (
            session.execute(
                select(ComponentApplicationRelation.service_id).where(ComponentApplicationRelation.tenant_id == tenant_id,
                                                                      ComponentApplicationRelation.region_name == region_name,
                                                                      ComponentApplicationRelation.group_id == app_id))
        ).scalars().all()
        return service_ids

    def get_services_by_group(self, session, group_id):
        return session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.group_id == group_id)).scalars().all()

    def get_group_by_service_ids(self, session, service_ids):
        sgr = session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.service_id.in_(service_ids))).scalars().all()
        sgr_map = {s.service_id: s.group_id for s in sgr}
        group_ids = [g.group_id for g in sgr]
        groups = session.execute(select(Application).where(
            Application.ID.in_(group_ids))).scalars().all()
        group_map = {g.ID: g.group_name for g in groups}
        result_map = {}
        for service_id in service_ids:
            group_id = sgr_map.get(service_id, None)
            group_info = dict()
            if group_id:
                group_info["group_name"] = group_map[group_id]
                group_info["group_id"] = group_id
                result_map[service_id] = group_info
            else:
                group_info["group_name"] = "未分组"
                group_info["group_id"] = -1
                result_map[service_id] = group_info
        return result_map

    def delete_relation_by_service_id(self, session, service_id):
        session.execute(
            delete(ComponentApplicationRelation).where(ComponentApplicationRelation.service_id == service_id)
        )

    def save(self, session, gsr):
        session.merge(gsr)

    def create_service_group_relation(self, session, **params):
        gsr = ComponentApplicationRelation(**params)
        session.add(gsr)

        return gsr

    def get_services_by_tenant_id_and_group(self, session, tenant_id, response_region, group_id):
        return (
            session.execute(
                select(Application).where(
                    Application.tenant_id == tenant_id,
                    Application.region_name == response_region,
                    Application.ID == group_id))
        ).scalars().first()


class ServiceInfoRepository(BaseRepository[TeamComponentInfo]):
    def get_services_by_service_ids_and_group_key(self, session, group_key, service_ids):
        """使用service_ids 和 group_key 查找一组云市应用下的组件"""
        service_source = session.execute(select(ComponentSourceInfo).where(
            ComponentSourceInfo.group_key == group_key,
            ComponentSourceInfo.service_id.in_(service_ids)
        )).scalars().all()
        service_ids = [service.service_id for service in service_source]
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_ids)
        )).scalars().all()

    def check_image_svc_by_eid(self, session, eid):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_id = b.tenant_id
                AND b.enterprise_id = "{eid}"
                AND a.create_status="complete"
                AND a.service_source IN ( "docker_image", "docker_compose", "docker_run" )
                LIMIT 1""".format(eid=eid)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def check_db_from_market_by_eid(self, session, eid):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_id = b.tenant_id
                AND b.enterprise_id = "{eid}"
                AND a.service_source = "market"
                AND ( a.image LIKE "%mysql%" OR a.image LIKE "%postgres%" OR a.image LIKE "%mariadb%" )
                LIMIT 1""".format(eid=eid)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def check_sourcecode_svc_by_eid(self, session, eid):
        sql = """
            SELECT
                service_alias
            FROM
                tenant_service a,
                tenant_info b
            WHERE
                a.tenant_id = b.tenant_id
                AND b.enterprise_id = "{eid}"
                AND a.service_source = "source_code"
                AND a.create_status = "complete"
                LIMIT 1""".format(eid=eid)
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
                a.tenant_id = b.team_id
                AND a.service_id = b.service_id
                AND b.service_share_uuid IN ( {uuids} )
                AND a.service_id = c.service_id
                AND c.group_id = {group_id}
            """.format(
            group_id=group_id, uuids=uuids)
        result = session.execute(sql).fetchall()
        return result

    def get_service_by_service_alias(self, session, service_alias):
        return (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.service_alias == service_alias))
        ).scalars().first()

    def get_team_service_num_by_team_id(self, session, team_id, region_name):
        count = (session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.tenant_id == team_id,
            ComponentApplicationRelation.region_name == region_name))).scalars().all()
        return len(count)

    def get_services_in_multi_apps_with_app_info(self, session, group_ids):
        ids = "{0}".format(",".join(str(group_id) for group_id in group_ids))
        sql = """
        select svc.*, sg.id as group_id, sg.group_name, sg.region_name, sg.is_default, sg.note
        from tenant_service svc
            left join service_group_relation sgr on svc.service_id = sgr.service_id
            left join service_group sg on sg.id = sgr.group_id
        where sg.id in ({ids});
        """.format(ids=ids)

        return session.execute(sql).fetchall()

    def get_tenant_region_services(self, session, region, tenant_id):
        return (session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_region == region,
            TeamComponentInfo.tenant_id == tenant_id))).scalars().all()

    def devops_get_tenant_region_services_by_service_id(self, session, tenant_id):
        return (session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.tenant_id == tenant_id))).scalars().all()

    def get_tenant_region_services_by_service_id(self, session, region, tenant_id, service_id):
        return (session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_region == region,
            TeamComponentInfo.tenant_id == tenant_id,
            not_(TeamComponentInfo.service_id == service_id)))).scalars().all()

    def get_service(self, session, service_alias, tenant_id):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_alias == service_alias,
            TeamComponentInfo.tenant_id == tenant_id)).scalars().first()

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_ids))).scalars().all()

    def get_service_by_service_id(self, session, service_id):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id == service_id)).scalars().first()

    def get_group_service_by_group_id(self, session, group_id, region_name, team_id, team_name, enterprise_id,
                                      query=""):
        # todo
        group_services_list = base_service.get_group_services_list(session=session, team_id=team_id,
                                                                   region_name=region_name, group_id=group_id,
                                                                   query=query)
        if not group_services_list:
            return []
        service_ids = [service.service_id for service in group_services_list]
        status_list = base_service.status_multi_service(session=session, region=region_name, tenant_name=team_name,
                                                        service_ids=service_ids, enterprise_id=enterprise_id)
        status_cache = {}
        statuscn_cache = {}
        for status in status_list:
            status_cache[status["service_id"]] = status["status"]
            statuscn_cache[status["service_id"]] = status["status_cn"]
        result = []
        for service in group_services_list:
            service = dict(service)
            service_obj = session.execute(select(TeamComponentInfo).where(
                TeamComponentInfo.service_id == service["service_id"])).scalars().first()
            if service_obj:
                service["service_source"] = service_obj.service_source
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

    def get_services_by_team_and_region(self, session, team_id, region_name):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_region == region_name,
            TeamComponentInfo.tenant_id == team_id)).scalars().all()

    def delete_services_by_team_and_region(self, session, team_id, region_name):
        session.execute(delete(TeamComponentInfo).where(
            TeamComponentInfo.service_region == region_name,
            TeamComponentInfo.tenant_id == team_id))

    def get_services_by_service_group_ids(self, session, component_ids, service_group_ids):

        return (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.service_id.in_(component_ids),
                                                TeamComponentInfo.tenant_service_group_id.in_(service_group_ids)))
        ).scalars().all()

    def get_no_group_service_status_by_group_id(self, session, team_name, team_id, region_name, enterprise_id):
        no_services = base_service.get_no_group_services_list(session=session, team_id=team_id,
                                                              region_name=region_name)
        if no_services:
            service_ids = [service.service_id for service in no_services]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name, tenant_name=team_name,
                                                            service_ids=service_ids, enterprise_id=enterprise_id)
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
                select(TeamComponentInfo).where(TeamComponentInfo.service_id.in_(service_ids)))
        ).scalars().all()

    def list_by_ids_upgrade_group_id(self, session, service_ids, upgrade_group_id):
        return (
            session.execute(
                select(TeamComponentInfo).where(
                    TeamComponentInfo.service_id.in_(service_ids),
                    TeamComponentInfo.tenant_service_group_id == upgrade_group_id))
        ).scalars().all()

    def get_services_by_service_ids(self, session, service_ids):
        return session.execute(
            select(TeamComponentInfo).where(TeamComponentInfo.service_id.in_(service_ids))).scalars().all()

    def get_services_by_service_ids_tenant_id(self, session, service_ids, tenant_id):
        return session.execute(
            select(TeamComponentInfo).where(
                TeamComponentInfo.service_id.in_(service_ids),
                TeamComponentInfo.tenant_id == tenant_id)).scalars().all()

    def save_service(self, session, service):
        session.merge(service)
        session.flush()

    def delete_service(self, session, pk):
        session.execute(
            delete(TeamComponentInfo).where(TeamComponentInfo.ID == pk))

    def get_services_by_service_group_id(self, session, service_group_id):
        return (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.tenant_service_group_id == service_group_id))
        ).scalars().all()

    def get_service_by_tenant_and_id(self, session, tenant_id, service_id):
        return (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.tenant_id == tenant_id,
                                                TeamComponentInfo.service_id == service_id))
        ).scalars().first()


group_service_relation_repo = GroupServiceRelationRepository(ComponentApplicationRelation)
service_repo = ServiceInfoRepository(TeamComponentInfo)
