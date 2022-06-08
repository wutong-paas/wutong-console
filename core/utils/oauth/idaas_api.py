# -*- coding: utf8 -*-
import requests
from loguru import logger
from core.utils.oauth.base.exception import (NoAccessKeyErr, NoOAuthServiceErr)
from core.utils.oauth.base.git_oauth import OAuth2Interface
from core.utils.oauth.base.oauth import OAuth2User
from core.utils.urlutil import set_get_url
from exceptions.bcode import ErrUnAuthnOauthService, ErrExpiredAuthnOauthService


class IDaaSOauth(object):
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

    def _api_logout_get(self, url_suffix, params=None):
        url = self._url + url_suffix
        rst = self.session.request(method='GET', url=url, headers=self.headers, params=params)
        return rst.status_code


class IDaaSApiV1MiXin(object):
    def set_api(self, host, access_token):
        self.api = IDaaSOauth(host, oauth_token=access_token)


class IDaaSApiV1(IDaaSApiV1MiXin, OAuth2Interface):
    def __init__(self):
        super(IDaaSApiV1, self).set_session()
        self.request_params = {
            "response_type": "code",
        }

    def get_auth_url(self, home_url=None):
        home_url.strip().strip("/")
        return "/".join([home_url, "login"])

    def get_access_token_url(self, home_url=None):
        home_url.strip().strip("/")
        return "/".join([home_url, "gateway/wutong-idaas-auth/auth/token"])

    def get_user_url(self, home_url=None):
        home_url.strip().strip("/")
        return "/".join([home_url, "gateway/wutong-idaas-auth/authz/oauth2/userinfojson"])

    def get_logout_url(self, home_url=None):
        home_url.strip().strip("/")
        return "/".join([home_url, "logout"])

    def _get_access_token(self, code=None):
        '''
        private function, get access_token
        :return: access_token, refresh_token
        '''
        if not self.oauth_service:
            raise NoOAuthServiceErr("no found oauth service")
        if code:
            headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                       "Connection": "close"}
            params = {
                "client_id": self.oauth_service.client_id,
                "client_secret": self.oauth_service.client_secret,
                "code": code,
                "redirect_uri": self.oauth_service.redirect_uri + '?service_id=' + str(self.oauth_service.ID),
                "grant_type": "authorization_code"
            }
            url = self.get_access_token_url(self.oauth_service.home_url)
            try:
                rst = self._session.request(method='POST', url=url, headers=headers, params=params)
            except Exception:
                raise NoAccessKeyErr("can not get access key")
            if rst.status_code == 200:
                data = rst.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                if self.access_token is None:
                    return None, None
                self.update_access_token(self.access_token, self.refresh_token)
                return self.access_token, self.refresh_token
            else:
                raise NoAccessKeyErr("can not get access key")
        else:
            if self.oauth_user:
                try:
                    user = self.api._api_get(self.get_user_url(""),
                                             params={"access_token": self.oauth_user.access_token})
                    if user["username"]:
                        return self.oauth_user.access_token, self.oauth_user.refresh_token
                except Exception:
                    if self.oauth_user.refresh_token:
                        try:
                            self.refresh_access_token()
                            return self.access_token, self.refresh_token
                        except Exception:
                            self.oauth_user.delete()
                            raise ErrExpiredAuthnOauthService
                    else:
                        self.oauth_user.delete()
                        raise ErrExpiredAuthnOauthService
            raise ErrUnAuthnOauthService

    def refresh_access_token(self):
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

        params = {"refresh_token": self.refresh_token, "grant_type": "refresh_token", "scope": "api"}
        rst = self._session.request(method='POST', url=self.oauth_service.access_token_url, headers=headers,
                                    params=params)
        data = rst.json()
        if rst.status_code == 200:
            self.oauth_user.refresh_token = data.get("refresh_token")
            self.oauth_user.access_token = data.get("access_token")
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.oauth_user = self.oauth_user.save()

    def get_user_info(self, code=None):
        access_token, refresh_token = self._get_access_token(code=code)
        self.set_api(self.oauth_service.home_url, access_token)
        try:
            user = self.api._api_get(self.get_user_url(""), params={"access_token": access_token})
        except Exception as e:
            logger.exception(e)
            raise NoAccessKeyErr("can not get user info")
        if user:
            return OAuth2User(user["realname"], user["userId"], user["email"], user["username"],
                              user["mobile"]), access_token, refresh_token
        return None, None, None

    def logout(self):
        try:
            status_code = self.api._api_logout_get(self.get_logout_url(""), params={"access_token": self.access_token})
        except Exception as e:
            logger.exception(e)
            raise NoAccessKeyErr("idaas logout failed")
        return status_code

    def get_authorize_url(self):
        if self.oauth_service:
            params = {
                "client_id": self.oauth_service.client_id,
                "redirect_uri": self.oauth_service.redirect_uri + "?service_id=" + str(self.oauth_service.ID),
            }
            params.update(self.request_params)
            return set_get_url(self.oauth_service.auth_url, params)
        else:
            raise NoOAuthServiceErr("no found oauth service")

    def get_clone_user_password(self):
        access_token, _ = self._get_access_token()
        return "oauth2", self.oauth_user.access_token

    def get_clone_url(self, url):
        name, password = self.get_clone_user_password()
        urls = url.split("//")
        return urls[0] + '//' + name + ':' + password + '@' + urls[-1]
