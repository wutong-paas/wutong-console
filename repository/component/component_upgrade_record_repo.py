from sqlalchemy import delete, select

from models.application.models import ServiceUpgradeRecord
from repository.base import BaseRepository


class ComponentUpgradeRecordRepository(BaseRepository[ServiceUpgradeRecord]):

    def list_by_app_record_id(self, session, app_record_id):
        return (session.execute(select(ServiceUpgradeRecord).where(
            ServiceUpgradeRecord.app_upgrade_record_id == app_record_id
        ))).scalars().all()

    def save(self, session, app_upgrade_record):
        session.merge(app_upgrade_record)
        session.flush()
        
    def bulk_update(self, session, records):
        for record in records:
            session.merge(record)
        session.flush()


component_upgrade_record_repo = ComponentUpgradeRecordRepository(ServiceUpgradeRecord)
