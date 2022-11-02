from sqlalchemy import select, delete, update
from database.session import SessionClass
from exceptions.bcode import ErrComponentGraphNotFound, ErrComponentGraphExists
from models.component.models import ComponentGraph
from repository.base import BaseRepository


class ComponentGraphRepository(BaseRepository[ComponentGraph]):

    def batch_delete(self, session, component_id, graph_ids):
        session.execute(delete(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.graph_id.in_(graph_ids)
        ))
        session.flush()

    def update(self, session, component_id, graph_id, **data):
        session.execute(update(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.graph_id == graph_id
        ).values(**data))
        session.flush()

    @staticmethod
    def list_between_sequence(session, component_id, left_sequence, right_sequence):
        return session.execute(select(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.sequence.__ge__(left_sequence),
            ComponentGraph.sequence.__lt__(right_sequence)
        )).scalars().all()

    @staticmethod
    def get_graph(session, component_id, graph_id):
        return session.execute(select(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.graph_id == graph_id
        )).scalars().first()

    @staticmethod
    def list_gt_sequence(session, component_id, sequence):
        return session.execute(select(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.sequence.__gt__(sequence)
        )).scalars().all()

    @staticmethod
    def delete(session, component_id, graph_id):
        session.execute(delete(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.graph_id == graph_id
        ))
        session.flush()

    @staticmethod
    def get(session, component_id, graph_id):
        cg = session.execute(select(ComponentGraph).where(
            ComponentGraph.component_id == component_id,
            ComponentGraph.graph_id == graph_id
        )).scalars().first()
        if not cg:
            raise ErrComponentGraphNotFound
        return cg

    def overwrite_by_component_ids(self, session, component_ids, component_graphs):
        session.execute(delete(ComponentGraph).where(
            ComponentGraph.component_id.in_(component_ids)))
        for component_graph in component_graphs:
            session.merge(component_graph)
        session.flush()

    def list(self, session: SessionClass, component_id):
        return session.execute(
            select(ComponentGraph).where(ComponentGraph.component_id == component_id).order_by(
                ComponentGraph.sequence.asc())).scalars().all()

    def bulk_create(self, session: SessionClass, graphs):
        session.add_all(graphs)
        

    def get_by_title(self, session: SessionClass, component_id, title):
        cg = (session.execute(
            select(ComponentGraph).where(ComponentGraph.component_id == component_id,
                                         ComponentGraph.title == title)
        )).scalars().all()
        if len(cg) == 0:
            raise ErrComponentGraphNotFound
        return cg

    def delete_by_component_id(self, session: SessionClass, component_id):
        session.execute(
            delete(ComponentGraph).where(ComponentGraph.component_id == component_id)
        )

    def create(self, session: SessionClass, component_id, graph_id, title, promql, sequence):
        # check if the component graph already exists
        graph = session.execute(select(ComponentGraph).where(ComponentGraph.component_id == component_id,
                                                             ComponentGraph.title == title)).scalars().first()
        if graph:
            raise ErrComponentGraphExists
        session.add(ComponentGraph(
            component_id=component_id,
            graph_id=graph_id,
            title=title,
            promql=promql,
            sequence=sequence,
        ))
        session.flush()


component_graph_repo = ComponentGraphRepository(ComponentGraph)
