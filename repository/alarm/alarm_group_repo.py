from sqlalchemy import select, delete, or_

from models.alarm.models import AlarmGroup
from repository.base import BaseRepository


class AlarmGroupRepo(BaseRepository[AlarmGroup]):

    def create_alarm_group(self, session, alarm_group_info):
        alarm_group = AlarmGroup(**alarm_group_info)
        session.add(alarm_group)
        session.flush()

    def get_alarm_group(self, session, query):
        if query:
            return session.execute(select(AlarmGroup).where(
                or_(AlarmGroup.team_name.contains(query),
                    AlarmGroup.group_name.contains(query)))).scalars().all()
        return session.execute(select(AlarmGroup)).scalars().all()

    def get_alarm_group_by_team(self, session, group_name, group_type, team_name):
        if group_type == 'team':
            return session.execute(select(AlarmGroup).where(
                AlarmGroup.group_name == group_name,
                AlarmGroup.team_name == team_name)).scalars().first()
        return session.execute(select(AlarmGroup).where(
            AlarmGroup.group_name == group_name,
            AlarmGroup.group_type == group_type)).scalars().first()

    def delete_alarm_group_by_id(self, session, group_id):
        session.execute(delete(AlarmGroup).where(AlarmGroup.ID == group_id))
        session.flush()

    def get_alarm_group_by_id(self, session, group_id):
        return session.execute(select(AlarmGroup).where(AlarmGroup.ID == group_id)).scalars().first()


alarm_group_repo = AlarmGroupRepo(AlarmGroup)
