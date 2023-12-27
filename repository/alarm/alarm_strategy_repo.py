from sqlalchemy import select, delete, or_

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


alarm_strategy_repo = AlarmStrategyRepo(AlarmStrategy)
