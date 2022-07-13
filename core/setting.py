import os
from typing import List

from pydantic import BaseSettings

from core.auth.role_required import RoleRequired


class Settings(BaseSettings):
    ENV = os.environ.get("wutong_env", "DEV")
    APP_NAME = "wutong-console"
    API_PREFIX = "/console"
    # 文件上传配置
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    HOME_DIR = os.getenv("HOME_DIR", BASE_DIR)
    DATA_DIR = os.path.join(HOME_DIR, 'data')
    DATA_DIR = os.getenv("DATA_DIR", DATA_DIR)
    MEDIA_URL = '/data/media/'
    MEDIA_ROOT = os.path.join(DATA_DIR, 'media')

    # 跨域白名单
    BACKEND_CORS_ORIGINS: List = ['*']

    # REDIS_STREAM_HOST = os.environ.get("REDIS_HOST", "localhost")
    # REDIS_STREAM_PORT = os.environ.get("REDIS_PORT", 6379)
    # REDIS_STREAM_PASSWORD = os.environ.get("REDIS_PASS", "123456")
    # REDIS_STREAM_DATABASE = os.environ.get("REDIS_DATABASE", 9)
    # REDIS_STREAM_NAME = os.environ.get("REDIS_STREAM_NAME", "wutong-report-stream")
    # REDIS_STREAM_CONSUMER_NAME = os.environ.get("REDIS_STREAM_CONSUMER_NAME", "wutong-report-consumer")
    # REDIS_STREAM_GROUP_NAME = os.environ.get("REDIS_STREAM_GROUP_NAME", "wutong-report-group")

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
    REDIS_PASSWORD = os.environ.get("REDIS_PASS", "123456")
    REDIS_DATABASE = os.environ.get("REDIS_DATABASE", 5)

    REDIS_CACHE_TTL = 24 * 60 * 60

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "wutong-mysql.wt-system")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_USER = os.environ.get("MYSQL_USER", "admin")
    MYSQL_PASS = os.environ.get("MYSQL_PASS", "admin")

    SQLALCHEMY_DATABASE_URI: str = 'mysql://' + MYSQL_USER + ':' + MYSQL_PASS + '@' + MYSQL_HOST + ':' + MYSQL_PORT + '/console'

    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    IMAGE_REPO = os.getenv("IMAGE_REPO", "goodrain.me")

    SECRET_KEY = "hd_279hu4@3^bq&8w5hm_l$+xrip$_r8vh5t%ru(q8#!rauoj1"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_DAY = 15

    EVENT_WEBSOCKET_URL = {
        'cloudbang': 'auto',
    }

    # 启动端口配置
    PORT = os.environ.get("PORT", 8888)

    # 是否热加载
    RELOAD = True

    SSO_LOGIN = True
    TENANT_VALID_TIME = 7

    class Config:
        case_sensitive = True


settings = Settings()
role_required = RoleRequired()
