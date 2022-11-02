from sqlalchemy import select, delete, update

from models.component.models import ComponentProbe
from repository.base import BaseRepository


class ServiceProbeRepository(BaseRepository[ComponentProbe]):

    def overwrite_by_component_ids(self, session, component_ids, probes):
        session.execute(delete(ComponentProbe).where(
            ComponentProbe.service_id.in_(component_ids)))
        for probe in probes:
            session.merge(probe)
        session.flush()

    def list_probes(self, session, service_id):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id))).scalars().all()

    def delete_service_probe(self, session, service_id):
        session.execute(
            delete(ComponentProbe).where(ComponentProbe.service_id == service_id)
        )

    def get_probe(self, session, service_id):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id))).scalars().first()

    def get_service_probe(self, session, service_id):
        return session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id,
            ComponentProbe.is_used == 1)).scalars().first()

    def get_all_service_probe(self, session, service_id):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id,
            ComponentProbe.is_used == 1))).scalars().all()

    def get_service_probes(self, session, service_id):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id))).scalars().all()

    def get_probe_by_probe_id(self, session, service_id, probe_id):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id,
            ComponentProbe.probe_id == probe_id))).scalars().first()

    def delete(self, session, service_id, probe_id):
        session.execute(delete(ComponentProbe).where(
            ComponentProbe.service_id == service_id,
            ComponentProbe.probe_id == probe_id))
        

    def update_service_probeb(self, session, **update_params):
        session.execute(update(ComponentProbe).where(
            ComponentProbe.service_id == update_params["service_id"],
            ComponentProbe.probe_id == update_params["probe_id"]).values(**update_params))

    def get_probe_by_mode(self, session, service_id, mode):
        return (session.execute(select(ComponentProbe).where(
            ComponentProbe.service_id == service_id,
            ComponentProbe.mode == mode))).scalars().first()


probe_repo = ServiceProbeRepository(ComponentProbe)
