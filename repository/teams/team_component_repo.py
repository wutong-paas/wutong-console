from models.component.models import TeamComponentInfo
from repository.base import BaseRepository


class TeamComponentRepository(BaseRepository[TeamComponentInfo]):
    pass


team_component_repo = TeamComponentRepository(TeamComponentInfo)
