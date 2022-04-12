from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, delete

from models.teams import ConsoleConfig


class CustomConfigsService(object):
    @staticmethod
    def bulk_create_or_update(session, configs):
        create_config_models = []
        update_config_models = []
        old_configs = session.execute(select(ConsoleConfig)).scalars().all()
        old_configs = jsonable_encoder(old_configs)
        exist_configs = {cfg["key"]: cfg["value"] for cfg in old_configs}
        for config in configs:
            if not config.get("key"):
                continue
            if not exist_configs.get(config["key"]):
                c_config_model = ConsoleConfig(key=config["key"], value=config.get("value", ""))
                create_config_models.append(c_config_model)
                continue
            u_config_model = ConsoleConfig(key=config["key"], value=config.get("value", ""))
            update_config_models.append(u_config_model)
        delete_keys = [ucm.key for ucm in update_config_models]
        session.execute(delete(ConsoleConfig).where(
            ConsoleConfig.key.in_(delete_keys)
        ))
        create_config_models.extend(update_config_models)
        return session.add_all(update_config_models)


custom_configs_service = CustomConfigsService()