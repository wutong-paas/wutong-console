from sqlalchemy import select

from models.teams import RoleInfo
from repository.base import BaseRepository


class RoleRepository(BaseRepository[RoleInfo]):

    def get_roles_by_kind(self, session, kind, kind_id):
        sql = select(RoleInfo).where(RoleInfo.kind_id == kind_id,
                                     RoleInfo.kind == kind)
        q = session.execute(sql)
        session.flush()
        result = q.scalars().all()
        return result


role_repo = RoleRepository(RoleInfo)
