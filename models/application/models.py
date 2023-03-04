from datetime import datetime
from enum import Enum

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from core.enum.app import GovernanceModeEnum, ApplicationUpgradeStatus, ApplicationUpgradeRecordType
from database.session import Base


class Application(Base):
    """组件分组（应用）"""

    __tablename__ = 'service_group'

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    project_id = Column(String(32), comment="项目id", nullable=True)
    tenant_name = Column(String(32), comment="团队名", nullable=False)
    env_name = Column(String(32), comment="环境名", nullable=False)
    project_name = Column(String(32), comment="项目名", nullable=True)
    group_name = Column(String(128), comment="组名", nullable=False)
    region_name = Column(String(64), comment="区域中心名称", nullable=False)
    is_default = Column(Boolean, default=False, comment='默认组件', nullable=False)
    order_index = Column(Integer, default=0, comment="应用排序", nullable=False)
    note = Column(String(2048), comment="备注", nullable=True)
    username = Column(String(255), comment="the username of principal", nullable=True)
    governance_mode = Column(
        String(255),
        comment="governance mode",
        nullable=True,
        default=GovernanceModeEnum.BUILD_IN_SERVICE_MESH.name)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    app_type = Column(String(255), comment="应用类型", nullable=False, default="wutong")
    app_store_name = Column(String(255), comment="应用商店名称", nullable=True)
    app_store_url = Column(String(255), comment="应用商店 URL", nullable=True)
    app_template_name = Column(String(255), comment="应用模板名称", nullable=True)
    version = Column(String(255), comment="Helm 应用版本", nullable=True)
    logo = Column(String(255), comment="应用logo", nullable=True)
    k8s_app = Column(String(64), comment="集群内应用名称", nullable=False, default='')

    @property
    def app_id(self):
        return self.ID

    @property
    def app_name(self):
        return self.group_name


class ComponentApplicationRelation(Base):
    """组件与分组关系"""

    __tablename__ = 'service_group_relation'

    ID = Column(Integer, primary_key=True)
    service_id = Column(String(32), comment="组件id", nullable=False)
    group_id = Column(Integer, nullable=False)
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    region_name = Column(String(64), comment="区域中心名称", nullable=False)


class ApplicationConfigGroup(Base):
    """应用配置组"""

    __tablename__ = "app_config_group"
    # todo
    unique_together = ('region_name', 'app_id', 'config_group_name')

    ID = Column(Integer, primary_key=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    app_id = Column(Integer, comment='应用id', nullable=False)
    config_group_name = Column(String(64), comment="配置组名", nullable=False)
    deploy_type = Column(String(32), comment="部署类型", nullable=False)
    enable = Column(Boolean, comment='有效状态', nullable=False)
    region_name = Column(String(64), comment="地区名称", nullable=False)
    config_group_id = Column(String(32), comment="配置组id", nullable=False)


class ConfigGroupItem(Base):
    __tablename__ = "app_config_group_item"

    ID = Column(Integer, primary_key=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    app_id = Column(Integer, comment='应用id', nullable=False)
    config_group_name = Column(String(64), comment="配置组名", nullable=False)
    item_key = Column(String(1024), comment="配置项目密钥", nullable=False)
    item_value = Column(Text, comment="配置项目值", nullable=False)
    config_group_id = Column(String(32), comment="配置组id", nullable=False)


class ConfigGroupService(Base):
    __tablename__ = "app_config_group_service"

    ID = Column(Integer, primary_key=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    app_id = Column(Integer, comment='应用id', nullable=False)
    config_group_name = Column(String(64), comment="配置组名", nullable=False)
    service_id = Column(String(32), comment="组件id", nullable=False)
    config_group_id = Column(String(32), comment="配置组id", nullable=False)


class ServiceShareRecord(Base):
    """应用发布记录"""

    __tablename__ = "service_share_record"

    ID = Column(Integer, primary_key=True)
    group_share_id = Column(String(32), comment="发布应用组或插件的唯一Key", nullable=False, unique=True)
    group_id = Column(String(32), comment="分享应用组id或者单独插件ID", nullable=False)
    team_name = Column(String(64), comment="应用所在团队唯一名称", nullable=False)
    event_id = Column(String(32), comment="介质同步事件ID,弃用，使用表service_share_record_event", nullable=True)
    share_version = Column(String(15), comment="应用组发布版本", nullable=True)
    share_version_alias = Column(String(64), comment="应用组发布版本别名", nullable=True)
    share_app_version_info = Column(String(255), comment="应用组发布版本描述", default="", nullable=False)
    is_success = Column(Boolean, comment="发布是否成功", nullable=False)
    step = Column(Integer, comment="当前发布进度", nullable=False, default=0)
    # 0 发布中 1 发布完成 2 取消发布 3 已删除
    status = Column(Integer, comment="当前发布状态 0, 1, 2, 3", nullable=False, default=0)
    app_id = Column(String(64), comment="应用id", nullable=True)
    scope = Column(String(64), comment="分享范围", nullable=True)
    share_app_market_name = Column(String(64), comment="分享应用商店标识", nullable=True)
    share_store_name = Column(String(64), comment="分享应用商店名称，用于记录发布范围指定的应用商店名", nullable=True)
    share_app_model_name = Column(String(64), comment="分享应用模板名称", nullable=True)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __unicode__(self):
        return self.to_dict()


class ServiceShareRecordEvent(Base):
    """应用发布订单关联发布事件"""

    __tablename__ = "service_share_record_event"

    ID = Column(Integer, primary_key=True)
    record_id = Column(Integer, comment="关联的订单ID", nullable=False)
    region_share_id = Column(String(36), comment="应用数据中心分享反馈ID", nullable=False)
    team_name = Column(String(64), comment="应用所在团队唯一名称", nullable=False)
    service_key = Column(String(32), comment="对应应用key", nullable=False)
    service_id = Column(String(32), comment="对应应用ID", nullable=False)
    service_alias = Column(String(64), comment="对应应用别名", nullable=False)
    service_name = Column(String(64), comment="对应应用名称", nullable=False)
    tenant_env_id = Column(String(32), comment="对应所在环境ID", nullable=False)
    event_id = Column(String(32), comment="介质同步事件ID", nullable=False, default="")
    event_status = Column(String(32), comment="事件状态", nullable=False, default="not_start")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __unicode__(self):
        return self.to_dict()


class GroupAppBackupRecord(Base):
    """应用组备份"""

    __tablename__ = 'groupapp_backup'

    ID = Column(Integer, primary_key=True)
    group_id = Column(Integer, comment="组ID", nullable=False)
    event_id = Column(String(32), comment="事件id", nullable=True)
    group_uuid = Column(String(32), comment="group UUID", nullable=True)
    version = Column(String(32), comment="备份版本", nullable=True)
    backup_id = Column(String(36), comment="备份ID", nullable=True)
    tenant_env_id = Column(String(32), comment="环境ID", nullable=True)
    user = Column(String(64), comment="备份人", nullable=True)
    region = Column(String(64), comment="数据中心", nullable=True)
    status = Column(String(15), comment="时间请求状态", nullable=True)
    note = Column(String(255), comment="备份说明", nullable=True, default="")
    mode = Column(String(15), comment="备份类型", nullable=True, default="")
    source_dir = Column(String(256), comment="目录地址", nullable=True, default="")
    backup_size = Column(Integer, comment="备份文件大小", nullable=False)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    total_memory = Column(Integer, comment="备份应用的总内存", nullable=False)
    backup_server_info = Column(String(400), comment="备份服务信息", nullable=True, default="")
    source_type = Column(String(32), comment="源类型", nullable=True)


class GroupAppMigrateRecord(Base):
    """备份导出恢复"""

    __tablename__ = 'groupapp_migrate'

    ID = Column(Integer, primary_key=True)
    group_id = Column(Integer, comment="组ID", nullable=False)
    event_id = Column(String(32), comment="事件id", nullable=True)
    group_uuid = Column(String(32), comment="group UUID", nullable=True)
    version = Column(String(32), comment="迁移的版本", nullable=True)
    backup_id = Column(String(36), comment="备份ID", nullable=True)
    migrate_team = Column(String(32), comment="迁移的团队名称", nullable=True)
    user = Column(String(64), comment="恢复人", nullable=True)
    migrate_region = Column(String(64), comment="迁移的数据中心", nullable=True)
    status = Column(String(15), comment="时间请求状态", nullable=True)
    migrate_type = Column(String(15), comment="类型", nullable=False, default="migrate")
    restore_id = Column(String(36), comment="恢复ID", nullable=True)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    original_group_id = Column(Integer, comment="原始组ID", nullable=False)
    original_group_uuid = Column(String(32), comment="原始group UUID", nullable=True)


class GroupAppBackupImportRecord(Base):
    """备份导入"""

    __tablename__ = 'groupapp_backup_import'

    ID = Column(Integer, primary_key=True)
    event_id = Column(String(32), comment="事件id", nullable=True)
    status = Column(String(15), comment="时间请求状态", nullable=True)
    file_temp_dir = Column(String(256), comment="目录地址", nullable=True, default="")
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    team_name = Column(String(64), comment="正在导入的团队名称", nullable=True)
    region = Column(String(64), comment="数据中心", nullable=True)


class ApplicationUpgradeRecord(Base):
    """云市应用升级记录"""

    __tablename__ = "app_upgrade_record"

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(33), comment="环境id", nullable=False)
    group_id = Column(Integer, comment="应用组id", nullable=False)
    group_key = Column(String(32), comment="应用包", nullable=False)
    group_name = Column(String(64), comment="应用包名", nullable=False)
    version = Column(String(20), comment="版本号", nullable=False, default='')
    old_version = Column(String(20), comment="旧版本号", nullable=False, default='')
    status = Column(Integer, comment="升级状态", nullable=False, default=ApplicationUpgradeStatus.NOT.value)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    market_name = Column(String(64), comment="商店标识", nullable=True)
    is_from_cloud = Column(Boolean, comment="应用来源", nullable=False, default=False)
    upgrade_group_id = Column(Integer, comment="升级组件组id", nullable=False, default=0)
    snapshot_id = Column(String(32), comment="快照id", nullable=True)
    record_type = Column(String(64), comment="记录类型, 升级/回滚", nullable=True)
    parent_id = Column(Integer, comment="回滚记录对应的升级记录ID", nullable=False, default=0)

    service_upgrade_records = relationship("ServiceUpgradeRecord", back_populates="app_upgrade_record")

    def to_dict(self):
        record = jsonable_encoder(super(ApplicationUpgradeRecord, self))
        record["can_rollback"] = self.can_rollback()
        record["is_finished"] = self.is_finished()
        return record

    def is_finished(self):
        return self.status not in [ApplicationUpgradeStatus.NOT.value, ApplicationUpgradeStatus.UPGRADING.value,
                                   ApplicationUpgradeStatus.ROLLING.value]

    def can_rollback(self):
        if self.record_type != ApplicationUpgradeRecordType.UPGRADE.value:
            return False
        statuses = [
            ApplicationUpgradeStatus.UPGRADED.value,
            ApplicationUpgradeStatus.ROLLBACK.value,
            ApplicationUpgradeStatus.PARTIAL_UPGRADED.value,
            ApplicationUpgradeStatus.PARTIAL_ROLLBACK.value,
            ApplicationUpgradeStatus.PARTIAL_ROLLBACK.value,
            ApplicationUpgradeStatus.DEPLOY_FAILED.value,
        ]
        return self.status in statuses

    def can_upgrade(self):
        return self.status == ApplicationUpgradeStatus.NOT.value

    def can_deploy(self):
        if not self.is_finished():
            return False
        statuses = [
            ApplicationUpgradeStatus.UPGRADE_FAILED.value, ApplicationUpgradeStatus.ROLLBACK_FAILED.value,
            ApplicationUpgradeStatus.PARTIAL_UPGRADED.value,
            ApplicationUpgradeStatus.PARTIAL_ROLLBACK.value, ApplicationUpgradeStatus.DEPLOY_FAILED.value
        ]
        return True if self.status in statuses else False


class ApplicationUpgradeSnapshot(Base):
    """云市应用升级快照"""

    __tablename__ = "app_upgrade_snapshots"

    ID = Column(Integer, primary_key=True)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    tenant_env_id = Column(String(32), comment="环境id", nullable=False)
    upgrade_group_id = Column(Integer, comment="升级组件组id", nullable=False, default=0)
    snapshot_id = Column(String(32), comment="快照id", nullable=False)
    snapshot = Column(LONGTEXT, comment="快照", nullable=False)


class ComposeGroup(Base):
    """compose组"""

    __tablename__ = "compose_group"

    ID = Column(Integer, primary_key=True)
    group_id = Column(Integer, comment="compose组关联的组id")
    team_id = Column(String(32), comment="团队 id")
    region = Column(String(64), comment="服务所属数据中心")
    compose_content = Column(Text, nullable=False, comment="compose文件内容")
    compose_id = Column(String(32), unique=True, comment="compose id")
    create_status = Column(String(15), nullable=True, comment="compose组创建状态 creating|checking|checked|complete")
    check_uuid = Column(String(36), nullable=True, default="", comment="compose检测ID")
    check_event_id = Column(String(32), nullable=True, default="", comment="compose检测事件ID")
    hub_user = Column(String(256), nullable=True, default="", comment="镜像仓库用户名称")
    hub_pass = Column(String(256), nullable=True, default="", comment="镜像仓库用户密码，服务创建后给服务赋值")

    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")


class ComposeServiceRelation(Base):
    """compose组和服务的关系"""

    __tablename__ = "compose_service_relation"

    ID = Column(Integer, primary_key=True)
    tenant_env_id = Column(String(32), comment="环境id")
    service_id = Column(String(32), comment="服务 id")
    compose_id = Column(String(32), comment="compose id")
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")


class ServiceUpgradeRecord(Base):
    """云市服务升级记录"""

    __tablename__ = "service_upgrade_record"

    class UpgradeType(Enum):
        UPGRADE = 'upgrade'
        ADD = 'add'

    app_upgrade_record_id = Column(
        Integer, ForeignKey('app_upgrade_record.ID')
    )

    service_id = Column(
        String(32), ForeignKey('tenant_service.service_id')
    )

    app_upgrade_record = relationship("ApplicationUpgradeRecord", back_populates="service_upgrade_records")
    service = relationship("TeamComponentInfo")

    ID = Column(Integer, primary_key=True)
    service_cname = Column(String(100), comment="服务名", nullable=False)
    upgrade_type = Column(String(20), default=UpgradeType.UPGRADE.value, comment="升级类型", nullable=False)
    event_id = Column(String(32), nullable=True)
    update = Column(Text, comment="升级信息", nullable=False)
    status = Column(Integer, default=ApplicationUpgradeStatus.NOT.value, comment="升级状态", nullable=False)
    update_time = Column(DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")

    def is_finished(self):
        return self.status not in [ApplicationUpgradeStatus.NOT.value, ApplicationUpgradeStatus.UPGRADING.value,
                                   ApplicationUpgradeStatus.ROLLING.value]


class ApplicationExportRecord(Base):
    """应用导出"""

    __tablename__ = 'app_export_record'

    ID = Column(Integer, primary_key=True)
    group_key = Column(String(32), comment="导出应用的key", nullable=False)
    version = Column(String(20), comment="导出应用的版本", nullable=False)
    format = Column(String(15), comment="导出应用的格式", nullable=False)
    event_id = Column(String(32), nullable=True, comment="事件id")
    status = Column(String(10), nullable=True, comment="事件请求状态")
    file_path = Column(String(256), nullable=True, comment="文件地址")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    region_name = Column(String(32), nullable=True, comment="执行导出的集群ID")
    is_export_image = Column(Boolean, nullable=True, comment="是否导出镜像", default=False)
