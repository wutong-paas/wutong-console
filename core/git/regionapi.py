# -*- coding: utf8 -*-
import json
import logging
import os
import socket
import ssl
import certifi
import httplib2
import urllib3
from addict import Dict
from urllib3.exceptions import MaxRetryError
from websockets import http
from common.api_base_http_client import Configuration
from core.setting import settings
from exceptions.main import ServiceHandleException, ErrClusterLackOfMemory, ErrTenantLackOfMemory
from models.region.models import EnvRegionInfo
from models.teams import TeamEnvInfo, RegionConfig
from repository.region.region_info_repo import region_repo

logger = logging.getLogger('default')


class RegionApiBaseHttpClient(object):
    class CallApiError(Exception):
        def __init__(self, apitype, url, method, res, body, describe=None):
            self.message = {
                "apitype": apitype,
                "url": url,
                "method": method,
                "httpcode": res.status,
                "body": body,
            }
            self.apitype = apitype
            self.url = url
            self.method = method
            self.body = body
            self.status = res.status

        def __str__(self):
            return json.dumps(self.message)

    class CallApiFrequentError(Exception):
        def __init__(self, apitype, url, method, res, body, describe=None):
            self.message = {
                "apitype": apitype,
                "url": url,
                "method": method,
                "httpcode": res.status,
                "body": body,
            }
            self.apitype = apitype
            self.url = url
            self.method = method
            self.body = body
            self.status = res.status

        def __str__(self):
            return json.dumps(self.message)

    class ApiSocketError(CallApiError):
        pass

    class InvalidLicenseError(Exception):
        pass

    def __init__(self, *args, **kwargs):
        self.timeout = 5
        # cache client
        self.clients = {}
        self.apitype = 'Not specified'

    def _jsondecode(self, string):
        try:
            pybody = json.loads(string)
        except ValueError:
            if len(string) < 10000:
                pybody = {"raw": string}
            else:
                pybody = {"raw": "too long to record!"}
        return pybody

    def _check_status(self, url, method, status, content):
        body = None
        if content:
            body = self._jsondecode(content)
        res = Dict({"status": status})
        if isinstance(body, dict):
            body = Dict(body)
        if 400 <= status <= 600:
            if not body:
                raise ServiceHandleException(msg="request region api body is nil", msg_show="集群请求网络异常", status_code=status)
            if "code" in body:
                raise ServiceHandleException(msg=body.get("msg"), status_code=status, error_code=body.get("code"))
            if status == 409:
                raise self.CallApiFrequentError(self.apitype, url, method, res, body)
            if status == 401 and isinstance(body, dict) and body.get("bean", {}).get("code", -1) == 10400:
                logger.warning(body["bean"]["msg"])
                raise self.InvalidLicenseError()
            if status == 412:
                if body.get("msg") == "cluster_lack_of_memory":
                    raise ErrClusterLackOfMemory()
                if body.get("msg") == "tenant_lack_of_memory":
                    raise ErrTenantLackOfMemory()
            raise self.CallApiError(self.apitype, url, method, res, body)
        else:
            return res, body

    def _unpack(self, dict_body):
        if 'data' not in dict_body:
            return dict_body

        data_body = dict_body['data']
        if 'bean' in data_body and data_body['bean']:
            return data_body['bean']
        elif 'list' in data_body and data_body['list']:
            return data_body['list']
        else:
            return dict()

    def get_default_timeout_conifg(self):
        connect, red = 2.0, 5.0
        try:
            connect = float(os.environ.get("REGION_CONNECTION_TIMEOUT", 2.0))
            red = float(os.environ.get("REGION_RED_TIMEOUT", 5.0))
        except Exception:
            connect, red = 2.0, 5.0
        return connect, red

    def _request(self, url, method, headers=None, body=None, *args, **kwargs):
        region_name = kwargs.get("region")
        retries = kwargs.get("retries", 2)
        d_connect, d_red = self.get_default_timeout_conifg()
        timeout = kwargs.get("timeout", d_red)
        preload_content = kwargs.get("preload_content")
        if kwargs.get("for_test"):
            region = region_name
            region_name = region.region_name
        else:
            region = region_repo.get_region_by_region_name(region_name)
        if not region:
            raise ServiceHandleException("region {0} not found".format(region_name), error_code=10412)
        client = self.get_client(region_config=region)
        if not client:
            raise ServiceHandleException(
                msg="create region api client failure", msg_show="创建集群通信客户端错误，请检查集群配置", error_code=10411)
        try:
            if preload_content is False:
                response = client.request(
                    url=url,
                    method=method,
                    headers=headers,
                    preload_content=preload_content,
                    timeout=None,  # None will set an infinite timeout.
                )
                return response, None
            if body is None:
                response = client.request(
                    url=url,
                    method=method,
                    headers=headers,
                    timeout=urllib3.Timeout(connect=d_connect, read=timeout),
                    retries=retries)
            else:
                response = client.request(
                    url=url,
                    method=method,
                    headers=headers,
                    body=body,
                    timeout=urllib3.Timeout(connect=d_connect, read=timeout),
                    retries=retries)
            return response.status, response.data
        except urllib3.exceptions.SSLError:
            self.destroy_client(region_config=region)
            raise ServiceHandleException(error_code=10411, msg="SSLError", msg_show="访问数据中心异常，请稍后重试")
        except socket.timeout as e:
            raise self.CallApiError(self.apitype, url, method, Dict({"status": 101}), {
                "type": "request time out",
                "error": str(e),
                "error_code": 10411,
            })
        except MaxRetryError as e:
            logger.debug("error url {}".format(url))
            logger.exception(e)
            raise ServiceHandleException(error_code=10411, msg="MaxRetryError", msg_show="访问数据中心异常，请稍后重试")
        except Exception as e:
            logger.debug("error url {}".format(url))
            logger.exception(e)
            raise ServiceHandleException(error_code=10411, msg="Exception", msg_show="访问数据中心异常，请稍后重试")

    def destroy_client(self, region_config):
        key = hash(region_config.url + region_config.ssl_ca_cert + region_config.cert_file + region_config.key_file)
        self.clients[key] = None

    def get_client(self, region_config):
        # get client from cache
        key = hash(region_config.url + region_config.ssl_ca_cert + region_config.cert_file + region_config.key_file)
        client = self.clients.get(key, None)
        if client:
            return client
        config = Configuration(region_config)
        pools_size = int(os.environ.get("CLIENT_POOL_SIZE", 20))
        client = self.create_client(config, pools_size)
        self.clients[key] = client
        return client

    def create_client(self, configuration, pools_size=4, maxsize=None, *args, **kwargs):

        if configuration.verify_ssl:
            cert_reqs = ssl.CERT_REQUIRED
        else:
            cert_reqs = ssl.CERT_NONE

        # ca_certs
        if configuration.ssl_ca_cert:
            ca_certs = configuration.ssl_ca_cert
        else:
            # if not set certificate file, use Mozilla's root certificates.
            ca_certs = certifi.where()

        addition_pool_args = {}
        if configuration.assert_hostname is not None:
            addition_pool_args['assert_hostname'] = configuration.assert_hostname

        if maxsize is None:
            if configuration.connection_pool_maxsize is not None:
                maxsize = configuration.connection_pool_maxsize
            else:
                maxsize = 4

        # https pool manager
        if configuration.proxy:
            self.pool_manager = urllib3.ProxyManager(
                num_pools=pools_size,
                maxsize=maxsize,
                cert_reqs=cert_reqs,
                ca_certs=ca_certs,
                cert_file=configuration.cert_file,
                key_file=configuration.key_file,
                proxy_url=configuration.proxy,
                timeout=5,
                **addition_pool_args)
        else:
            self.pool_manager = urllib3.PoolManager(
                num_pools=pools_size,
                maxsize=maxsize,
                cert_reqs=cert_reqs,
                ca_certs=ca_certs,
                cert_file=configuration.cert_file,
                key_file=configuration.key_file,
                timeout=5,
                **addition_pool_args)
        return self.pool_manager

    def _get(self, url, headers, body=None, *args, **kwargs):
        if body is not None:
            response, content = self._request(url, 'GET', headers=headers, body=body, *args, **kwargs)
        else:
            response, content = self._request(url, 'GET', headers=headers, *args, **kwargs)
        preload_content = kwargs.get("preload_content")
        if preload_content is False:
            return response, None
        res, body = self._check_status(url, 'GET', response, content)
        return res, body

    def _post(self, url, headers, body=None, *args, **kwargs):
        if body is not None:
            response, content = self._request(url, 'POST', headers=headers, body=body, *args, **kwargs)
        else:
            response, content = self._request(url, 'POST', headers=headers, *args, **kwargs)
        res, body = self._check_status(url, 'POST', response, content)
        return res, body

    def _put(self, url, headers, body=None, *args, **kwargs):
        if body is not None:
            response, content = self._request(url, 'PUT', headers=headers, body=body, *args, **kwargs)
        else:
            response, content = self._request(url, 'PUT', headers=headers, *args, **kwargs)
        res, body = self._check_status(url, 'PUT', response, content)
        return res, body

    def _delete(self, url, headers, body=None, *args, **kwargs):
        if body is not None:
            response, content = self._request(url, 'DELETE', headers=headers, body=body, *args, **kwargs)
        else:
            response, content = self._request(url, 'DELETE', headers=headers, *args, **kwargs)
        res, body = self._check_status(url, 'DELETE', response, content)
        return res, body

    def proxy(self, request, url, region_name, requests_args=None):
        """
        Forward as close to an exact copy of the request as possible along to the
        given url.  Respond with as close to an exact copy of the resulting
        response as possible.
        If there are any additional arguments you wish to send to requests, put
        them in the requests_args dictionary.
        """
        requests_args = (requests_args or {}).copy()
        headers = self.get_headers(request.META)

        if 'headers' not in requests_args:
            requests_args['headers'] = {}
        if 'body' not in requests_args:
            requests_args['body'] = request.body
        if 'fields' not in requests_args:
            requests_args['fields'] = Dict('', mutable=True)

        # Overwrite any headers and params from the incoming request with explicitly
        # specified values for the requests library.
        headers.update(requests_args['headers'])

        # If there's a content-length header from Django, it's probably in all-caps
        # and requests might not notice it, so just remove it.
        for key in list(headers.keys()):
            if key.lower() == 'content-length':
                del headers[key]

        requests_args['headers'] = headers

        region = region_repo.get_region_by_region_name(region_name)
        if not region:
            raise ServiceHandleException("region {0} not found".format(region_name), error_code=10412)
        client = self.get_client(region_config=region)
        response = client.request(method=request.method, timeout=20, url="{}{}".format(region.url, url), **requests_args)

        from fastapi.responses import JSONResponse
        proxy_response = JSONResponse(response.data, status_code=response.status)

        excluded_headers = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
                            'transfer-encoding', 'upgrade', 'content-encoding', 'content-length'}
        for key, value in list(response.headers.items()):
            if key.lower() in excluded_headers:
                continue
            elif key.lower() == 'location':
                # If the location is relative at all, we want it to be absolute to
                # the upstream server.
                proxy_response[key] = self.make_absolute_location(response.url, value)
            else:
                proxy_response[key] = value

        return proxy_response

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

    def handle_error(self, body):
        region_bcode = json.loads(body)
        if "code" in region_bcode:
            raise ServiceHandleException(
                msg=region_bcode.get("msg"), status_code=region_bcode.get("status"), error_code=region_bcode.get("code"))
        logger.error("request api failure, response body is {}".format(body))
        raise ServiceHandleException(msg="request region api failure", status_code=500, error_code=10411)



class RegionInvokeApi(RegionApiBaseHttpClient):
    def __init__(self, *args, **kwargs):
        RegionApiBaseHttpClient.__init__(self, *args, **kwargs)
        self.default_headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def make_proxy_http(self, region_service_info):
        proxy_info = region_service_info['proxy']
        if proxy_info['type'] == 'http':
            proxy_type = httplib2.socks.PROXY_TYPE_HTTP_NO_TUNNEL
        else:
            raise TypeError("unsupport type: %s" % proxy_info['type'])

        proxy = httplib2.ProxyInfo(proxy_type, proxy_info['host'], proxy_info['port'])
        client = httplib2.Http(proxy_info=proxy, timeout=25)
        return client

    def _set_headers(self, token):
        if settings.MODULES["RegionToken"]:
            if not token:
                if os.environ.get('REGION_TOKEN'):
                    self.default_headers.update({"Authorization": os.environ.get('REGION_TOKEN')})
                else:
                    self.default_headers.update({"Authorization": ""})
            else:
                self.default_headers.update({"Authorization": token})
        # logger.debug('Default headers: {0}'.format(self.default_headers))

    def __get_env_region_info(self, tenant_name, region):
        if type(tenant_name) == TeamEnvInfo:
            tenant_name = tenant_name.tenant_name
        tenants = TeamEnvInfo.objects.filter(tenant_name=tenant_name)
        if tenants:
            tenant = tenants[0]
            tenant_regions = EnvRegionInfo.objects.filter(tenant_id=tenant.tenant_id, region_name=region)
            if not tenant_regions:
                logger.error("tenant {0} is not init in region {1}".format(tenant_name, region))
                raise http.Http404
        else:
            logger.error("team {0} is not found!".format(tenant_name))
            raise http.Http404
        return tenant_regions[0]

    def get_tenant_resources(self, region, tenant_name, enterprise_id):
        """获取指定租户的资源使用情况"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/resources?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10)
        return body

    def get_region_publickey(self, tenant_name, region, enterprise_id, tenant_id):
        url, token = self.__get_region_access_info(tenant_name, region)
        url += "/v2/builder/publickey/" + tenant_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def create_tenant(self, region, tenant_name, tenant_id, enterprise_id):
        """创建租户"""
        url, token = self.__get_region_access_info(tenant_name, region)
        data = {"tenant_id": tenant_id, "tenant_name": tenant_name, "eid": enterprise_id}
        url += "/v2/tenants"

        self._set_headers(token)
        logger.debug("create tenant url :{0}".format(url))
        try:
            res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
            return res, body
        except RegionApiBaseHttpClient.CallApiError as e:
            return {'status': e.message['httpcode']}, e.message['body']

    def delete_tenant(self, region, tenant_name):
        """删除组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def create_service(self, region, tenant_name, body):
        """创建组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_service_info(self, region, tenant_name, service_alias):
        """获取组件信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def update_service(self, region, tenant_name, service_alias, body):
        """更新组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service(self, region, tenant_name, service_alias, enterprise_id, data=None):
        """删除组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "?enterprise_id=" + enterprise_id

        self._set_headers(token)
        if not data:
            data = {}
        res, body = self._delete(url, self.default_headers, region=region, body=json.dumps(data))
        return body

    def build_service(self, region, tenant_name, service_alias, body):
        """组件构建"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/build"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def code_check(self, region, tenant_name, body):
        """发送代码检测消息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/code-check"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_service_language(self, region, service_id, tenant_name):
        """获取组件语言"""

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/builder/codecheck/service/{0}".format(service_id)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def add_service_dependency(self, region, tenant_name, service_alias, body):
        """增加组件依赖"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/dependency"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service_dependency(self, region, tenant_name, service_alias, body):
        """取消组件依赖"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/dependency"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def add_service_env(self, region, tenant_name, service_alias, body):
        """添加环境变量"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service_env(self, region, tenant_name, service_alias, body):
        """删除环境变量"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        # 更新tenant_id 为数据中心tenant_id
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def update_service_env(self, region, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def horizontal_upgrade(self, region, tenant_name, service_alias, body):
        """组件水平伸缩"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/horizontal"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def vertical_upgrade(self, region, tenant_name, service_alias, body):
        """组件垂直伸缩"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/vertical"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def change_memory(self, region, tenant_name, service_alias, body):
        """根据组件语言设置内存"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/language"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_region_labels(self, region, tenant_name):
        """获取数据中心可用的标签"""

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/resources/labels"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def addServiceNodeLabel(self, region, tenant_name, service_alias, body):
        """添加组件对应的节点标签"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def deleteServiceNodeLabel(self, region, tenant_name, service_alias, body):
        """删除组件对应的节点标签"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def add_service_state_label(self, region, tenant_name, service_alias, body):
        """添加组件有无状态标签"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, body, region=region)
        return body

    def update_service_state_label(self, region, tenant_name, service_alias, body):
        """修改组件有无状态标签"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def get_service_pods(self, region, tenant_name, service_alias, enterprise_id):
        """获取组件pod信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/pods?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, None, region=region, timeout=15)
        return body

    def get_dynamic_services_pods(self, region, tenant_name, services_ids):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/pods?service_ids={}".format(",".join(services_ids))
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=15)
        return body

    def pod_detail(self, region, tenant_name, service_alias, pod_name):
        """获取组件pod信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/pods/" + pod_name + "/detail"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, None, region=region)
        return body

    def add_service_port(self, region, tenant_name, service_alias, body):
        """添加组件端口"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        port_list = body["port"]
        for port in port_list:
            port["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/ports"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_service_port(self, region, tenant_name, service_alias, body):
        """更新组件端口"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        port_list = body["port"]
        for port in port_list:
            port["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/ports"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_service_port(self, region, tenant_name, service_alias, port, enterprise_id, body={}):
        """删除组件端口"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/ports/" + str(
            port) + "?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def manage_inner_port(self, region, tenant_name, service_alias, port, body):
        """打开关闭对内端口"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/ports/" + str(
            port) + "/inner"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def manage_outer_port(self, region, tenant_name, service_alias, port, body):
        """打开关闭对外端口"""
        try:
            url, token = self.__get_region_access_info(tenant_name, region)
            tenant_region = self.__get_env_region_info(tenant_name, region)
            url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/ports/" + str(
                port) + "/outer"

            self._set_headers(token)
            res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
            return body
        except RegionApiBaseHttpClient.CallApiError as e:
            message = e.body.get("msg")
            if message and message.find("do not allow operate outer port for thirdpart domain endpoints") >= 0:
                raise ServiceHandleException(
                    status_code=400,
                    msg="do not allow operate outer port for thirdpart domain endpoints",
                    msg_show="该第三方组件具有域名类实例，暂不支持开放网关访问")
            else:
                raise e

    def update_service_probec(self, region, tenant_name, service_alias, body):
        """更新组件探针信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def add_service_probe(self, region, tenant_name, service_alias, body):
        """添加组件探针信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_probe(self, region, tenant_name, service_alias, body):
        """删除组件探针信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def restart_service(self, region, tenant_name, service_alias, body):
        """重启组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/restart"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def rollback(self, region, tenant_name, service_alias, body):
        """组件版本回滚"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/rollback"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def start_service(self, region, tenant_name, service_alias, body):
        """启动组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/start"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def stop_service(self, region, tenant_name, service_alias, body):
        """关闭组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/stop"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def upgrade_service(self, region, tenant_name, service_alias, body):
        """升级组件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/upgrade"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def check_service_status(self, region, tenant_name, service_alias, enterprise_id):
        """获取单个组件状态"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/status?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_volume_options(self, region, tenant_name):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        url = uri_prefix + "/v2/volume-options"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_service_volumes_status(self, region, tenant_name, service_alias):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/volumes-status".format(tenant_name, service_alias)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_service_volumes(self, region, tenant_name, service_alias, enterprise_id):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/volumes?enterprise_id={2}".format(
            tenant_name, service_alias, enterprise_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def add_service_volumes(self, region, tenant_name, service_alias, body):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/volumes".format(tenant_name, service_alias)
        self._set_headers(token)
        return self._post(url, self.default_headers, json.dumps(body), region=region)

    def delete_service_volumes(self, region, tenant_name, service_alias, volume_name, enterprise_id, body={}):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/volumes/{2}?enterprise_id={3}".format(
            tenant_name, service_alias, volume_name, enterprise_id)
        self._set_headers(token)
        return self._delete(url, self.default_headers, json.dumps(body), region=region)

    def upgrade_service_volumes(self, region, tenant_name, service_alias, body):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/volumes".format(tenant_name, service_alias)
        self._set_headers(token)
        return self._put(url, self.default_headers, json.dumps(body), region=region)

    def get_service_dep_volumes(self, region, tenant_name, service_alias, enterprise_id):
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/depvolumes?enterprise_id={2}".format(
            tenant_name, service_alias, enterprise_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def add_service_dep_volumes(self, region, tenant_name, service_alias, body):
        """ Add dependent volumes """
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/depvolumes".format(tenant_name, service_alias)
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_dep_volumes(self, region, tenant_name, service_alias, body):
        """ Delete dependent volume"""
        uri_prefix, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        tenant_name = tenant_region.region_tenant_name
        url = uri_prefix + "/v2/tenants/{0}/services/{1}/depvolumes".format(tenant_name, service_alias)
        self._set_headers(token)
        return self._delete(url, self.default_headers, json.dumps(body), region=region)

    def add_service_volume(self, region, tenant_name, service_alias, body):
        """添加组件持久化目录"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/volume"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_volume(self, region, tenant_name, service_alias, body):
        """删除组件持久化目录"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/volume"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def add_service_volume_dependency(self, region, tenant_name, service_alias, body):
        """添加组件持久化挂载依赖"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/volume-dependency"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_service_volume_dependency(self, region, tenant_name, service_alias, body):
        """删除组件持久化挂载依赖"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/volume-dependency"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def service_status(self, region, tenant_name, body):
        """获取多个组件的状态"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services_status"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body), timeout=20)
        return body

    def get_enterprise_running_services(self, enterprise_id, region, test=False):
        if test:
            self.get_enterprise_api_version_v2(enterprise_id, region=region)
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url = url + "/v2/enterprise/" + enterprise_id + "/running-services"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10)
        if res.get("status") == 200 and isinstance(body, dict):
            return body
        return None

    def get_docker_log_instance(self, region, tenant_name, service_alias, enterprise_id):
        """获取日志实体"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/log-instance?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_service_logs(self, region, tenant_name, service_alias, rows):
        """获取组件日志"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/{0}/services/{1}/logs?rows={2}".format(tenant_region.region_tenant_name, service_alias, rows)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_service_log_files(self, region, tenant_name, service_alias, enterprise_id):
        """获取组件日志文件列表"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/log-file?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_event_log(self, region, tenant_name, service_alias, body):
        """获取事件日志"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/event-log"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body), timeout=10)
        return res, body

    def get_target_events_list(self, region, tenant_name, target, target_id, page, page_size):
        """获取作用对象事件日志列表"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/events" + "?target={0}&target-id={1}&page={2}&size={3}".format(target, target_id, page, page_size)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=20)
        return res, body

    def get_events_log(self, tenant_name, region, event_id):
        """获取作用对象事件日志内容"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/events/" + event_id + "/log"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_api_version(self, url, token, region):
        """获取api版本"""
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_api_version_v2(self, tenant_name, region_name):
        """获取api版本-v2"""
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return res, body

    def get_enterprise_api_version_v2(self, enterprise_id, region, **kwargs):
        """获取api版本-v2"""
        kwargs["retries"] = 1
        kwargs["timeout"] = 1
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, **kwargs)
        return res, body

    def get_region_tenants_resources(self, region, data, enterprise_id=""):
        """获取租户在数据中心下的资源使用情况"""
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url += "/v2/resources/tenants"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(data), region=region, timeout=15.0)
        return body

    def get_service_resources(self, tenant_name, region, data):
        """获取一批组件的资源使用情况"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url += "/v2/resources/services"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(data), region=region, timeout=10.0)
        return body

    # v3.5版本后弃用
    def share_clound_service(self, region, tenant_name, body):
        """分享应用到云市"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/cloud-share"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    # v3.5版本新加可用
    def share_service(self, region, tenant_name, service_alias, body):
        """分享应用"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = "{0}/v2/tenants/{1}/services/{2}/share".format(url, tenant_region.region_tenant_name, service_alias)
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def share_service_result(self, region, tenant_name, service_alias, region_share_id):
        """查询分享应用状态"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = "{0}/v2/tenants/{1}/services/{2}/share/{3}".format(url, tenant_region.region_tenant_name, service_alias,
                                                                 region_share_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def share_plugin(self, region_name, tenant_name, plugin_id, body):
        """分享插件"""
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = "{0}/v2/tenants/{1}/plugins/{2}/share".format(url, tenant_region.region_tenant_name, plugin_id)
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return res, body

    def share_plugin_result(self, region_name, tenant_name, plugin_id, region_share_id):
        """查询分享插件状态"""
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = "{0}/v2/tenants/{1}/plugins/{2}/share/{3}".format(url, tenant_region.region_tenant_name, plugin_id,
                                                                region_share_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return res, body

    def bindDomain(self, region, tenant_name, service_alias, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/domains"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbindDomain(self, region, tenant_name, service_alias, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/domains/" + \
            body["domain"]
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def bind_http_domain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_http_domain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_http_domain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_name + "/http-rule"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def bindTcpDomain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def updateTcpDomain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        return body

    def unbindTcpDomain(self, region, tenant_name, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_name + "/tcp-rule"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, json.dumps(body), region=region)
        return body

    def get_port(self, region, tenant_name, lock=False):
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/gateway/ports?lock={}".format(lock)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_ips(self, region, tenant_name):
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/gateway/ips"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def pluginServiceRelation(self, region, tenant_name, service_alias, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        return self._post(url, self.default_headers, json.dumps(body), region=region)

    def delPluginServiceRelation(self, region, tenant_name, plugin_id, service_alias):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin/" + plugin_id

        self._set_headers(token)
        return self._delete(url, self.default_headers, None, region=region)

    def updatePluginServiceRelation(self, region, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)

        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        return self._put(url, self.default_headers, json.dumps(body), region=region)

    def postPluginAttr(self, region, tenant_name, service_alias, plugin_id, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin/" \
            + plugin_id + "/setenv"

        self._set_headers(token)
        return self._post(url, self.default_headers, json.dumps(body), region=region)

    def putPluginAttr(self, region, tenant_name, service_alias, plugin_id, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)

        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/plugin/" + plugin_id + "/upenv"

        self._set_headers(token)
        return self._put(url, self.default_headers, json.dumps(body), region=region)

    def create_plugin(self, region, tenant_name, body):
        """创建数据中心端插件"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/plugin"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def build_plugin(self, region, tenant_name, plugin_id, body):
        """创建数据中心端插件"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/{0}/plugin/{1}/build".format(tenant_region.region_tenant_name, plugin_id)

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def get_build_status(self, region, tenant_name, plugin_id, build_version):
        """获取插件构建状态"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/{0}/plugin/{1}/build-version/{2}".format(tenant_region.region_tenant_name, plugin_id,
                                                                          build_version)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_plugin_event_log(self, region, tenant_name, data):
        """获取插件日志信息"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/{0}/event-log".format(tenant_region.region_tenant_name)
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(data), region=region)
        return body

    def delete_plugin_version(self, region, tenant_name, plugin_id, build_version):
        """删除插件某个版本信息"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)

        url = url + "/v2/tenants/{0}/plugin/{1}/build-version/{2}".format(tenant_region.region_tenant_name, plugin_id,
                                                                          build_version)

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def get_query_data(self, region, tenant_name, params):
        """获取监控数据"""

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_service_access(self, region, tenant_name, params):
        """获取团队下组件访问量排序"""

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_domain_access(self, region, tenant_name, params):
        """获取团队下域名访问量排序"""

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_range_data(self, region, tenant_name, params):
        """获取监控范围数据"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/api/v1/query_range" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_service_publish_status(self, region, tenant_name, service_key, app_version):

        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/builder/publish/service/{0}/version/{1}".format(service_key, app_version)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_tenant_events(self, region, tenant_name, event_ids):
        """获取多个事件的状态"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/event"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, body=json.dumps({"event_ids": event_ids}), timeout=10)
        return body

    def get_events_by_event_ids(self, region_name, event_ids):
        """获取多个event的事件"""
        region_info = self.get_region_info(region_name)
        url = region_info.url + "/v2/event"
        self._set_headers(region_info.token)
        res, body = self._get(
            url, self.default_headers, region=region_name, body=json.dumps({"event_ids": event_ids}), timeout=10)
        return body

    def __get_region_access_info(self, tenant_name, region):
        """获取一个团队在指定数据中心的身份认证信息"""
        # 如果团队所在企业所属数据中心信息不存在则使用通用的配置(兼容未申请数据中心token的企业)
        # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
        region_info = self.get_region_info(region_name=region)
        if region_info is None:
            raise ServiceHandleException("region not found")
        url = region_info.url
        token = region_info.token
        return url, token

    def __get_region_access_info_by_enterprise_id(self, enterprise_id, region):
        # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
        region_info = self.get_region_info(region_name=region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        token = region_info.token
        return url, token

    def get_protocols(self, region, tenant_name):
        """
        @ 获取当前数据中心支持的协议
        """
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/protocols"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def get_region_info(self, region_name):
        configs = RegionConfig.objects.filter(region_name=region_name)
        if configs:
            return configs[0]
        return None

    def get_enterprise_region_info(self, eid, region):
        configs = RegionConfig.objects.filter(enterprise_id=eid, region_name=region)
        if configs:
            return configs[0]
        else:
            configs = RegionConfig.objects.filter(enterprise_id=eid, region_id=region)
            if configs:
                return configs[0]
        return None

    def service_source_check(self, region, tenant_name, body):
        """组件源检测"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/servicecheck"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def get_service_check_info(self, region, tenant_name, uuid):
        """组件源检测信息获取"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/servicecheck/" + str(uuid)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def service_chargesverify(self, region, tenant_name, data):
        """组件扩大资源申请接口"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + \
            "/chargesverify?quantity={0}&reason={1}&eid={2}".format(data["quantity"], data["reason"], data["eid"])
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def update_plugin_info(self, region, tenant_name, plugin_id, data):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url += "/v2/tenants/{0}/plugin/{1}".format(tenant_region.region_tenant_name, plugin_id)
        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(data), region=region)
        return body

    def delete_plugin(self, region, tenant_name, plugin_id):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url += "/v2/tenants/{0}/plugin/{1}".format(tenant_region.region_tenant_name, plugin_id)
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def install_service_plugin(self, region, tenant_name, service_alias, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        return self._post(url, self.default_headers, json.dumps(body), region=region)

    def uninstall_service_plugin(self, region, tenant_name, plugin_id, service_alias, body={}):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin/" + plugin_id
        self._set_headers(token)
        return self._delete(url, self.default_headers, json.dumps(body), region=region)

    def update_plugin_service_relation(self, region, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)

        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        return self._put(url, self.default_headers, json.dumps(body), region=region)

    def update_service_plugin_config(self, region, tenant_name, service_alias, plugin_id, body):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)

        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/plugin/" + plugin_id + "/upenv"

        self._set_headers(token)
        return self._put(url, self.default_headers, json.dumps(body), region=region)

    def get_services_pods(self, region, tenant_name, service_id_list, enterprise_id):
        """获取多个组件的pod信息"""
        service_ids = ",".join(service_id_list)
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/pods?enterprise_id=" \
            + enterprise_id + "&service_ids=" + service_ids

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, None, region=region, timeout=10)
        return body

    def export_app(self, region, enterprise_id, data):
        """导出应用"""
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url += "/v2/app/export"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data).encode('utf-8'))
        return res, body

    def get_app_export_status(self, region, enterprise_id, event_id):
        """查询应用导出状态"""
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url = url + "/v2/app/export/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def import_app_2_enterprise(self, region, enterprise_id, data):
        """ import app to enterprise"""
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region)
        url += "/v2/app/import"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def import_app(self, region, tenant_name, data):
        """导入应用"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url += "/v2/app/import"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def get_app_import_status(self, region, tenant_name, event_id):
        """查询导入状态"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_enterprise_app_import_status(self, region, eid, event_id):
        url, token = self.__get_region_access_info_by_enterprise_id(eid, region)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_enterprise_import_file_dir(self, region, eid, event_id):
        url, token = self.__get_region_access_info_by_enterprise_id(eid, region)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_import_file_dir(self, region, tenant_name, event_id):
        """查询导入目录"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def delete_enterprise_import(self, region, eid, event_id):
        url, token = self.__get_region_access_info_by_enterprise_id(eid, region)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def delete_import(self, region, tenant_name, event_id):
        """删除导入"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def create_import_file_dir(self, region, tenant_name, event_id):
        """创建导入目录"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region)
        return res, body

    def delete_enterprise_import_file_dir(self, region, eid, event_id):
        url, token = self.__get_region_access_info_by_enterprise_id(eid, region)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def delete_import_file_dir(self, region, tenant_name, event_id):
        """删除导入目录"""
        url, token = self.__get_region_access_info(tenant_name, region)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def backup_group_apps(self, region, tenant_name, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_backup_status_by_backup_id(self, region, tenant_name, backup_id):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + str(backup_id)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def delete_backup_by_backup_id(self, region, tenant_name, backup_id):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + str(backup_id)

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def get_backup_status_by_group_id(self, region, tenant_name, group_uuid):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups?group_id=" + str(group_uuid)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def star_apps_migrate_task(self, region, tenant_name, backup_id, data):
        """发起迁移命令"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + backup_id + "/restore"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return body

    def get_apps_migrate_status(self, region, tenant_name, backup_id, restore_id):
        """获取迁移结果"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" \
            + backup_id + "/restore/" + restore_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def copy_backup_data(self, region, tenant_name, data):
        """数据中心备份数据进行拷贝"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backupcopy"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return body

    def get_service_build_versions(self, region, tenant_name, service_alias):
        """获取组件的构建版本"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/build-list"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def delete_service_build_version(self, region, tenant_name, service_alias, version_id):
        """删除组件的某次构建版本"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/build-version/" + version_id

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def get_service_build_version_by_id(self, region, tenant_name, service_alias, version_id):
        """查询组件的某次构建版本"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
            + service_alias + "/build-version/" + version_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_env_services_deploy_version(self, region, tenant_name, data):
        """查询指定组件的部署版本"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/deployversions"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def get_service_deploy_version(self, region, tenant_name, service_alias):
        """查询指定组件的部署版本"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/deployversions"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 获取数据中心应用异常信息

    def get_app_abnormal(self, url, token, region, start_stamp, end_stamp):
        url += "/v2/notificationEvent?start={0}&end={1}".format(start_stamp, end_stamp)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 第三方注册api注册方式添加endpoints
    def put_third_party_service_endpoints(self, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方注册api注册方式添加endpoints
    def post_third_party_service_endpoints(self, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方注册api注册方式添加endpoints
    def delete_third_party_service_endpoints(self, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方组件endpoint数据
    def get_third_party_service_pods(self, region, tenant_name, service_alias):
        """获取第三方组件endpoint数据"""
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 获取第三方组件健康检测信息
    def get_third_party_service_health(self, region, tenant_name, service_alias):

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/3rd-party/probe"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 修改第三方组件健康检测信息
    def put_third_party_service_health(self, region, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/3rd-party/probe"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    # 5.1版本组件批量操作
    def batch_operation_service(self, region, tenant_name, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/batchoperation"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    # 修改网关自定义配置项
    def upgrade_configuration(self, region, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/rule-config"
        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        logger.debug('-------1111--body----->{0}'.format(body))
        return res, body

    def restore_properties(self, region, tenant_name, service_alias, uri, body):
        """When the upgrade fails, restore the properties of the service"""

        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + uri

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body

    def list_scaling_records(self, region, tenant_name, service_alias, page=None, page_size=None):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparecords"

        if page is not None and page_size is not None:
            url = url + "?page={}&page_size={}".format(page, page_size)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def create_xpa_rule(self, region, tenant_name, service_alias, data):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparules"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, body=json.dumps(data), region=region)
        return body

    def update_xpa_rule(self, region, tenant_name, service_alias, data):
        url, token = self.__get_region_access_info(tenant_name, region)
        tenant_region = self.__get_env_region_info(tenant_name, region)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparules"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(data), region=region)
        return body

    def update_ingresses_by_certificate(self, region_name, tenant_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + region.region_tenant_name + "/gateway/certificate"
        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(body), region=region_name)
        return res, body

    def get_region_resources(self, enterprise_id, **kwargs):
        region_name = kwargs.get("region")
        if kwargs.get("test"):
            self.get_enterprise_api_version_v2(enterprise_id, region=region_name)
        url, token = self.__get_region_access_info_by_enterprise_id(enterprise_id, region_name)
        url = url + "/v2/cluster"
        self._set_headers(token)
        kwargs["retries"] = 1
        kwargs["timeout"] = 3
        res, body = self._get(url, self.default_headers, **kwargs)
        return res, body

    def test_region_api(self, region_data):
        region = RegionConfig(**region_data)
        url = region.url + "/v2/show"
        return self._get(url, self.default_headers, region=region, for_test=True, retries=1, timeout=1)

    def check_region_api(self, enterprise_id, region):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        try:
            url = region_info.url + "/v2/show"
            _, body = self._get(url, self.default_headers, region=region_info.region_name, retries=1, timeout=1)
            return body
        except Exception as e:
            logger.exception(e)
            return None

    def list_tenants(self, enterprise_id, region, page=1, page_size=10):
        """list tenants"""
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants?page={0}&pageSize={1}&eid={2}".format(page, page_size, enterprise_id)
        try:
            res, body = self._get(url, self.default_headers, region=region_info.region_name)
            return res, body
        except RegionApiBaseHttpClient.CallApiError as e:
            return {'status': e.message['httpcode']}, e.message['body']

    def set_tenant_env_limit_memory(self, enterprise_id, tenant_name, region, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/limit_memory".format(tenant_name)
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def create_service_monitor(self, enterprise_id, region, tenant_name, service_alias, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors".format(tenant_name, service_alias)
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def update_service_monitor(self, enterprise_id, region, tenant_name, service_alias, name, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors/{2}".format(tenant_name, service_alias, name)
        res, body = self._put(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def delete_service_monitor(self, enterprise_id, region, tenant_name, service_alias, name, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors/{2}".format(tenant_name, service_alias, name)
        res, body = self._delete(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))

    def delete_maven_setting(self, enterprise_id, region, name):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._delete(url, self.default_headers, region=region_info.region_name)
        return res, body

    def add_maven_setting(self, enterprise_id, region, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting"
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def get_maven_setting(self, enterprise_id, region, name):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._get(url, self.default_headers, region=region_info.region_name)
        return res, body

    def update_maven_setting(self, enterprise_id, region, name, body):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._put(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def list_maven_settings(self, enterprise_id, region):
        region_info = self.get_enterprise_region_info(enterprise_id, region)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting"
        res, body = self._get(url, self.default_headers, region=region_info.region_name)
        return res, body

    def update_app_ports(self, region_name, tenant_name, app_id, data):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/ports"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(data), region=region_name)
        return body

    def get_app_status(self, region_name, tenant_name, region_app_id):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/status"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name)
        return body["bean"]

    def get_app_detect_process(self, region_name, tenant_name, region_app_id):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/detect-process"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]

    def get_pod(self, region_name, tenant_name, pod_name):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/pods/" + pod_name

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body["bean"]

    def install_app(self, region_name, tenant_name, region_app_id, data):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/install"

        self._set_headers(token)
        _, _ = self._post(url, self.default_headers, region=region_name, body=json.dumps(data))

    def list_app_services(self, region_name, tenant_name, region_app_id):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + region_app_id + "/services"

        self._set_headers(token)
        _, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]

    def create_application(self, region_name, tenant_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_create_application(self, region_name, tenant_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/batch_create_apps"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("list", None)

    def update_service_app_id(self, region_name, tenant_name, service_alias, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def batch_update_service_app_id(self, region_name, tenant_name, app_id, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/services"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app(self, region_name, tenant_name, app_id, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def create_app_config_group(self, region_name, tenant_name, app_id, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def update_app_config_group(self, region_name, tenant_name, app_id, config_group_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region_name, body=json.dumps(body))
        return body.get("bean", None)

    def delete_app(self, region_name, tenant_name, app_id, data={}):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id

        self._set_headers(token)
        _, _ = self._delete(url, self.default_headers, region=region_name, body=json.dumps(data))

    def delete_app_config_group(self, region_name, tenant_name, app_id, config_group_name):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/configgroups/" + config_group_name

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region_name)
        return res, body

    def get_monitor_metrics(self, region_name, tenant, target, app_id, component_id):
        url, token = self.__get_region_access_info(tenant.tenant_name, region_name)
        url = url + "/v2/monitor/metrics?target={target}&tenant={tenant_id}&app={app_id}&component={component_id}".format(
            target=target, tenant_id=tenant.tenant_id, app_id=app_id, component_id=component_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body

    def check_resource_name(self, tenant_name, region_name, rtype, name):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/checkResourceName"

        self._set_headers(token)
        _, body = self._post(
            url, self.default_headers, region=region_name, body=json.dumps({
                "type": rtype,
                "name": name,
            }))
        return body["bean"]

    def parse_app_services(self, region_name, tenant_name, app_id, values):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/parse-services"

        self._set_headers(token)
        _, body = self._post(
            url, self.default_headers, region=region_name, body=json.dumps({
                "values": values,
            }))
        return body["list"]

    def list_app_releases(self, region_name, tenant_name, app_id):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        tenant_region = self.__get_env_region_info(tenant_name, region_name)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/apps/" + app_id + "/releases"

        self._set_headers(token)
        _, body = self._get(url, self.default_headers, region=region_name)
        return body["list"]

    def sync_components(self, tenant_name, region_name, app_id, components):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url = url + "/v2/tenants/{tenant_name}/apps/{app_id}/components".format(tenant_name=tenant_name, app_id=app_id)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(components), region=region_name)

    def sync_config_groups(self, tenant_name, region_name, app_id, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url = url + "/v2/tenants/{tenant_name}/apps/{app_id}/app-config-groups".format(tenant_name=tenant_name, app_id=app_id)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(body), region=region_name)

    def sync_plugins(self, tenant_name, region_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url = url + "/v2/tenants/{tenant_name}/plugins".format(tenant_name=tenant_name)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(body), region=region_name)

    def build_plugins(self, tenant_name, region_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url = url + "/v2/tenants/{tenant_name}/batch-build-plugins".format(tenant_name=tenant_name)
        self._set_headers(token)
        self._post(url, self.default_headers, body=json.dumps(body), region=region_name)

    def get_region_license_feature(self, tenant: TeamEnvInfo, region_name):
        url, token = self.__get_region_access_info(tenant.tenant_name, region_name)
        url = url + "/license/features"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body

    def list_app_statuses_by_app_ids(self, tenant_name, region_name, body):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        url = url + "/v2/tenants/{tenant_name}/appstatuses".format(tenant_name=tenant_name)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, body=json.dumps(body), region=region_name)
        return body

    def get_component_log(self, tenant_name, region_name, service_alias, pod_name, container_name, follow=False):
        url, token = self.__get_region_access_info(tenant_name, region_name)
        follow = "true" if follow else "false"
        url = url + "/v2/tenants/{}/services/{}/log?podName={}&containerName={}&follow={}".format(
            tenant_name, service_alias, pod_name, container_name, follow)
        self._set_headers(token)
        resp, _ = self._get(url, self._set_headers(token), region=region_name, preload_content=False)
        return resp
