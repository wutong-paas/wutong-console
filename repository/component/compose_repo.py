from sqlalchemy import select, delete

from models.application.models import ComposeGroup, ComposeServiceRelation
from repository.base import BaseRepository


class ComposeGroupRepository(BaseRepository[ComposeGroup]):

    def delete_group_compose_by_group_id(self, session, group_id):
        session.execute(
            delete(ComposeGroup).where(
                ComposeGroup.group_id == group_id)
        )
        session.flush()

    def delete_group_compose_by_compose_id(self, session, compose_id):
        session.execute(
            delete(ComposeGroup).where(
                ComposeGroup.compose_id == compose_id)
        )
        session.flush()

    def get_group_compose_by_compose_id(self, session, compose_id):
        return session.execute(select(ComposeGroup).where(
            ComposeGroup.compose_id == compose_id
        )).scalars().first()

    def create_group_compose(self, session, **params):
        cg = ComposeGroup(**params)
        session.add(cg)
        session.flush()
        return cg

    def get_group_compose_by_group_id(self, session, group_id):
        return (
            session.execute(select(ComposeGroup).where(ComposeGroup.group_id == group_id))
        ).scalars().first()


class ComposeServiceRelationRepository(BaseRepository[ComposeServiceRelation]):

    def bulk_create_compose_service_relation(self, session, service_ids, team_id, compose_id):
        csr_list = []
        for service_id in service_ids:
            csr = ComposeServiceRelation()
            csr.compose_id = compose_id
            csr.team_id = team_id
            csr.service_id = service_id
            csr_list.append(csr)
        session.add_all(csr_list)
        session.flush()

    def delete_compose_service_relation_by_compose_id(self, session, compose_id):
        session.execute(
            delete(ComposeServiceRelation).where(
                ComposeServiceRelation.compose_id == compose_id)
        )
        session.flush()

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
