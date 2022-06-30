import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_tenant_region_info
from common.client_auth_service import client_auth_service
from exceptions.bcode import ErrNamespaceExists


class RemoteTenantClient(ApiBaseHttpClient):
    """
    RemoteTenantClient
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

    def get_tenant_resources(self, session, region, tenant_name, enterprise_id):
        """获取指定租户的资源使用情况"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/resources?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10)
        return body

    # 新建团队
    def create_tenant(self, session, region, tenant_name, tenant_id, enterprise_id, namespace):
        """创建租户"""
        url, token = get_region_access_info(tenant_name, region, session)
        cloud_enterprise_id = client_auth_service.get_region_access_enterprise_id_by_tenant(session, tenant_name,
                                                                                            region)
        if cloud_enterprise_id:
            enterprise_id = cloud_enterprise_id
        data = {"tenant_id": tenant_id, "tenant_name": tenant_name, "eid": enterprise_id, "namespace": namespace}
        url += "/v2/tenants"

        self._set_headers(token)
        logger.debug("create tenant url :{0}".format(url))
        try:
            res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
            return res, body
        except ApiBaseHttpClient.CallApiError as e:
            if "namespace exists" in e.message['body'].get('msg', ""):
                raise ErrNamespaceExists
            return {'status': e.message['http_code']}, e.message['body']

    # 删除团队
    def delete_tenant(self, session, region, tenant_name):
        """删除组件"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body


remote_tenant_client = RemoteTenantClient()
