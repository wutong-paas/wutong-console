from sqlalchemy import select

from models.region.models import TeamRegionInfo
from repository.region.region_info_repo import region_repo
from repository.teams.team_repo import team_repo


class CertService(object):
    def get_team_usable_regions(self, session, team_name, enterprise_id):
        usable_regions = region_repo.get_usable_cert_regions(session, enterprise_id)
        region_names = [r.region_name for r in usable_regions]
        team_opened_regions = region_repo.get_team_opened_region(session, team_name)
        if team_opened_regions:
            tenant = team_repo.get_team_by_team_name(session, team_name)
            team_opened_regions = session.execute(select(TeamRegionInfo).where(
                TeamRegionInfo.tenant_id == tenant.tenant_id,
                TeamRegionInfo.is_init == 1,
                TeamRegionInfo.region_name.in_(region_names)
            )).scalars().all()
        return team_opened_regions


cert_service = CertService()
