from sqlalchemy import select, delete

from models.virtual.models import VirtualOsInfo
from repository.base import BaseRepository


class VirtualOsRepository(BaseRepository[VirtualOsInfo]):

    def create_virtual_os(self, session, virtual_os_info):
        virtual_os_info = VirtualOsInfo(**virtual_os_info)
        session.add(virtual_os_info)
        session.flush()

    def get_os_info_by_os_name(self, session, os_name):
        return session.execute(select(VirtualOsInfo).where(
            VirtualOsInfo.os_name == os_name
        )).scalars().first()

    def get_all_os_info(self, session):
        return session.execute(select(VirtualOsInfo).order_by(
            VirtualOsInfo.create_time.desc())).scalars().all()

    def delete_os_info_by_os_name(self, session, os_name):
        session.execute(delete(VirtualOsInfo).where(
            VirtualOsInfo.os_name == os_name
        ))


virtual_os_repo = VirtualOsRepository(VirtualOsInfo)
