import json
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

    def set_node_cordon(self, session, region_code, node_name, cordon, evict_pods):
        """设置节点调度"""

        body = {}
        if not cordon:
            body = {"evict_pods": evict_pods}
        url, token = get_region_access_info(region_code, session)

        if cordon:
            url = url + "/v2/cluster/nodes/{0}/cordon".format(node_name)
        else:
            url = url + "/v2/cluster/nodes/{0}/uncordon".format(node_name)

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def add_node_label(self, session, region_code, node_name, body):
        """新增节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/label".format(node_name)

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def delete_node_label(self, session, region_code, node_name, body):
        """删除节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/label".format(node_name)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def add_node_vm_label(self, session, region_code, node_name, body):
        """新增虚拟机节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/scheduling/vm/label".format(node_name)

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def delete_node_vm_label(self, session, region_code, node_name, body):
        """删除虚拟机节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/scheduling/vm/label".format(node_name)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body["list"]

    def get_node_label(self, session, region_code, node_name):
        """查询节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/common/label".format(node_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["list"]

    def get_node_vm_label(self, session, region_code, node_name):
        """查询虚拟机节点标签"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/scheduling/vm/label".format(node_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["list"]

    def get_node_annotations(self, session, region_code, node_name):
        """查询节点注解"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/annotation".format(node_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["list"]

    def add_node_annotation(self, session, region_code, node_name, body):
        """新增节点注解"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/annotation".format(node_name)

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def delete_node_annotation(self, session, region_code, node_name, body):
        """删除节点注解"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/annotation".format(node_name)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def get_node_taint(self, session, region_code, node_name):
        """查询节点污点"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/taint".format(node_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_code)
        return body["list"]

    def add_node_taint(self, session, region_code, node_name, body):
        """新增节点污点"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/taint".format(node_name)

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body

    def delete_node_taint(self, session, region_code, node_name, body):
        """删除节点污点"""

        url, token = get_region_access_info(region_code, session)

        url = url + "/v2/cluster/nodes/{0}/taint".format(node_name)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region_code, body=json.dumps(body))
        return body


remote_node_client_api = RemoteNodeClient()
