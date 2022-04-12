from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint

from database.session import Base


class EnterpriseUserPerm(Base):
    """用户在企业的权限"""

    __tablename__ = 'enterprise_user_perm'

    ID = Column(Integer, primary_key=True, comment="id")
    user_id = Column(Integer, comment="用户id", nullable=False)
    enterprise_id = Column(String(32), comment="企业id", nullable=False)
    identity = Column(String(15), comment="用户在企业的身份", nullable=False)
    token = Column(String(64), comment="API通信密钥", unique=True, nullable=False)


class TeamUserRole(Base):
    """用户在一个团队中的角色"""

    __tablename__ = 'tenant_user_role'

    ID = Column(Integer, autoincrement=0, primary_key=True, comment="id")
    role_name = Column(String(32), comment='角色名称')
    tenant_id = Column(Integer, nullable=False, comment='团队id')
    is_default = Column(Boolean(), default=False)

    __table_args__ = (
        UniqueConstraint('role_name', 'tenant_id'),
    )


class TeamComponentRelation(Base):
    __tablename__ = 'tenant_service_relation'
    # todo
    # unique_together = ('service_id', 'dep_service_id')
    ID = Column(Integer, primary_key=True, comment="id")
    tenant_id = Column(String(32), comment="租户id")
    service_id = Column(String(32), comment="组件id")
    dep_service_id = Column(String(32), comment="依赖组件id")
    dep_service_type = Column(String(50), nullable=True, comment="组件类型:web,mysql,redis,mongodb,phpadmin")
    dep_order = Column(Integer, comment="依赖顺序")
