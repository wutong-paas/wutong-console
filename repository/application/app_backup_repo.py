from sqlalchemy import select, func, delete

from models.application.models import GroupAppBackupRecord
from repository.base import BaseRepository


class AppBackupRecordRepository(BaseRepository[GroupAppBackupRecord]):

    def count_by_app_id(self, session, app_id):
        """
        统计应用下备份数量

        :param app_id:
        :return:
        """
        return (session.execute(
            select(func.count(GroupAppBackupRecord.ID)).where(GroupAppBackupRecord.group_id == app_id)
        )).first()[0]

    def get_group_backup_records(self, session, team_id, region_name, group_id):
        return (session.execute(
            select(GroupAppBackupRecord).where(
                GroupAppBackupRecord.team_id == team_id,
                GroupAppBackupRecord.region == region_name,
                GroupAppBackupRecord.group_id == group_id).order_by(GroupAppBackupRecord.ID.desc())
        )).scalars().all()

    def get_record_by_group_id(self, session, group_id):
        return (session.execute(
            select(GroupAppBackupRecord).where(
                GroupAppBackupRecord.group_id == group_id))).scalars().all()

    def create_backup_records(self, session, **params):
        babr = GroupAppBackupRecord(**params)
        session.add(babr)
        session.flush()
        return babr

    def get_record_by_backup_id(self, session, team_id, backup_id):
        if team_id:
            return (session.execute(
                select(GroupAppBackupRecord).where(
                    GroupAppBackupRecord.team_id == team_id,
                    GroupAppBackupRecord.backup_id == backup_id))).scalars().first()
        else:
            return (session.execute(
                select(GroupAppBackupRecord).where(
                    GroupAppBackupRecord.backup_id == backup_id))).scalars().first()

    def delete_record_by_backup_id(self, session, team_id, backup_id):
        session.execute(
            delete(GroupAppBackupRecord).where(
                GroupAppBackupRecord.team_id == team_id,
                GroupAppBackupRecord.backup_id == backup_id))
        

    def get_record_by_group_id_and_backup_id(self, session, group_id, backup_id):
        return session.execute(
            select(GroupAppBackupRecord).where(
                GroupAppBackupRecord.group_id == group_id,
                GroupAppBackupRecord.backup_id == backup_id)).scalars().all()

    def get_group_backup_records_by_team_id(self, session, team_id, region_name):
        return session.execute(
            select(GroupAppBackupRecord).where(
                GroupAppBackupRecord.team_id == team_id,
                GroupAppBackupRecord.region == region_name).order_by(
                GroupAppBackupRecord.ID.desc())).scalars().all()


backup_record_repo = AppBackupRecordRepository(GroupAppBackupRecord)
