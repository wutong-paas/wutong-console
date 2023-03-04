from sqlalchemy import select, delete

from database.session import SessionClass
from models.component.models import ComponentEnvVar
from repository.base import BaseRepository


class ServiceEnvVarRepository(BaseRepository[ComponentEnvVar]):

    def overwrite_by_component_ids(self, session, component_ids, envs):
        session.execute(delete(ComponentEnvVar).where(
            ComponentEnvVar.service_id.in_(component_ids)))
        for env in envs:
            session.merge(env)
        session.flush()

    def list_envs_by_component_ids(self, session, tenant_env_id, component_ids):
        return session.execute(select(ComponentEnvVar).where(
            ComponentEnvVar.tenant_env_id == tenant_env_id,
            ComponentEnvVar.service_id.in_(component_ids))).scalars().all()

    def get_service_env_by_tenant_env_id_and_service_id(self, session, tenant_env_id, service_id):
        return (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id))).scalars().all()

    def get_service_env(self, session, tenant_env_id, service_id, scopes, is_change,
                        attr_names, container_port, scope):
        return (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id,
                                          ComponentEnvVar.scope.in_(scopes),
                                          ComponentEnvVar.is_change == is_change,
                                          ComponentEnvVar.attr_name.in_(attr_names),
                                          ComponentEnvVar.container_port == container_port,
                                          ComponentEnvVar.scope == scope))).scalars().all()

    def get_service_env_by_port(self, session, tenant_env_id, service_id, port):
        return (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id,
                                          ComponentEnvVar.container_port == port))).scalars().all()

    def get_env_by_ids_and_attr_names(self, session, tenant_env_id, service_ids, attr_names):
        return (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id.in_(service_ids),
                                          ComponentEnvVar.attr_name.in_(attr_names),
                                          ComponentEnvVar.scope == "outer"))).scalars().all()

    def get_service_env_by_scope(self, session, tenant_env_id, service_id):
        return (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id,
                                          ComponentEnvVar.scope == "outer"))).scalars().all()

    def delete_service_env(self, session, tenant_env_id, service_id):
        session.execute(
            delete(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id))

    def get_service_envs(self, session, tenant_env_id, service_id):
        return session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                          ComponentEnvVar.service_id == service_id)).scalars().all()


env_var_repo = ServiceEnvVarRepository(ComponentEnvVar)
