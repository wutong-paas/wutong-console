import json
import os

from loguru import logger
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_env_region_info
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

    def get_tenant_resources(self, session, region, tenant_env):
        """获取指定租户的资源使用情况"""

        url, token = get_region_access_info(tenant_env.env_name, region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + \
              "/resources"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region, timeout=10)
        return body

    # 新建环境
    def create_env(self, session, region, team_id, team_name, env_name, env_id, namespace):
        """创建环境"""
        url, token = get_region_access_info(env_name, region, session)
        data = {"tenant_env_id": team_id, "tenant_name": team_name, "tenant_env_id": env_id, "tenant_env_name": env_name,
                "namespace": namespace}
        url += "/v2/tenants/{0}/envs".format(team_name)

        print("data = ", data)
        self._set_headers(token)
        logger.debug("create env url :{0}".format(url))
        try:
            res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(data))
            return res, body
        except ApiBaseHttpClient.CallApiError as e:
            if "namespace exists" in e.message['body'].get('msg', ""):
                raise ErrNamespaceExists
            return {'status': e.message['http_code']}, e.message['body']

    # 删除环境
    def delete_env(self, session, region, tenant_env):
        """删除环境"""

        url, token = get_region_access_info(tenant_env.env_name, region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region)
        return body

    # 获取kubeconfig
    def get_kubeconfig(self, session, region, tenant_env, tenant_name):
        """获取kubeconfig"""

        url, token = get_region_access_info(tenant_env.env_name, region, session)
        url = url + "/v2/tenants/{0}/envs/{1}/kubeconfig".format(tenant_name, tenant_env.env_name)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    # 获取kuberesources
    def get_kuberesources(self, session, region, tenant_env, app_id, service_alias_list, custom_namespace):
        """获取kubeconfig"""

        params = ""
        url, token = get_region_access_info(tenant_env.env_name, region, session)

        for service_alias in service_alias_list:
            params += "&service_aliases={0}".format(service_alias)
        url = url + "/v2/tenants/{0}/envs/{1}/apps/{2}/kube-resources?namespace={3}{4}".format(tenant_env.tenant_name,
                                                                                               tenant_env.env_name,
                                                                                               app_id,
                                                                                               custom_namespace, params)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body


remote_tenant_client = RemoteTenantClient()
