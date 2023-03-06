from sqlalchemy import select

from models.region.models import EnvRegionInfo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo


class CertService(object):
    def get_team_usable_regions(self, session, env_name):
        usable_regions = region_repo.get_usable_cert_regions(session)
        region_names = [r.region_name for r in usable_regions]
        team_opened_regions = region_repo.get_team_opened_region(session, env_name)
        if team_opened_regions:
            tenant = env_repo.get_team_by_env_name(session, env_name)
            team_opened_regions = session.execute(select(EnvRegionInfo).where(
                EnvRegionInfo.region_env_id == tenant.tenant_env_id,
                EnvRegionInfo.is_init == 1,
                EnvRegionInfo.region_name.in_(region_names)
            )).scalars().all()
        return team_opened_regions


cert_service = CertService()
