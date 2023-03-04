from sqlalchemy import select

from models.component.models import ComponentEvent
from repository.base import BaseRepository


class ServiceEventRepository(BaseRepository[ComponentEvent]):

    def get_events_before_specify_time(self, session, tenant_env_id, service_id, start_time):
        if start_time:
            return (session.execute(
                select(ComponentEvent).where(ComponentEvent.tenant_env_id == tenant_env_id,
                                             ComponentEvent.service_id == service_id,
                                             ComponentEvent.start_time.lte(start_time)).order_by(
                    ComponentEvent.start_time.desc()))).scalars().all()
        else:
            return (session.execute(
                select(ComponentEvent).where(ComponentEvent.tenant_env_id == tenant_env_id,
                                             ComponentEvent.service_id == service_id))).scalars().all()


event_repo = ServiceEventRepository(ComponentEvent)
