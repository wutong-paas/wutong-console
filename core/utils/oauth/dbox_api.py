# -*- coding: utf8 -*-
import urllib.error
import urllib.parse
import urllib.request

import requests
from loguru import logger

from exceptions.bcode import ErrOauthUserNotLogout
from core.utils.oauth.base.exception import (NoAccessKeyErr, NoOAuthServiceErr)
from core.utils.oauth.base.oauth import OAuth2Interface, OAuth2User
from core.utils.urlutil import set_get_url


class DboxOauth(object):
    def __init__(self, url, oauth_token=None):
        self._base_url = url
        self._url = "%s" % (url)
        self.oauth_token = oauth_token
        self.session = requests.Session()
        self.headers = {
            "Accept": "application/json",
            "Authorization": self.oauth_token,
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


class DboxApiV1MiXin(object):
    def set_api(self, host, access_token):
        self.api = DboxOauth(host, oauth_token=access_token)


class DboxApiV1(DboxApiV1MiXin, OAuth2Interface):
    def __init__(self):
        super(DboxApiV1, self).set_session()
        self.request_params = {
            "response_type": "code",
        }

    def get_auth_url(self, home_url=""):
        return home_url.strip().strip("/") + "/oauth/authorize"

    def get_access_token_url(self, home_url=""):
        return home_url.strip().strip("/") + "/oauth/token"

    def get_user_url(self, home_url=""):
        return home_url.strip().strip("/") + "/oauth/userinfo"

    def _get_user_info(self):
        '''
        private function, get access_token
        :return: access_token, refresh_token
        '''
        if not self.oauth_service:
            raise NoOAuthServiceErr("no found oauth service")
        try:
            user = self.api._api_get(self.get_user_url(""))
        except Exception as e:
            logger.exception(e)
            raise NoAccessKeyErr("can not get user info")
        if user:
            return user
        else:
            raise NoAccessKeyErr("can not get user info")

    def refresh_access_token(self):
        if not self.oauth_service:
            raise NoOAuthServiceErr("no found oauth service")
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Connection": "close"}
        params = {
            "client_id": self.oauth_service.client_id,
            "client_secret": self.oauth_service.client_secret,
            "refresh_token": self.refresh_token,
            "redirect_uri": self.oauth_service.redirect_uri + '?service_id=' + str(self.oauth_service.ID),
            "grant_type": "authorization_code"
        }
        url = self.get_access_token_url(self.oauth_service.home_url)
        try:
            rst = self._session.request(method='POST', url=url, headers=headers, data=params)
        except Exception as e:
            logger.exception(e)
            raise NoAccessKeyErr("can not get access key")
        if rst.status_code == 200:
            data = rst.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            if self.access_token is None:
                return None, None
            self.set_api(self.oauth_service.home_url, self.access_token)
            self.update_access_token(self.access_token, self.refresh_token)
            return self.access_token, self.refresh_token
        else:
            raise NoAccessKeyErr("can not get access key")

    def _get_access_token(self, code=None):
        '''
        private function, get access_token
        :return: access_token, refresh_token
        '''
        if not self.oauth_service:
            raise NoOAuthServiceErr("no found oauth service")
        if code:
            headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Connection": "close"}
            params = {
                "client_id": self.oauth_service.client_id,
                "client_secret": self.oauth_service.client_secret,
                "code": code,
                "redirect_uri": self.oauth_service.redirect_uri + '?service_id=' + str(self.oauth_service.ID),
                "grant_type": "authorization_code"
            }
            url = self.get_access_token_url(self.oauth_service.home_url)
            try:
                rst = self._session.request(method='POST', url=url, headers=headers, data=params)
            except Exception as e:
                logger.exception(e)
                raise NoAccessKeyErr("can not get access key")
            if rst.status_code == 200:
                data = rst.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                if self.access_token is None:
                    return None, None
                self.set_api(self.oauth_service.home_url, self.access_token)
                self.update_access_token(self.access_token, self.refresh_token)
                return self.access_token, self.refresh_token
            else:
                raise NoAccessKeyErr("can not get access key")

    def get_user_info(self, code=None):
        access_token, refresh_token = self._get_access_token(code=code)
        user = self._get_user_info()
        if user:
            return OAuth2User(user["username"], user["userID"], user["email"]), access_token, refresh_token
        return None, None, None

    def get_authorize_url(self):
        if self.oauth_service:
            params = {
                "client_id": self.oauth_service.client_id,
                "scope": "snsapi_login",
                "redirect_uri":
                urllib.parse.quote(self.oauth_service.redirect_uri + "?service_id=" + str(self.oauth_service.ID)),
            }
            params.update(self.request_params)
            return set_get_url(self.oauth_service.auth_url, params)
        else:
            raise NoOAuthServiceErr("no found oauth service")

    def is_logout(self):
        """
        Check if the user is logged out.
        """
        self.set_api(self.oauth_service.home_url, self.oauth_user.access_token)
        resp = self.api._api_get("/oauth/islogout")
        if resp:
            raise ErrOauthUserNotLogout
