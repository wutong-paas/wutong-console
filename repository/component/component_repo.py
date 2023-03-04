from sqlalchemy import select, delete, update

from database.session import SessionClass
from exceptions.bcode import ErrComponentGroupNotFound
from models.component.models import ComponentSourceInfo, TeamApplication
from repository.base import BaseRepository


class ComponentSourceRepository(BaseRepository[ComponentSourceInfo]):

    def update_service_source(self, session: SessionClass, env_id, service_id, **data):
        session.execute(update(ComponentSourceInfo).where(
            ComponentSourceInfo.tenant_env_id == env_id,
            ComponentSourceInfo.service_id == service_id).values(**data))

    def delete_service_source(self, session: SessionClass, env_id, service_id):
        session.execute(
            delete(ComponentSourceInfo).where(
                ComponentSourceInfo.service_id == service_id,
                ComponentSourceInfo.tenant_env_id == env_id)
        )

    def save(self, session: SessionClass, new_service_source):
        session.merge(new_service_source)

    def get_service_sources_by_service_ids(self, session: SessionClass, service_ids):
        """使用service_ids获取组件源信息的查询集"""
        return (
            #     todo
            session.execute(
                select(ComponentSourceInfo).where(ComponentSourceInfo.service_id.in_(service_ids)))
        ).scalars().all()

    def get_service_source(self, session: SessionClass, env_id, service_id):
        return session.execute(select(ComponentSourceInfo).where(
            ComponentSourceInfo.tenant_env_id == env_id,
            ComponentSourceInfo.service_id == service_id)).scalars().first()

    def get_service_sources(self, session: SessionClass, env_id, service_ids):
        return session.execute(select(ComponentSourceInfo).where(
            ComponentSourceInfo.tenant_env_id == env_id,
            ComponentSourceInfo.service_id.in_(service_ids))).scalars().all()

    def create_service_source(self, session: SessionClass, **params):
        ssi = ComponentSourceInfo(**params)
        session.add(ssi)


class TeamApplicationRepository(BaseRepository[TeamApplication]):

    def get_group_by_app_id(self, session: SessionClass, app_id):
        return (
            session.execute(
                select(TeamApplication).where(TeamApplication.service_group_id == app_id))
        ).scalars().all()

    def delete_tenant_service_group_by_pk(self, session: SessionClass, pk):
        session.execute(
            delete(TeamApplication).where(TeamApplication.ID == pk))

    def get_component_group(self, session: SessionClass, service_group_id):
        component_group = (session.execute(
            select(TeamApplication).where(TeamApplication.ID == service_group_id))).scalars().first()
        if not component_group:
            raise ErrComponentGroupNotFound
        return component_group


service_source_repo = ComponentSourceRepository(ComponentSourceInfo)
tenant_service_group_repo = TeamApplicationRepository(TeamApplication)
