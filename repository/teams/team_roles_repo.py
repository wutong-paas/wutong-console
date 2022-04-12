from loguru import logger
from sqlalchemy import select, or_, delete

from core.utils.perms import get_team_perms_model, get_enterprise_perms_model, get_perms_model, DEFAULT_TEAM_ROLE_PERMS, \
    DEFAULT_ENTERPRISE_ROLE_PERMS
from exceptions.main import ServiceHandleException
from models.teams import RoleInfo, TeamInfo
from repository.base import BaseRepository
from repository.users.role_perm_relation_repo import role_perm_repo
from repository.users.role_repo import role_repo
from repository.users.user_role_repo import user_role_repo


class TeamRolesRepository(BaseRepository[RoleInfo]):
    def update_role(self, session, kind, kind_id, id, name):
        if not name:
            raise ServiceHandleException(msg="role name exit", msg_show="角色名称不能为空")
        exit_role = self.get_role_by_name(session, kind, kind_id, name, with_default=True)
        if exit_role:
            if int(exit_role.ID) != int(id):
                raise ServiceHandleException(msg="role name exit", msg_show="角色名称已存在")
            else:
                return exit_role
        role = self.get_role_by_id(session, kind, kind_id, id)
        if not role:
            raise ServiceHandleException(msg="role no found", msg_show="角色不存在或为默认角色", status_code=404)
        role.name = name

        return role

    def delete_role(self, session, kind, kind_id, id):
        role = self.get_role_by_id(session, kind, kind_id, id)
        if not role:
            raise ServiceHandleException(msg="role no found or is default", msg_show="角色不存在或为默认角色")
        role_perm_repo.delete_role_perm_relation(session, role.ID)
        user_role_repo.delete_users_role(session, kind, kind_id, role.ID)
        self.delete_role_by_id(session, kind, kind_id, id)

    # 已有一维角色权限列表变更权限模型权限的默认值
    def __build_perms_list(self, model_perms, role_codes, is_owner):
        perms_list = []
        for model_perm in model_perms:
            model_perm_key = list(model_perm.keys())
            model_perm_key.remove("code")
            if is_owner:
                perms_list.append({model_perm_key[0]: True})
            else:
                if model_perm["code"] in role_codes:
                    perms_list.append({model_perm_key[0]: True})
                else:
                    perms_list.append({model_perm_key[0]: False})
        return perms_list

    # 角色权限树打包
    def pack_role_perms_tree(self, models, role_codes, is_owner=False):
        items_list = list(models.items())
        sub_models = []
        for items in items_list:
            kind_name, body = items
            if body["sub_models"]:
                for sub in body["sub_models"]:
                    sub_models.append(self.pack_role_perms_tree(sub, role_codes, is_owner))
                models[kind_name]["sub_models"] = sub_models
            models[kind_name]["perms"] = self.__build_perms_list(body["perms"], role_codes, is_owner)
        return models

    def get_team_id_by_team_name(self, session, team_name):
        logger.info("获取团队id")
        return session.execute(select(TeamInfo.tenant_id).where(
            TeamInfo.tenant_name == team_name
        )).scalars().first()

    # todo 数据库查询
    def get_role_by_team_name(self, session, kind, team_name):

        tenant_id = self.get_team_id_by_team_name(session=session, team_name=team_name)

        logger.info("获取团队角色信息")
        sql = select(RoleInfo).where(or_(RoleInfo.kind_id == tenant_id, RoleInfo.kind_id == "default"),
                                     RoleInfo.kind == kind)
        q = session.execute(sql)
        session.flush()
        result = q.scalars().all()
        return result

    def delete_role_by_id(self, session, kind, kind_id, id, with_default=False):
        if with_default:
            sql = delete(RoleInfo).where(or_(RoleInfo.kind_id == kind_id,
                                             RoleInfo.kind_id == "default"),
                                         RoleInfo.kind == kind,
                                         RoleInfo.ID == id)
        else:
            sql = delete(RoleInfo).where(RoleInfo.kind_id == kind_id,
                                         RoleInfo.kind == kind,
                                         RoleInfo.ID == id)
        session.execute(sql)

    def get_role_by_id(self, session, kind, kind_id, id, with_default=False):
        if with_default:
            sql = select(RoleInfo).where(or_(RoleInfo.kind_id == kind_id,
                                             RoleInfo.kind_id == "default"),
                                         RoleInfo.kind == kind,
                                         RoleInfo.ID == id)
        else:
            sql = select(RoleInfo).where(RoleInfo.kind_id == kind_id,
                                         RoleInfo.kind == kind,
                                         RoleInfo.ID == id)
        q = session.execute(sql)
        result = q.scalars().first()
        return result

    def get_role_by_name(self, session, kind, kind_id, name, with_default=False):
        if with_default:
            sql = select(RoleInfo).where(or_(RoleInfo.kind_id == kind_id,
                                             RoleInfo.kind_id == "default"),
                                         RoleInfo.kind == kind,
                                         RoleInfo.name == name)
        else:
            sql = select(RoleInfo).where(RoleInfo.kind_id == kind_id,
                                         RoleInfo.kind == kind,
                                         RoleInfo.name == name)
        q = session.execute(sql)
        result = q.scalars().first()
        return result

    def create_role_by_team_name(self, session, name, kind, team_name):
        logger.info("获取团队id team_name {}", team_name)
        kind_id = self.get_team_id_by_team_name(session=session, team_name=team_name)

        if not name:
            raise ServiceHandleException(msg="role name exit", msg_show="角色名称不能为空")
        if self.get_role_by_name(session, kind, kind_id, name):
            raise ServiceHandleException(msg="role name exit", msg_show="角色名称已存在")

        add = RoleInfo(name=name, kind=kind, kind_id=kind_id)
        session.add(add)
        session.flush()
        return add

    def get_roles_perms(self, session, roles, kind=None):
        roles_perms = {}
        role_ids = []
        if not roles:
            return []
        for row in roles:
            role_ids.append(str(row.ID))
            roles_perms.update({str(row.ID): []})
        roles_perm_relation_mode = role_perm_repo.get_role_perms_relation(session, role_ids)
        data = []
        for role_id, rule_perms in list(roles_perms.items()):
            role_perms_info = {"role_id": int(role_id)}
            permissions = self.pack_role_perms_tree(get_team_perms_model(), rule_perms)
            role_perms_info.update({"permissions": permissions})
            data.append(role_perms_info)
        return data

    def get_role_perms(self, session, role, kind=None):
        if not role:
            return None
        roles_perms = {str(role.ID): []}
        roles_perm_relations = []
        role_perm_relation_mode = role_perm_repo.get_role_perm_relation(session, role.ID)
        if role_perm_relation_mode:
            for role_perm in role_perm_relation_mode:
                roles_perm_relations.append(
                    {"role_id": role_perm.role_id,
                     "perm_code": role_perm.perm_code}
                )
            for roles_perm_relation in roles_perm_relations:
                if str(roles_perm_relation["role_id"]) not in roles_perms:
                    roles_perms[str(roles_perm_relation["role_id"])] = []
                roles_perms[str(roles_perm_relation["role_id"])].append(roles_perm_relation["perm_code"])
        data = []
        for role_id, rule_perms in list(roles_perms.items()):
            role_perms_info = {"role_id": role_id}
            if kind == "team":
                permissions = self.pack_role_perms_tree(get_team_perms_model(), rule_perms)
            elif kind == "enterprise":
                permissions = self.pack_role_perms_tree(get_enterprise_perms_model(), rule_perms)
            else:
                permissions = self.pack_role_perms_tree(get_perms_model(), rule_perms)
            role_perms_info.update({"permissions": permissions})
            data.append(role_perms_info)
        return data[0]

    def init_default_role_perms(self, session, role):
        if role.name in list(DEFAULT_TEAM_ROLE_PERMS.keys()):
            role_perm_repo.delete_role_perm_relation(session, role.ID)
            role_perm_repo.create_role_perm_relation(session, role.ID, DEFAULT_TEAM_ROLE_PERMS[role.name])

    def init_default_roles(self, session, kind, kind_id):
        if kind == "team":
            DEFAULT_ROLES = list(DEFAULT_TEAM_ROLE_PERMS.keys())
        elif kind == "enterprise":
            DEFAULT_ROLES = list(DEFAULT_ENTERPRISE_ROLE_PERMS.keys())
        else:
            DEFAULT_ROLES = []
        if DEFAULT_ROLES == []:
            pass
        for default_role in DEFAULT_ROLES:
            role = self.get_role_by_name(session, kind, kind_id, default_role)
            if not role:
                role = role_repo.base_create(session=session,
                                             add_model=RoleInfo(kind=kind, kind_id=kind_id, name=default_role))
            self.init_default_role_perms(session=session, role=role)


team_roles_repo = TeamRolesRepository(RoleInfo)
