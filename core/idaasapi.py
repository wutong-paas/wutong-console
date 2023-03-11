# -*- coding: utf8 -*-
import json
import requests
from loguru import logger
from exceptions.exceptions import NoAccessKeyErr
from exceptions.main import ServiceHandleException
from schemas.user import UserInfo


class IDaaSApi:
    def __init__(self):
        self._url = "http://p5ayvh.natappfree.cc"
        self.session = requests.Session()
        self.headers = {}
        self.token = ""

    def set_token(self, token):
        self.token = token
        self.headers = {
            "Accept": "application/json",
            "Authorization": self.token,
        }

    def _api_get(self, url_suffix, params=None):
        url = self._url + url_suffix
        try:
            rst = self.session.request(method='GET', url=url, headers=self.headers, params=params)
            if rst.status_code == 200:
                data = rst.json()
                if not isinstance(data, (list, dict)):
                    data = None
            else:
                logger.error("request path {} responset status {} content {}".format(url, rst.status_code, rst.content))
                data = None
        except Exception as e:
            logger.exception(e)
            data = None
        return data

    def _api_post(self, url_suffix, params=None):
        err_msg = None
        url = self._url + url_suffix
        try:
            rst = self.session.request(method='POST', url=url, headers=self.headers, json=params)
            if rst.status_code == 200:
                data = rst.json()
                if not isinstance(data, (list, dict)):
                    data = None
            else:
                err_msg = rst.text
                logger.error("request path {} responset status {} content {}".format(url, rst.status_code, rst.content))
                data = None
        except Exception as e:
            logger.exception(e)
            data = None
        return data, err_msg

    def __post(self, url, params):
        try:
            rst, err_msg = self._api_post(url, params=params)
        except Exception as e:
            logger.exception(e)
            raise NoAccessKeyErr("can not get user info")
        if not rst:
            err_msg = json.loads(err_msg)
            raise ServiceHandleException(msg=err_msg.get("code") + " can not get user info",
                                         msg_show=err_msg.get("msg"),
                                         status_code=400)
        code = rst.get("code", None)
        if code == '0':
            data = rst.get("data", None)
            if isinstance(data, dict):
                records = data.get("records", None)
                if records:
                    data = records
            return data, "", ""
        return None, rst["msg"], code

    def get_url(self, home_url=None):
        return "/wutong-bone-core" + home_url

    def get_user_info(self, params):
        data, msg, code = self.__post(self.get_url("/user/detail"), params=params)
        if not data:
            raise ServiceHandleException(msg_show=msg, msg="failed", status_code=code)
        user = {
            "user_id": data.get("id"),
            "user_name": data.get("userName"),
            "real_name": data.get("realName"),
            "nick_name": data.get("nickName"),
            "email": data.get("email"),
            "phone": data.get("mobile")
        }
        user = UserInfo(**user)
        return user

    def get_user_infos(self, url, params):
        data, msg, code = self.__post(self.get_url(url), params=params)
        if not data:
            raise ServiceHandleException(msg_show=msg, msg="failed", status_code=code)
        user_list = []
        for user_info in data:
            user = {
                "user_id": user_info.get("id"),
                "real_name": user_info.get("realName"),
                "nick_name": user_info.get("nickName"),
                "email": user_info.get("email"),
                "phone": user_info.get("mobile")
            }
            user = UserInfo(**user)
            user_list.append(user)
        return user_list

    def get_all_user_infos(self):
        params = {
            "current": 1,
            "orders": [
                {
                    "asc": True,
                    "column": "id"
                }
            ],
            "queryVO": {
            },
            "size": 9999
        }
        users = self.get_user_infos(url="/user/page", params=params)
        return users

    def check_user_password(self, params):
        data, msg, code = self.__post(self.get_url("/user/check-password-MD5"), params=params)
        return data


idaas_api = IDaaSApi()
