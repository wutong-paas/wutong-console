from sqlalchemy import delete, select

from database.session import SessionClass
from models.application.models import ConfigGroupService, ConfigGroupItem
from repository.base import BaseRepository


class ApplicationConfigGroupServiceRepository(BaseRepository[ConfigGroupService]):

    def create(self, session, **data):
        cgs = ConfigGroupService(**data)
        session.add(cgs)
        session.flush()
        return cgs

    @staticmethod
    def bulk_create_or_update(session, config_group_components):
        cgc_ids = [cgc.ID for cgc in config_group_components]
        session.execute(delete(ConfigGroupService).where(
            ConfigGroupService.ID.in_(cgc_ids)
        ))
        session.add_all(config_group_components)

    @staticmethod
    def list_by_app_id(session, app_id):
        return session.execute(select(ConfigGroupService).where(
            ConfigGroupService.app_id == app_id
        )).scalars().all()

    def delete_effective_service(self, session: SessionClass, service_id):
        session.execute(
            delete(ConfigGroupService).where(ConfigGroupService.service_id == service_id)
        )
        

    def list(self, session: SessionClass, config_group_id):
        return (session.execute(
            select(ConfigGroupService).where(ConfigGroupService.config_group_id == config_group_id)
        )).scalars().all()

    def delete_by_config_group_id(self, session: SessionClass, config_group_id):
        session.execute(
            delete(ConfigGroupService).where(ConfigGroupService.config_group_id == config_group_id)
        )
        

class ApplicationConfigGroupItemRepository(BaseRepository[ConfigGroupItem]):
    @staticmethod
    def bulk_create_or_update(session, items):
        item_ids = [item.ID for item in items]
        session.execute(delete(ConfigGroupItem).where(
            ConfigGroupItem.ID.in_(item_ids)
        ))
        session.add_all(items)

    def list_by_app_id(self, session, app_id):
        return (session.execute(
            select(ConfigGroupItem).where(ConfigGroupItem.app_id == app_id)
        )).scalars().all()

    def list(self, session: SessionClass, config_group_id):
        return (session.execute(
            select(ConfigGroupItem).where(ConfigGroupItem.config_group_id == config_group_id)
        )).scalars().all()

    def create(self, session: SessionClass, **group_item):
        cgi = ConfigGroupItem(**group_item)
        session.add(cgi)
        session.flush()

    def delete_by_config_group_id(self, session: SessionClass, config_group_id):
        session.execute(
            delete(ConfigGroupItem).where(ConfigGroupItem.config_group_id == config_group_id)
        )
        

app_config_group_service_repo = ApplicationConfigGroupServiceRepository(ConfigGroupService)
app_config_group_item_repo = ApplicationConfigGroupItemRepository(ConfigGroupItem)
