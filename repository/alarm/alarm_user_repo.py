from sqlalchemy import select
from models.alarm.models import AlarmGroupUserRelation
from repository.base import BaseRepository


class AlarmGroupUserRepo(BaseRepository[AlarmGroupUserRelation]):

    def get_alarm_user_by_group_id(self, session, group_id):
        return session.execute(select(AlarmGroupUserRelation).where(AlarmGroupUserRelation.group_id == group_id)).scalars().all()

    def add_alarm_user(self, session, users):
        group_users = [AlarmGroupUserRelation(**user) for user in users]
        session.add_all(group_users)
        session.flush()

    def delete_alarm_user_by_group_id(self, session, group_id, user_name):
        session.execute(delete(AlarmGroupUserRelation).where(
            AlarmGroupUserRelation.group_id == group_id,
            AlarmGroupUserRelation.user_name == user_name))
        session.flush()


alarm_group_user_repo = AlarmGroupUserRepo(AlarmGroupUserRelation)
