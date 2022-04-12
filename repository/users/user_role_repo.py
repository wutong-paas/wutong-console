from sqlalchemy import select, delete

from database.session import SessionClass
from exceptions.exceptions import UserRoleNotFoundException
from exceptions.main import ServiceHandleException
from models.teams import RoleInfo, UserRole
from repository.base import BaseRepository


class UserRoleRepository(BaseRepository[UserRole]):

    def get_user_roles_model(self, session, kind, kind_id, user):
        user_roles = []
        if not user:
            raise ServiceHandleException(msg="no found user", msg_show="用户不存在", status_code=404)
        result_roles = session.execute(
            select(RoleInfo).where(RoleInfo.kind == kind, RoleInfo.kind_id == kind_id)
        )
        roles = result_roles.scalars().all()
        if roles:
            role_ids = [role.ID for role in roles]
            result_user_roles = session.execute(
                select(UserRole).where(UserRole.user_id == user.user_id, UserRole.role_id.in_(role_ids))
            )
            user_roles = result_user_roles.scalars().all()
        return user_roles

    def get_users_roles(self, session, kind, kind_id, users, creater_id=0):
        data = []
        user_roles_kv = {}
        # todo commit?

        roles = (session.execute(select(RoleInfo).where(
            RoleInfo.kind == kind, RoleInfo.kind_id == kind_id))).scalars().all()
        if roles:
            for user in users:
                user_roles_kv.update({str(user.user_id): []})
            role_id_name_kv = {}
            role_ids = []
            for role in roles:
                role_id_name_kv.update({str(role.ID): role.name})
                role_ids.append(role.ID)

            users_roles = (session.execute(select(UserRole).where(
                UserRole.role_id.in_(role_ids)))).scalars().all()
            for user_role in users_roles:
                user_roles_kv.get(str(user_role.user_id), []).append({
                    "role_id": user_role.role_id,
                    "role_name": role_id_name_kv[str(user_role.role_id)]
                })
        for user in users:
            if int(user.user_id) == int(creater_id):
                user_roles_kv.get(str(user.user_id), []).append({"role_id": 0, "role_name": "拥有者"})
            data.append({
                "nick_name": user.nick_name,
                "email": user.email,
                "user_id": user.user_id,
                "roles": user_roles_kv.get(str(user.user_id), [])
            })
        return data

    def get_user_roles(self, session, kind, kind_id, user):
        if not user:
            raise ServiceHandleException(msg="no found user", msg_show="用户不存在", status_code=404)
        user_roles_list = []
        sql = select(RoleInfo).where(RoleInfo.kind == kind, RoleInfo.kind_id == kind_id)
        q = session.execute(sql)
        roles = q.scalars().all()
        if roles:
            role_id_name_kv = {}
            role_ids = []
            for role in roles:
                role_id_name_kv.update({str(role.ID): role.name})
                role_ids.append(role.ID)
            sql = select(UserRole).where(UserRole.role_id.in_(role_ids), UserRole.user_id == user.user_id)
            q = session.execute(sql)
            user_roles = q.scalars().all()
            if user_roles:
                for user_role in user_roles:
                    user_roles_list.append(
                        {"role_id": user_role.role_id, "role_name": role_id_name_kv[str(user_role.role_id)]})
        data = {"nick_name": user.nick_name, "user_id": user.user_id, "roles": user_roles_list}
        return data

    def update_user_roles(self, session, kind, kind_id, user, role_ids):
        if not user:
            raise ServiceHandleException(msg="no found user", msg_show="用户不存在", status_code=404)

        sql = select(RoleInfo).where(RoleInfo.kind == kind, RoleInfo.kind_id == kind_id)
        q = session.execute(sql)
        roles = q.scalars().all()

        has_role_ids = []
        user_role_list = []
        for row in roles:
            has_role_ids.append(row.ID)
        update_role_ids = list(set(has_role_ids) & set(role_ids))
        if not update_role_ids and len(role_ids):
            raise ServiceHandleException(msg="no found can update params", msg_show="传入角色不可被分配，请检查参数", status_code=404)
        for role_id in update_role_ids:
            user_role_list.append(UserRole(user_id=user.user_id, role_id=role_id))
        session.add_all(user_role_list)

    def delete_user_roles(self, session, kind, kind_id, user, role_ids=None):
        if not user:
            raise ServiceHandleException(msg="no found user", msg_show="用户不存在", status_code=404)

        sql = select(RoleInfo).where(RoleInfo.kind == kind, RoleInfo.kind_id == kind_id)
        q = session.execute(sql)
        roles = q.scalars().all()

        if roles:
            has_role_ids = []
            for row in roles:
                has_role_ids.append(row.ID)
            if role_ids:
                sql = delete(UserRole).where(UserRole.role_id.in_(role_ids), UserRole.user_id == user.user_id)
            else:
                sql = delete(UserRole).where(UserRole.role_id.in_(has_role_ids), UserRole.user_id == user.user_id)
            session.execute(sql)
            session.flush()

    def get_role_names(self, session: SessionClass, user_id, tenant_id):
        sql: str = """
        select 
        group_concat( b.role_name ) as role_names 
        from 
        tenant_perms a,tenant_user_role b,tenant_info c
        where
        a.role_id = b.ID
        AND a.tenant_id = c.ID
        AND a.user_id = :user_id
        AND c.tenant_id = :tenant_id
        """
        params = {
            "user_id": user_id,
            "tenant_id": tenant_id
        }
        results = session.execute(sql, params)
        data = results.scalars().first()
        if not data:
            raise UserRoleNotFoundException("tenant_id: {tenant_id}; user_id: {user_id}; user role not found".format(
                tenant_id=tenant_id, user_id=user_id))
        return data["role_names"]

    def delete_users_role(self, session, kind, kind_id, role_id):
        roles = session.execute(
            select(RoleInfo).where(RoleInfo.kind == kind, RoleInfo.kind_id == kind_id)
        ).scalars().all()
        if roles:
            has_role_ids = [role.ID for role in roles]
            if role_id in has_role_ids:
                session.execute(
                    delete(UserRole).where(UserRole.role_id == role_id)
                )


user_role_repo = UserRoleRepository(UserRole)
