from sqlalchemy import select, delete, or_, update

from models.alarm.models import AlarmStrategy
from repository.base import BaseRepository


class AlarmStrategyRepo(BaseRepository[AlarmStrategy]):

    def create_alarm_strategy(self, session, alarm_strategy_info):
        alarm_region = AlarmStrategy(**alarm_strategy_info)
        session.add(alarm_region)
        session.flush()

    def get_alarm_strategy_by_code(self, session, strategy_code):
        return session.execute(select(AlarmStrategy).where(
            AlarmStrategy.strategy_code == strategy_code)).scalars().first()

    def get_alarm_strategy_by_name(self, session, strategy_name):
        return session.execute(select(AlarmStrategy).where(
            AlarmStrategy.strategy_name == strategy_name)).scalars().first()

    def get_alarm_strategy_by_team_code(self, session, team_code):
        if team_code:
            alarm_strategys = session.execute(select(AlarmStrategy).where(
                AlarmStrategy.team_code == team_code)).scalars().all()
        else:
            alarm_strategys = session.execute(select(AlarmStrategy)).scalars().all()
        return alarm_strategys if alarm_strategys else []

    def update_alarm_strategy(self, session, strategy_id, alarm_strategy_info):
        session.execute(update(AlarmStrategy).where(
            AlarmStrategy.ID == strategy_id).values(alarm_strategy_info))
        session.flush()

    def delete_alarm_strategy(self, session, strategy_id):
        session.execute(delete(AlarmStrategy).where(
            AlarmStrategy.ID == strategy_id))
        session.flush()

    def get_alarm_strategys_by_object(self, session, object_code, object_type):
        return session.execute(select(AlarmStrategy).where(
            AlarmStrategy.object_code == object_code,
        AlarmStrategy.object_type == object_type)).scalars().all()


alarm_strategy_repo = AlarmStrategyRepo(AlarmStrategy)
