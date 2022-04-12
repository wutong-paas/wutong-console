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


class UserOAuthServices(Base):
    __tablename__ = "user_oauth_service"

    ID = Column(Integer, primary_key=True)
    oauth_user_id = Column(String(64), nullable=True, comment="oauth_user_id")
    oauth_user_name = Column(String(64), nullable=True, comment="oauth_user_name")
    oauth_user_email = Column(String(64), nullable=True, comment="oauth_user_email")
    service_id = Column(Integer, nullable=True, comment="service_id")
    is_auto_login = Column(Boolean(), nullable=True, default=False, comment="is_auto_login")
    is_authenticated = Column(Boolean(), nullable=True, default=False, comment="is_authenticated")
    is_expired = Column(Boolean(), nullable=True, default=False, comment="is_expired")
    access_token = Column(String(2047), nullable=True, comment="access_token_url")
    refresh_token = Column(String(64), nullable=True, comment="refresh_token")
    user_id = Column(Integer, nullable=True, default=None, comment="user_id")
    code = Column(String(256), nullable=True, comment="user_id")
