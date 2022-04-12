from sqlalchemy import select, delete

from models.teams import RolePerms, PermsInfo
from repository.base import BaseRepository


class RolePermsRepository(BaseRepository[RolePerms]):

    def get_roles_perm_relation(self, session, role_ids):
        results = session.execute(
            select(RolePerms).where(RolePerms.role_id.in_(role_ids))
        )
        data = results.scalars().all()
        return data

    def get_role_perm_relation(self, session, role_id):
        sql = select(RolePerms).where(RolePerms.role_id == role_id)
        q = session.execute(sql)
        session.flush()
        result = q.scalars().all()
        return result

    def get_role_perms_relation(self, session, role_ids):
        sql = select(RolePerms).where(RolePerms.role_id.in_(role_ids))
        q = session.execute(sql)
        session.flush()
        result = q.scalars().all()
        return result

    def create_role_perm_relation(self, session, role_id, perm_codes):
        if perm_codes:
            role_perm_list = []
            for perm_code in perm_codes:
                role_perm_list.append({"role_id": role_id, "perm_code": perm_code})
            session.execute(RolePerms.__table__.insert(), role_perm_list)
            session.flush()
            return role_perm_list
        return []

    def delete_role_perm_relation(self, session, role_id):
        sql = delete(RolePerms).where(RolePerms.role_id == role_id)
        session.execute(sql)

    def get_role_perms(self, session, role_id):
        role_perms = self.get_role_perm_relation(session=session, role_id=role_id)
        if not role_perms:
            return role_perms
        perm_codes = role_perms[0].perm_code

        sql = select(RolePerms).where(PermsInfo.code.in_(perm_codes))
        q = session.execute(sql)
        session.flush()
        result = q.scalars().all()
        return result


role_perm_repo = RolePermsRepository(RolePerms)
