from models.component.models import TeamComponentVolume
from repository.base import BaseRepository


class ComponentVolumeRepository(BaseRepository[TeamComponentVolume]):
    pass


component_volume_repo = ComponentVolumeRepository(TeamComponentVolume)
