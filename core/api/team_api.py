import requests

from core.setting import settings
from exceptions.main import ServiceHandleException


class TeamApi(object):
    def __init__(self):
        self.headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def get_user_env_auth(self, user, team_id, role_id):
        params = {
            "userId": user.user_id,
            "teamId": team_id,
            "roleId": role_id,
        }

        self.headers.update({"Authorization": user.token})
        url = "{}/wutong-cube-core/role-user/valid-role-user-team-project".format(settings.USER_AUTH_API_URL)
        response = requests.post(url, json=params, headers=self.headers)

        data = response.json()
        code = data["code"]
        msg = data["msg"]
        is_admin = data["data"]
        if code != '0':
            raise ServiceHandleException(msg="get user auth error", msg_show=msg, status_code=400)
        return is_admin

    def get_user_project_ids(self, user_id, team_id, token):
        params = {
            "userId": user_id,
            "teamId": team_id,
        }

        self.headers.update({"Authorization": token})
        url = "{}/wutong-cube-core/role-user/query-project-by-user".format(settings.USER_AUTH_API_URL)
        response = requests.post(url, json=params, headers=self.headers)

        data = response.json()
        code = data["code"]
        msg = data["msg"]
        project_ids = data["data"]
        if code != '0':
            raise ServiceHandleException(msg="get user project auth error", msg_show=msg, status_code=500)
        return project_ids


team_api = TeamApi()
