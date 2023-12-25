import json
from clients.remote_app_client import remote_app_client
from exceptions.main import ServiceHandleException


class AlarmService:

    async def obs_service_alarm(self, request, url, body, region):
        remoteurl = "{}/obs{}".format(region.url, url)
        response = await remote_app_client.proxy(
            request,
            remoteurl,
            region,
            body,
            {})
        if response.status_code != 200:
            raise ServiceHandleException("obs service error", msg_show=bytes.decode(response.body),
                                         error_code=response.status_code)
        return json.loads(response.body)


alarm_service = AlarmService()
