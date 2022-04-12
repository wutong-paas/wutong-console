from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime

from database.session import Base


class TeamRegionInfo(Base):
    """租户集群"""

    __tablename__ = 'tenant_region'
    unique_together = (('tenant_id', 'region_name'),)

    ID = Column(Integer, primary_key=True)
    tenant_id = Column(String(33), comment="租户id", nullable=False)
    region_name = Column(String(64), comment="集群ID", nullable=False)
    is_active = Column(Boolean, comment="是否已激活", nullable=False, default=True)
    is_init = Column(Boolean, comment="是否创建租户网络", nullable=False, default=False)
    service_status = Column(Integer, comment="组件状态", nullable=False, default=1)
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=False, default=datetime.now, comment="更新时间")
    region_tenant_name = Column(String(64), comment="数据中心租户名", nullable=True, default='')
    region_tenant_id = Column(String(32), comment="数据中心租户id", nullable=True, default='')
    region_scope = Column(String(32), comment="数据中心类型", nullable=True, default='')
    enterprise_id = Column(String(32), comment="企业id", nullable=True, default='')


class RegionApp(Base):
    """the dependencies between region app and console app"""

    __tablename__ = 'region_app'
    unique_together = ('region_name', 'region_app_id', 'app_id')

    ID = Column(Integer, primary_key=True)
    region_name = Column(String(64), comment="region name", nullable=False)
    region_app_id = Column(String(32), comment="region app id", nullable=False)
    app_id = Column(Integer, comment="app id", nullable=False)
