from sqlalchemy import select
from models.application.models import Application, ComponentApplicationRelation
from models.component.models import TeamComponentInfo
from models.teams import TeamEnvInfo


class HunanExpresswayRepository(object):

    def get_all_app(self, session, region_name):
        return session.execute(select(Application).where(
            Application.region_name == region_name
        )).scalars().all()

    def get_app_by_app_id(self, session, app_id):
        return session.execute(select(Application).where(
            Application.ID == app_id
        )).scalars().first()

    def get_tenant_by_tenant_id(self, session, tenant_id):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.tenant_id == tenant_id
        )).scalars().first()

    def get_groups_by_service_id(self, session, service_ids):
        return session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.service_id.in_(service_ids)
        )).scalars().all()

    def get_services_by_tenant_id(self, session, tenant_id):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.tenant_id == tenant_id
        )).scalars().all()


hunan_expressway_repo = HunanExpresswayRepository()
