from models.market.models import CenterAppTag
from repository.base import BaseRepository


class CenterAppTagRepository(BaseRepository[CenterAppTag]):
    pass


center_app_tag_repo = CenterAppTagRepository(CenterAppTag)
