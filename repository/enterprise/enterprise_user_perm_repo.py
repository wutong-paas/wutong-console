from sqlalchemy import select, func, delete, update

from core.enum.enterprise_enum import EnterpriseRolesEnum
from models.relate.models import EnterpriseUserPerm
from repository.base import BaseRepository


class EnterpriseUserPermRepo(BaseRepository[EnterpriseUserPerm]):
    def is_admin(self, session, eid, user_id):
        perm = session.execute(select(EnterpriseUserPerm).where(
            EnterpriseUserPerm.enterprise_id == eid,
            EnterpriseUserPerm.user_id == user_id
        )).scalars().first()
        if not perm:
            return False
        return EnterpriseRolesEnum.admin.name in perm.identity

    def get(self, session, enterprise_id, user_id):
        return session.execute(select(EnterpriseUserPerm).where(
            EnterpriseUserPerm.enterprise_id == enterprise_id,
            EnterpriseUserPerm.user_id == user_id
        )).scalars().first()

    def update_roles(self, session, enterprise_id, user_id, identity):
        session.execute(update(EnterpriseUserPerm).where(
            EnterpriseUserPerm.enterprise_id == enterprise_id,
            EnterpriseUserPerm.user_id == user_id
        ).values({"identity": identity}))
        session.flush()

    def create_enterprise_user_perm(self, session, user_id, enterprise_id, identity, token=None):
        if token is None:
            eup = EnterpriseUserPerm(user_id=user_id, enterprise_id=enterprise_id, identity=identity)
            session.add(eup)
            session.flush()
            return eup
        else:
            eup = EnterpriseUserPerm(user_id=user_id, enterprise_id=enterprise_id, identity=identity, token=token)
            session.add(eup)
            session.flush()
            return eup

    def get_backend_enterprise_admin_by_user_id(self, session, user_id):
        """
        管理后台查询企业管理员，只有一个企业
        :param user_id:
        :param enterprise_id:
        :return:
        """
        return session.execute(select(EnterpriseUserPerm).where(
            EnterpriseUserPerm.user_id == user_id
        )).scalars().first()

    def count_by_eid(self, session, eid):
        return session.execute(select(func.count(EnterpriseUserPerm.ID)).where(
            EnterpriseUserPerm.enterprise_id == eid
        )).first()[0]

    def delete_backend_enterprise_admin_by_user_id(self, session, user_id):
        """
        管理后台删除企业管理员，只有一个企业
        :param user_id:
        :param enterprise_id:
        :return:
        """
        session.execute(delete(EnterpriseUserPerm).where(
            EnterpriseUserPerm.user_id == user_id
        ))
        session.flush()


enterprise_user_perm_repo = EnterpriseUserPermRepo(EnterpriseUserPerm)
