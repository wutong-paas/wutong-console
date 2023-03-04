# -*- coding: utf-8 -*-
from sqlalchemy import select, delete

from models.component.models import TeamServiceBackup
from repository.base import BaseRepository


class TeamServiceBackupRepository(BaseRepository[TeamServiceBackup]):

    def get_newest_by_sid(self, session, tid, sid):
        return session.execute(select(TeamServiceBackup).where(
            TeamServiceBackup.tenant_env_id == tid,
            TeamServiceBackup.service_id == sid
        ).order_by(TeamServiceBackup.update_time.desc())).scalars().first()

    def del_by_sid(self, session, tid, sid):
        session.execute(delete(TeamServiceBackup).where(
            TeamServiceBackup.tenant_env_id == tid,
            TeamServiceBackup.service_id == sid
        ))


service_backup_repo = TeamServiceBackupRepository(TeamServiceBackup)
