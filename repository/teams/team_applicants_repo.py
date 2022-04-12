from sqlalchemy import select, delete

from models.teams import Applicants
from repository.base import BaseRepository


class ApplyRepo(BaseRepository[Applicants]):

    def create_apply_info(self, session, **params):
        app = Applicants(**params)
        session.add(app)
        return app

    def get_append_applicants_team(self, session, user_id):
        return session.execute(select(Applicants).where(
            Applicants.user_id == user_id,
            Applicants.is_pass == 0)).scalars().all()

    def get_applicants(self, session, team_name):
        return (session.execute(select(Applicants).where(
            Applicants.team_name == team_name))).scalars().all()

    def get_applicants_by_id_team_name(self, session, user_id, team_name):
        return session.execute(select(Applicants).where(
            Applicants.team_name == team_name,
            Applicants.user_id == user_id)).scalars().first()

    def delete_applicants_by_id_team_name(self, session, user_id, team_name):
        session.execute(delete(Applicants).where(
            Applicants.team_name == team_name,
            Applicants.user_id == user_id))


apply_repo = ApplyRepo(Applicants)
