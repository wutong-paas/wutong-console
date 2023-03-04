from sqlalchemy import select, delete

from database.session import SessionClass
from exceptions.main import AbortRequest
from models.component.models import ComponentEnvVar
from repository.base import BaseRepository


class TeamServiceEnvVarRepository(BaseRepository[ComponentEnvVar]):

    def get_service_env_by_attr_name(self, session, tenant_env_id, service_id, attr_name):
        return session.execute(select(ComponentEnvVar).where(
            ComponentEnvVar.tenant_env_id == tenant_env_id,
            ComponentEnvVar.service_id == service_id,
            ComponentEnvVar.attr_name == attr_name
        )).scalars().first()

    def get_service_env_by_port(self, session: SessionClass, tenant_env_id, service_id, port):
        return (
            session.execute(select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                                          ComponentEnvVar.service_id == service_id,
                                                          ComponentEnvVar.container_port == port))
        ).scalars().all()

    def get_service_env(self, session, tenant_env_id, service_id):
        return session.execute(select(ComponentEnvVar).where(
            ComponentEnvVar.tenant_env_id == tenant_env_id,
            ComponentEnvVar.service_id == service_id)).scalars().all()

    def delete_service_env_by_port(self, session: SessionClass, tenant_env_id, service_id, container_port):
        session.execute(delete(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                                      ComponentEnvVar.service_id == service_id,
                                                      ComponentEnvVar.container_port == container_port
                                                      ))

    def get_service_env_by_scope(self, session: SessionClass, tenant_env_id, service_id, scope):
        return (
            session.execute(select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                                          ComponentEnvVar.service_id == service_id,
                                                          ComponentEnvVar.scope == scope
                                                          ))).scalars().all()

    def delete_service_env_by_attr_name(self, session: SessionClass, tenant_env_id, service_id, attr_name):
        session.execute(delete(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                                      ComponentEnvVar.service_id == service_id,
                                                      ComponentEnvVar.attr_name == attr_name
                                                      ))

    def change_service_env_scope(self, env, scope):
        """变更环境变量范围"""
        try:
            scope = ComponentEnvVar.ScopeType(scope).value
            env.scope = scope
        except ValueError:
            raise AbortRequest(msg="the value of scope is outer or inner")


env_var_repo = TeamServiceEnvVarRepository(ComponentEnvVar)
