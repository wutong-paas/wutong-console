import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_tenant_region_info


class RemoteDomainClient(ApiBaseHttpClient):
    """
    RemoteDomainClient
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

    def bind_domain(self, session, region, tenant_name, service_alias, body):
        """
        bind_domain
        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/domains"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbind_domain(self, session, region, tenant_name, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/domains/" + \
              body["domain"]
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def bind_http_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_http_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_http_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def bind_tcp_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_tcp_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbind_tcp_domain(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body


remote_domain_client_api = RemoteDomainClient()
