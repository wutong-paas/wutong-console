import os
import sys
from typing import List
from loguru import logger
from pydantic import BaseSettings
import socket

logger.remove()


class Settings(BaseSettings):
    DEBUG = True
    ENV = os.environ.get("wutong_env", "DEV")
    APP_NAME = "wutong-console"
    API_PREFIX = "/paas-console/console"
    # 文件上传配置
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    HOME_DIR = os.getenv("HOME_DIR", BASE_DIR)
    DATA_DIR = os.path.join(HOME_DIR, 'data')
    DATA_DIR = os.getenv("DATA_DIR", DATA_DIR)
    MEDIA_URL = '/data/media/'
    MEDIA_ROOT = os.path.join(DATA_DIR, 'media')
    YAML_URL = '/data/file/'
    YAML_ROOT = os.path.join(DATA_DIR, 'file')

    # 团队API路由配置
    USER_AUTH_API_URL = os.environ.get("USER_AUTH_API_URL", "http://cube.wutong-dev.talkweb.com.cn/bone/cube-gateway")

    # 跨域白名单
    BACKEND_CORS_ORIGINS: List = ['*']

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
    REDIS_PASSWORD = os.environ.get("REDIS_PASS", "123456")
    REDIS_DATABASE = os.environ.get("REDIS_DATABASE", 5)

    REDIS_CACHE_TTL = 24 * 60 * 60

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "wutong-mysql.wt-system")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_USER = os.environ.get("MYSQL_USER", "admin")
    MYSQL_PASS = os.environ.get("MYSQL_PASS", "admin")

    SQLALCHEMY_DATABASE_URI: str = 'mysql://root:0O9zvQ00@192.168.36.74:64248/console'

    # 日志级别
    # CRITICAL = 50
    # FATAL = CRITICAL
    # ERROR = 40
    # WARNING = 30
    # WARN = WARNING
    # INFO = 20
    # DEBUG = 10
    # NOTSET = 0
    log_level = os.environ.get("LOG_LEVEL", 10)
    logger.add(sys.stdout, level=log_level)
    # logger.add("errlog/somefile.log", enqueue=True, level=logging.ERROR, retention="1 days")

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

    # nacos 配置
    ip_address = socket.gethostbyname(socket.gethostname())
    NACOS_HOST = os.environ.get("NACOS_HOST", "wtb1e507-8848.cube:8848")
    SERVER_NAMESPACE_ID = os.environ.get("SERVER_NAMESPACE_ID", "CUBE")
    SERVICE_NAME = "paas-console"
    SERVICE_IP = os.environ.get("SERVICE_IP", ip_address)
    SERVICE_PORT = os.environ.get("SERVICE_PORT", "8888")
    SERVICE_GROUP_NAME = os.environ.get("SERVICE_GROUP_NAME", "CUBE")

    source_code_type = {
        "github": "",
        "gitlab": "",
        "gitee": "",
        "aliyun": "",
        "dingtalk": "",
        "dbox": ""
    }

    class Config:
        case_sensitive = True


settings = Settings()
