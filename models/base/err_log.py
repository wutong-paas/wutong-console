from sqlalchemy import Column, String, Integer

from database.session import Base


class Errorlog(Base):
    """错误日志"""

    __tablename__ = "errlog"

    ID = Column(Integer, primary_key=True)
    msg = Column(String(2047), comment="error log of front end", nullable=True, default="")
    username = Column(String(255), comment="用户名", nullable=True, default="")
    address = Column(String(2047), comment="地址", nullable=True, default="")
