from sqlalchemy import select, delete, or_

from models.alarm.models import AlarmRobot
from repository.base import BaseRepository


class AlarmRobotRepo(BaseRepository[AlarmRobot]):

    def add_alarm_robot(self, session, alarm_robot_info):
        alarm_robot = AlarmRobot(**alarm_robot_info)
        session.add(alarm_robot)
        session.flush()

    def get_alarm_robot_by_id(self, session, alarm_robot_id):
        return session.execute(select(AlarmRobot).where(AlarmRobot.ID == alarm_robot_id)).scalars().first()

    def get_alarm_robot_by_name(self, session, alarm_robot_name):
        return session.execute(select(AlarmRobot).where(AlarmRobot.robot_name == alarm_robot_name)).scalars().first()

    def get_all_alarm_robot(self, session, team_code):
        if team_code:
            return session.execute(select(AlarmRobot).where(AlarmRobot.team_code == team_code)).scalars().all()
        return session.execute(select(AlarmRobot)).scalars().all()

    def delete_alarm_robot_by_name(self, session, alarm_robot_name):
        session.execute(delete(AlarmRobot).where(AlarmRobot.robot_name == alarm_robot_name))
        session.flush()


alarm_robot_repo = AlarmRobotRepo(AlarmRobot)
