import json
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, DECIMAL
from sqlalchemy.dialects.mysql import LONGTEXT
from core.enum.component_enum import ComponentSource
from database.session import Base


class Component(Base):
    """组件管理"""

    __tablename__ = 'tenant_service'
    # todo
    # unique_together = ('tenant_env_id', 'service_alias')

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id", nullable=False, unique=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_key = Column(String(32), comment="组件key", nullable=False)
    service_alias = Column(String(100), comment="组件别名", nullable=False)
    service_cname = Column(String(100), comment="组件名", nullable=False, default='')
    service_region = Column(String(64), comment="组件所属区", nullable=False)
    desc = Column(String(200), comment="描述", nullable=True)
    category = Column(String(15), comment="组件分类", nullable=False)
    service_port = Column(Integer, comment="组件端口", nullable=False, default=0)
    is_web_service = Column(Boolean, comment="是否web组件", nullable=False, default=False)
    version = Column(String(255), comment="版本", nullable=False)
    update_version = Column(Integer, comment="内部发布次数", nullable=False, default=1)
    image = Column(String(200), comment="镜像", nullable=False)
    cmd = Column(String(2048), comment="启动参数", nullable=True)
    min_node = Column(Integer, comment="实例数量", nullable=False, default=1)
    min_cpu = Column(Integer, comment="cpu分配额 1000=1core", nullable=False, default=500)
    container_gpu = Column(Integer, comment="gpu显存数量", nullable=False, default=0)
    gpu_type = Column(String(32), comment="gpu类型", nullable=True)
    min_memory = Column(Integer, comment="内存大小单位（M）", nullable=False, default=256)
    image_hub = Column(String(32), comment="镜像源类型", nullable=True)

    # deprecated
    setting = Column(String(200), comment="设置项", nullable=True)
    extend_method = Column(String(32), comment="组件部署类型", nullable=False, default='stateless_multiple')
    # deprecated
    env = Column(String(200), comment="环境变量", nullable=True)
    # deprecated
    inner_port = Column(Integer, comment="内部端口", nullable=False, default=0)
    # deprecated
    volume_mount_path = Column(String(200), comment="mount目录", nullable=True)
    # deprecated
    host_path = Column(String(300), comment="mount目录", nullable=True)
    # deprecated
    deploy_version = Column(String(20), comment="仅用于云市创建应用表示构建源的部署版本-小版本", nullable=True)
    code_from = Column(String(20), comment="代码来源:gitlab,github", nullable=True)
    git_url = Column(String(2047), comment="code代码仓库", nullable=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    git_project_id = Column(Integer, comment="gitlab中项目id", nullable=False, default=0)
    # deprecated
    is_code_upload = Column(Boolean, comment="是否上传代码", nullable=False, default=False)
    # deprecated
    code_version = Column(String(100), comment="代码版本", nullable=True)
    service_type = Column(String(50), comment="组件类型", nullable=True)
    creater = Column(String(64), comment="组件创建者", nullable=False, default="admin")
    language = Column(String(40), comment="代码语言", nullable=True)
    # deprecated
    protocol = Column(String(15), comment="服务协议：http,stream", nullable=False, default='')
    # deprecated
    total_memory = Column(Integer, comment="内存使用M", nullable=False, default=0)
    # deprecated
    is_service = Column(Boolean, comment="是否inner组件", nullable=False, default=False)
    # deprecated
    namespace = Column(String(100), comment="镜像发布云帮的区间", nullable=False, default='')
    # deprecated
    volume_type = Column(String(64), comment="共享类型shared、exclusive", nullable=False, default='shared')
    # deprecated
    port_type = Column(String(15), comment="端口类型", nullable=False, default='multi_outer')
    # 组件创建类型,cloud、assistant
    service_origin = Column(String(15), comment="组件创建类型cloud云市组件", nullable=False, default='assistant')
    # 组件所属关系，从模型安装的多个组件所属一致。
    tenant_service_group_id = Column(Integer, comment="组件归属的组件组id", nullable=False, default=0)
    # deprecated
    expired_time = Column(DateTime(), nullable=True, default=datetime.now, comment="过期时间")
    open_webhooks = Column(Boolean, comment="是否开启自动触发部署功能(兼容老版本组件)", nullable=False, default=False)
    service_source = Column(String(15), comment="组件来源", nullable=True, default="")
    create_status = Column(String(15), comment="组件创建状态 creating|complete", nullable=True)
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    check_uuid = Column(String(36), comment="组件检测ID", nullable=True, default="")
    check_event_id = Column(String(32), comment="组件检测事件ID", nullable=True, default="")
    docker_cmd = Column(String(1024), comment="镜像创建命令", nullable=True)
    secret = Column(String(64), comment="webhooks验证密码", nullable=True)
    server_type = Column(String(5), comment="源码仓库类型", nullable=False, default='git')
    is_upgrate = Column(Boolean, comment="是否可以更新", nullable=False, default=False)
    build_upgrade = Column(Boolean, comment="组件构建后是否升级", nullable=False, default=True)
    service_name = Column(String(100), comment="组件名称", nullable=True, default='')
    oauth_service_id = Column(Integer, comment="拉取源码所用的OAuth服务id", nullable=True, default=None)
    git_full_name = Column(String(64), comment="git项目的fullname", nullable=True, default=None)
    k8s_component_name = Column(String(100), comment="集群组件名称", nullable=True)

    monitor = Column(String(32), comment="组件监控类型(devops、plugin、None)", nullable=True, default=None)
    obs_strategy_code = Column(String(32), comment="告警策略标识", nullable=True, default=None)

    is_delete = Column(Boolean, comment="是否删除", nullable=False, default=False)
    delete_time = Column(DateTime(), nullable=True, comment="删除时间")
    delete_operator = Column(String(100), comment="删除操作人", nullable=True)

    def toJSON(self):
        data = {}
        for f in self._meta.fields:
            obj = getattr(self, f.name)
            if type(f.name) == DateTime:
                data[f.name] = obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                data[f.name] = obj
        return data

    @property
    def clone_url(self):
        if self.code_from == "github":
            code_user = self.git_url.split("/")[3]
            code_project_name = self.git_url.split("/")[4].split(".")[0]
            # todo
            # createUser = Users.objects.get(user_id=self.creater)
            # git_url = "https://{github_token}@github.com/{code_user}/{code_project_name}.git".format(
            #     github_token=createUser.github_token, code_user=code_user, code_project_name=code_project_name)
            # return git_url
        else:
            return self.git_url

    def is_slug(self):
        return bool(self.image.endswith('/runner')) or bool('/runner:' in self.image)

    def is_third_party(self):
        if self.service_source == ComponentSource.THIRD_PARTY.value:
            return True
        return False

    def component_id(self):
        return self.service_id


class ComponentMonitor(Base):
    """组件业务监控"""

    __tablename__ = "tenant_service_monitor"
    unique_together = ('name', 'tenant_env_id')

    ID = Column(Integer, primary_key=True)
    name = Column(String(64), comment="名称", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="组件ID", nullable=False)
    path = Column(String(255), comment="监控路径", nullable=False)
    port = Column(Integer, nullable=False, comment="端口号")
    service_show_name = Column(String(64), comment="展示名称", nullable=False)
    interval = Column(String(10), comment="收集指标时间间隔", nullable=False)


class TeamComponentLog(Base):
    """组件日志"""

    __tablename__ = 'tenant_service_log'

    ID = Column(Integer, primary_key=True)
    user_id = Column(String(32), nullable=False, comment="用户id")
    user_name = Column(String(40), comment="用户名", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    action = Column(String(15), comment="分类", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class AutoscalerRules(Base):
    """组件自动伸缩规则"""

    __tablename__ = "autoscaler_rules"

    ID = Column(Integer, primary_key=True)
    rule_id = Column(String(32), comment="自动伸缩规则ID", nullable=False, unique=True)
    service_id = Column(String(32), comment="关联的组件ID", nullable=False)
    enable = Column(Boolean, comment="是否启用自动伸缩规则", nullable=False, default=True)
    xpa_type = Column(String(3), comment="自动伸缩规则类型", nullable=False)
    min_replicas = Column(Integer, comment="最小副本数", nullable=False)
    max_replicas = Column(Integer, comment="最大副本数", nullable=False)


class AutoscalerRuleMetrics(Base):
    """组件自动缩放规则指标"""

    __tablename__ = "autoscaler_rule_metrics"
    unique_together = ('rule_id', 'metric_type', 'metric_name')

    ID = Column(Integer, primary_key=True)
    rule_id = Column(String(32), comment="关联的自动伸缩规则ID", nullable=False)
    metric_type = Column(String(16), comment="指标类型", nullable=False)
    metric_name = Column(String(255), comment="指标名称", nullable=False)
    metric_target_type = Column(String(13), comment="指标目标类型", nullable=False)
    metric_target_value = Column(Integer, comment="指标目标值", nullable=False)


class TeamComponentVolume(Base):
    """数据持久化表格"""

    __tablename__ = 'tenant_service_volume'

    SHARE = 'share-file'
    LOCAL = 'local'
    TMPFS = 'memoryfs'
    CONFIGFILE = 'config-file'

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id", nullable=False)
    category = Column(String(50), comment="组件类型", nullable=False)
    host_path = Column(String(400), comment="物理机的路径,绝对路径", nullable=False)
    volume_type = Column(String(64), comment="容器类型", nullable=False)
    volume_path = Column(String(400), comment="容器内路径", nullable=False)
    volume_name = Column(String(100), comment="容器名称", nullable=False)
    volume_capacity = Column(Integer, comment="存储大小，单位(Mi)", nullable=False, default=0)
    volume_provider_name = Column(String(100), comment="存储驱动名字", nullable=True)
    access_mode = Column(String(100), comment="读写模式：RWO、ROX、RWX", nullable=True)
    share_policy = Column(String(100), comment="共享模式", nullable=True, default='')
    backup_policy = Column(String(100), comment="备份策略", nullable=True, default='')
    reclaim_policy = Column(String(100), comment="回收策略", nullable=True, default='')
    allow_expansion = Column(Boolean, comment="只是支持控制扩展，0：不支持；1：支持", nullable=True, default=False)
    mode = Column(Integer, comment="存储权限", nullable=True)
    config_type = Column(String(32), comment="配置文件类型：single:单文件配置;multi：多文件配置", nullable=True, default='')


class TeamComponentMountRelation(Base):
    """组件环境配置共享配置文件"""

    __tablename__ = 'tenant_service_mnt_relation'
    unique_together = ('service_id', 'dep_service_id', 'mnt_name')

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    dep_service_id = Column(String(32), comment="依赖组件id", nullable=False)
    mnt_name = Column(String(100), comment="mnt name", nullable=False)
    mnt_dir = Column(String(400), comment="mnt dir", nullable=False)

    def key(self):
        return self.service_id + self.dep_service_id + self.mnt_name


class ComponentEnvVar(Base):
    """组件自定义环境变量"""

    __tablename__ = 'tenant_service_env_var'

    class ScopeType(Enum):
        """范围"""
        OUTER = "outer"
        INNER = "inner"

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    container_port = Column(Integer, comment="端口", nullable=False, default=0)
    name = Column(String(1024), comment="名称", nullable=True)
    attr_name = Column(String(1024), comment="属性", nullable=False)
    attr_value = Column(Text, comment="值", nullable=False)
    is_change = Column(Boolean, comment="是否可改变", nullable=False, default=False)
    scope = Column(String(10), comment="范围", nullable=False, default=ScopeType.OUTER.value)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")

    def is_port_env(self):
        return self.container_port != 0

    def is_host_env(self):
        return self.container_port != 0 and self.attr_name.endswith("_HOST")


class TeamComponentPort(Base):
    """组件端口"""

    __tablename__ = 'tenant_services_port'
    unique_together = ('service_id', 'container_port')

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=True)
    service_id = Column(String(32), comment="组件id", nullable=False)
    container_port = Column(Integer, comment="容器端口", nullable=False, default=0)
    mapping_port = Column(Integer, comment="映射端口", nullable=False, default=0)
    lb_mapping_port = Column(Integer, comment="负载均衡映射端口", nullable=False, default=0)
    protocol = Column(String(15), comment="组件协议", nullable=False, default='')
    port_alias = Column(String(64), comment="port别名", nullable=False, default='')
    is_inner_service = Column(Boolean, comment="是否内部组件；0:不绑定；1:绑定", nullable=False, default=False)
    is_outer_service = Column(Boolean, comment="是否外部组件；0:不绑定；1:绑定", nullable=False, default=False)
    k8s_service_name = Column(String(63), comment="the name of kubernetes service", nullable=False)


class TeamApplication(Base):
    """从应用模型安装的组件从属关系记录"""

    __tablename__ = 'tenant_service_group'
    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id")
    group_name = Column(String(64), comment="组件组名")
    group_alias = Column(String(64), comment="组件别名")
    group_key = Column(String(32), comment="组件组id")
    group_version = Column(String(32), comment="组件组版本")
    region_name = Column(String(64), comment="区域中心名称")
    service_group_id = Column(Integer, default=0, comment="安装时所属应用的主键ID")


class ComponentSourceInfo(Base):
    """服务源信息"""

    __tablename__ = "service_source"

    # todo
    # service = relationship("tenant_service", backref="service_id", uselist=False)
    service_id = Column(String(255), comment="服务信息")

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="服务所在环境ID")
    user_name = Column(String(255), nullable=True, comment="用户名")
    password = Column(String(255), nullable=True, comment="密码")
    group_key = Column(String(32), nullable=True, comment="group of service from market")
    version = Column(String(32), nullable=True, comment="version of service from market")
    service_share_uuid = Column(
        String(65), nullable=True, comment="unique identification of service from market")
    extend_info = Column(String(1024), nullable=True, default="", comment="扩展信息")
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")

    def is_install_from_cloud(self):
        if self.extend_info:
            extend_info = json.loads(self.extend_info)
            if extend_info and extend_info.get("install_from_cloud", False):
                return True
        return False

    def get_market_name(self):
        if self.extend_info:
            extend_info = json.loads(self.extend_info)
            return extend_info.get("market_name")

    def get_template_update_time(self):
        if self.extend_info:
            extend_info = json.loads(self.extend_info)
            update_time = extend_info.get("update_time", None)
            if update_time:
                return datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')


class ThirdPartyComponentEndpoints(Base):
    """第三方组件endpoints"""

    __tablename__ = 'third_party_service_endpoints'

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    service_cname = Column(String(128), comment="组件名", nullable=False)
    endpoints_info = Column(Text, comment="endpoints信息", nullable=False)
    endpoints_type = Column(String(32), comment="类型", nullable=False)


class DeployRelation(Base):
    __tablename__ = "deploy_relation"

    ID = Column(Integer, primary_key=True)
    # 应用服务id
    service_id = Column(String(32), comment="服务id", nullable=False, unique=True)
    key_type = Column(String(10), comment="密钥类型", nullable=False)
    secret_key = Column(String(200), comment="密钥", nullable=False)


class ComponentEvent(Base):
    __tablename__ = 'service_event'

    ID = Column(Integer, primary_key=True)
    event_id = Column(String(32), comment="操作id", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    user_name = Column(String(64), comment="操作用户", nullable=False)
    start_time = Column(DateTime(), default=datetime.now, comment="操作开始时间", nullable=False)
    end_time = Column(DateTime(), default=datetime.now, comment="操作结束时间", nullable=True)
    type = Column(String(20), comment="操作类型", nullable=False)
    status = Column(String(20), comment="操作处理状态 success failure", nullable=False)
    final_status = Column(String(20), default="", comment="操作状态，complete or timeout or null", nullable=False)
    message = Column(Text, comment="操作说明", nullable=False)
    deploy_version = Column(String(20), comment="部署版本", nullable=False)
    old_deploy_version = Column(String(20), comment="历史部署版本", nullable=False)
    code_version = Column(String(200), comment="部署代码版本", nullable=False)
    old_code_version = Column(String(200), comment="历史部署代码版本", nullable=False)
    region = Column(String(64), default="", comment="组件所属数据中心", nullable=False)


class ComponentGraph(Base):
    __tablename__ = "component_graphs"

    ID = Column(Integer, primary_key=True)
    component_id = Column(String(32), comment="the identity of the component")
    graph_id = Column(String(32), comment="the identity of the graph")
    title = Column(String(255), comment="the title of the graph")
    promql = Column(String(2047), comment="the title of the graph")
    sequence = Column(Integer, comment="the sequence number of the graph")


class TeamServiceBackup(Base):
    __tablename__ = "tenant_service_backup"

    ID = Column(Integer, primary_key=True)
    region_name = Column(String(64), comment="数据中心名称")
    tenant_env_id = Column(String(32))
    service_id = Column(String(32))
    backup_id = Column(String(32), unique=True)
    backup_data = Column(Text, comment="内容")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=False)
    update_time = Column(DateTime(), default=datetime.now, onupdate=datetime.now, comment="更新时间", nullable=False)


class ComponentLabels(Base):
    __tablename__ = "service_labels"
    ID = Column(Integer, primary_key=True)

    tenant_env_id = Column(String(32), comment="环境id")
    service_id = Column(String(32), comment="服务id")
    label_id = Column(String(32), comment="标签id")
    region = Column(String(30), comment="区域中心")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=False)


class ComponentProbe(Base):
    __tablename__ = 'service_probe'
    ID = Column(Integer, primary_key=True)

    service_id = Column(String(32), comment="组件id")
    probe_id = Column(String(32), comment="探针id")
    mode = Column(String(20), comment="不健康处理方式readiness（下线）或liveness（重启）或ignore（忽略）")
    scheme = Column(String(10), default="tcp", comment="探针使用协议,tcp,http,cmd")
    path = Column(String(200), default="", comment="路径")
    port = Column(Integer, default=80, comment="检测端口")
    cmd = Column(String(1024), default="", comment="cmd 命令")
    http_header = Column(String(300), nullable=True, default="", comment="http请求头，key=value,key2=value2")
    initial_delay_second = Column(Integer, default=4, comment="初始化等候时间")
    period_second = Column(Integer, default=3, comment="检测间隔时间")
    timeout_second = Column(Integer, default=5, comment="检测超时时间")
    failure_threshold = Column(Integer, default=3, comment="标志为失败的检测次数")
    success_threshold = Column(Integer, default=1, comment="标志为成功的检测次数")
    is_used = Column(Boolean, default=1, comment="是否启用")


class TeamComponentAuth(Base):
    __tablename__ = 'tenant_service_auth'
    ID = Column(Integer, primary_key=True)

    service_id = Column(String(32), comment="组件id")
    user = Column(String(64), nullable=True, comment="用户")
    password = Column(String(200), nullable=True, comment="密码")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=False)


class TeamComponentInfoDelete(Base):
    __tablename__ = 'tenant_service_delete'
    ID = Column(Integer, primary_key=True)

    service_id = Column(String(32), unique=True, comment="组件id")
    tenant_env_id = Column(String(32), comment="环境id")
    service_key = Column(String(32), comment="组件key")
    service_alias = Column(String(100), comment="组件别名")
    service_cname = Column(String(100), default='', comment="组件名")
    service_region = Column(String(64), comment="组件所属区")
    desc = Column(String(200), nullable=True, comment="描述")
    category = Column(String(15), comment="组件分类：application,cache,store")
    service_port = Column(Integer, comment="组件端口", default=8000)
    is_web_service = Column(Boolean, default=False, nullable=True, comment="是否web组件")
    version = Column(String(255), comment="版本")
    update_version = Column(Integer, default=1, comment="内部发布次数")
    image = Column(String(200), comment="镜像")
    cmd = Column(String(2048), nullable=True, comment="启动参数")
    setting = Column(String(200), nullable=True, comment="设置项")
    extend_method = Column(String(32), default='stateless', comment="伸缩方式")
    env = Column(String(200), nullable=True, comment="环境变量")
    min_node = Column(Integer, comment="启动个数", default=1)
    min_cpu = Column(Integer, comment="cpu个数", default=500)
    min_memory = Column(Integer, comment="内存大小单位（M）", default=256)
    container_gpu = Column(Integer, comment="gpu显存数量", default=0)
    inner_port = Column(Integer, comment="内部端口")
    volume_mount_path = Column(String(200), nullable=True, comment="mount目录")
    host_path = Column(String(300), nullable=True, comment="mount目录")
    deploy_version = Column(String(20), nullable=True, comment="部署版本")
    code_from = Column(String(20), nullable=True, comment="代码来源:gitlab,github")
    git_url = Column(String(200), nullable=True, comment="code代码仓库")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=True)
    git_project_id = Column(Integer, comment="gitlab 中项目id", default=0)
    is_code_upload = Column(Boolean, default=False, nullable=True, comment="是否上传代码")
    code_version = Column(String(100), nullable=True, comment="代码版本")
    service_type = Column(String(50), nullable=True, comment="组件类型:web,mysql,redis,mongodb,phpadmin")
    delete_time = Column(DateTime(), default=datetime.now, comment="删除时间", nullable=True)
    creater = Column(String(64), comment="组件创建者", default="admin")
    language = Column(String(40), nullable=True, comment="代码语言")
    protocol = Column(String(15), comment="服务协议：http,stream")
    total_memory = Column(Integer, comment="内存使用M", default=0)
    is_service = Column(Boolean, default=False, nullable=True, comment="是否inner组件")
    namespace = Column(String(100), default='', comment="镜像发布云帮的区间")
    volume_type = Column(String(64), default='shared', comment="共享类型shared、exclusive")
    port_type = Column(String(15), default='multi_outer', comment="端口类型，one_outer;dif_protocol;multi_outer")
    # 组件创建类型,cloud、assistant
    service_origin = Column(String(15), default='assistant', comment="组件创建类型cloud云市组件,assistant云帮组件")
    expired_time = Column(DateTime(), comment="过期时间", nullable=True)
    service_source = Column(String(15), default="source_code", nullable=True, comment="组件来源")
    create_status = Column(String(15), nullable=True, comment="组件创建状态 creating|complete")
    update_time = Column(DateTime(), default=datetime.now, onupdate=datetime.now, comment="更新时间", nullable=True)
    tenant_service_group_id = Column(Integer, default=0, comment="组件归属的组件组id")
    open_webhooks = Column(Boolean, default=False, comment='是否开启自动触发部署功能(兼容老版本组件)')
    check_uuid = Column(String(36), nullable=True, default="", comment="组件id")
    check_event_id = Column(String(32), nullable=True, default="", comment="组件检测事件ID")
    docker_cmd = Column(String(1024), nullable=True, comment="镜像创建命令")
    secret = Column(String(64), nullable=True, comment="webhooks验证密码")
    server_type = Column(String(5), default='git', comment="源码仓库类型")
    is_upgrate = Column(Boolean, default=False, comment='是否可以更新')
    build_upgrade = Column(Boolean, default=True, comment='组件构建后是否升级')
    service_name = Column(String(100), default='', comment="组件名称（新加属性，数据中心使用）")
    k8s_component_name = Column(String(100), nullable=False, comment="集群组件名称")


class ComponentExtendMethod(Base):
    __tablename__ = 'app_service_extend_method'

    ID = Column(Integer, primary_key=True)
    service_key = Column(String(32), comment="组件key", nullable=False)
    app_version = Column(String(64), comment="当前最新版本", nullable=False)
    min_node = Column(Integer, default=1, comment="最小节点", nullable=False)
    max_node = Column(Integer, default=20, comment="最大节点", nullable=False)
    step_node = Column(Integer, default=1, comment="节点步长", nullable=False)
    min_memory = Column(Integer, default=1, comment="最小内存", nullable=False)
    max_memory = Column(Integer, default=20, comment="最大内存", nullable=False)
    step_memory = Column(Integer, default=1, comment="内存步长", nullable=False)
    is_restart = Column(Boolean, default=False, comment="是否重启", nullable=False)
    container_cpu = Column(Integer, default=0, comment="容器CPU, 0表示不用限制", nullable=False)

    def to_dict(self):
        opts = self._meta
        data = {}
        for f in opts.concrete_fields:
            value = f.value_from_object(self)
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            data[f.name] = value
        return data


class TeamComponentConfigurationFile(Base):
    """组件配置文件"""

    __tablename__ = 'tenant_service_config'

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id", nullable=False)
    volume_id = Column(Integer, nullable=True, comment="存储id")
    volume_name = Column(String(32), nullable=True, comment="组件名称, 唯一标识")
    file_content = Column(LONGTEXT, nullable=False, comment="配置文件内容")


class TeamComponentEnv(Base):
    __tablename__ = 'tenant_service_env'

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id")
    language = Column(String(40), nullable=True, comment="代码语言")
    check_dependency = Column(String(100), nullable=True, comment="检测运行环境依赖")
    user_dependency = Column(String(1000), nullable=True, comment="用户自定义运行环境依赖")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=False)


class ComponentWebhooks(Base):
    """组件的自动部署属性"""

    __tablename__ = 'service_webhooks'

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id", nullable=False)
    state = Column(Boolean, default=False, comment="状态（开启，关闭）", nullable=False)
    webhooks_type = Column(String(128), comment="webhooks类型（image_webhooks, code_webhooks, api_webhooks）",
                           nullable=False)
    deploy_keyword = Column(String(128), default='deploy', comment="触发自动部署关键字", nullable=False)
    trigger = Column(String(256), default='', comment="触发正则表达式", nullable=False)


class ComponentRecycleBin(Base):
    __tablename__ = 'tenant_service_recycle_bin'
    # unique_together = ('tenant_env_id', 'service_alias')

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), unique=True, comment="服务id")
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_key = Column(String(32), comment="服务key", nullable=False)
    service_alias = Column(String(100), comment="服务别名", nullable=False)
    service_cname = Column(String(100), default='', comment="服务名", nullable=False)
    service_region = Column(String(64), comment="服务所属区", nullable=False)
    desc = Column(String(200), nullable=True, comment="描述")
    category = Column(String(15), comment="服务分类：application,cache,store", nullable=False)
    service_port = Column(Integer, comment="服务端口", default=0, nullable=False)
    is_web_service = Column(Boolean, default=False, comment="是否web服务", nullable=False)
    version = Column(String(20), comment="版本", nullable=False)
    update_version = Column(Integer, default=1, comment="内部发布次数", nullable=False)
    image = Column(String(200), comment="镜像", nullable=False)
    cmd = Column(String(2048), nullable=True, comment="启动参数")
    setting = Column(String(100), nullable=True, comment="设置项")
    extend_method = Column(String(15), default='stateless', comment="伸缩方式", nullable=False)
    env = Column(String(200), nullable=True, comment="环境变量")
    min_node = Column(Integer, comment="启动个数", default=1, nullable=False)
    min_cpu = Column(Integer, comment="cpu个数", default=500, nullable=False)
    min_memory = Column(Integer, comment="内存大小单位（M）", default=256, nullable=False)
    inner_port = Column(Integer, comment="内部端口", default=0, nullable=False)
    volume_mount_path = Column(String(200), nullable=True, comment="mount目录")
    host_path = Column(String(300), nullable=True, comment="mount目录")
    deploy_version = Column(String(20), nullable=True, comment="部署版本")
    code_from = Column(String(20), nullable=True, comment="代码来源:gitlab,github")
    git_url = Column(String(200), nullable=True, comment="code代码仓库")
    create_time = Column(DateTime(), default=datetime.now, comment="创建时间", nullable=False)
    git_project_id = Column(Integer, comment="gitlab 中项目id", default=0, nullable=False)
    is_code_upload = Column(Boolean, default=False, comment="是否上传代码", nullable=False)
    code_version = Column(String(100), nullable=True, comment="代码版本")
    service_type = Column(String(50), nullable=True, comment="服务类型:web,mysql,redis,mongodb,phpadmin")
    creater = Column(String(64), comment="服务创建者", default="admin", nullable=False)
    language = Column(String(40), nullable=True, comment="代码语言")
    protocol = Column(String(15), default='', comment="服务协议：http,stream", nullable=False)
    total_memory = Column(Integer, comment="内存使用M", default=0, nullable=False)
    is_service = Column(Boolean, default=False, comment="是否inner服务", nullable=False)
    namespace = Column(String(100), default='', comment="镜像发布云帮的区间", nullable=False)

    volume_type = Column(String(64), default='shared', comment="共享类型shared、exclusive", nullable=False)
    port_type = Column(String(15), nullable=False, default='multi_outer',
                       comment="端口类型，one_outer;dif_protocol;multi_outer")
    # 服务创建类型,cloud、assistant
    service_origin = Column(String(15), nullable=False, default='assistant', comment="服务创建类型cloud云市服务,assistant云帮服务")
    expired_time = Column(DateTime(), default=datetime.now, nullable=True, comment="过期时间")
    tenant_service_group_id = Column(Integer, default=0, comment="应用归属的服务组id", nullable=False)
    service_source = Column(
        String(15), default="", nullable=True, comment="应用来源(source_code, market, docker_run, docker_compose)")
    create_status = Column(String(15), nullable=True, comment="应用创建状态 creating|complete")
    update_time = Column(DateTime(), default=datetime.now, onupdate=datetime.now, comment="更新时间", nullable=False)
    check_uuid = Column(String(36), nullable=True, default="", comment="应用检测ID")
    check_event_id = Column(String(32), nullable=True, default="", comment="应用检测事件ID")
    docker_cmd = Column(String(1024), nullable=True, comment="镜像创建命令")


class ComponentRelationRecycleBin(Base):
    __tablename__ = 'tenant_service_relation_recycle_bin'
    # unique_together = ('service_id', 'dep_service_id')

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    service_id = Column(String(32), comment="服务id", nullable=False)
    dep_service_id = Column(String(32), comment="依赖服务id", nullable=False)
    dep_service_type = Column(String(50), nullable=True, comment="服务类型:web,mysql,redis,mongodb,phpadmin")
    dep_order = Column(Integer, comment="依赖顺序", nullable=False)
