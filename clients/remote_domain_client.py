import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_env_region_info


class RemoteDomainClient(ApiBaseHttpClient):
    """
    RemoteDomainClient
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

    def bind_domain(self, session, region, tenant_env, service_alias, body):
        """
        bind_domain
        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        body["tenant_env_id"] = tenant_region.region_tenant_env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name +\
              "/services/" + service_alias + "/domains"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbind_domain(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name +\
              "/services/" + service_alias + "/domains/" + \
              body["domain"]
        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def bind_http_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        body["tenant_env_id"] = tenant_region.region_tenant_env_id
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/http-rule"
        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_http_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        body["tenant_env_id"] = tenant_region.region_tenant_env_id
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/http-rule"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_http_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/http-rule"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def bind_tcp_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        body["tenant_env_id"] = tenant_region.region_tenant_env_id
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/tcp-rule"
        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_tcp_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        body["tenant_env_id"] = tenant_region.region_tenant_env_id
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbind_tcp_domain(self, session, region, tenant_name, tenant_env, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        url = url + "/v2/tenants/" + tenant_name + "/envs/" + tenant_env.env_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body


remote_domain_client_api = RemoteDomainClient()
