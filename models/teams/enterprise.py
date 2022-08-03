from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text

from database.session import Base


class TeamEnterprise(Base):
    """企业管理"""

    __tablename__ = 'tenant_enterprise'

    ID = Column(Integer, primary_key=True)
    enterprise_id = Column(String(32), comment="企业id", nullable=False, unique=True)
    enterprise_name = Column(String(64), comment="企业名称", nullable=False)
    enterprise_alias = Column(String(64), comment="企业别名", nullable=True, default='')
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    enterprise_token = Column(String(256), comment="企业身份token", nullable=True, default='')
    is_active = Column(Integer, comment="是否在云市上激活", nullable=False, default=0)
    logo = Column(String(128), comment="企业logo", nullable=True, default='')


class TeamEnterpriseToken(Base):
    __tablename__ = 'tenant_enterprise_token'
    # unique_together = ('enterprise_id', 'access_target')

    ID = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, comment="企业id", nullable=False, default=0)
    access_target = Column(String(32), comment="要访问的目标组件名称", nullable=True, default='')
    access_url = Column(String(255), comment="需要访问的api地址", nullable=False)
    access_id = Column(String(32), comment="target分配给客户端的ID", nullable=False)
    access_token = Column(String(256), comment="客户端token", nullable=True, default='')
    crt = Column(Text, comment="客户端证书", nullable=True, default='')
    key = Column(Text, comment="客户端证书key", nullable=True, default='')
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

