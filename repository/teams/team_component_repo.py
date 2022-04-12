from models.component.models import TeamComponentInfo
from repository.base import BaseRepository


class TeamComponentRepository(BaseRepository[TeamComponentInfo]):

    def index(self):
        # todo
        return None


team_component_repo = TeamComponentRepository(TeamComponentInfo)
