from sqlalchemy import select, delete

from models.region.label import NodeLabels, Labels
from models.component.models import ComponentLabels
from repository.base import BaseRepository


class ServiceLabelsReporsitory(BaseRepository[ComponentLabels]):

    def overwrite_by_component_ids(self, session, component_ids, labels: [ComponentLabels]):
        session.execute(delete(ComponentLabels).where(
            ComponentLabels.service_id.in_(component_ids)
        ))
        session.add_all(labels)

    def delete_service_all_labels(self, session, service_id):
        session.execute(
            delete(ComponentLabels).where(ComponentLabels.service_id == service_id)
        )

    def get_service_labels(self, session, service_id):
        return session.execute(select(ComponentLabels).where(
            ComponentLabels.service_id == service_id)).scalars().all()

    def get_service_label(self, session, service_id, label_id):
        return (session.execute(select(ComponentLabels).where(
            ComponentLabels.service_id == service_id,
            ComponentLabels.label_id == label_id))).scalars().first()

    def delete_service_labels(self, session, service_id, label_id):
        session.execute(delete(ComponentLabels).where(
            ComponentLabels.service_id == service_id,
            ComponentLabels.label_id == label_id))
        


class NodeLabelsReporsitory(BaseRepository[NodeLabels]):

    def get_node_label_by_region(self, session, region_id, service_label_ids):
        return (session.execute(select(NodeLabels).where(
            NodeLabels.region_id == region_id,
            NodeLabels.label_id.in_(service_label_ids)))).scalars().all()

    def get_all_labels(self, session):
        return (session.execute(select(NodeLabels))).scalars().all()


class LabelsReporsitory(BaseRepository[Labels]):

    def get_labels_by_label_ids(self, session, label_ids):
        return session.execute(select(Labels).where(
            Labels.label_id.in_(label_ids))).scalars().all()

    def get_labels_by_label_name(self, session, label_name):
        return (session.execute(select(Labels).where(
            Labels.label_name == label_name))).scalars().first()

    def get_all_labels(self, session):
        return (session.execute(select(Labels))).scalars().all()

    def bulk_create(self, session, labels: [Labels]):
        session.add_all(labels)
        

    def get_label_by_label_id(self, session, label_id):
        return (session.execute(select(Labels).where(
            Labels.label_id == label_id))).scalars().first()


service_label_repo = ServiceLabelsReporsitory(ComponentLabels)
node_label_repo = NodeLabelsReporsitory(NodeLabels)
label_repo = LabelsReporsitory(Labels)
