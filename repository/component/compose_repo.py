from sqlalchemy import select, delete

from models.application.models import ComposeGroup, ComposeServiceRelation
from repository.base import BaseRepository


class ComposeGroupRepository(BaseRepository[ComposeGroup]):

    def get_group_compose_by_group_id(self, session, group_id):
        return (
            session.execute(select(ComposeGroup).where(ComposeGroup.group_id == group_id))
        ).scalars().first()


class ComposeServiceRelationRepository(BaseRepository[ComposeServiceRelation]):

    def delete_relation_by_service_id(self, session, service_id):
        session.execute(
            delete(ComposeServiceRelation).where(
                ComposeServiceRelation.service_id == service_id)
        )

    def get_compose_id_by_service_id(self, session, service_id):
        return (session.execute(select(ComposeServiceRelation).where(
            ComposeServiceRelation.service_id == service_id))).scalars().first()

    def get_compose_service_relation_by_compose_id(self, session, compose_id):
        return (session.execute(select(ComposeServiceRelation).where(
            ComposeServiceRelation.compose_id == compose_id))).scalars().all()


compose_repo = ComposeGroupRepository(ComposeGroup)
compose_relation_repo = ComposeServiceRelationRepository(ComposeServiceRelation)
