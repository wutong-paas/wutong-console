import copy

from sqlalchemy import select, delete

from core.utils.perms import get_perms_metadata, get_structure, TEAM, ENTERPRISE
from models.teams import PermsInfo
from repository.base import BaseRepository


class PermsServerRepository(BaseRepository[PermsInfo]):
    """
    PermsServerRepository

    """

    # todo 事物处理
    def initialize_permission_settings(self, session):
        """判断有没有初始化权限数据，没有则初始化"""
        all_perms_list = get_perms_metadata()
        results = session.execute(select(PermsInfo))
        has_perms = results.scalars().all()
        # has_perms_list = list(has_perms.values_list("name", "desc", "code", "group", "kind"))
        # attr=[o.attr for o in objsm]
        all_perms_code = [perm[2] for perm in all_perms_list]
        has_perms_code = [perm.code for perm in has_perms]
        if all_perms_code != has_perms_code:
            # todo
            # has_perms.delete()
            ids = [p.ID for p in has_perms]
            session.execute(
                delete(PermsInfo).where(PermsInfo.ID.in_(ids))
            )
            perms_list = []
            for perm in all_perms_list:
                perms_list.append(PermsInfo(name=perm[0], desc=perm[1], code=perm[2], group=perm[3], kind=perm[4]))
            session.add_all(perms_list)

    def get_perms_info(self):
        perms_structure = {}
        team = get_structure(copy.deepcopy(TEAM), "team")
        enterprise = get_structure(copy.deepcopy(ENTERPRISE), "enterprise")
        perms_structure.update(team)
        perms_structure.update(enterprise)
        return perms_structure


perms_repo = PermsServerRepository(PermsInfo)
