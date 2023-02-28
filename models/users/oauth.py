from sqlalchemy import String, Column, Boolean, Integer

from database.session import Base


class OAuthServices(Base):
    __tablename__ = "oauth_service"

    ID = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True, comment="oauth服务名称")
    client_id = Column(String(64), nullable=False, comment="client_id")
    client_secret = Column(String(64), nullable=False, comment="client_secret")
    redirect_uri = Column(String(255), nullable=False, comment="redirect_uri")
    home_url = Column(String(255), nullable=True, comment="auth_url")
    auth_url = Column(String(255), nullable=True, comment="auth_url")
    access_token_url = Column(String(255), nullable=True, comment="access_token_url")
    api_url = Column(String(255), nullable=True, comment="api_url")
    oauth_type = Column(String(16), nullable=True, comment="oauth_type")
    eid = Column(String(64), nullable=True, comment="user_id")
    enable = Column(Boolean(), nullable=True, default=True, comment="user_id")
    is_deleted = Column(Boolean(), nullable=True, default=False, comment="is_deleted")
    is_console = Column(Boolean(), nullable=True, default=False, comment="is_console")
    is_auto_login = Column(Boolean(), nullable=True, default=False, comment="is_auto_login")
    is_git = Column(Boolean(), nullable=True, default=True, comment="是否为git仓库")
