import json
import os
import re
from urllib.parse import urlparse
from fastapi.encoders import jsonable_encoder
from loguru import logger
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_env_region_info


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

    def install_app(self, session, region_name, tenant_env, region_app_id, data):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param region_app_id:
        :param data:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/apps/" + \
              region_app_id + "/install"

        self._set_headers(token)
        _, _ = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(data))

    def list_app_services(self, session, region_name, tenant_env, region_app_id):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param region_app_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/apps/" + \
              region_app_id + "/services"

        self._set_headers(token)
        _, body = self._get(session, url, self.default_headers, region=region_name)
        return body["list"]

    def create_application(self, session, region_name, tenant_env, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/apps"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_create_application(self, session, region_name, tenant_env, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + \
              "/batch_create_apps"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("list", None)

    def update_service_app_id(self, session, region_name, tenant_env, service_alias, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/services/" + \
              service_alias

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_update_service_app_id(self, session, region_name, tenant_env, app_id, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/services/" + \
              "/apps/" + app_id + "/services"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app(self, session, region_name, tenant_env, app_id, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/services/" + \
              "/apps/" + app_id

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def create_app_config_group(self, session, region_name, tenant_env, app_id, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/services/" + \
              "/apps/" + app_id + "/configgroups"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app_config_group(self, session, region_name, tenant_env, app_id, config_group_name, body):
        """
        :param session
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param config_group_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/apps/" + \
              app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def delete_app(self, session, region_name, tenant_env, app_id, data=None):
        """
        :param session:
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param data:
        """
        if data is None:
            data = {}
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + "/apps/" + app_id

        self._set_headers(token)
        _, _ = self._delete(session, url, self.default_headers, region=region_name, body=json.dumps(data))

    def delete_app_config_group(self, session, region_name, tenant_env, app_id, config_group_name):
        """
        :param session:
        :param region_name:
        :param tenant_env:
        :param app_id:
        :param config_group_name:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + \
              "/apps/" + app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region_name)
        return res, body

    def check_app_governance_mode(self, session, region_name, tenant_env, region_app_id, query):
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/{}/envs/{}/apps/{}/governance/check?governance_mode={}".format(
            tenant_region.region_tenant_name,
            tenant_env.env_name,
            region_app_id, query)

        self._set_headers(token)
        _, _ = self._get(session, url, self.default_headers, region=region_name)

    def list_app_releases(self, session, region_name, tenant_env, app_id):
        """
        :param session:
        :param region_name:
        :param tenant_env:
        :param app_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + \
              "/apps/" + app_id + "/releases"

        self._set_headers(token)
        _, body = self._get(session, url, self.default_headers, region=region_name)
        return body["list"]

    def sync_components(self, session, tenant_env, region_name, app_id, components):
        """
        :param session:
        :param tenant_env:
        :param region_name:
        :param app_id:
        :param components:
        """
        url, token = get_region_access_info(region_name, session)
        url += "/v2/tenants/{tenant_name}/envs/{env_name}/apps/{app_id}/components".format(
            tenant_name=tenant_env.tenant_name,
            env_name=tenant_env.env_name,
            app_id=app_id)
        self._set_headers(token)
        self._post(session, url, self.default_headers, body=json.dumps(components), region=region_name)

    def sync_config_groups(self, session, tenant_env, region_name, app_id, body):
        """
        :param session:
        :param tenant_env:
        :param region_name:
        :param app_id:
        :param body:
        """
        url, token = get_region_access_info(region_name, session)
        url += "/v2/tenants/{tenant_name}/envs/{env_name}/apps/{app_id}/app-config-groups".format(
            tenant_name=tenant_env.tenant_name,
            env_name=tenant_env.env_name,
            app_id=app_id)
        self._set_headers(token)
        self._post(session, url, self.default_headers, body=json.dumps(body), region=region_name)

    def get_app_status(self, session, region_name, tenant_env, region_app_id):
        """
        :param session:
        :param region_name:
        :param tenant_env:
        :param region_app_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        tenant_region = get_env_region_info(tenant_env, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/envs/" + tenant_env.env_name + \
              "/apps/" + region_app_id + "/status"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region_name)
        return body["bean"]

    def get_headers(self, environ):
        """
        Retrieve the HTTP headers from a WSGI environment dictionary.  See
        https://docs.djangoproject.com/en/dev/ref/request-response/#django.http.HttpRequest.META
        """
        headers = {}
        for key, value in list(environ.items()):
            # Sometimes, things don't like when you send the requesting host through.
            if key.startswith('HTTP_') and key != 'HTTP_HOST':
                headers[key[5:].replace('_', '-')] = value
            elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                headers[key.replace('_', '-')] = value

        return headers

    def make_absolute_location(self, base_url, location):
        """
        Convert a location header into an absolute URL.
        """
        absolute_pattern = re.compile(r'^[a-zA-Z]+://.*$')
        if absolute_pattern.match(location):
            return location

        parsed_url = urlparse(base_url)

        if location.startswith('//'):
            # scheme relative
            return parsed_url.scheme + ':' + location

        elif location.startswith('/'):
            # host relative
            return parsed_url.scheme + '://' + parsed_url.netloc + location

        else:
            # path relative
            return parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path.rsplit('/', 1)[0] + '/' + location

    async def proxy(self, request, url, region, data_json, body, requests_args=None):
        """
        Forward as close to an exact copy of the request as possible along to the
        given url.  Respond with as close to an exact copy of the resulting
        response as possible.
        If there are any additional arguments you wish to send to requests, put
        them in the requests_args dictionary.
        """
        requests_args = (requests_args or {}).copy()
        headers = jsonable_encoder(request.headers)  # self.get_headers(request.headers)

        if 'headers' not in requests_args:
            requests_args['headers'] = {}
        if 'body' not in requests_args:
            requests_args['body'] = json.dumps(data_json)
        if 'fields' not in requests_args:
            requests_args['fields'] = {}

        if requests_args['body'] == '{}':
            requests_args['body'] = body

        # Overwrite any headers and params from the incoming request with explicitly
        # specified values for the requests library.
        headers.update(requests_args['headers'])

        # If there's a content-length header from Django, it's probably in all-caps
        # and requests might not notice it, so just remove it.
        for key in list(headers.keys()):
            if key.lower() == 'content-length':
                del headers[key]

        requests_args['headers'] = headers

        client = self.get_client(region_config=region)
        response = client.request(method=request.method, timeout=20, url=url,
                                  **requests_args)

        from fastapi.responses import Response
        proxy_response_headers = {}

        excluded_headers = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
                            'transfer-encoding', 'upgrade', 'content-encoding', 'content-length'}
        for key, value in list(response.headers.items()):
            if key.lower() in excluded_headers:
                continue
            elif key.lower() == 'location':
                # If the location is relative at all, we want it to be absolute to
                # the upstream server.
                proxy_response_headers.update({key: self.make_absolute_location(response.url, value)})
            else:
                proxy_response_headers.update({key: value})

        proxy_response_headers.update({"content-security-policy": "upgrade-insecure-requests"})

        proxy_response = Response(response.data, headers=proxy_response_headers, status_code=response.status)
        return proxy_response


remote_app_client = RemoteAppClient()
