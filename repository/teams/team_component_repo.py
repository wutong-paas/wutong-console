from models.component.models import Component
from repository.base import BaseRepository


class TeamComponentRepository(BaseRepository[Component]):
    pass


team_component_repo = TeamComponentRepository(Component)
