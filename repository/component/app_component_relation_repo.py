from sqlalchemy import select, delete, func

from models.application.models import ComponentApplicationRelation, Application
from repository.base import BaseRepository


class ComponentApplicationRelationRepository(BaseRepository[ComponentApplicationRelation]):

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
            select(ComponentApplicationRelation).where(
                ComponentApplicationRelation.service_id == service_id)).scalars().first()

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
                select(ComponentApplicationRelation.service_id).where(
                    ComponentApplicationRelation.tenant_id == tenant_id,
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


app_component_relation_repo = ComponentApplicationRelationRepository(ComponentApplicationRelation)
