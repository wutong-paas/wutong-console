from sqlalchemy import select, not_

from models.application.models import ApplicationUpgradeRecord, ApplicationUpgradeStatus
from repository.base import BaseRepository


class AppUpgradeRepository(BaseRepository[ApplicationUpgradeRecord]):

    def get_app_not_upgrade_record(self, session, tenant_id, group_id, group_key):
        result = session.execute(
            select(ApplicationUpgradeRecord).where(ApplicationUpgradeRecord.status < ApplicationUpgradeStatus.UPGRADED.value,
                                                   ApplicationUpgradeRecord.tenant_id == tenant_id,
                                                   ApplicationUpgradeRecord.group_id == group_id,
                                                   ApplicationUpgradeRecord.group_key == group_key).order_by(
                ApplicationUpgradeRecord.update_time.desc())).scalars().first()
        return result

    def list_records_by_app_id(self, session, app_id, record_type=None):
        sql = select(ApplicationUpgradeRecord).where(
            ApplicationUpgradeRecord.group_id == app_id,
            not_(ApplicationUpgradeRecord.status == 1)
        ).order_by(ApplicationUpgradeRecord.create_time.desc())
        if record_type:
            sql = select(ApplicationUpgradeRecord).where(
                ApplicationUpgradeRecord.group_id == app_id,
                ApplicationUpgradeRecord.record_type == record_type,
                not_(ApplicationUpgradeRecord.status == 1)
            ).order_by(ApplicationUpgradeRecord.create_time.desc())
        return (session.execute(sql)).scalars().all()

    def get_last_upgrade_record(self, session, tenant_id, app_id, upgrade_group_id=None, record_type=None):
        sql = select(ApplicationUpgradeRecord).where(
            ApplicationUpgradeRecord.group_id == app_id,
            ApplicationUpgradeRecord.tenant_id == tenant_id
        ).order_by(ApplicationUpgradeRecord.update_time.desc())
        if upgrade_group_id:
            sql = select(ApplicationUpgradeRecord).where(
                ApplicationUpgradeRecord.group_id == app_id,
                ApplicationUpgradeRecord.tenant_id == tenant_id,
                ApplicationUpgradeRecord.upgrade_group_id == upgrade_group_id
            ).order_by(ApplicationUpgradeRecord.update_time.desc())
        if record_type:
            sql = select(ApplicationUpgradeRecord).where(
                ApplicationUpgradeRecord.group_id == app_id,
                ApplicationUpgradeRecord.tenant_id == tenant_id,
                ApplicationUpgradeRecord.record_type == record_type
            ).order_by(ApplicationUpgradeRecord.update_time.desc())
        return (session.execute(sql)).scalars().first()


upgrade_repo = AppUpgradeRepository(ApplicationUpgradeRecord)
