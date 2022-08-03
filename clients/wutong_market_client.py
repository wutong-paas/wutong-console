import base64
import hmac
import json
import os
import random
import socket
import ssl
import string
import time
from hashlib import sha1
from urllib.parse import urlencode, quote

import certifi
import urllib3
from addict import Dict
from fastapi.encoders import jsonable_encoder
from loguru import logger
from urllib3.exceptions import MaxRetryError

from common.api_base_http_client import _json_decode
from exceptions.main import ServiceHandleException, AbortRequest
from models.market.models import AppMarket


def encode_params(params: dict, secret: str, method, sorted_dict_body: dict = None):
    # 参数排序
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sorted_params = dict(sorted_params)
    logger.info("参数排序,before:{},after:{}", params, sorted_params)

    # URLEncode编码 拼接
    param_str = urlencode(sorted_params)
    logger.info("请求参数编码拼接:{}", param_str)
    if sorted_dict_body:
        param_body_str = param_str + "&body=" + json.dumps(sorted_dict_body)
        param_encode_str = quote(param_body_str.replace(" ", ""), safe="")
    else:
        param_encode_str = quote(param_str)
    logger.info("请求参数编码,before:{},after:{}", param_str, param_encode_str)

    # 加签
    code_str = method + "&%2F&" + param_encode_str
    code_str = code_str.replace("+", "%20").replace("*", "%2A").replace("%7E", "~")
    sign_str = hash_hmac(secret=secret, code=code_str)
    logger.info("参数加签,参数:{},加签:{}", code_str, sign_str)

    return sign_str, param_str


def hash_hmac(secret, code):
    hmac_code = hmac.new(secret.encode(), code.encode(), sha1).digest()
    return base64.b64encode(hmac_code).decode()


def build_sign_params(access_key):
    params = {
        "SignatureVersion": "1.0",
        "SignatureNonce": ''.join(random.sample(string.ascii_letters + string.digits, 8)),
        "SignatureMethod": "HMAC-SHA1",
        "AccessKey": access_key,
        "Timestamp": time.strftime("%Y%m%d%H%M%S", time.localtime())
    }
    return params


def get_default_timeout_config():
    connect, red = 2.0, 5.0
    try:
        connect = float(os.environ.get("REGION_CONNECTION_TIMEOUT", 2.0))
        red = float(os.environ.get("REGION_RED_TIMEOUT", 5.0))
    except Exception:
        connect, red = 2.0, 5.0
    return connect, red


class Configuration():
    """
    Configuration
    """

    def __init__(self):
        """
        Constructor
        """
        # create new client
        self.verify_ssl = False

        self.ssl_ca_cert = None
        self.cert_file = None
        self.key_file = None

        self.assert_hostname = None

        self.connection_pool_maxsize = 20

        # Proxy URL
        self.proxy = None
        # Safe chars for path_param
        self.safe_chars_for_path_param = ''


class MarketHttpClient(object):
    class CallApiError(Exception):
        """
        CallApiError
        """

        def __init__(self, api_type, url, method, res, body, describe=None):
            self.message = {
                "api_type": api_type,
                "url": url,
                "method": method,
                "http_code": res.status,
                "body": body,
            }
            self.api_type = api_type
            self.url = url
            self.method = method
            self.body = body
            self.status = res.status

        def __str__(self):
            return json.dumps(jsonable_encoder(self.message))

    class CallApiFrequentError(Exception):
        """
        CallApiFrequentError
        """

        def __init__(self, api_type, url, method, res, body, describe=None):
            self.message = {
                "api_type": api_type,
                "url": url,
                "method": method,
                "http_code": res.status,
                "body": body,
            }
            self.api_type = api_type
            self.url = url
            self.method = method
            self.body = body
            self.status = res.status

        def __str__(self):
            return json.dumps(self.message)

    class InvalidLicenseError(Exception):
        """
        InvalidLicenseError
        """
        pass

    def __init__(self):
        self.timeout = 5
        # cache client
        self.clients = {}
        self.api_type = 'Not specified'

    def get_client(self):
        """

        :param region_config:
        :return:
        """
        # get client from cache
        # key = hash(region_config.url + region_config.ssl_ca_cert + region_config.cert_file + region_config.key_file)
        key = "wutong_market_http_client"
        client = self.clients.get(key, None)
        if client:
            return client
        config = Configuration()
        pools_size = int(os.environ.get("CLIENT_POOL_SIZE", 20))
        client = self.create_client(configuration=config, pools_size=pools_size)
        self.clients[key] = client
        return client

    def create_client(self, configuration, pools_size=4, maxsize=None):
        """

        :param configuration:
        :param pools_size:
        :param maxsize:
        :param args:
        :param kwargs:
        :return:
        """
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

    def destroy_client(self):
        """

        """
        self.clients["wutong_market_http_client"] = None

    def _check_status(self, url, method, status, content):
        body = None
        if content:
            body = _json_decode(content)
        res = Dict({"status": status})
        if isinstance(body, dict):
            body = Dict(body)
        if 400 <= status <= 600:
            if not body:
                raise ServiceHandleException(msg="resp body is nil", msg_show="HTTP请求返回为空", status_code=status)
            if status == 409:
                raise self.CallApiFrequentError(self.api_type, url, method, res, body)
            if status == 401:
                raise self.InvalidLicenseError()
            raise self.CallApiError(self.api_type, url, method, res, body)
        else:
            return res, body

    def _request(self, url, method, headers=None, body=None, **kwargs):
        retries = kwargs.get("retries", 2)
        d_connect, d_red = get_default_timeout_config()
        timeout = kwargs.get("timeout", d_red)
        preload_content = kwargs.get("preload_content")
        client = self.get_client()
        if not client:
            raise ServiceHandleException(
                msg="create wutong market api client failure", msg_show="创建梧桐市场通信客户端错误,请检查配置", error_code=10411)
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
            self.destroy_client()
            raise ServiceHandleException(error_code=10411, msg="SSLError", msg_show="访问数据中心异常，请稍后重试")
        except socket.timeout as e:
            raise self.CallApiError(self.api_type, url, method, Dict({"status": 101}), {
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

    def _get(self, url, headers, body=None, **kwargs):
        if body is not None:
            response, content = self._request(url, 'GET', headers=headers, body=body, **kwargs)
        else:
            response, content = self._request(url, 'GET', headers=headers, **kwargs)
        preload_content = kwargs.get("preload_content")
        if preload_content is False:
            return response, None
        logger.info("发送HTTP请求,method:{},url:{},header:{},response:{}", "GET", url, headers, content)
        res, body = self._check_status(url, 'GET', response, content)
        return res, body

    def _post(self, url, headers, body=None, **kwargs):
        if body is not None:
            response, content = self._request(url, 'POST', headers=headers, body=body, **kwargs)
        else:
            response, content = self._request(url, 'POST', headers=headers, **kwargs)
        res, res_body = self._check_status(url, 'POST', response, content)
        logger.info("发送HTTP请求,method:{},url:{},header:{},body:{},response:{}", "POST", url, headers, body, res_body)
        return res, res_body


class WutongMarketClient(MarketHttpClient):
    def __init__(self):
        MarketHttpClient.__init__(self)
        self.default_headers = {'Connection': 'keep-alive', 'Content-Type': 'application/json'}

    def check_store(self, url: str, access_key: str, access_secret: str):
        sign_str, param_str = encode_params(params=build_sign_params(access_key=access_key),
                                            secret=access_secret, method="GET")
        try:
            url += "?Signature=" + quote(sign_str) + "&" + param_str
            res, body = self._get(url, self.default_headers, timeout=10)
            if body.code == "0":
                return body.data
            else:
                logger.error("绑定店铺,校验失败,url:{},resp:{}", url, res)
                return False
        except MarketHttpClient.CallApiError as e:
            logger.error("远程校验店铺信息失败,error:{}", e)
            raise AbortRequest("远程校验店铺信息失败", "远程校验店铺信息失败",
                               status_code=500, error_code=500)
        except Exception as e:
            logger.error("远程校验店铺信息失败,error:{}", e)
            raise AbortRequest("远程校验店铺信息失败", "远程校验店铺信息失败", status_code=500, error_code=500)

    def get_market_apps(self, body: dict, market: AppMarket):
        # 参数排序
        sorted_body = dict(sorted(body.items(), key=lambda x: x[0]))
        # 编码
        sign_str, param_str = encode_params(params=build_sign_params(market.access_key), secret=market.access_secret,
                                            method="POST", sorted_dict_body=sorted_body)
        # 构建请求链接
        url = """{prefix}/{path}?Signature={signature}&{param_str}""".format(prefix=market.url,
                                                                             path="wutong-open-market-admin/app-info/page",
                                                                             signature=quote(sign_str),
                                                                             param_str=param_str)
        try:
            res, body = self._post(url, self.default_headers, body=json.dumps(sorted_body).replace(" ", ""))
            logger.info("查询商店应用,params:{},resp:{}", json.dumps(sorted_body), json.dumps(body))
            if body.code == "0":
                return body.data
            else:
                raise AbortRequest("获取远程商店应用列表失败", "获取远程商店应用列表失败", status_code=500, error_code=500)
        except MarketHttpClient.CallApiError as e:
            logger.error("获取远程商店应用列表失败,error:{}", e)
            raise AbortRequest("获取远程商店应用列表失败", "获取远程商店应用列表失败",
                               status_code=500, error_code=500)
        except Exception as e:
            logger.error("获取远程商店应用列表失败,error:{}", e)
            raise AbortRequest("获取远程商店应用列表失败", "获取远程商店应用列表失败", status_code=500, error_code=500)

    def get_market_app_detail(self, market: AppMarket, app_id: str):
        """获取梧桐商店应用详情"""
        sign_str, param_str = encode_params(params=build_sign_params(access_key=market.access_key),
                                            secret=market.access_secret, method="GET")
        url = """{prefix}/{path}/{app_id}?Signature={signature}&{param_str}""".format(prefix=market.url,
                                                                                      path="wutong-open-market-admin/app-info/detail",
                                                                                      app_id=app_id,
                                                                                      signature=quote(sign_str),
                                                                                      param_str=param_str)
        res, body = self._get(url, self.default_headers, timeout=10)
        if body.code == "0":
            return body.data
        else:
            return {"status": body.code, "error_message": body.msg}

    def push_local_app(self, param_body: dict, market: AppMarket, store_id: str):
        sorted_body = dict(sorted(param_body.items(), key=lambda x: x[0]))
        sign_str, param_str = encode_params(params=build_sign_params(market.access_key), secret=market.access_secret,
                                            method="POST", sorted_dict_body=sorted_body)
        url = """{prefix}/{path}/{store_id}?Signature={signature}&{param_str}""".format(prefix=market.url,
                                                                                        path="wutong-open-market-admin/app-info/addApp",
                                                                                        store_id=store_id,
                                                                                        signature=quote(sign_str),
                                                                                        param_str=param_str)
        try:
            res, body = self._post(url, self.default_headers, body=json.dumps(sorted_body).replace(" ", ""))
            logger.info("推送本地应用至远程仓库,params:{},resp:{}", json.dumps(sorted_body), json.dumps(body))
            if body.code == "0":
                return body.data
            else:
                raise AbortRequest("获取远程商店应用列表失败", "获取远程商店应用列表失败", status_code=500, error_code=500)
        except MarketHttpClient.CallApiError as e:
            logger.error("推送本地应用至远程仓库,HTTP请求失败,error:{}", e)
            raise AbortRequest("推送本地应用至远程仓库,HTTP请求失败", "推送本地应用至远程仓库,HTTP请求失败",
                               status_code=500, error_code=500)
        except Exception as e:
            logger.error("推送本地应用至远程仓库,HTTP请求失败,error:{}", e)
            raise AbortRequest("推送本地应用至远程仓库,HTTP请求失败", "推送本地应用至远程仓库,HTTP请求失败", status_code=500, error_code=500)

    def get_market_app_versions(self, market: AppMarket, query_body: dict):
        """获取梧桐商店应用版本列表"""

        # 参数排序
        sorted_body = dict(sorted(query_body.items(), key=lambda x: x[0]))
        sign_str, param_str = encode_params(params=build_sign_params(access_key=market.access_key),
                                            secret=market.access_secret, method="POST", sorted_dict_body=sorted_body)

        # 构建请求链接
        url = """{prefix}/{path}?Signature={signature}&{param_str}""".format(prefix=market.url,
                                                                             path="wutong-open-market-admin/app-version/page",
                                                                             signature=quote(sign_str),
                                                                             param_str=param_str)
        try:
            res, body = self._post(url, self.default_headers, body=json.dumps(sorted_body).replace(" ", ""))
            logger.info("查询商店应用版本列表,params:{},resp:{}", json.dumps(body), json.dumps(body))
            if body.code == "0":
                return body.data
            else:
                raise AbortRequest(body.msg, "查询商店应用版本列表失败:{error}".format(error=body.msg),
                                   status_code=500, error_code=500)
        except MarketHttpClient.CallApiError as e:
            logger.error("查询商店应用版本列表,HTTP请求失败,error:{}", e)
            raise AbortRequest("查询商店应用版本列表,HTTP请求失败", "查询商店应用版本列表,HTTP请求失败",
                               status_code=500, error_code=500)
        except Exception as e:
            logger.error("查询商店应用版本列表,HTTP请求失败,error:{}", e)
            raise AbortRequest("查询商店应用版本列表,HTTP请求失败", "查询商店应用版本列表,HTTP请求失败", status_code=500, error_code=500)

    def get_market_app_version_detail(self, market: AppMarket, version_id: str):
        """获取梧桐商店应用版本详情"""
        sign_str, param_str = encode_params(params=build_sign_params(access_key=market.access_key),
                                            secret=market.access_secret, method="GET")
        url = """{prefix}/{path}/{version_id}?Signature={signature}&{param_str}""".format(prefix=market.url,
                                                                                          path="wutong-open-market-admin/app-version/detail",
                                                                                          version_id=version_id,
                                                                                          signature=quote(sign_str),
                                                                                          param_str=param_str)
        res, body = self._get(url=url, headers=self.default_headers, timeout=10)
        if body.code == "0":
            return body.data
        else:
            raise AbortRequest("获取梧桐商店应用版本详情失败", "获取梧桐商店应用版本详情失败", status_code=500, error_code=500)


wutong_market_client = WutongMarketClient()
