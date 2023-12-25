from sqlalchemy import select, delete, or_

from models.alarm.models import AlarmRegionRelation
from repository.base import BaseRepository


class AlarmRegionRepo(BaseRepository[AlarmRegionRelation]):

    def create_alarm_region(self, session, alarm_region_info):
        alarm_region = AlarmRegionRelation(**alarm_region_info)
        session.add(alarm_region)
        session.flush()

    def get_alarm_region(self, session, group_id, region_code):
        return session.execute(select(AlarmRegionRelation).where(
            AlarmRegionRelation.group_id == group_id,
            AlarmRegionRelation.region_code == region_code)).scalars().first()


alarm_region_repo = AlarmRegionRepo(AlarmRegionRelation)
