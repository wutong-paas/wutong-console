from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer

from database.session import Base


class Labels(Base):
    __tablename__ = "labels"
    ID = Column(Integer, primary_key=True)
    label_id = Column(String(32), comment="标签id")
    label_name = Column(String(128), comment="标签名(汉语拼音)")
    label_alias = Column(String(15), comment="标签名(汉字)")
    category = Column(String(20), default="", comment="标签分类")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")

class NodeLabels(Base):
    __tablename__ = "node_labels"

    ID = Column(Integer, primary_key=True)
    region_id = Column(String(36), comment="数据中心 id")
    node_uuid = Column(String(36), comment="节点uuid")
    label_id = Column(String(32), comment="标签id")
    create_time = Column(DateTime(), nullable=False, default=datetime.now, comment="创建时间")
