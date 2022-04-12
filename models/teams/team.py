import json
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime, DECIMAL, Text
from sqlalchemy_utils import ChoiceType

from core.utils.crypt import make_tenant_id, make_uuid
from database.session import Base
from core.setting import settings

tenant_type = (("免费租户", "free"), ("付费租户", "payed"))
tenant_identity = (("拥有者", "owner"), ("管理员", "admin"), ("开发者", "developer"), ("观察者", "viewer"), ("访问", "access"))


class TeamInfo(Base):
    """
    租户表
    """

    __tablename__ = 'tenant_info'

    ID = Column(Integer, primary_key=True)
    tenant_id = Column(String(33), comment="租户id", nullable=False, unique=True, default=make_tenant_id)
    tenant_name = Column(String(64), comment="租户名称", nullable=False, unique=True)
    # This property is deprecated
    # region = Column(String(64, default='', comment="区域中心,弃用")
    is_active = Column(Boolean, comment="激活状态", nullable=False, default=True)
    pay_type = Column(String(5), ChoiceType(tenant_type), comment="付费状态", nullable=False)
    balance = Column(DECIMAL(10), comment="账户余额", nullable=False, default=0.00)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    creater = Column(Integer, nullable=False, default=0, comment="租户创建者")
    limit_memory = Column(Integer, nullable=False, default=1024, comment="内存大小单位（M）")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, comment="更新时间")
    pay_level = Column(String(30), comment="付费级别", nullable=False, default='free')
    expired_time = Column(DateTime(), nullable=True, comment="过期时间")
    tenant_alias = Column(String(64), comment="团队别名", nullable=True, default='')
    enterprise_id = Column(String(32), ChoiceType(tenant_type), comment="企业id", nullable=True, default='')
    namespace = Column(String(33), comment="团队的命名空间", unique=True, nullable=False)

    def __unicode__(self):
        return self.tenant_name


class ServiceDomain(Base):
    """访问策略管理(http)"""

    __tablename__ = 'service_domain'

    ID = Column(Integer, primary_key=True)
    http_rule_id = Column(String(128), comment="规则id", nullable=False, unique=True)
    region_id = Column(String(36), comment="区域id", nullable=False)
    tenant_id = Column(String(32), comment="租户id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    service_name = Column(String(64), comment="组件名", nullable=False)
    domain_name = Column(String(128), comment="域名", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    container_port = Column(Integer, nullable=False, default=0, comment="容器端口")
    protocol = Column(String(15), comment="域名类型", nullable=False, default='http')
    certificate_id = Column(Integer, nullable=False, default=0, comment="证书ID")
    domain_type = Column(String(20), comment="组件域名类型", nullable=False, default='www')
    service_alias = Column(String(64), comment="组件别名", nullable=False, default='')
    is_senior = Column(Boolean, comment="是否有高级路由", nullable=False, default=False)
    domain_path = Column(Text, comment="域名path", nullable=False)
    domain_cookie = Column(Text, comment="域名cookie", nullable=False)
    domain_heander = Column(Text, comment="域名heander", nullable=False)
    type = Column(Integer, nullable=False, default=0, comment="类型（默认：0， 自定义：1）")
    the_weight = Column(Integer, nullable=False, default=100, comment="权重")
    rule_extensions = Column(Text, comment="扩展功能", nullable=False)
    is_outer_service = Column(Boolean, comment="是否已开启对外端口", nullable=False, default=True)
    auto_ssl = Column(Boolean, comment="是否自动匹配证书", nullable=False, default=False)
    auto_ssl_config = Column(String(32), comment="自动分发证书配置", nullable=True, default=None)

    def __unicode__(self):
        return self.domain_name

    @property
    def load_balancing(self):
        for ext in self.rule_extensions.split(","):
            ext = ext.split(":")
            if len(ext) != 2 or ext[0] == "" or ext[1] == "":
                continue
            if ext[0] == "lb-type":
                return ext[1]
        # round-robin is the default value of load balancing
        return "round-robin"


class ServiceTcpDomain(Base):
    """Tcp/Udp策略"""

    __tablename__ = 'service_tcp_domain'

    ID = Column(Integer, primary_key=True)
    tcp_rule_id = Column(String(128), comment="规则id", nullable=False, unique=True)
    region_id = Column(String(36), comment="区域id", nullable=False)
    tenant_id = Column(String(32), comment="租户id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    service_name = Column(String(64), comment="组件名", nullable=False)
    end_point = Column(String(256), comment="ip+port", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    protocol = Column(String(15), comment="服务协议：tcp,udp", nullable=False, default='')
    container_port = Column(Integer, nullable=False, default=0, comment="容器端口")
    service_alias = Column(String(64), comment="组件别名", nullable=False, default='')
    type = Column(Integer, nullable=False, default=0, comment="类型（默认：0， 自定义：1）")
    rule_extensions = Column(Text, comment="扩展功能", nullable=True)
    is_outer_service = Column(Boolean, comment="是否已开启对外端口", nullable=False, default=True)

    @property
    def load_balancing(self):
        for ext in self.rule_extensions.split(","):
            ext = ext.split(":")
            if len(ext) != 2 or ext[0] == "" or ext[1] == "":
                continue
            if ext[0] == "lb-type":
                return ext[1]
        # round-robin is the default value of load balancing
        return "round-robin"


class GatewayCustomConfiguration(Base):
    """网关自定义参数配置"""

    __tablename__ = 'gateway_custom_configuration'

    ID = Column(Integer, primary_key=True)
    rule_id = Column(String(32), comment="规则id", nullable=False, unique=True)
    value = Column(Text, comment="配置value", nullable=False)


class ServiceDomainCertificate(Base):
    """网关证书管理"""

    __tablename__ = 'service_domain_certificate'

    ID = Column(Integer, primary_key=True)
    tenant_id = Column(String(32), comment="租户id", nullable=False)
    certificate_id = Column(String(50), comment="证书的唯一uuid", nullable=False)
    private_key = Column(Text, comment="证书key", nullable=False, default='')
    certificate = Column(Text, comment="证书", nullable=False, default='')
    certificate_type = Column(Text, comment="证书类型", nullable=False, default='')
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    alias = Column(String(64), comment="证书别名", nullable=False)

    def __unicode__(self):
        return "private_key:{} certificate:{}".format(self.private_key, self.certificate)


class Applicants(Base):
    """待审批人员信息"""

    __tablename__ = 'applicants'

    ID = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    user_name = Column(String(64), comment="申请用户名", nullable=False)
    team_id = Column(String(33), comment="所属团队id", nullable=False)
    team_name = Column(String(64), comment="申请组名", nullable=False)
    apply_time = Column(DateTime(), nullable=False, default=datetime.now, comment="申请时间")
    is_pass = Column(Integer, nullable=False, comment="审核状态", default=0)
    team_alias = Column(String(64), comment="团队名", nullable=False)


class PermRelTenant(Base):
    """
    用户和团队的关系表
    identity ：租户权限
    """

    __tablename__ = 'tenant_perms'

    ID = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, comment="关联用户")
    tenant_id = Column(Integer, nullable=False, comment="团队id")
    identity = Column(String(15), ChoiceType(tenant_identity), comment="租户身份", nullable=True)
    enterprise_id = Column(Integer, nullable=False, comment="关联企业")
    role_id = Column(Integer, nullable=True, comment="角色")


class RegionConfig(Base):
    """集群管理"""

    __tablename__ = 'region_info'

    ID = Column(Integer, primary_key=True)
    region_id = Column(String(36), comment="区域id", nullable=False, unique=True)
    region_name = Column(String(64), comment="数据中心名称,不可修改", nullable=False, unique=True)
    region_alias = Column(String(64), comment="数据中心别名", nullable=False)
    region_type = Column(String(64), comment="数据中心类型", nullable=True, default=json.dumps([]))
    url = Column(String(256), comment="数据中心API url", nullable=False)
    wsurl = Column(String(256), comment="数据中心Websocket url", nullable=False)
    httpdomain = Column(String(256), comment="数据中心http应用访问根域名", nullable=False)
    tcpdomain = Column(String(256), comment="数据中心tcp应用访问根域名", nullable=False)
    token = Column(String(255), comment="数据中心token", nullable=True, default="")
    status = Column(String(2), comment="数据中心状态", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    desc = Column(String(200), comment="数据中心描述", nullable=False)
    scope = Column(String(10), comment="数据中心范围 private|public", nullable=False, default="private")
    ssl_ca_cert = Column(Text, comment="数据中心访问ca证书地址", nullable=True)
    cert_file = Column(Text, comment="验证文件", nullable=True)
    key_file = Column(Text, comment="验证的key", nullable=True)
    enterprise_id = Column(String(36), comment="企业id", nullable=True)
    provider = Column(String(24), comment="底层集群供应类型", nullable=True, default='')
    provider_cluster_id = Column(String(64), comment="底层集群ID", nullable=True, default='')


def logo_path(instance, filename):
    suffix = filename.split('.')[-1]
    return '{0}/logo/{1}.{2}'.format(settings.MEDIA_ROOT, make_uuid(), suffix)


class RoleInfo(Base):
    """权限角色信息（管理员，开发者，观察者）"""

    __tablename__ = 'role_info'

    ID = Column(Integer, primary_key=True)
    name = Column(String(32), comment="角色名称", nullable=False)
    kind_id = Column(String(64), comment="角色所属范围id", nullable=False)
    kind = Column(String(32), comment="角色所属", nullable=False)


class PermsInfo(Base):
    """权限分配信息"""

    __tablename__ = 'perms_info'

    ID = Column(Integer, primary_key=True)
    name = Column(String(32), comment="权限名称", nullable=False, unique=True)
    desc = Column(String(32), comment="权限描述", nullable=False)
    code = Column(Integer, comment="权限编码", nullable=False, unique=True)
    group = Column(String(32), comment="权限类型", nullable=False)
    kind = Column(String(32), comment="权限所属", nullable=False)


class ConsoleConfig(Base):
    """
    控制台配置
    """
    __tablename__ = 'console_config'
    ID = Column(Integer, primary_key=True)
    key = Column(String(100), comment="配置名称")
    value = Column(String(1000), comment="配置值")
    description = Column(Text(), nullable=True, default="", comment="说明")
    update_time = Column(DateTime(), comment="更新时间", nullable=True)


class ConsoleSysConfig(Base):
    """企业基础设置"""

    __tablename__ = 'console_sys_config'

    ID = Column(Integer, primary_key=True)
    key = Column(String(32), comment="key", nullable=False)
    type = Column(String(32), comment="类型", nullable=False)
    value = Column(String(4096), comment="value", nullable=True)
    desc = Column(String(100), comment="描述", nullable=True, default="")
    enable = Column(Boolean, comment="是否生效", nullable=False, default=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    enterprise_id = Column(String(32), comment="eid", nullable=False, default="")


class RolePerms(Base):
    """角色权限管理"""

    __tablename__ = 'role_perms'

    ID = Column(Integer, primary_key=True)
    role_id = Column(Integer, comment="角色id", nullable=False)
    perm_code = Column(Integer, comment="权限编码", nullable=False)


class UserRole(Base):
    """用户角色"""

    __tablename__ = 'user_role'

    ID = Column(Integer, primary_key=True)
    user_id = Column(String(32), comment="用户id", nullable=False)
    role_id = Column(String(32), comment="角色id", nullable=False)


class UserMessage(Base):
    """用户站内信"""

    __tablename__ = 'user_message'

    ID = Column(Integer, primary_key=True)
    message_id = Column(String(32), comment="消息ID", nullable=False)
    receiver_id = Column(Integer, comment="接受消息用户ID", nullable=False)
    content = Column(String(1000), comment="消息内容", nullable=False)
    is_read = Column(Boolean, comment="是否已读", nullable=False, default=False)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, comment="更新时间")
    msg_type = Column(String(32), comment="消息类型", nullable=False)
    announcement_id = Column(String(32), comment="公告ID", nullable=True)
    title = Column(String(64), comment="消息标题", nullable=False, default="title")
    level = Column(String(32), comment="通知的等级", nullable=False, default="low")
