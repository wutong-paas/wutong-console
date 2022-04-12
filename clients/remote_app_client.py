import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_tenant_region_info


class RemoteAppClient(ApiBaseHttpClient):
    """
    RemoteAppClient
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

    def install_app(self, session, region_name, tenant_name, region_app_id, data):
        """

        :param region_name:
        :param tenant_name:
        :param region_app_id:
        :param data:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/install"

        self._set_headers(token)
        _, _ = self._post(url, self.default_headers, region=region_name, body=json.dumps(data))

    def list_app_services(self, session, region_name, tenant_name, region_app_id):
        """

        :param region_name:
        :param tenant_name:
        :param region_app_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/services"

        self._set_headers(token)
        _, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]

    def create_application(self, session, region_name, tenant_name, body):
        """

        :param region_name:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_create_application(self, session, region_name, tenant_name, body):
        """

        :param region_name:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/batch_create_apps"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("list", None)

    def update_service_app_id(self, session, region_name, tenant_name, service_alias, body):
        """

        :param region_name:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_update_service_app_id(self, session, region_name, tenant_name, app_id, body):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/services"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app(self, session, region_name, tenant_name, app_id, body):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def create_app_config_group(self, session, region_name, tenant_name, app_id, body):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app_config_group(self, session, region_name, tenant_name, app_id, config_group_name, body):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param config_group_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def delete_app(self, session, region_name, tenant_name, app_id, data={}):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param data:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id

        self._set_headers(token)
        _, _ = self._delete(url, self.default_headers, region=region_name, body=json.dumps(data))

    def delete_app_config_group(self, session, region_name, tenant_name, app_id, config_group_name):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param config_group_name:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region_name)
        return res, body

    def check_app_governance_mode(self, session, region_name, tenant_name, region_app_id, query):
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/{}/apps/{}/governance/check?governance_mode={}".format(tenant_region.region_tenant_name,
                                                                                        region_app_id, query)

        self._set_headers(token)
        _, _ = self._get(url, self.default_headers, region=region_name)

    def parse_app_services(self, session, region_name, tenant_name, app_id, values):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param values:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/parse-services"

        self._set_headers(token)
        _, body = self._post(
            url, self.default_headers, region=region_name, body=json.dumps({
                "values": values,
            }))
        return body["list"]

    def list_app_releases(self, session, region_name, tenant_name, app_id):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/releases"

        self._set_headers(token)
        _, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]

    def sync_components(self, session, tenant_name, region_name, app_id, components):
        """

        :param tenant_name:
        :param region_name:
        :param app_id:
        :param components:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        url += "/v2/tenants/{tenant_name}/apps/{app_id}/components".format(tenant_name=tenant_name, app_id=app_id)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(components), region=region_name)

    def sync_config_groups(self, session, tenant_name, region_name, app_id, body):
        """

        :param tenant_name:
        :param region_name:
        :param app_id:
        :param body:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        url += "/v2/tenants/{tenant_name}/apps/{app_id}/app-config-groups".format(tenant_name=tenant_name,
                                                                                  app_id=app_id)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(body), region=region_name)

    def update_app_ports(self, session, region_name, tenant_name, app_id, data):
        """

        :param region_name:
        :param tenant_name:
        :param app_id:
        :param data:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/ports"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(data), region=region_name)
        return body

    def get_app_status(self, session, region_name, tenant_name, region_app_id):
        """

        :param region_name:
        :param tenant_name:
        :param region_app_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/status"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name)
        return body["bean"]

    def get_app_detect_process(self, session, region_name, tenant_name, region_app_id):
        """

        :param region_name:
        :param tenant_name:
        :param region_app_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/detect-process"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]


remote_app_client = RemoteAppClient()
