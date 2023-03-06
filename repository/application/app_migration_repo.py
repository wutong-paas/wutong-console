from sqlalchemy import not_, select, update

from models.application.models import GroupAppMigrateRecord
from repository.base import BaseRepository


class AppMigrationRespository(BaseRepository[GroupAppMigrateRecord]):
    def get_by_event_id(self, session, event_id):
        return session.execute(select(GroupAppMigrateRecord).filter(
            GroupAppMigrateRecord.event_id == event_id
        )).scalars().first()

    def get_user_unfinished_migrate_record(self, session, group_uuid):
        return session.query(GroupAppMigrateRecord).filter(
            GroupAppMigrateRecord.group_uuid == group_uuid,
            not_(GroupAppMigrateRecord.status.in_(['success', 'failed']))
        ).all()

    def create_migrate_record(self, session, **params):
        gamr = GroupAppMigrateRecord(**params)
        session.add(gamr)
        session.flush()
        return gamr

    def get_by_restore_id(self, session, restore_id):
        return session.execute(select(GroupAppMigrateRecord).where(
            GroupAppMigrateRecord.restore_id == restore_id
        )).scalars().first()

    def get_by_original_group_id(self, session, original_grup_id, original_group_id):
        session.execute(update(GroupAppMigrateRecord).where(
            GroupAppMigrateRecord.original_group_id == original_grup_id).values(
            {"original_group_id": original_group_id}))


migrate_repo = AppMigrationRespository(GroupAppMigrateRecord)
