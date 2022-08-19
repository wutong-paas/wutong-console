import re
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy_utils import ChoiceType

from core.utils.crypt import encrypt_passwd
from database.session import Base
from models.component.models import user_origion


class Users(Base):
    USERNAME_FIELD = 'nick_name'

    __tablename__ = 'user_info'

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(35), comment="邮件地址", nullable=False)
    nick_name = Column(String(64), comment="账号", nullable=True)
    real_name = Column(String(64), comment="姓名", nullable=True)
    password = Column(String(64), comment="密码", nullable=False)
    phone = Column(String(15), comment="手机号码", nullable=True)
    is_active = Column(Boolean, comment="激活状态", nullable=False, default=False)
    origion = Column(String(12), ChoiceType(user_origion), comment="用户来源", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    git_user_id = Column(Integer, comment="git用户id", nullable=False, default=0)
    github_token = Column(String(60), comment="github token", nullable=False)
    client_ip = Column(String(20), comment="注册ip", nullable=False)
    rf = Column(String(60), comment="注册源", nullable=False)
    # 0:普通注册,未绑定微信
    # 1:普通注册,绑定微信
    # 2:微信注册,绑定微信,未补充信息
    # 3:微信注册,绑定微信,已补充信息
    # 4:微信注册,解除微信绑定,已补充信息
    status = Column(Integer, comment="用户类型", nullable=False, default=0)
    union_id = Column(String(100), comment="绑定微信的union_id", nullable=False)
    sso_user_id = Column(String(32), comment="统一认证中心的user_id", default='', nullable=True)
    sso_user_token = Column(String(256), comment="统一认证中心的user_token", default='', nullable=True)
    enterprise_id = Column(String(32), comment="统一认证中心的enterprise_id", default='', nullable=True)
    enterprise_center_user_id = Column(String(32), comment="统一认证中心的user", default='', nullable=True)
    login_sta = Column(Boolean, comment="登录是否锁定", default=False, nullable=True)
    login_suo = Column(DateTime(), comment="登录锁定时间", nullable=True)
    pass_errnum = Column(Integer, comment="用户密码输错次数", default=0, nullable=True)

    def set_password(self, raw_password):
        self.password = encrypt_passwd(self.email + raw_password)

    def check_password(self, raw_password):
        return bool(encrypt_passwd(self.email + raw_password) == self.password)

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    def get_name(self):
        if self.real_name:
            return self.real_name
        return self.nick_name

    # def get_session_auth_hash(self):
    #     """
    #     Returns an HMAC of the password field.
    #     """
    #     key_salt = "goodrain.com.models.get_session_auth_hash"
    #     return salted_hmac(key_salt, self.password).hexdigest()

    @property
    def safe_email(self):
        return re.sub(r'(?<=\w{2}).*(?=\w@.*)', 'xxxx', self.email)

    def __unicode__(self):
        return self.nick_name or self.email

    def to_dict(self):
        opts = self._meta
        data = {}
        for f in opts.concrete_fields:
            value = f.value_from_object(self)
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            data[f.name] = value
        return data

    def get_username(self):
        return self.nick_name


class SuperAdminUser(Base):
    """超级管理员"""

    __tablename__ = "user_administrator"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, comment="用户ID", nullable=False)
    email = Column(String(35), comment="邮件地址", nullable=True)


class UserAccessKey(Base):
    """企业通信凭证"""

    # class Meta:
    #     db_table = 'user_access_key'
    #     unique_together = (('note', 'user_id'), )

    __tablename__ = 'user_access_key'

    ID = Column(Integer, primary_key=True)
    note = Column(String(32), comment="凭证标识")
    user_id = Column(Integer, comment="用户id")
    access_key = Column(String(512), unique=True, comment="凭证")
    expire_time = Column(DateTime(), nullable=True, comment="过期时间")


class UserFavorite(Base):
    __tablename__ = "user_favorite"

    ID = Column(Integer, primary_key=True)
    name = Column(String(64), comment="收藏视图名称")
    url = Column(String(255), comment="收藏视图链接")
    user_id = Column(Integer, comment="用户id")
    create_time = Column(DateTime(), default=datetime.now)
    update_time = Column(DateTime(), default=datetime.now, onupdate=datetime.now)
    custom_sort = Column(Integer, comment="用户自定义排序")
    is_default = Column(Boolean(), default=False, comment="用户自定义排序")
