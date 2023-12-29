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
    team_code = Column(String(32), comment="团队标识", nullable=False)
    env_code = Column(String(64), comment="环境标识", nullable=False)
    alarm_object = Column(LONGTEXT, comment="团队|环境|应用|组件", nullable=False)
    alarm_rules = Column(LONGTEXT, comment="告警规则", nullable=False)
    alarm_notice = Column(LONGTEXT, comment="告警通知", nullable=False)
    operator = Column(String(64), comment="创建人名", nullable=True)
    enable = Column(Boolean, comment="是否启用", nullable=False, default=True)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime(), nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    desc = Column(String(255), nullable=True, comment="策略描述")


class AlarmGroup(Base):
    """告警分组"""

    __tablename__ = "alarm_group"

    ID = Column(Integer, primary_key=True)
    group_name = Column(String(32), comment="分组名", nullable=True)
    group_code = Column(String(32), comment="分组标识", nullable=True)
    team_name = Column(String(64), comment="团队名", nullable=True)
    group_type = Column(String(32), comment="分组类型(plat/team)", nullable=False)
    contacts = Column(LONGTEXT, comment="联系人", nullable=True)
    team_code = Column(String(32), comment="团队标识", nullable=True)
    operator = Column(String(64), comment="创建人", nullable=False)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")


class AlarmRobot(Base):
    """告警机器人"""

    __tablename__ = "alarm_robot"

    ID = Column(Integer, primary_key=True)
    robot_name = Column(String(32), comment="机器人名称", nullable=False)
    robot_code = Column(String(32), comment="机器人标识", nullable=False)
    webhook_addr = Column(String(255), comment="webhook地址", nullable=False)
    team_code = Column(String(32), comment="团队标识", nullable=True)
    operator = Column(String(64), comment="创建人", nullable=False)
    create_time = Column(DateTime(), nullable=True, default=datetime.now, comment="创建时间")


class AlarmRegionRelation(Base):
    """分组及机器人uuid与集群关联"""

    __tablename__ = "alarm_region_relation"

    ID = Column(Integer, primary_key=True)
    alarm_type = Column(String(32), comment="告警类型(email/robot)", nullable=False)
    group_id = Column(Integer, comment="机器人名称", nullable=False)
    code = Column(String(64), comment="分组或机器人code", nullable=True)
    region_code = Column(String(33), comment="集群标识", nullable=False)
