from loguru import logger
from sqlalchemy import select

from models.teams.enterprise import TeamEnterpriseToken
from repository.base import BaseRepository


class TeamEnterpriseTokenRepository(BaseRepository[TeamEnterpriseToken]):

    def get_tenant_enterprise_token(self, session, enterprise_id, access_target):
        logger.info("get_tenant_enterprise_token,param-enterprise_id:{},param-access_target:{}", enterprise_id,
                    access_target)
        sql = select(TeamEnterpriseToken).where(TeamEnterpriseToken.enterprise_id == enterprise_id,
                                                TeamEnterpriseToken.access_target == access_target)
        results = session.execute(sql)
        return results.scalars().first()


tenant_enterprise_token_repo = TeamEnterpriseTokenRepository(TeamEnterpriseToken)
