import json
import os

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.bcode import ErrInternalGraphsNotFound, ErrComponentGraphNotFound
from exceptions.main import AbortRequest
from models.component.models import ComponentGraph
from repository.component.graph_repo import component_graph_repo
from repository.component.service_config_repo import port_repo
from service.app_config.promql_service import BASE_DIR, promql_service


class ComponentGraphService(object):

    def batch_delete(self, session, component_id, graph_ids):
        component_graph_repo.batch_delete(session, component_id, graph_ids)

    @staticmethod
    def _sequence_move_back(session, component_id, left_sequence, right_sequence):
        graphs = component_graph_repo.list_between_sequence(
            session=session, component_id=component_id, left_sequence=left_sequence, right_sequence=right_sequence)
        for graph in graphs:
            graph.sequence += 1
            # graph.save()

    def update_component_graph(self, session, graph, title, promql, sequence):
        data = {
            "title": title,
            "promql": promql_service.add_or_update_label(graph.component_id, promql),
        }
        if sequence != graph.sequence:
            data["sequence"] = sequence
        self._sequence_move_back(session, graph.component_id, sequence, graph.sequence)
        component_graph_repo.update(session, graph.component_id, graph.graph_id, **data)
        return jsonable_encoder(component_graph_repo.get(session, graph.component_id, graph.graph_id))

    @staticmethod
    def _sequence_move_forward(session, component_id, sequence):
        graphs = component_graph_repo.list_gt_sequence(session=session, component_id=component_id, sequence=sequence)
        for graph in graphs:
            graph.sequence -= 1
            # graph.save()

    def delete_component_graph(self, session, graph):
        component_graph_repo.delete(session, graph.component_id, graph.graph_id)
        self._sequence_move_forward(session, graph.component_id, graph.sequence)

    def delete_by_component_id(self, session, component_id):
        return component_graph_repo.delete_by_component_id(session, component_id)

    def _load_internal_graphs(self):
        filenames = []
        internal_graphs = {}
        path_to_graphs = BASE_DIR + "/hack/component-graphs"
        try:
            for filename in os.listdir(path_to_graphs):
                path = path_to_graphs + "/" + filename
                try:
                    with open(path, encoding='utf-8') as f:
                        name, _ = os.path.splitext(filename)
                        internal_graphs[name] = json.load(f)
                        filenames.append(name)
                except ValueError as e:
                    # ignore wrong json file
                    logger.warning(e)
        except OSError as e:
            # directory not found
            logger.warning(e)
        return filenames, internal_graphs

    def _next_sequence(self, session: SessionClass, component_id):
        graphs = component_graph_repo.list(session=session, component_id=component_id)
        if not graphs:
            return 0
        sequences = [graph.sequence for graph in graphs]
        sequences.sort()
        return sequences[len(sequences) - 1] + 1

    def create_internal_graphs(self, session: SessionClass, component_id, graph_name):
        _, internal_graphs = self._load_internal_graphs()
        if not internal_graphs or not internal_graphs.get(graph_name):
            raise ErrInternalGraphsNotFound

        graphs = []
        seq = self._next_sequence(session=session, component_id=component_id)
        for graph in internal_graphs.get(graph_name):
            try:
                _ = component_graph_repo.get_by_title(session, component_id, graph.get("title"))
                continue
            except ErrComponentGraphNotFound:
                pass

            try:
                promql = promql_service.add_or_update_label(component_id, graph["promql"])
            except AbortRequest as e:
                logger.warning("promql {}: {}".format(graph["promql"], e))
                continue
            # make sure there are no duplicate graph
            graphs.append(
                ComponentGraph(
                    component_id=component_id,
                    graph_id=make_uuid(),
                    title=graph["title"],
                    promql=promql,
                    sequence=seq,
                ))
            seq += 1
        component_graph_repo.bulk_create(session, graphs)

    def bulk_create(self, session: SessionClass, component_id, graphs):
        if not graphs:
            return
        cgs = []
        for graph in graphs:
            try:
                _ = component_graph_repo.get_by_title(component_id, graph.get("title"))
                continue
            except ErrComponentGraphNotFound:
                pass

            try:
                promql = promql_service.add_or_update_label(component_id, graph.get("promql"))
            except AbortRequest as e:
                logger.warning("promql: {}, {}".format(graph.get("promql"), e))
                continue

            cgs.append(
                ComponentGraph(
                    component_id=component_id,
                    graph_id=make_uuid(),
                    title=graph.get("title"),
                    promql=promql,
                    sequence=graph.get("sequence"),
                ))
        port_repo.bulk_all(session, cgs)

    def list_component_graphs(self, session, component_id):
        graphs = component_graph_repo.list(session, component_id)
        return [jsonable_encoder(graph) for graph in graphs]

    def list_internal_graphs(self):
        graphs, _ = self._load_internal_graphs()
        return graphs

    def rearrange(self, session, component_id):
        graphs = component_graph_repo.list(session, component_id)
        sequence = 0
        for graph in graphs:
            graph.sequence = sequence
            
            sequence += 1

    def create_component_graph(self, session, component_id, title, promql):
        promql = promql_service.add_or_update_label(component_id, promql)
        graph_id = make_uuid()
        sequence = self._next_sequence(session, component_id)
        if sequence > 10000:
            # rearrange to avoid overflow
            self.rearrange(session, component_id)
            sequence = self._next_sequence(session, component_id)
        component_graph_repo.create(session, component_id, graph_id, title, promql, sequence)
        return jsonable_encoder(component_graph_repo.get(session, component_id, graph_id))


component_graph_service = ComponentGraphService()
