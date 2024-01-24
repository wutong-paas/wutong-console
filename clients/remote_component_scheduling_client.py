import json
import os
from loguru import logger
from sqlalchemy import select
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info
from exceptions.main import ServiceHandleException
from models.teams import RegionConfig


class RemoteSchedulingClient(ApiBaseHttpClient):
    """
    RemoteComponentClient
    """

    def __init__(self, *args, **kwargs):
        ApiBaseHttpClient.__init__(self, *args, **kwargs)
        self.default_headers = {'Connection': 'close', 'Content-Type': 'application/json'}

    def _set_headers(self, token):

        if not token:
            if os.environ.get('REGION_TOKEN'):
                self.default_headers.update({"Authorization": os.environ.get('REGION_TOKEN')})
            else:
                self.default_headers.update({"Authorization": ""})
        else:
            self.default_headers.update({"Authorization": token})
        logger.debug('Default headers: {0}'.format(self.default_headers))

    def get_service_scheduling_rule(self, session, region_name, tenant_env, service_alias):
        """获取组件调度配置"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/scheduling/details".format(tenant_env.tenant_name,
                                                                                       tenant_env.env_name,
                                                                                       service_alias)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_name)
        return body['bean']

    def add_service_label_scheduling(self, session, region_name, tenant_env, service_alias, body):
        """新增组件标签调度"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/scheduling/labels".format(tenant_env.tenant_name,
                                                                                       tenant_env.env_name,
                                                                                       service_alias)

        self._set_headers(token)
        self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body))

    def update_service_label_scheduling(self, session, region_name, tenant_env, service_alias, body):
        """更新组件标签调度"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/scheduling/labels".format(tenant_env.tenant_name,
                                                                                       tenant_env.env_name,
                                                                                       service_alias)

        self._set_headers(token)
        self._put(session, url, self.default_headers, region=region_name, body=json.dumps(body))

    def delete_service_label_scheduling(self, session, region_name, tenant_env, service_alias, body):
        """删除组件标签调度"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/scheduling/labels".format(tenant_env.tenant_name,
                                                                                       tenant_env.env_name,
                                                                                       service_alias)

        self._set_headers(token)
        self._delete(session, url, self.default_headers, region=region_name, body=json.dumps(body))


remote_scheduling_client = RemoteSchedulingClient()
