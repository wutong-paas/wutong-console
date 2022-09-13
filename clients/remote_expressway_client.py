import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info_by_enterprise_id


class HunanExpresswayClient(ApiBaseHttpClient):
    """
    RemoteComponentClient
    """

    def __init__(self, *args, **kwargs):
        ApiBaseHttpClient.__init__(self, *args, **kwargs)
        self.default_headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def _set_headers(self, token):

        if not token:
            if os.environ.get('REGION_TOKEN'):
                self.default_headers.update({"Authorization": os.environ.get('REGION_TOKEN')})
            else:
                self.default_headers.update({"Authorization": ""})
        else:
            self.default_headers.update({"Authorization": token})
        logger.debug('Default headers: {0}'.format(self.default_headers))

    def get_region_cluster(self, session, region, enterprise_id):
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url = url + "/v2/cluster"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return res, body

    def get_region_event(self, session, region, enterprise_id):
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url = url + "/v2/cluster/events"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return res, body


hunan_expressway_client = HunanExpresswayClient()
