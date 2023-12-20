from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from database.session import Base


class AlarmStrategy(Base):
    """告警策略"""

    __tablename__ = "alarm_strategy"

    ID = Column(Integer, primary_key=True)
    strategy_name = Column(String(32), comment="策略名", nullable=False)
    strategy_code = Column(String(32), comment="策略标识", nullable=False)
    monitor_type = Column(String(32), comment="监控类型", nullable=False)
    alarm_object = Column(String(255), comment="团队|环境|应用|组件", nullable=False)
    alarm_rules = Column(LONGTEXT, comment="告警规则", nullable=False)
    alarm_notice = Column(LONGTEXT, comment="告警通知", nullable=False)
    operator = Column(String(64), comment="创建人名", nullable=True)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    desc = Column(String(255), nullable=True, comment="策略描述")


class AlarmGroup(Base):
    """告警分组"""

    __tablename__ = "alarm_group"

    ID = Column(Integer, primary_key=True)
    group_name = Column(String(32), comment="分组名", nullable=False)
    team_name = Column(String(64), comment="团队名", nullable=True)
    operator = Column(String(64), comment="创建人", nullable=True)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
