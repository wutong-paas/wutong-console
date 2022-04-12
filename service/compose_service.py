from database.session import SessionClass
from repository.component.compose_repo import compose_relation_repo


class ComposeService(object):
    def get_service_compose_id(self, session: SessionClass, service):
        return compose_relation_repo.get_compose_id_by_service_id(service.service_id)


compose_service = ComposeService()
