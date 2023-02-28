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
