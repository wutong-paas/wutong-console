from datetime import datetime
from sqlalchemy_utils import ChoiceType
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from database.session import Base

data_type = (
    ("组件端口", 'upstream_port'),
    ("组件下游依赖端口", "downstream_port"),
    ("无", "un_define"),
)
injection_method = (("自主发现", 'auto'), ("环境变量", "env"))
plugin_status = (
    ("启用", "active"),
    ("停用", "deactivate"),
)


class TeamPlugin(Base):
    """插件基础信息"""

    __tablename__ = "tenant_plugin"

    ID = Column(Integer, primary_key=True)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    region = Column(String(64), comment="数据中心", nullable=False)
    create_user = Column(Integer, nullable=False, comment="创建插件的用户id")
    desc = Column(String(256), comment="描述", nullable=False, default="")
    plugin_name = Column(String(32), comment="插件名称", nullable=False)
    plugin_alias = Column(String(32), comment="插件别名", nullable=False)
    category = Column(String(32), comment="插件类别", nullable=False)
    build_source = Column(String(12), comment="安装来源", nullable=False)
    image = Column(String(256), comment="镜像地址", nullable=True)
    code_repo = Column(String(256), comment="docker构建代码仓库地址", nullable=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    origin = Column(String(256), comment="插件来源", nullable=False, default="tenant")
    origin_share_id = Column(String(32), comment="分享的插件的id", nullable=False, default="new_create")
    username = Column(String(32), comment="镜像仓库或代码仓库用户名", nullable=True)
    password = Column(String(32), comment="镜像仓库或代码仓库秘密", nullable=True)


class PluginBuildVersion(Base):
    """插件构建版本"""

    __tablename__ = "plugin_build_version"

    ID = Column(Integer, primary_key=True)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    region = Column(String(64), comment="数据中心", nullable=False)
    user_id = Column(Integer, nullable=False, comment="构建此版本的用户id")
    update_info = Column(String(256), comment="插件更新说明", nullable=False)
    build_version = Column(String(32), comment="构建版本", nullable=False)
    build_status = Column(String(32), comment="构建状态", nullable=False)
    plugin_version_status = Column(String(32), comment="版本状态", nullable=False, default="unfixed")
    min_memory = Column(Integer, nullable=False, comment="构建内存大小")
    min_cpu = Column(Integer, nullable=False, comment="构建cpu大小")
    event_id = Column(String(32), comment="事件ID", nullable=True, default="")
    build_cmd = Column(String(128), comment="构建命令", nullable=True)
    image_tag = Column(String(100), comment="镜像版本", nullable=True, default="latest")
    code_version = Column(String(32), comment="代码版本", nullable=True, default="master")
    build_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class PluginConfigGroup(Base):
    """插件配置组"""

    __tablename__ = "plugin_config_group"

    ID = Column(Integer, primary_key=True)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    build_version = Column(String(32), comment="构建版本", nullable=False)
    config_name = Column(String(32), comment="配置名称", nullable=False)
    service_meta_type = Column(String(32), ChoiceType(data_type), comment="依赖数据类型", nullable=False)
    injection = Column(String(32), comment="注入方式", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class PluginConfigItems(Base):
    """插件配置组下的配置项"""

    __tablename__ = "plugin_config_items"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    build_version = Column(String(32), comment="构建版本", nullable=False)
    service_meta_type = Column(String(32), ChoiceType(data_type), comment="依赖数据类型", nullable=False)
    attr_name = Column(String(32), comment="属性名", nullable=False)
    attr_type = Column(String(32), comment="属性类型", nullable=False)
    attr_alt_value = Column(String(1024), comment="属性值", nullable=False)
    attr_default_value = Column(String(128), comment="默认值", nullable=True)
    is_change = Column(Boolean, comment="是否可改变", nullable=False, default=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    attr_info = Column(String(32), comment="配置项说明", nullable=True)
    protocol = Column(String(32), comment="协议", nullable=True, default="")


class TeamComponentPluginRelation(Base):
    """组件和插件关系"""

    __tablename__ = "tenant_service_plugin_relation"

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件ID", nullable=False)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    build_version = Column(String(32), comment="构建版本", nullable=False)
    service_meta_type = Column(String(32), ChoiceType(data_type), comment="依赖数据类型", nullable=False)
    plugin_status = Column(Boolean, comment="插件状态", nullable=False, default=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    min_memory = Column(Integer, nullable=False, comment="构建内存大小")
    min_cpu = Column(Integer, nullable=True, comment="构建cpu大小")


class ComponentPluginConfigVar(Base):
    """新版组件插件属性"""

    __tablename__ = "service_plugin_config_var"

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件ID", nullable=False)
    plugin_id = Column(String(32), comment="插件ID", nullable=False)
    build_version = Column(String(32), comment="构建版本", nullable=False)
    service_meta_type = Column(String(32), ChoiceType(data_type), comment="依赖数据类型", nullable=False)
    injection = Column(String(32), comment="注入方式", nullable=False)
    dest_service_id = Column(String(32), comment="组件ID", nullable=False, default='')
    dest_service_alias = Column(String(32), comment="组件别名", nullable=False, default="")
    container_port = Column(Integer, comment="依赖端口", nullable=False)
    attrs = Column(String(1024), comment="键值对", nullable=False, default="")
    protocol = Column(String(16), comment="端口协议", nullable=False, default="")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class TeamPluginShareInfo(Base):
    """分享插件"""

    __tablename__ = "tenant_plugin_share"

    ID = Column(Integer, primary_key=True)
    share_id = Column(String(32), comment="分享的插件ID", nullable=False)
    share_version = Column(String(32), comment="分享的构建版本", nullable=False)
    origin_plugin_id = Column(String(32), comment="插件原始的ID", nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    user_id = Column(Integer, comment="分享插件的用户id", nullable=False)
    desc = Column(String(256), comment="描述", nullable=False, default="")
    plugin_name = Column(String(32), comment="插件名称", nullable=False)
    plugin_alias = Column(String(32), comment="插件别名", nullable=False)
    category = Column(String(32), comment="插件类别", nullable=False)
    image = Column(String(256), comment="镜像地址", nullable=True)

    update_info = Column(String(256), comment="分享更新说明", nullable=False)

    min_memory = Column(Integer, comment="构建内存大小", nullable=False)
    min_cpu = Column(Integer, comment="构建cpu大小", nullable=False)
    build_cmd = Column(String(128), comment="构建命令", nullable=True)
    config = Column(String(4096), comment="插件配置项", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class PluginShareRecordEvent(Base):
    """插件分享订单关联发布事件"""

    __tablename__ = "plugin_share_record_event"

    ID = Column(Integer, primary_key=True)
    record_id = Column(Integer, comment="关联的记录ID", nullable=False)
    region_share_id = Column(String(36), comment="应用数据中心分享反馈ID", nullable=False)
    tenant_env_id = Column(String(32), comment="对应所在环境ID", nullable=False)
    env_name = Column(String(64), comment="应用所在环境唯一名称", nullable=False)
    plugin_id = Column(String(32), comment="对应插件ID", nullable=False)
    plugin_name = Column(String(64), comment="对应插件名称", nullable=False)
    event_id = Column(String(32), default="", comment="介质同步事件ID", nullable=False)
    event_status = Column(String(32), default="not_start", comment="事件状态", nullable=False)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
