from models.market.models import CenterAppVersion
from repository.base import BaseRepository


class CenterAppVersionRepository(BaseRepository[CenterAppVersion]):
    pass


center_app_version_repo = CenterAppVersionRepository(CenterAppVersion)
