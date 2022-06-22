from models.market.models import AppMarket
from repository.base import BaseRepository


class WutongMarketRepository(BaseRepository[AppMarket]):
    pass


wutong_market_repo = WutongMarketRepository(AppMarket)
