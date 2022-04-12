"""
通用http rest client
"""
import json
import socket

import httplib2
from addict import Dict
from loguru import logger


def _json_decode(string):
    try:
        body = json.loads(string)
    except ValueError:
        if len(string) < 10000:
            body = {"raw": string}
        else:
            body = {"raw": "too long to record!"}
    return body


def _unpack(dict_body):
    if 'data' not in dict_body:
        return dict_body

    data_body = dict_body['data']
    if 'bean' in data_body and data_body['bean']:
        return data_body['bean']
    elif 'list' in data_body and data_body['list']:
        return data_body['list']
    else:
        return dict()


class HttpClient(object):
    """
    HttpClient
    """
    class CallApiError(Exception):
        def __init__(self, apitype, url, method, res, body, describe=None):
            self.message = {
                "apitype": apitype,
                "url": url,
                "method": method,
                "httpcode": res.status,
                "body": body,
            }
            self.status = res.status

        def __str__(self):
            return json.dumps(self.message)

    class RemoteInvokeError(Exception):
        """
        RemoteInvokeError
        """

        def __init__(self, api_type, url, method, res, body, describe=None):
            self.message = {
                "api_type": api_type,
                "url": url,
                "method": method,
                "http_code": res.status,
                "body": body,
            }
            self.status = res.status

        def __str__(self):
            return json.dumps(self.message)

    class SocketError(RemoteInvokeError):
        """
        SocketError
        """
        pass

    def __init__(self, *args, **kwargs):
        self.timeout = 3
        self.api_type = 'Not specified'

    def _check_status(self, url, method, response, content):
        res = Dict(response)
        res.status = int(res.status)
        body = _json_decode(content)
        if isinstance(body, dict):
            body = Dict(body)
        if 400 <= res.status <= 600:
            raise self.RemoteInvokeError(self.api_type, url, method, res, body)

    def _request(self, url, method, headers=None, body=None, client=None, *args, **kwargs):
        retry_count = 2
        if client is None:
            timeout = kwargs.get("timeout", self.timeout)
            client = httplib2.Http(timeout=timeout)
        while retry_count:
            try:
                if body is None:
                    response, content = client.request(url, method, headers=headers)
                else:
                    response, content = client.request(url, method, headers=headers, body=body)
                return response, content
            except socket.timeout as e:
                logger.error('client_error', "timeout: %s" % url)
                logger.exception('client_error', e)
                raise self.RemoteInvokeError(self.api_type, url, method, Dict({"status": 101}), {
                    "type": "request time out",
                    "error": str(e)
                })
            except socket.error as e:
                retry_count -= 1
                if retry_count:
                    logger.error("client_error", "retry request: %s" % url)
                else:
                    logger.exception('client_error', e)
                    raise self.SocketError(self.api_type, url, method, Dict({"status": 101}), {
                        "type": "connect error",
                        "error": str(e)
                    })

    def _get(self, url, headers, body=None, *args, **kwargs):
        if body is not None:
            response, content = self._request(url, 'GET', headers=headers, body=body, *args, **kwargs)
        else:
            response, content = self._request(url, 'GET', headers=headers, *args, **kwargs)
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
