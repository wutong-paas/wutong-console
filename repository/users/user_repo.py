from sqlalchemy import select

from database.session import SessionClass
from exceptions.bcode import ErrUserNotFound
from models.users.users import Users, SuperAdminUser, UserAccessKey
from repository.base import BaseRepository


class UserRepository(BaseRepository[Users]):

    def get_by_user_id(self, session, user_id):
        return session.execute(select(Users).where(
            Users.user_id == user_id
        )).scalars().first()

    def get_enterprise_users(self, session, enterprise_id):
        session.execute(
            select(Users).where(
                Users.enterprise_id == enterprise_id).order_by(
                Users.user_id.asc())).scalars().all()

    def is_sys_admin(self, session: SessionClass, user_id):
        user = (session.execute(
            select(SuperAdminUser).where(SuperAdminUser.user_id == user_id))).scalars().first()
        if user:
            return True
        return False

    # def get_user_by_email(self, session: SessionClass, email):
    #     return session.execute(select(Users).where(
    #         Users.email == email
    #     )).scalars().first()

    def get_enterprise_user_by_username(self, session: SessionClass, eid, user_name):
        return session.execute(select(Users).where(
            Users.nick_name == user_name,
            Users.enterprise_id == eid
        )).scalars().first()

    def get_user_by_user_id(self, session: SessionClass, user_id):
        q = session.execute(select(Users).where(Users.user_id == user_id))
        u = q.scalars().all()
        if not u:
            return None
        return u[0]

    def get_user_by_phone(self, session: SessionClass, phone):
        return session.execute(select(Users).where(
            Users.phone == phone)).scalars().first()

    def get_enterprise_user_by_id(self, session: SessionClass, enterprise_id, user_id):
        return session.execute(select(Users).where(
            Users.user_id == user_id,
            Users.enterprise_id == enterprise_id)).scalars().first()

    def get_user_by_username(self, session: SessionClass, user_name):
        user = (
            session.execute(select(Users).where(Users.nick_name == user_name))
        ).scalars().first()
        if not user:
            raise ErrUserNotFound
        return user


class UserAccessKeyRepository(BaseRepository[UserAccessKey]):
    pass


user_access_key_repo = UserAccessKeyRepository(UserAccessKey)
user_repo = UserRepository(Users)
