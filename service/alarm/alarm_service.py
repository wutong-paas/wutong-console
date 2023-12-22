import json
from clients.remote_app_client import remote_app_client
from exceptions.main import ServiceHandleException
from repository.region.region_info_repo import region_repo


class AlarmService:

    async def obs_service_alarm(self, session, request, url, body, region_name):
        try:
            data_json = await request.json()
        except:
            data_json = {}
        region = region_repo.get_region_by_region_name(session, region_name)

        remoteurl = "{}/obs{}".format(region.url, url)
        response = await remote_app_client.proxy(
            request,
            remoteurl,
            region,
            data_json,
            body)
        if response.status_code != 200:
            raise ServiceHandleException("obs service error", msg_show=bytes.decode(response.body),
                                         error_code=response.status_code)
        return json.loads(response.body)


alarm_service = AlarmService()
