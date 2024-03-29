import os
import sys
from typing import List
from loguru import logger
from pydantic import BaseSettings
from core.auth.role_required import RoleRequired
import socket

logger.remove()


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

    INIT_AGENT_PLUGIN_ENV = os.getenv("JAVA_TOOL_OPTIONS",
                                      "-javaagent:/agent/agent.jar -Dotel.exporter.jaeger.endpoint=http://grafana-labs-traces-agent.wutong-obs:14250 -Dotel.traces.exporter=jaeger -Dotel.metrics.exporter=none -Dotel.resource.attributes=service.name=")

    EVENT_WEBSOCKET_URL = {
        'cloudbang': 'auto',
    }

    ORIGIN_REFERER_OFFICIAL_WEBSITE = os.getenv("official_website", "wutong.talkweb.com.cn")

    # 启动端口配置
    PORT = os.environ.get("PORT", 8888)

    # 是否热加载
    RELOAD = True

    SSO_LOGIN = True
    TENANT_VALID_TIME = 7

    MODULES = {
        "Owned_Fee": True,
        "Memory_Limit": True,
        "Finance_Center": True,
        "Team_Invite": True,
        "Monitor_Control": True,
        "User_Register": True,
        "Sms_Check": True,
        "Email_Invite": True,
        "Package_Show": True,
        "RegionToken": True,
        "Add_Port": False,
        "License_Center": True,
        "WeChat_Module": False,
        "Docker_Console": True,
        "Publish_YunShi": True,
        "Publish_Service": False,
        "Privite_Github": False,
        "SSO_LOGIN": SSO_LOGIN == "TRUE",
    }

    # nacos 配置
    ip_address = socket.gethostbyname(socket.gethostname())
    NACOS_HOST = os.environ.get("NACOS_HOST", "192.168.0.19:10848")
    SERVER_NAMESPACE_ID = os.environ.get("SERVER_NAMESPACE_ID", "TEST")
    SERVICE_NAME = "console"
    SERVICE_IP = ip_address
    SERVICE_PORT = "8888"
    SERVICE_GROUP_NAME = os.environ.get("SERVICE_GROUP_NAME", "IDAAS")

    class Config:
        case_sensitive = True


settings = Settings()
role_required = RoleRequired()
