from sqlalchemy import select, not_

from exceptions.bcode import ErrAppUpgradeRecordNotFound
from models.application.models import ApplicationUpgradeRecord, ApplicationUpgradeStatus
from repository.base import BaseRepository


class AppUpgradeRepository(BaseRepository[ApplicationUpgradeRecord]):

    @staticmethod
    def list_by_rollback_records(session, parent_id):
        return session.execute(select(ApplicationUpgradeRecord).where(
            ApplicationUpgradeRecord.parent_id == parent_id
        ).order_by(ApplicationUpgradeRecord.create_time.desc())).scalars().all()

    @staticmethod
    def create_app_upgrade_record(session, **kwargs):
        app_upgrade_record = ApplicationUpgradeRecord(**kwargs)
        session.add(app_upgrade_record)
        session.flush()
        return app_upgrade_record

    def change_app_record_status(self, session, app_record, status):
        """改变应用升级记录状态"""
        app_record.status = status

    def get_by_record_id(self, session, record_id: int):
        record = session.execute(select(ApplicationUpgradeRecord).where(
            ApplicationUpgradeRecord.ID == record_id
        )).scalars().first()
        if not record:
            raise ErrAppUpgradeRecordNotFound
        return record

    def get_app_not_upgrade_record(self, session, tenant_env_id, group_id, group_key):
        result = session.execute(
            select(ApplicationUpgradeRecord).where(
                ApplicationUpgradeRecord.status < ApplicationUpgradeStatus.UPGRADED.value,
                ApplicationUpgradeRecord.tenant_env_id == tenant_env_id,
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

    def get_last_upgrade_record(self, session, tenant_env_id, app_id, upgrade_group_id=None, record_type=None):
        sql = "select * from app_upgrade_record where group_id=:group_id and tenant_env_id=:tenant_env_id"
        params = {
            "group_id": app_id,
            "tenant_env_id": tenant_env_id,
            "upgrade_group_id": upgrade_group_id,
            "record_type": record_type
        }
        if upgrade_group_id:
            sql += " and upgrade_group_id=:upgrade_group_id"
        if record_type:
            sql += " and record_type=:record_type"

        records = session.execute(sql, params).fetchall()
        if records:
            return records[0]
        else:
            return None


upgrade_repo = AppUpgradeRepository(ApplicationUpgradeRecord)
