from sqlalchemy import select, func, delete, update

from models.alarm.models import AlarmGroup
from repository.base import BaseRepository


class AlarmGroupRepo(BaseRepository[AlarmGroup]):

    def create_alarm_group(self, session, alarm_group_info):
        alarm_group = AlarmGroup(**alarm_group_info)
        session.add(alarm_group)
        session.flush()

    def get_alarm_group(self, session):
        return session.execute(select(AlarmGroup)).scalars().all()

    def get_alarm_group_by_team(self, session, group_name, team_name):
        return session.execute(select(AlarmGroup).where(
            AlarmGroup.group_name == group_name,
            AlarmGroup.team_name == team_name)).scalars().first()

    def delete_alarm_group_by_id(self, session, group_id):
        session.execute(delete(AlarmGroup).where(AlarmGroup.ID == group_id))
        session.flush()

    def get_alarm_group_by_id(self, session, group_id):
        return session.execute(select(AlarmGroup).where(AlarmGroup.ID == group_id)).scalars().first()


alarm_group_repo = AlarmGroupRepo(AlarmGroup)
