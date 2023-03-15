import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from core.utils.crypt import make_env_id
from database.session import Base

tenant_env_identity = (("拥有者", "owner"), ("管理员", "admin"), ("开发者", "developer"), ("观察者", "viewer"), ("访问", "access"))


class TeamEnvInfo(Base):
    """
    环境表
    """

    __tablename__ = 'tenant_env_info'

    ID = Column(Integer, primary_key=True)
    env_id = Column(String(33), comment="环境id", nullable=False, unique=True, default=make_env_id)
    region_name = Column(String(33), comment="集群名", nullable=False)
    region_code = Column(String(33), comment="集群标识", nullable=False)
    env_name = Column(String(31), comment="环境名称", nullable=False)
    tenant_id = Column(String(33), comment="团队id", nullable=False)
    tenant_name = Column(String(31), comment="团队名称", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    creater = Column(String(64), nullable=False, default="admin", comment="租户创建者")
    limit_memory = Column(Integer, nullable=False, default=1024, comment="内存大小单位（M）")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    env_alias = Column(String(64), comment="环境别名", nullable=False)
    namespace = Column(String(33), comment="环境的命名空间", nullable=False)
    desc = Column(String(255), comment="描述", nullable=True)

    def __unicode__(self):
        return self.env_name


class ServiceDomain(Base):
    """访问策略管理(http)"""

    __tablename__ = 'service_domain'

    ID = Column(Integer, primary_key=True)
    http_rule_id = Column(String(128), comment="规则id", nullable=False, unique=True)
    region_id = Column(String(36), comment="区域id", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
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
    path_rewrite = Column(Boolean, comment="是否开启简单路由重写", nullable=False, default=False)
    rewrites = Column(Text, comment="复杂路由重写配置", nullable=True)

    is_delete = Column(Boolean, comment="是否删除", nullable=False, default=False)
    delete_time = Column(DateTime(), nullable=True, comment="删除时间")
    delete_operator = Column(String(100), comment="删除操作人", nullable=True)

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
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
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

    is_delete = Column(Boolean, comment="是否删除", nullable=False, default=False)
    delete_time = Column(DateTime(), nullable=True, comment="删除时间")
    delete_operator = Column(String(100), comment="删除操作人", nullable=True)

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
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    certificate_id = Column(String(50), comment="证书的唯一uuid", nullable=False)
    private_key = Column(Text, comment="证书key", nullable=False, default='')
    certificate = Column(Text, comment="证书", nullable=False, default='')
    certificate_type = Column(Text, comment="证书类型", nullable=False, default='')
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    alias = Column(String(64), comment="证书别名", nullable=False)

    def __unicode__(self):
        return "private_key:{} certificate:{}".format(self.private_key, self.certificate)


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
    provider = Column(String(24), comment="底层集群供应类型", nullable=True, default='')
    provider_cluster_id = Column(String(64), comment="底层集群ID", nullable=True, default='')
