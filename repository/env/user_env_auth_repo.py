from sqlalchemy import select
from models.teams import EnvUserRelation


class UserEnvAuthRepo(object):
    def is_auth_in_env(self, session, env_id, user_name):
        user_env_rel = session.execute(select(EnvUserRelation).where(
            EnvUserRelation.env_id == env_id
        )).scalars().first()
        if user_env_rel:
            user_names = user_env_rel.user_names
            if user_names == "all":
                return True
            if user_name in user_names:
                return True
        return False


user_env_auth_repo = UserEnvAuthRepo()
