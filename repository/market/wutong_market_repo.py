from sqlalchemy import select

from database.session import SessionClass
from models.market.models import AppMarket
from repository.base import BaseRepository


class WutongMarketRepository(BaseRepository[AppMarket]):

    def get_market_list(self, session: SessionClass, enterprise_id):
        markets = session.execute(
            select(AppMarket).where(AppMarket.enterprise_id == enterprise_id)
        ).scalars().all()
        if markets:
            return markets
        return []


wutong_market_repo = WutongMarketRepository(AppMarket)
