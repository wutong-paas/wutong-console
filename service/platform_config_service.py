import json
import os
from datetime import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from core.enum.system_config import ConfigKeyEnum
from database.session import SessionClass
from exceptions.exceptions import ConfigExistError
from models.teams import ConsoleSysConfig
from repository.config.config_repo import sys_config_repo


class ConfigService(object):
    """
    ConfigService
    """

    def __init__(self):
        self.base_cfg_keys = None
        self.cfg_keys = None
        self.cfg_keys_value = None
        self.base_cfg_keys_value = None
        self.enterprise_id = ""

    def init_base_config_value(self, session):
        # no need
        pass

    def get_config_by_key(self, session, key):
        return session.execute(select(ConsoleSysConfig).where(
            ConsoleSysConfig.key == key,
            ConsoleSysConfig.enterprise_id == self.enterprise_id
        )).scalars().first()

    def get_config_by_key_and_enterprise_id(self, session, key, enterprise_id):
        """
        获取console系统配置
        :param key:
        :param enterprise_id:
        :return:
        """
        sql = select(ConsoleSysConfig).where(
            ConsoleSysConfig.key == key,
            ConsoleSysConfig.enterprise_id == enterprise_id
        )
        return session.execute(sql).scalars().first()

    def initialization_or_get_config(self, session: SessionClass):
        """
        initialization_or_get_config

        :return:
        """
        self.init_base_config_value(session)
        rst_datas = {}
        for key in self.base_cfg_keys:
            tar_key = sys_config_repo.get_config_by_key_and_enterprise_id(session, key, self.enterprise_id)
            if not tar_key:
                enable = self.base_cfg_keys_value[key]["enable"]
                value = self.base_cfg_keys_value[key]["value"]
                desc = self.base_cfg_keys_value[key]["desc"]
                config_type = "string"
                if isinstance(value, (dict, list)):
                    config_type = "json"
                if not value:
                    value = None
                rst_key = sys_config_repo.add_config(session=session, key=key, enterprise_id=self.enterprise_id,
                                                     default_value=value, config_type=config_type,
                                                     enable=enable, desc=desc)

                value = rst_key.value
                enable = rst_key.enable
                rst_data = {key.lower(): {"enable": enable, "value": value}}
                rst_datas.update(rst_data)
            else:
                if tar_key.type == "json":
                    rst_value = jsonable_encoder(tar_key.value)
                else:
                    rst_value = tar_key.value
                rst_data = {key.lower(): {"enable": tar_key.enable, "value": rst_value}}
                rst_datas.update(rst_data)
                rst_datas[key.lower()] = {"enable": tar_key.enable, "value": self.base_cfg_keys_value[key]["value"]}

        for key in self.cfg_keys:
            tar_key = self.get_config_by_key(session, key)
            if not tar_key:
                enable = self.cfg_keys_value[key]["enable"]
                value = self.cfg_keys_value[key]["value"]
                desc = self.cfg_keys_value[key]["desc"]
                config_type = "string"
                if isinstance(value, (dict, list)):
                    config_type = "json"
                rst_key = sys_config_repo.add_config(session=session, key=key, default_value=value,
                                                     config_type=config_type,
                                                     enable=enable,
                                                     desc=desc,
                                                     enterprise_id=self.enterprise_id)

                value = rst_key.value
                enable = rst_key.enable
                rst_data = {key.lower(): {"enable": enable, "value": value}}
                rst_datas.update(rst_data)
            else:
                if tar_key.type == "json":
                    rst_value = eval(tar_key.value)
                else:
                    rst_value = tar_key.value
                rst_data = {key.lower(): {"enable": tar_key.enable, "value": rst_value}}
                rst_datas.update(rst_data)

        # rst_datas["default_market_url"] = os.getenv("DEFAULT_APP_MARKET_URL", "https://store.goodrain.com")
        return rst_datas

    def update_config(self, session: SessionClass, key, value):
        update_result = self.update_config_by_key(session=session, key=key, data=value)
        return update_result

    def delete_config(self, session: SessionClass, key):
        delete_result = self.delete_config_by_key(session=session, key=key)
        return delete_result

    def update_config_by_key(self, session: SessionClass, key, data):
        enable = data["enable"]
        value = data["value"]
        if key in self.base_cfg_keys:
            update_result = self.update_config_enable_status(session=session, key=key, enable=enable)
            return update_result
        if enable:
            self.update_config_enable_status(session=session, key=key, enable=enable)
            config = self.update_config_value(session=session, key=key, value=value)
        else:
            config = self.update_config_enable_status(session=session, key=key, enable=enable)
        return config

    def update_config_enable_status(self, session: SessionClass, key, enable):
        """
        更新配置项

        :param key:
        :param enable:
        :return:
        """
        self.init_base_config_value(session)
        config = sys_config_repo.get_config_by_key_and_enterprise_id(session=session, key=key,
                                                                     enterprise_id=self.enterprise_id)
        if config.enable != enable:
            config.enable = enable
        if key in self.base_cfg_keys:
            return {key.lower(): {"enable": enable, "value": self.base_cfg_keys_value[key]["value"]}}
        return {
            key.lower(): {"enable": enable, "value": (eval(config.value) if config.type == "json" else config.value)}}

    def update_config_value(self, session: SessionClass, key, value):
        config = sys_config_repo.get_config_by_key_and_enterprise_id(session=session, key=key,
                                                                     enterprise_id=self.enterprise_id)
        config.value = json.dumps(value)
        if isinstance(value, (dict, list)):
            config_type = "json"
        else:
            config_type = "string"
        config.type = config_type
        # todo update database
        # config.save()
        return {key.lower(): {"enable": True, "value": config.value}}

    def delete_config_by_key(self, session: SessionClass, key):
        rst = sys_config_repo.get_config_by_key_and_enterprise_id(session=session, key=key,
                                                                  enterprise_id=self.enterprise_id)
        rst.enable = self.cfg_keys_value[key]["enable"]
        rst.value = self.cfg_keys_value[key]["value"]
        rst.desc = self.cfg_keys_value[key]["desc"]
        if isinstance(rst.value, (dict, list)):
            rst.type = "json"
        else:
            rst.type = "string"
        # rst.save()
        # todo update database
        return {key.lower(): {"enable": rst.enable, "value": rst.value}}


class PlatformConfigService(ConfigService):
    """
    PlatformConfigService
    """

    def __init__(self):
        super(PlatformConfigService, self).__init__()
        self.base_cfg_keys = ["IS_PUBLIC", "ENTERPRISE_CENTER_OAUTH", "VERSION"]

        self.cfg_keys = [
            "TITLE",
            "LOGO",
            "FAVICON",
            "IS_REGIST",
            "DOCUMENT",
            "OFFICIAL_DEMO",
            ConfigKeyEnum.ENTERPRISE_EDITION.name,
            "LOG_QUERY",
            "CALL_LINK_QUERY",
        ]
        self.cfg_keys_value = {
            "TITLE": {
                "value": "Rainbond",
                "desc": "Rainbond web tile",
                "enable": True
            },
            "LOGO": {
                "value": None,
                "desc": "Rainbond Logo url",
                "enable": True
            },
            "FAVICON": {
                "value": None,
                "desc": "Rainbond web favicon url",
                "enable": True
            },
            "DOCUMENT": {
                # {
                #                     "platform_url": "https://www.rainbond.com/",
                #                 },
                "value": None,
                "desc": "开启/关闭文档",
                "enable": False
            },
            "OFFICIAL_DEMO": {
                "value": None,
                "desc": "开启/关闭官方Demo",
                "enable": True
            },
            "IS_REGIST": {
                "value": None,
                "desc": "是否允许注册",
                "enable": True
            },
            ConfigKeyEnum.ENTERPRISE_EDITION.name: {
                "value": "false",
                "desc": "是否是企业版",
                "enable": True
            },
            "LOG_QUERY": {
                "value": None,
                "desc": "用于对采集到的日志进行筛选查询与分析",
                "enable": False
            },
            "CALL_LINK_QUERY": {
                "value": None,
                "desc": "用于对采集到的调用链路进行查询与分析",
                "enable": False
            },
        }

    def add_config_without_reload(self, session, key, default_value, type, desc=""):
        console_sys_config = session.execute(select(ConsoleSysConfig).where(
            ConsoleSysConfig.key == key
        )).scalars().first()
        if not console_sys_config:
            create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            config = ConsoleSysConfig(
                key=key, type=type, value=default_value, desc=desc, create_time=create_time, enterprise_id="")
            session.add(config)
            return config
        else:
            raise ConfigExistError("配置{}已存在".format(key))

    def init_base_config_value(self, session):
        self.base_cfg_keys_value = {
            "IS_PUBLIC": {
                "value": os.getenv('IS_PUBLIC', False),
                "desc": "是否是Cloud",
                "enable": True
            },
            "ENTERPRISE_CENTER_OAUTH": {
                # todo 移除相关功能
                "value": None,
                "desc": "enterprise center oauth 配置",
                "enable": True
            },
            "VERSION": {
                "value": os.getenv("RELEASE_DESC", "public-cloud"),
                "desc": "平台版本",
                "enable": True
            },
        }


platform_config_service = PlatformConfigService()
