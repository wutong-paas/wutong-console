import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from core.setting import settings

pymysql.install_as_MySQLdb()
DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI
# pool_size=10, max_overflow=2, pool_pre_ping=True,
engine = create_engine(DATABASE_URL, future=True, echo=True, poolclass=NullPool)

# sync_session = sessionmaker(engine, expire_on_commit=False, autoflush=False)
SessionClass = sessionmaker(bind=engine, autoflush=False)

Base = declarative_base()
