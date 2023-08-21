import requests

from core.setting import settings
from exceptions.main import ServiceHandleException


class TeamApi(object):
    def __init__(self):
        self.headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def get_user_env_auth(self, user_id, team_id, role_id):
        params = {
            "userId": user_id,
            "teamId": team_id,
            "roleId": role_id,
        }

        url = "{}/wutong-cube-core/role-user/valid-role-user-team-project".format(settings.USER_AUTH_API_URL)
        response = requests.post(url, json=params, headers=self.headers)

        data = response.json()
        code = data["code"]
        msg = data["msg"]
        is_admin = data["data"]
        if code != '0':
            raise ServiceHandleException(msg="get user auth error", msg_show=msg, status_code=400)
        return is_admin


team_api = TeamApi()
