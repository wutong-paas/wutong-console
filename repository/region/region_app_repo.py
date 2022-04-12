from sqlalchemy import select

from database.session import SessionClass
from models.region.models import RegionApp
from repository.base import BaseRepository


class RegionAppRepository(BaseRepository[RegionApp]):

    def create(self, session: SessionClass, **data):
        region_app = RegionApp(**data)
        session.add(region_app)
        return region_app

    def insert(self, session: SessionClass, model: RegionApp):
        session.add(model)
        session.flush()

    def bulk_create(self, session: SessionClass, app_list):
        session.add_all(app_list)
        session.flush()

    def get_region_app_id(self, session: SessionClass, region_name, app_id):
        region_app = session.execute(
            select(RegionApp).where(RegionApp.region_name == region_name,
                                    RegionApp.app_id == app_id)).scalars().first()
        if region_app:
            return region_app.region_app_id
        return None

    def list_by_app_ids(self, session: SessionClass, region_name, app_ids):
        region_apps = (session.execute(
            select(RegionApp).where(RegionApp.region_name == region_name,
                                    RegionApp.app_id.in_(app_ids)))).scalars().all()
        return region_apps


region_app_repo = RegionAppRepository(RegionApp)
