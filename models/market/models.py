from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from database.session import Base


class CenterApp(Base):
    """云市应用包(组)"""

    __tablename__ = "center_app"

    ID = Column(Integer, primary_key=True)
    app_id = Column(String(32), comment="应用包", nullable=False)
    app_name = Column(String(64), comment="应用包名", nullable=False)
    create_user = Column(Integer, comment="创建人id", nullable=True)
    create_user_name = Column(String(64), comment="创建人名", nullable=True)
    create_team = Column(String(64), nullable=True, comment="应用所属团队,可以和创建人id不统一")
    pic = Column(String(200), nullable=True, comment="应用头像信息")
    source = Column(String(15), default="", nullable=True, comment="应用来源(本地创建、云商店)")
    dev_status = Column(String(32), default="", nullable=True, comment="开发状态")
    # choices=app_scope,
    scope = Column(String(50), comment="可用范围", nullable=False)
    store_id = Column(String(64), comment="市场店铺ID", nullable=True)
    #
    describe = Column(String(400), nullable=True, comment="云市应用描述信息")
    is_ingerit = Column(Boolean(), default=True, comment="是否可被继承", nullable=False)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    install_number = Column(Integer, default=0, comment='安装次数', nullable=False)
    is_official = Column(Boolean, default=False, comment='是否官方认证', nullable=False)
    details = Column(Text, nullable=True, comment="应用详情")


class CenterAppVersion(Base):
    """云市应用版本"""
    # todo 改表名
    __tablename__ = "center_app_version"

    ID = Column(Integer, primary_key=True)
    app_id = Column(String(32), comment="应用id", nullable=False)
    version = Column(String(32), comment="版本", nullable=False)
    version_alias = Column(String(64), default="NA", comment="别名", nullable=False)
    app_version_info = Column(String(255), comment="版本信息", nullable=False)
    record_id = Column(Integer, comment="分享流程id，控制一个分享流程产出一个实体", nullable=False)
    share_user = Column(Integer, nullable=True, comment="分享人id")
    share_env = Column(String(64), comment="来源应用所属环境", nullable=False)
    group_id = Column(Integer, default=0, comment="应用归属的服务组id", nullable=False)
    dev_status = Column(String(32), default="", nullable=True, comment="开发状态")
    source = Column(String(15), default="", nullable=True, comment="应用来源(本地创建、云商店)")
    scope = Column(String(15), default="", nullable=True, comment="应用分享范围")
    app_template = Column(LONGTEXT, comment="全量应用与插件配置信息", nullable=False)
    template_version = Column(String(10), default="v2", comment="模板版本", nullable=False)
    create_time = Column(DateTime(), default=datetime.now, nullable=True, comment="创建时间")
    update_time = Column(DateTime(), default=datetime.now, onupdate=datetime.now, nullable=True, comment="更新时间")
    upgrade_time = Column(String(30), default="", comment="升级时间", nullable=False)
    install_number = Column(Integer, default=0, comment='安装次数', nullable=False)
    is_official = Column(Boolean(), default=False, comment='是否官方认证', nullable=False)
    is_ingerit = Column(Boolean(), default=True, comment="是否可被继承", nullable=False)
    is_complete = Column(Boolean(), default=False, comment="代码或镜像是否同步完成", nullable=False)
    template_type = Column(String(32), nullable=True, default=None, comment="模板类型（ram、oam）")
    release_user_id = Column(String(32), nullable=True, default=None, comment="版本release操作人id")
    # region_name is not null,This means that the version can only be installed on that cluster.
    region_name = Column(String(64), nullable=True, default=None, comment="数据中心名称")


class CenterAppTagsRelation(Base):
    """云市应用标签关系"""
    # todo 改表名
    __tablename__ = "center_app_tag_relation"

    ID = Column(Integer, primary_key=True, comment="主键")
    app_id = Column(String(32), comment="当前应用", nullable=False)
    tag_id = Column(Integer, comment="标签id", nullable=False)


class CenterAppTag(Base):
    """云市应用标签"""
    # todo 改表名
    __tablename__ = "center_app_tag"

    ID = Column(Integer, primary_key=True, comment="主键")
    name = Column(String(32), unique=True, comment="标签名称", nullable=False)
    is_deleted = Column(Boolean(), default=False, comment="是否删除", nullable=False)


class AppImportRecord(Base):
    __tablename__ = 'app_import_record'

    ID = Column(Integer, primary_key=True, comment="主键")
    event_id = Column(String(32), nullable=True, comment="事件id")
    status = Column(String(15), nullable=True, comment="导入状态")
    scope = Column(String(10), nullable=True, default="", comment="导入范围")
    format = Column(String(15), nullable=True, default="", comment="类型")
    source_dir = Column(String(256), nullable=True, default="", comment="目录地址")
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    team_name = Column(String(64), nullable=True, comment="正在导入的团队名称")
    region = Column(String(64), nullable=True, comment="数据中心")
    user_name = Column(String(64), nullable=True, comment="操作人")
