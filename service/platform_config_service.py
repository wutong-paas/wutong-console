from core.enum.system_config import ConfigKeyEnum


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


platform_config_service = PlatformConfigService()
