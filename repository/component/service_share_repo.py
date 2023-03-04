from fastapi_pagination import Params, paginate
from sqlalchemy import select, func, not_, delete, text

from models.application.models import ServiceShareRecord, ComponentApplicationRelation, ServiceShareRecordEvent
from models.application.plugin import TeamComponentPluginRelation
from models.component.models import TeamComponentInfo
from models.market.models import CenterApp, CenterAppVersion
from repository.base import BaseRepository


class ComponentShareRepository(BaseRepository[ServiceShareRecord]):
    def check_app_by_eid(self, session):
        """
        check if an app has been shared
        """
        sql = """
            SELECT
                a.team_name
            FROM
                service_share_record a,
                tenant_info b
            WHERE
                a.team_name = b.tenant_name
                LIMIT 1"""
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def count_by_app_id(self, session, app_id):
        """
        统计应用分享数量

        :param app_id:
        :return:
        """
        return (session.execute(
            select(func.count(ServiceShareRecord.ID)).where(ServiceShareRecord.group_id == app_id,
                                                            ServiceShareRecord.status.in_([0, 1, 2]))
        )).first()[0]

    def get_service_share_records_by_groupid(self, session, team_name, group_id, page=1, page_size=10):
        query = session.execute(select(ServiceShareRecord).where(
            ServiceShareRecord.group_id == group_id,
            ServiceShareRecord.team_name == team_name,
            ServiceShareRecord.status.in_([0, 1, 2])
        ).order_by(ServiceShareRecord.create_time.desc())).scalars().all()
        params = Params(page=page, size=page_size)
        event_paginator = paginate(query, params)
        total = event_paginator.total
        page_events = event_paginator.items
        return total, page_events

    def get_service_list_by_group_id(self, session, tenant_env, group_id):
        svc_relations = (session.execute(
            select(ComponentApplicationRelation).where(
                ComponentApplicationRelation.tenant_env_id == tenant_env.env_id,
                ComponentApplicationRelation.group_id == group_id)
        )).scalars().all()
        if not svc_relations:
            return []
        svc_ids = [svc_rel.service_id for svc_rel in svc_relations]
        return (session.execute(
            select(TeamComponentInfo).where(
                TeamComponentInfo.service_id.in_(svc_ids),
                not_(TeamComponentInfo.service_source == 'third_party'))
        )).scalars().all()

    def create_service_share_record(self, session, **kwargs):
        service_share_record = ServiceShareRecord(**kwargs)
        session.add(service_share_record)
        session.flush()
        return service_share_record

    def get_service_share_record_by_ID(self, session, ID, team_name):
        return session.execute(
            select(ServiceShareRecord).where(
                ServiceShareRecord.ID == ID,
                ServiceShareRecord.team_name == team_name)
        ).scalars().first()

    def delete_record(self, session, ID, team_name):
        session.execute(
            delete(ServiceShareRecord).where(
                ServiceShareRecord.ID == ID,
                ServiceShareRecord.team_name == team_name))

    def get_app_by_key(self, session, key):
        return session.execute(
            select(CenterApp).where(
                CenterApp.app_id == key)
        ).scalars().first()

    def delete_app(self, session, key):
        session.execute(
            delete(CenterApp).where(
                CenterApp.app_id == key))
        session.flush()

    def get_app_version_by_record_id(self, session, record_id):
        return session.execute(
            select(CenterAppVersion).where(
                CenterAppVersion.record_id == record_id)
        ).scalars().first()

    def delete_tenant_service_plugin_relation(self, session, service_id):
        session.execute(
            delete(TeamComponentPluginRelation).where(TeamComponentPluginRelation.service_id == service_id)
        )

    def get_service_share_record_by_groupid(self, session, group_id):
        return session.execute(
            select(ServiceShareRecord).where(
                ServiceShareRecord.group_id == group_id)).scalars().first()


class ServiceShareRecordEventRepository(BaseRepository[ServiceShareRecordEvent]):
    pass


component_share_repo = ComponentShareRepository(ServiceShareRecord)
component_share_event_repo = ServiceShareRecordEventRepository(ServiceShareRecordEvent)
