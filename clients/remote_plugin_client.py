import json
import os
from loguru import logger
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_env_region_info


class RemotePluginClient(ApiBaseHttpClient):
    """
    RemotePluginClient
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

    def plugin_service_relation(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        data = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def del_plugin_service_relation(self, session, region, tenant_env, plugin_id, service_alias):
        """

        :param region:
        :param tenant_name:
        :param plugin_id:
        :param service_alias:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin/" + plugin_id

        self._set_headers(token)
        data = self._delete(session, url, self.default_headers, None, region=region)
        return data

    def update_plugin_service_relation(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        data = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def post_plugin_attr(self, session, region, tenant_env, service_alias, plugin_id, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param plugin_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin/" + plugin_id + "/setenv"

        self._set_headers(token)
        data = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def put_plugin_attr(self, session, region, tenant_env, service_alias, plugin_id, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param plugin_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin/" + plugin_id + "/upenv"

        self._set_headers(token)
        data = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def create_plugin(self, session, region, tenant_env, body):
        """创建数据中心端插件"""

        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/plugin"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def build_plugin(self, session, region, tenant_env, plugin_id, body):
        """创建数据中心端插件"""
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url += "/v2/tenants/{0}/envs/{1}/plugin/{2}/build".format(tenant_env.tenant_name, tenant_env.env_name,
                                                                  plugin_id)

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def get_build_status(self, session, region, tenant_env, plugin_id, build_version):
        """获取插件构建状态"""
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url += "/v2/tenants/{0}/envs/{1}/plugin/{2}/build-version/{3}".format(tenant_env.tenant_name,
                                                                              tenant_env.env_name, plugin_id,
                                                                              build_version)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def get_plugin_event_log(self, session, region, tenant_env, data):
        """获取插件日志信息"""

        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url += "/v2/tenants/{0}/envs/{1}/event-log".format(tenant_env.tenant_name, tenant_env.env_name)
        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(data), region=region)
        return body

    def delete_plugin_version(self, session, region, tenant_env, plugin_id, build_version):
        """删除插件某个版本信息"""
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)

        url += "/v2/tenants/{0}/envs/{1}/plugin/{2}/build-version/{3}".format(tenant_env.tenant_name,
                                                                              tenant_env.env_name, plugin_id,
                                                                              build_version)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region)
        return body

    def update_plugin_info(self, session, region, tenant_env, plugin_id, data):
        """

        :param region:
        :param tenant_name:
        :param plugin_id:
        :param data:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url += "/v2/tenants/{0}/envs/{1}/plugin/{2}".format(tenant_env.tenant_name, tenant_env.env_name,
                                                            plugin_id)
        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(data), region=region)
        return body

    def delete_plugin(self, session, region, tenant_env, plugin_id):
        """

        :param region:
        :param tenant_name:
        :param plugin_id:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url += "/v2/tenants/{0}/envs/{1}/plugin/{2}".format(tenant_env.tenant_name, tenant_env.env_name,
                                                            plugin_id)
        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region)
        return res, body

    def install_service_plugin(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin"

        self._set_headers(token)
        data = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def uninstall_service_plugin(self, session, region, tenant_env, plugin_id, service_alias, body={}):
        """

        :param region:
        :param tenant_name:
        :param plugin_id:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin/" + plugin_id
        self._set_headers(token)
        data = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def update_service_plugin_config(self, session, region, tenant_env, service_alias, plugin_id, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param plugin_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)
        tenant_region = get_env_region_info(tenant_env, region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/plugin/" + plugin_id + "/upenv"

        self._set_headers(token)
        data = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return data

    def share_plugin(self, session, region_name, tenant_env, plugin_id, body):
        """分享插件"""
        url, token = get_region_access_info(region_name, session)
        
        url = "{0}/v2/tenants/{1}/envs/{2}/plugins/{3}/share".format(url, tenant_env.tenant_name,
                                                                     tenant_env.env_name, plugin_id)
        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body))
        return res, body

    def share_plugin_result(self, session, region_name, tenant_env, plugin_id, region_share_id):
        """查询分享插件状态"""
        url, token = get_region_access_info(region_name, session)
        
        url = "{0}/v2/tenants/{1}/envs/{2}/plugins/{3}/share/{4}".format(url, tenant_env.tenant_name,
                                                                         tenant_env.env_name, plugin_id,
                                                                         region_share_id)
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_name)
        return res, body

    def sync_plugins(self, session, tenant_env, tenant_name, region_name, body):
        """

        :param tenant_name:
        :param region_name:
        :param body:
        """
        url, token = get_region_access_info(region_name, session)
        url += "/v2/tenants/{tenant_name}/envs/{env_name}/plugins".format(tenant_name=tenant_name,
                                                                          env_name=tenant_env.env_name)
        self._set_headers(token)
        self._post(session, url, self.default_headers, body=json.dumps(body), region=region_name)

    def build_plugins(self, session, tenant_env, tenant_name, region_name, body):
        """

        :param tenant_name:
        :param region_name:
        :param body:
        """
        url, token = get_region_access_info(region_name, session)
        url += "/v2/tenants/{tenant_name}/envs/{env_name}/batch-build-plugins".format(tenant_name=tenant_name,
                                                                                      env_name=tenant_env.env_name)
        self._set_headers(token)
        self._post(session, url, self.default_headers, body=json.dumps(body), region=region_name)


remote_plugin_client = RemotePluginClient()
