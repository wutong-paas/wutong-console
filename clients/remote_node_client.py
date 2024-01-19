import os
from loguru import logger
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info


class RemoteNodeClient(ApiBaseHttpClient):
    """
    RemoteMigrateClient
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

    def get_nodes(self, session, region_code):
        """查询集群节点列表"""
        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["bean"]["nodes"]

    def get_node_by_name(self, session, region_code, node_name):
        """查询节点详情"""
        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}".format(node_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["bean"]


remote_node_client_api = RemoteNodeClient()
