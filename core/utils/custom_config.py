# -*- coding: utf8 -*-
import json
import logging

logger = logging.getLogger('default')

configKey = "SYS_C_F_K"


class ConfigCenter(object):

    def loadfromDB(self):

        objects = {}
        # 查询启用的配置
        configs = ConsoleSysConfig.objects.filter(enable=True)
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


custom_config = ConfigCenter()
