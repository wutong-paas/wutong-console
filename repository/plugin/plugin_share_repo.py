from models.application.plugin import PluginShareRecordEvent
from repository.base import BaseRepository


class PluginShareRecordEventRepository(BaseRepository[PluginShareRecordEvent]):
    pass


plugin_share_repo = PluginShareRecordEventRepository(PluginShareRecordEvent)
