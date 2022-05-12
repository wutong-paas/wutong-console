# -*- coding: utf8 -*-
import binascii
import copy
import os
import pickle
import re

from jose import jwt
from loguru import logger
from sqlalchemy import select, or_, func, delete

from core.setting import settings
from core.utils import perms
from core.utils.oauth.oauth_types import get_oauth_instance
from core.utils.perms import get_perms_model, get_enterprise_perms_model, get_team_perms_model, TEAM, ENTERPRISE
from database.session import SessionClass
from exceptions.exceptions import ErrCannotDelLastAdminUser, ErrAdminUserDoesNotExist, UserNotExistError
from exceptions.main import ServiceHandleException, AbortRequest
from models.region.models import TeamRegionInfo
from models.relate.models import EnterpriseUserPerm
from models.teams import PermsInfo, RoleInfo, UserRole, RolePerms, PermRelTenant, TeamInfo
from models.teams.enterprise import TeamEnterprise
from models.users.users import Users
from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from repository.users.role_perm_relation_repo import role_perm_repo
from repository.users.user_role_repo import user_role_repo
from repository.users.user_oauth_repo import oauth_user_repo
from repository.users.user_repo import user_repo

error_messages = {
    'nick_name_used': "该用户名已存在",
    'email_used': "邮件地址已被注册",
    'tenant_used': "团队名已存在",
    'password_repeat': "两次输入的密码不一致",
    'phone_used': "手机号已存在",
    'phone_empty': "手机号为空",
    'phone_captch_error': "手机验证码已失效",
    'phone_code_error': "手机验证码错误",
    'captcha_code_error': "验证码有误",
    'machine_region_error': "请选择数据中心",
}


def get_perms_name_code(perms_model, kind_name):
    perms = {}
    sub_models = list(perms_model.keys())
    if "perms" in sub_models:
        sub_models.remove("perms")
    for perm in perms_model.get("perms", []):
        perms.update({'_'.join([kind_name, perm[0]]): perm[2]})
    if sub_models:
        for sub_model in sub_models:
            perms.update(get_perms_name_code(perms_model[sub_model], sub_model))
    return perms


def get_perms_name_code_kv():
    perms = {}
    perms.update(get_perms_name_code(copy.deepcopy(TEAM), "team"))
    perms.update(get_perms_name_code(copy.deepcopy(ENTERPRISE), "enterprise"))
    return perms


class UserService(object):
    def is_user_admin_in_current_enterprise(self, session, current_user, enterprise_id):
        """判断用户在该企业下是否为管理员"""
        if current_user.enterprise_id != enterprise_id:
            return False
        is_admin = enterprise_user_perm_repo.is_admin(session, enterprise_id, current_user.user_id)
        if is_admin:
            return True
        users = user_repo.get_enterprise_users(session, enterprise_id)
        if users:
            admin_user = users[0]
            # 如果有，判断用户最开始注册的用户和当前用户是否为同一人，如果是，添加数据返回true
            if admin_user.user_id == current_user.user_id:
                token = self.generate_key()
                enterprise_user_perm_repo.create_enterprise_user_perm(session, current_user.user_id, enterprise_id,
                                                                      "admin", token)
                return True
        return False

    def make_user_as_admin_for_enterprise(self, session, user_id, enterprise_id):
        # user_perm = enterprise_user_perm_repo.get_user_enterprise_perm(user_id, enterprise_id)
        # EnterpriseUserPerm.objects.filter(user_id=user_id, enterprise_id=enterprise_id)
        user_perm = session.execute(select(EnterpriseUserPerm).where(EnterpriseUserPerm.user_id == user_id,
                                                                     EnterpriseUserPerm.enterprise_id == enterprise_id)).scalars().all()
        if not user_perm:
            token = self.generate_key()
            return enterprise_user_perm_repo.create_enterprise_user_perm(session, user_id, enterprise_id, "admin",
                                                                         token)
        return user_perm

    def list_roles(self, session, enterprise_id, user_id):
        perm = enterprise_user_perm_repo.get(session, enterprise_id, user_id)
        if not perm:
            return []
        return perm.identity.split(",")

    def create_user_set_password(self, session, user_name, email, raw_password, rf, enterprise_id, client_ip,
                                 phone=None,
                                 real_name=None):
        user = Users(
            origion="registration",
            union_id="",
            github_token="",
            nick_name=user_name,
            email=email,
            sso_user_id="",
            enterprise_id=enterprise_id,
            is_active=True,
            rf=rf,
            client_ip=client_ip,
            phone=phone,
            real_name=real_name,
        )
        user.set_password(raw_password)
        return user

    def create_enterprise_center_user_set_password(self, session, user_name, email, raw_password, rf, enterprise_id,
                                                   client_ip, phone, real_name, instance):
        data = {
            "username": user_name,
            "real_name": real_name,
            "password": raw_password,
            "email": email,
            "phone": phone,
        }
        enterprise_center_user = instance.create_user(enterprise_id, data)
        user = self.create_user_set_password(
            session, enterprise_center_user.username, email, raw_password, rf, enterprise_id, client_ip, phone=phone,
            real_name=real_name)
        user.enterprise_center_user_id = enterprise_center_user.user_id
        return user

    def get_client_ip(self, request):
        ip = request.client.host
        return ip

    def get_enterprise_user_by_username(self, session, user_name, eid):
        return user_repo.get_enterprise_user_by_username(session=session, eid=eid, user_name=user_name)

    def is_user_exist(self, session, user_name, eid=None):
        if self.get_enterprise_user_by_username(session, user_name, eid):
            return True
        else:
            return False

    def __check_user_name(self, session, user_name, eid=None):
        if not user_name:
            raise AbortRequest("empty username", "用户名不能为空")
        if self.is_user_exist(session, user_name, eid):
            raise AbortRequest("username already exists", "用户{0}已存在".format(user_name), status_code=409, error_code=409)
        r = re.compile('^[a-zA-Z0-9_\\-\\u4e00-\\u9fa5]+$')
        if not r.match(user_name):
            raise AbortRequest("invalid username", "用户名称只支持中英文下划线和中划线")
        return False

    def devops_check_user_name(self, session, user_name, eid=None):
        if not user_name:
            raise AbortRequest("empty username", "用户名不能为空")
        if self.is_user_exist(session, user_name, eid):
            return True
        r = re.compile('^[a-zA-Z0-9_\\-\\u4e00-\\u9fa5]+$')
        if not r.match(user_name):
            raise AbortRequest("invalid username", "用户名称只支持中英文下划线和中划线")
        return False

    def get_user_by_email(self, session, email):
        return user_repo.get_one_by_model(session=session, query_model=Users(email=email))
        # return user_repo.get_user_by_email(session=session, email=email)

    def __check_email(self, session, email):
        if not email:
            raise AbortRequest("empty email", "邮箱不能为空")
        if self.get_user_by_email(session, email):
            raise AbortRequest("email already exists", "邮箱{0}已存在".format(email))
        r = re.compile(r'^[\w\-\.]+@[\w\-]+(\.[\w\-]+)+$')
        if not r.match(email):
            raise AbortRequest("invalid email", "邮箱地址不合法")
        if self.get_user_by_email(session, email):
            raise AbortRequest("username already exists", "邮箱已存在", status_code=409, error_code=409)

    def __check_phone(self, session, phone):
        if not phone:
            return
        user = user_repo.get_user_by_phone(session=session, phone=phone)
        if user is not None:
            raise AbortRequest("user phone already exists", "用户手机号已存在", status_code=409)

    def check_params(self, session, user_name, email, password, re_password, eid=None, phone=None):
        self.__check_user_name(session, user_name, eid)
        self.__check_email(session, email)
        self.__check_phone(session, phone)
        if password != re_password:
            raise AbortRequest("The two passwords do not match", "两次输入的密码不一致")

    def devops_check_params(self, session, user_name, email, password, re_password, eid=None, phone=None):
        result = self.devops_check_user_name(session, user_name, eid)
        if result:
            return True
        self.__check_email(session, email)
        self.__check_phone(session, phone)
        if password != re_password:
            raise AbortRequest("The two passwords do not match", "两次输入的密码不一致")
        return False

    def update_roles(self, session, enterprise_id, user_id, roles):
        enterprise_user_perm_repo.update_roles(session, enterprise_id, user_id, ",".join(roles))

    def delete_admin_user(self, session, user_id):
        perm = enterprise_user_perm_repo.get_backend_enterprise_admin_by_user_id(session, user_id)
        if perm is None:
            raise ErrAdminUserDoesNotExist("用户'{}'不是企业管理员".format(user_id))
        count = enterprise_user_perm_repo.count_by_eid(session, perm.enterprise_id)
        if count == 1:
            raise ErrCannotDelLastAdminUser("当前用户为最后一个企业管理员，无法删除")
        enterprise_user_perm_repo.delete_backend_enterprise_admin_by_user_id(session, user_id)

    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()

    def create_admin_user(self, session, user, ent, roles):
        eup = enterprise_user_perm_repo.get(session, ent.enterprise_id, user.user_id)
        if not eup:
            token = self.generate_key()
            return enterprise_user_perm_repo.create_enterprise_user_perm(session, user.user_id, ent.enterprise_id,
                                                                         ",".join(roles),
                                                                         token)
        return enterprise_user_perm_repo.update_roles(session, ent.enterprise_id, user.user_id, ",".join(roles))

    def get_admin_users(self, session, eid):
        perms = session.execute(select(EnterpriseUserPerm).where(
            EnterpriseUserPerm.enterprise_id == eid
        )).scalars().all()
        users = []
        for item in perms:
            try:
                user = user_repo.get_user_by_user_id(session=session, user_id=item.user_id)
                users.append({
                    "user_id": user.user_id,
                    "email": user.email,
                    "nick_name": user.nick_name,
                    "real_name": user.real_name,
                    "phone": user.phone,
                    "is_active": user.is_active,
                    "origion": user.origion,
                    "create_time": user.create_time,
                    "client_ip": user.client_ip,
                    "enterprise_id": user.enterprise_id,
                    "roles": item.identity.split(","),
                })
            except UserNotExistError:
                logger.warning("user_id: {}; user not found".format(item.user_id))
                continue
        return users

    def list_user_team_perms(self, session: SessionClass, user, tenant):
        admin_roles = []
        identity = (
            session.execute(
                select(EnterpriseUserPerm.identity).where(EnterpriseUserPerm.enterprise_id == user.enterprise_id,
                                                          EnterpriseUserPerm.user_id == user.user_id))
        ).scalars().first()
        if identity:
            admin_roles = identity.split(",")

        user_perms = list(perms.list_enterprise_perm_codes_by_roles(admin_roles))
        if tenant.creater == user.user_id:
            perms_info = (
                session.execute(select(PermsInfo.code).where(PermsInfo.kind == "team"))
            ).scalars().all()

            team_perms = list(perms_info)
            user_perms.extend(team_perms)
            user_perms.append(200000)
        else:
            role_ids = (
                session.execute(
                    select(RoleInfo.ID).where(RoleInfo.kind_id == tenant.tenant_id, RoleInfo.kind == "team"))
            ).scalars().all()

            if role_ids:
                team_user_role_ids = (
                    session.execute(
                        select(UserRole.role_id).where(UserRole.user_id == user.user_id,
                                                       UserRole.role_id.in_(role_ids)))
                ).scalars().all()

                if team_user_role_ids:
                    team_role_perm_codes = (
                        session.execute(
                            select(RolePerms.perm_code).where(RolePerms.role_id.in_(team_user_role_ids)))
                    ).scalars().all()

                    if team_role_perm_codes:
                        user_perms.extend(list(team_role_perm_codes))
        return list(set(user_perms))

    def create_user(self, session: SessionClass, user):
        session.add(user)
        session.flush()

    def get_user_by_id(self, session: SessionClass, user_id):
        try:
            sql = select(Users).where(Users.user_id == user_id)
            q = session.execute(sql)
            session.flush()
            return q.scalars().first()
        except Users.DoesNotExist:
            return None

    def get_default_tenant_by_user(self, session: SessionClass, user_id):
        tenants = self.list_user_tenants(session=session, user_id=user_id)

        for tenant in tenants:
            if tenant.creater == user_id:
                return tenant

        return tenants[0] if tenants else None

    def list_user_tenants(self, session: SessionClass, user_id, load_region=False):
        if not user_id:
            return []

        sql = select(PermRelTenant).where(PermRelTenant.user_id == user_id)
        q = session.execute(sql)
        session.flush()
        perms = q.scalars().all()
        if not perms:
            return []

        tenant_ids = [t.tenant_id for t in perms]
        sql = select(TeamInfo).where(TeamInfo.ID.in_(tenant_ids))
        q = session.execute(sql)
        session.flush()
        tenants = q.scalars().all()
        if load_region:
            for tenant in tenants:
                if not hasattr(tenant, 'regions'):
                    tenant.regions = []
                sql = select(TeamRegionInfo).where(TeamRegionInfo.tenant_id == tenant.tenant_id)
                q = session.execute(sql)
                session.flush()
                tenant_regions = q.scalars().all()
                tenant.regions.extend(tenant_regions)

        return tenants

    def delete_tenant(self, user_id):
        """
        清理云帮用户信息
        :param user_id:
        :return:
        """
        user = Users.objects.get(user_id=user_id)
        tenants = TeamInfo.objects.filter(creater=user.user_id)
        for tenant in tenants:
            TeamRegionInfo.objects.filter(tenant_id=tenant.tenant_id).delete()
            tenant.delete()

        PermRelTenant.objects.filter(user_id=user.user_id).delete()
        TeamEnterprise.objects.filter(enterprise_id=user.enterprise_id).delete()
        user.delete()

    def is_exist(self, session: SessionClass, username, password):
        sql = select(Users).where(or_(Users.phone == username,
                                      Users.email == username,
                                      Users.nick_name == username))
        q = session.execute(sql)
        session.flush()
        u = q.scalars().first()
        if not u:
            return None, '用户不存在', 404
        if not u.check_password(password):
            return None, '密码不正确', 400
        return u, "验证成功", 200

    def num_to_char(self, num):
        """数字转中文"""
        num = str(num)
        new_str = ""
        num_dict = {"0": u"零", "1": u"一", "2": u"二", "3": u"三", "4": u"四", "5": u"五", "6": u"六", "7": u"七", "8": u"八",
                    "9": u"九"}
        listnum = list(num)
        shu = []
        for i in listnum:
            shu.append(num_dict[i])
        new_str = "".join(shu)
        return new_str

    def devops_get_current_user(self, session: SessionClass, token):
        if not token:
            raise ServiceHandleException(msg="parse token failed", msg_show="访问令牌解析失败")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user = user_repo.get_by_primary_key(session=session, primary_key=payload["user_id"])
        return user

    def check_user_password(self, session, user_id, password):
        u = user_repo.get_user_by_user_id(session=session, user_id=user_id)
        if u:
            default_pass = u.check_password("goodrain")
            if not default_pass:
                return u.check_password(password)
            return default_pass
        else:
            return None

    def update_password(self, session: SessionClass, user_id, new_password):
        u = user_repo.get_user_by_user_id(session=session, user_id=user_id)
        if not u:
            return None
        else:
            if len(new_password) < 8:
                return False, "密码不能小于8位"
            u.set_password(new_password)
            session.add(u)
            session.flush()
            return True, "password update success"

    def check_user_is_enterprise_center_user(self, session: SessionClass, user_id):
        oauth_user, oauth_service = oauth_user_repo.get_enterprise_center_user_by_user_id(session, user_id)
        if oauth_user and oauth_service:
            return get_oauth_instance(oauth_service.oauth_type, oauth_service, oauth_user), oauth_user
        return None, None

    def get_user_by_eid(self, session: SessionClass, eid, name, page, page_size):
        if page < 1:
            page = 1
        if name:
            users = (
                session.execute(select(Users).where(Users.enterprise_id == eid,
                                                    or_(Users.nick_name.like('%' + name + '%'),
                                                        Users.real_name.like('%' + name + '%'))))
            ).scalars().all()
            total = (
                session.execute(
                    select(func.count(Users.user_id)).where(
                        Users.enterprise_id == eid,
                        or_(Users.nick_name.like('%' + name + '%'), Users.real_name.like('%' + name + '%'))))
            ).first()[0]
        else:
            users = (
                session.execute(
                    select(Users).where(Users.enterprise_id == eid).limit(page_size).offset((page - 1) * page_size))
            ).scalars().all()
            total = (
                session.execute(
                    select(func.count(Users.user_id)).where(Users.enterprise_id == eid))
            ).first()[0]
        return users, total

    def update_user_set_password(self, request, session: SessionClass, enterprise_id, user_id, raw_password, real_name,
                                 phone):
        user = (session.execute(
            select(Users).where(Users.user_id == user_id,
                                Users.enterprise_id == enterprise_id))).scalars().first()
        user.real_name = real_name
        if phone:
            u = user_repo.get_user_by_phone(session=session, phone=phone)
            if u and int(u.user_id) != int(user.user_id):
                raise "手机号已存在"
            user.phone = phone
        if raw_password:
            user.set_password(raw_password)
        request.app.state.redis.set("user_%d" % user.user_id, pickle.dumps(user), 24 * 60 * 60)
        return user

    def delete_user(self, session: SessionClass, user_id):
        user = (session.execute(
            select(Users).where(Users.user_id == user_id))).scalars().first()
        session.execute(
            delete(PermRelTenant).where(PermRelTenant.user_id == user.user_id))
        session.execute(
            delete(UserRole).where(UserRole.user_id == user.user_id))
        session.execute(
            delete(Users).where(Users.user_id == user_id))
        session.execute(
            delete(EnterpriseUserPerm).where(EnterpriseUserPerm.user_id == user_id))


class UserKindPermService(object):
    def get_user_perms(self, session: SessionClass, kind, kind_id, user, is_owner=False, is_ent_admin=False):
        if is_owner or is_ent_admin:
            is_owner = True
        user_roles = user_role_repo.get_user_roles_model(session, kind, kind_id, user)
        perms = role_perm_service.get_roles_union_perms(session=session, roles=user_roles, kind=kind, is_owner=is_owner)
        data = {"user_id": user.user_id}
        data.update(perms)
        return data


class RolePermService(object):
    def __unpack_to_build_perms_list(self, session, perms_model, role_id, perms_name_code_kv):
        role_perms_list = []
        items_list = list(perms_model.items())
        for items in items_list:
            kind_name, body = items
            if body["sub_models"]:
                for sub in body["sub_models"]:
                    role_perms_list.extend(self.__unpack_to_build_perms_list(session, sub, role_id, perms_name_code_kv))
            for perm in body["perms"]:
                perm_items = list(perm.items())[0]
                perm_key, perms_value = perm_items
                if perms_value:
                    role_perms_list.append(
                        RolePerms(role_id=role_id, perm_code=perms_name_code_kv["_".join([kind_name, perm_key])]))
        return role_perms_list

    # 角色的权限树降维
    def unpack_role_perms_tree(self, session, perms_model, role_id, perms_name_code_kv):
        role_perms_list = self.__unpack_to_build_perms_list(session, perms_model, role_id, perms_name_code_kv)
        session.add_all(role_perms_list)

    def delete_role_perms(self, session, role_id):
        return role_perm_repo.delete_role_perm_relation(session, role_id)

    def update_role_perms(self, session, role_id, perms_model, kind=None):
        self.delete_role_perms(session, role_id)
        self.unpack_role_perms_tree(session, perms_model, role_id, get_perms_name_code_kv())

    def get_roles_union_perms(self, session: SessionClass, roles, kind=None, is_owner=False):
        union_role_perms = []
        if roles:
            role_ids = [role.role_id for role in roles]
            roles_perm_relation_mode = role_perm_repo.get_roles_perm_relation(session, role_ids)
            if roles_perm_relation_mode:
                # roles_perm_relations = roles_perm_relation_mode.values("role_id", "perm_code")
                union_role_perms = [mode.perm_code for mode in roles_perm_relation_mode]
                # for roles_perm_relation in roles_perm_relations:
                #     union_role_perms.append(roles_perm_relation["perm_code"])
        if kind == "team":
            permissions = self.pack_role_perms_tree(get_team_perms_model(), union_role_perms, is_owner)
        elif kind == "enterprise":
            permissions = self.pack_role_perms_tree(get_enterprise_perms_model(), union_role_perms, is_owner)
        else:
            permissions = self.pack_role_perms_tree(get_perms_model(), union_role_perms, is_owner)
        return {"permissions": permissions}

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


class UserKindRoleService(object):
    def get_user_roles(self, session, kind, kind_id, user):
        return user_role_repo.get_user_roles(session, kind, kind_id, user)

    def get_users_roles(self, session: SessionClass, kind, kind_id, users, creater_id=0):
        return user_role_repo.get_users_roles(session, kind, kind_id, users, creater_id=creater_id)

    def delete_user_roles(self, session, kind, kind_id, user):
        user_role_repo.delete_user_roles(session, kind, kind_id, user)

    def update_user_roles(self, session, kind, kind_id, user, role_ids):
        self.delete_user_roles(session, kind, kind_id, user)
        user_role_repo.update_user_roles(session, kind, kind_id, user, role_ids)


user_svc = UserService()
role_perm_service = RolePermService()
user_kind_perm_service = UserKindPermService()
user_kind_role_service = UserKindRoleService()
