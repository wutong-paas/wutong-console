import requests

from exceptions.main import ServiceHandleException


class TeamApi(object):
    def __init__(self):
        self.kw = {"teamCode": "biechuangyingyonga", }

        self.headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def get_team_name_by_team_code(self, team_code, token):
        self.headers.update({"Authorization": token})
        params = {"teamCode": team_code}
        response = requests.post("http://wt044803-18099.cube:18099/wutong-devops-platform/team/list",
                                 json=params, headers=self.headers)

        data = response.json()
        code = data["code"]
        msg = data["msg"]
        try:
            team_name = data["data"][0]["teamName"]
        except:
            team_name = None
        if code != '0':
            raise ServiceHandleException(msg="get team info error", msg_show=msg, status_code=400)
        return team_name


team_api = TeamApi()
