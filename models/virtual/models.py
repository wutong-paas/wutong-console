from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from database.session import Base


class VirtualImageInfo(Base):
    """虚拟机镜像表"""

    __tablename__ = 'virtual_image_info'

    ID = Column(Integer, primary_key=True, comment="id")
    image_name = Column(String(32), nullable=False, unique=True, comment="镜像名称")
    os_name = Column(String(32), nullable=False, comment="操作系统")
    image_address = Column(String(255), nullable=False, comment="镜像地址")
    image_type = Column(String(32), nullable=False, comment="镜像类型")
    version = Column(String(32), nullable=False, comment="版本")
    desc = Column(String(255), nullable=True, comment="描述")
    operator = Column(String(64), nullable=True, comment="操作人")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")


class VirtualOsInfo(Base):
    """虚拟机操作系统表"""

    __tablename__ = 'virtual_os_info'

    ID = Column(Integer, primary_key=True, comment="id")
    os_name = Column(String(32), nullable=False, unique=True, comment="操作系统名称")
    operator = Column(String(64), nullable=True, comment="操作人")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
