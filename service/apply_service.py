import datetime

from exceptions.main import ServiceHandleException
from repository.teams.team_applicants_repo import apply_repo
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo


class ApplyService(object):
    def delete_applicants(self, session, user_id, team_name):
        apply_repo.delete_applicants_by_id_team_name(session=session, user_id=user_id, team_name=team_name)

    def create_applicants(self, session, user_id, team_name):
        applicant = apply_repo.get_applicants_by_id_team_name(session=session, user_id=user_id, team_name=team_name)
        if not applicant:
            team = team_repo.get_team_by_team_name(session=session, team_name=team_name)
            user = user_repo.get_by_primary_key(session=session, primary_key=user_id)
            info = {
                "user_id": user_id,
                "user_name": user.get_username(),
                "team_id": team.tenant_id,
                "team_name": team_name,
                "team_alias": team.tenant_alias,
                "apply_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            return apply_repo.create_apply_info(session, **info)
        if applicant.is_pass == 0:
            raise ServiceHandleException(msg="already applied for it", msg_show="该团队已经申请过")
        if applicant.is_pass == 1:
            teams = team_repo.get_tenants_by_user_id(session, user_id)
            tnames = [team.tenant_name for team in teams]
            if team_name in tnames:
                raise ServiceHandleException(msg="already join for it", msg_show="您已加入该团队")
        applicant.apply_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        applicant.is_pass = 0
        return applicant


apply_service = ApplyService()
