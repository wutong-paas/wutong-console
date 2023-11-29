from sqlalchemy import select

from models.virtual.models import VirtualImageInfo
from repository.base import BaseRepository


class VirtualImageRepository(BaseRepository[VirtualImageInfo]):

    def create_virtual_image(self, session, virtual_image_info):
        virtual_image_info = VirtualImageInfo(**virtual_image_info)
        session.add(virtual_image_info)
        session.flush()

    def get_virtual_image_by_name(self, session, image_name):
        return session.execute(
            select(VirtualImageInfo).where(
                VirtualImageInfo.image_name == image_name)).scalars().first()

    def get_all_virtual_image(self, session):
        return session.execute(
            select(VirtualImageInfo)).scalars().all()


virtual_image_repo = VirtualImageRepository(VirtualImageInfo)
