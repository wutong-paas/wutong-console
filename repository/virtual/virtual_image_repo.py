from sqlalchemy import select, delete

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

    def get_virtual_imagever_by_os_name(self, session, os_name):
        return session.execute(
            select(VirtualImageInfo.version).where(
                VirtualImageInfo.os_name == os_name)).scalars().all()

    def get_virtual_imagever_by_id(self, session, id):
        return session.execute(
            select(VirtualImageInfo.version).where(
                VirtualImageInfo.ID == id)).scalars().first()

    def get_virtual_image_by_os_name(self, session, os_name, version):
        return session.execute(
            select(VirtualImageInfo).where(
                VirtualImageInfo.os_name == os_name,
                VirtualImageInfo.version == version)).scalars().first()

    def delete_virtual_imagever_by_image_name(self, session, image_name):
        session.execute(
            delete(VirtualImageInfo).where(
                VirtualImageInfo.image_name == image_name))


virtual_image_repo = VirtualImageRepository(VirtualImageInfo)
