from sqlalchemy import select

from models.application.models import ComponentApplicationRelation
from repository.base import BaseRepository


class ServiceGroupRelationRepositry(BaseRepository[ComponentApplicationRelation]):

    def get_group_id_by_service(self, session, svc):
        group = session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.service_id == svc.service_id,
            ComponentApplicationRelation.tenant_id == svc.tenant_id,
            ComponentApplicationRelation.region_name == svc.service_region)).scalars().first()
        if group:
            return group.group_id
        return None

    def bulk_create(self, session, service_group_rels):
        session.add_all(service_group_rels)
        

    def get_components_by_app_id(self, session, app_id):
        return session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.group_id == app_id
        )).scalars().all()


service_group_relation_repo = ServiceGroupRelationRepositry(ComponentApplicationRelation)
