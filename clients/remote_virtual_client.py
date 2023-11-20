import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info


class RemoteVirtualClient(ApiBaseHttpClient):
    """
    RemoteTenantClient
    """

    def __init__(self, *args, **kwargs):
        ApiBaseHttpClient.__init__(self, *args, **kwargs)
        self.default_headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }

    def _set_headers(self, token):
        if not token:
            if os.environ.get("REGION_TOKEN"):
                self.default_headers.update(
                    {"Authorization": os.environ.get("REGION_TOKEN")}
                )
            else:
                self.default_headers.update({"Authorization": ""})
        else:
            self.default_headers.update({"Authorization": token})
        logger.debug("Default headers: {0}".format(self.default_headers))

    def create_virtual_machine(self, session, region, tenant_env, body):
        """
        :param session:
        :param region:
        :param tenant_env:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, json.dumps(body), region=region
        )
        return body["bean"]


remote_virtual_client = RemoteVirtualClient()
