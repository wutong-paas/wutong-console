from datetime import datetime

from sqlalchemy import select

from exceptions.exceptions import ConfigExistError
from models.teams import ConsoleSysConfig, ConsoleConfig
from repository.base import BaseRepository


class ConsoleConfigRepository(BaseRepository[ConsoleConfig]):
    pass


class SystemConfigRepository(BaseRepository[ConsoleSysConfig]):
    """
    SystemConfigRepository
    """

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

    def add_config(self, session, key, enterprise_id, default_value, config_type, enable=True, desc=""):
        """
        添加系统配置

        :param key:
        :param enterprise_id:
        :param default_value:
        :param config_type:
        :param enable:
        :param desc:
        :return:
        """
        config = self.get_config_by_key_and_enterprise_id(session=session, key=key, enterprise_id=enterprise_id)
        if not config:
            create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            config = ConsoleSysConfig(
                key=key,
                type=config_type,
                value=default_value,
                desc=desc,
                create_time=create_time,
                enable=enable,
                enterprise_id=enterprise_id
            )
            session.add(config)
            # todo
            # custom_settings.reload()
            return config
        else:
            raise ConfigExistError("配置{}已存在".format(key))


console_config_repo = ConsoleConfigRepository(ConsoleConfig)
sys_config_repo = SystemConfigRepository(ConsoleSysConfig)
