# -*- coding: utf8 -*-
import json
import logging

from sqlalchemy import select
from core.setting import settings
from models.teams import ConsoleSysConfig

logger = logging.getLogger('default')


class MemcachedCli(object):
    def __init__(self):
        pass

    def getKey(self, key):
        pass

    def setKey(self, key, value):
        pass


mcli = MemcachedCli()
configKey = "SYS_C_F_K"


class ConfigCenter(object):

    def __init__(self):
        self.session = None

    def __getattr__(self, name):
        configs = self.configs(self.session)
        if name in configs:
            return configs[name]
        else:
            if hasattr(settings, name):
                return getattr(settings, name)
            else:
                return None

    def configs(self, session):
        return self.loadfromDB(session)

    def reload(self, session):
        mcli.setKey(configKey, json.dumps(self.loadfromDB(session)))

    def loadfromDB(self, session):

        objects = {}
        # 查询启用的配置
        configs = session.execute(select(ConsoleSysConfig).where(
            ConsoleSysConfig.enable == 1
        )).scalars().all()
        for config in configs:
            if config.type == "int":
                c_value = int(config.value)
            elif config.type == "list":
                c_value = eval(config.value)
            elif config.type == "bool":
                if config.value == "0":
                    c_value = False
                else:
                    c_value = True
            elif config.type == "json":
                try:
                    if config.value != "" and config.value is not None:
                        c_value = json.loads(config.value)
                except ValueError:
                    c_value = config.value
            else:
                c_value = config.value

            objects[config.key] = c_value
        mcli.setKey(configKey, json.dumps(objects))
        return objects

    def init_session(self, session):
        self.session = session


custom_config = ConfigCenter()
