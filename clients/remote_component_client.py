import json
import os
from loguru import logger
from sqlalchemy import select
from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info
from exceptions.main import ServiceHandleException
from models.teams import RegionConfig


class RemoteComponentClient(ApiBaseHttpClient):
    """
    RemoteComponentClient
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

    def create_service(self, session, region, tenant_env, body):
        """创建组件"""

        url, token = get_region_access_info(region, session)

        # 更新tenant_env_id 为数据中心tenant_env_id
        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + "/services"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def update_service(self, session, region, tenant_env, service_alias, body):
        """更新组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service(self, session, region, tenant_env, service_alias, data=None):
        """删除组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias

        self._set_headers(token)
        if not data:
            data = {}
        res, body = self._delete(session, url, self.default_headers, region=region, body=json.dumps(data))
        return body

    def build_service(self, session, region, tenant_env, service_alias, body):
        """组件构建"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/build"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def add_service_dependency(self, session, region, tenant_env, service_alias, body):
        """增加组件依赖"""

        url, token = get_region_access_info(region, session)

        # 更新tenant_env_id 为数据中心tenant_env_id
        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/dependency"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service_dependency(self, session, region, tenant_env, service_alias, body):
        """取消组件依赖"""

        url, token = get_region_access_info(region, session)

        # 更新tenant_env_id 为数据中心tenant_env_id
        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/dependency"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def add_service_env(self, session, region, tenant_env, service_alias, body):
        """添加环境变量"""

        url, token = get_region_access_info(region, session)

        # 更新tenant_env_id 为数据中心tenant_env_id
        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def delete_service_env(self, session, region, tenant_env, service_alias, body):
        """删除环境变量"""

        url, token = get_region_access_info(region, session)

        # 更新tenant_env_id 为数据中心tenant_env_id
        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def update_service_env(self, session, region, tenant_env, service_alias, body):
        url, token = get_region_access_info(region, session)

        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/env"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def horizontal_upgrade(self, session, region, tenant_env, service_alias, body):
        """组件水平伸缩"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/horizontal"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def vertical_upgrade(self, session, region, tenant_env, service_alias, body):
        """组件垂直伸缩"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/vertical"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_region_labels(self, session, region, tenant_env):
        """获取数据中心可用的标签"""

        url, token = get_region_access_info(region, session)
        url = url + "/v2/resources/labels"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def addServiceNodeLabel(self, session, region, tenant_env, service_alias, body):
        """添加组件对应的节点标签"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def deleteServiceNodeLabel(self, session, region, tenant_env, service_alias, body):
        """删除组件对应的节点标签"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/label"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def get_service_pods(self, session, region, tenant_env, service_alias):
        """获取组件pod信息"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + "/services/" \
              + service_alias + "/pods"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, None, region=region, timeout=15)
        return body

    def get_dynamic_services_pods(self, session, region, tenant_env, services_ids):
        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/pods?service_ids={}".format(",".join(services_ids))
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region, timeout=15)
        return body

    def pod_detail(self, session, region, tenant_env, service_alias, pod_name):
        """获取组件pod信息"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/pods/" + pod_name + "/detail"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, None, region=region)
        return body

    def add_service_port(self, session, region, tenant_env, service_alias, body):
        """添加组件端口"""

        url, token = get_region_access_info(region, session)

        port_list = body["port"]
        for port in port_list:
            port["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/ports"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def update_service_port(self, session, region, tenant_env, service_alias, body):
        """更新组件端口"""

        url, token = get_region_access_info(region, session)

        port_list = body["port"]
        for port in port_list:
            port["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/ports"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def delete_service_port(self, session, region, tenant_env, service_alias, port, body={}):
        """删除组件端口"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/ports/" + str(port)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def manage_inner_port(self, session, region, tenant_env, service_alias, port, body):
        """打开关闭对内端口"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/ports/" + str(port) + "/inner"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def manage_outer_port(self, session, region, tenant_env, service_alias, port, body):
        """打开关闭对外端口"""
        try:
            url, token = get_region_access_info(region, session)

            url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
                  "/services/" + service_alias + "/ports/" + str(port) + "/outer"

            self._set_headers(token)
            res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
            return body
        except ApiBaseHttpClient.CallApiError as e:
            message = e.body.get("msg")
            if message and message.find("do not allow operate outer port for thirdpart domain endpoints") >= 0:
                raise ServiceHandleException(
                    status_code=400,
                    msg="do not allow operate outer port for thirdpart domain endpoints",
                    msg_show="该第三方组件具有域名类实例，暂不支持开放网关访问")
            else:
                raise e

    def update_service_probec(self, session, region, tenant_env, service_alias, body):
        """更新组件探针信息"""

        url, token = get_region_access_info(region, session)

        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._put(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def add_service_probe(self, session, region, tenant_env, service_alias, body):
        """添加组件探针信息"""

        url, token = get_region_access_info(region, session)

        body["tenant_env_id"] = tenant_env.env_id
        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_probe(self, session, region, tenant_env, service_alias, body):
        """删除组件探针信息"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/probe"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def restart_service(self, session, region, tenant_env, service_alias, body):
        """重启组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/restart"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def rollback(self, session, region, tenant_env, service_alias, body):
        """组件版本回滚"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/rollback"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def start_service(self, session, region, tenant_env, service_alias, body):
        """启动组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/start"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def stop_service(self, session, region, tenant_env, service_alias, body):
        """关闭组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/stop"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def upgrade_service(self, session, region, tenant_env, service_alias, body):
        """升级组件"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/upgrade"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return body

    def check_service_status(self, session, region, tenant_env, service_alias):
        """获取单个组件状态"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/status"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def get_volume_options(self, session, region, tenant_env):
        """

        :param region:
        :param tenant_name:
        :return:
        """
        url, token = get_region_access_info(region, session)
        url += "/v2/volume-options"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def get_service_volumes(self, session, region, tenant_env, service_alias):
        """
        :param session:
        :param region:
        :param tenant_env:
        :param service_alias:
        :return:
        """
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/volumes".format(
            tenant_name, tenant_env.env_name, service_alias)
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return res, body

    def add_service_volumes(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/volumes".format(tenant_name, tenant_env.env_name, service_alias)
        self._set_headers(token)
        return self._post(session, url, self.default_headers, json.dumps(body), region=region)

    def delete_service_volumes(self, session, region, tenant_env, service_alias, volume_name, body={}):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param volume_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/volumes/{3}".format(
            tenant_name, tenant_env.env_name, service_alias, volume_name)
        self._set_headers(token)
        return self._delete(session, url, self.default_headers, json.dumps(body), region=region)

    def upgrade_service_volumes(self, session, region, tenant_env, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/volumes".format(tenant_name, tenant_env.env_name, service_alias)
        self._set_headers(token)
        return self._put(session, url, self.default_headers, json.dumps(body), region=region)

    def add_service_dep_volumes(self, session, region, tenant_env, service_alias, body):
        """ Add dependent volumes """
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/depvolumes".format(tenant_name, tenant_env.env_name,
                                                                         service_alias)
        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_dep_volumes(self, session, region, tenant_env, service_alias, body):
        """ Delete dependent volume"""
        url, token = get_region_access_info(region, session)

        tenant_name = tenant_env.tenant_name
        url += "/v2/tenants/{0}/envs/{1}/services/{2}/depvolumes".format(tenant_name, tenant_env.env_name,
                                                                         service_alias)
        self._set_headers(token)
        return self._delete(session, url, self.default_headers, json.dumps(body), region=region)

    def add_service_volume(self, session, region, tenant_env, service_alias, body):
        """添加组件持久化目录"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/volume"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def delete_service_volume(self, session, region, tenant_env, service_alias, body):
        """删除组件持久化目录"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/volume"

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, json.dumps(body), region=region)
        return res, body

    def service_status(self, session, region, tenant_env, body):
        """获取多个组件的状态"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + "/services_status"

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region, body=json.dumps(body), timeout=20)
        return body

    def get_enterprise_api_version_v2(self, session, region, **kwargs):
        """获取api版本-v2"""
        kwargs["retries"] = 1
        kwargs["timeout"] = 1
        url, token = get_region_access_info(region, session)
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region, **kwargs)
        return res, body

    def get_enterprise_running_services(self, session, region, test=False):
        """
        :param session:
        :param region:
        :param test:
        :return:
        """
        if test:
            self.get_enterprise_api_version_v2(session, region=region)
        url, token = get_region_access_info(region, session)
        url = url + "/v2/enterprise/running-services"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region, timeout=10)
        if res.get("status") == 200 and isinstance(body, dict):
            return body
        return None

    def get_all_services_status(self, session, region, test=False):
        """
        :param session:
        :param region:
        :param test:
        :return:
        """
        if test:
            self.get_enterprise_api_version_v2(session, region=region)
        url, token = get_region_access_info(region, session)
        url = url + "/v2/enterprise/services/status"
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region, timeout=10)
        if res.get("status") == 200 and isinstance(body, dict):
            return body
        return None

    def get_service_logs(self, session, region, tenant_env, service_alias, rows):
        """获取组件日志"""
        url, token = get_region_access_info(region, session)

        url += "/v2/tenants/{0}/envs/{1}/services/{2}/logs?rows={3}".format(tenant_env.tenant_name,
                                                                            tenant_env.env_name, service_alias,
                                                                            rows)
        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def get_service_log_files(self, session, region, tenant_env, service_alias):
        """获取组件日志文件列表"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/" + tenant_env.tenant_name + "/envs/" + tenant_env.env_name + \
              "/services/" + service_alias + "/log-file"

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region)
        return body

    def get_component_log(self, session, tenant_env, region_name, service_alias, pod_name, container_name,
                          follow=False):
        """
        :param session:
        :param tenant_env:
        :param region_name:
        :param service_alias:
        :param pod_name:
        :param container_name:
        :param follow:
        :return:
        """
        url, token = get_region_access_info(region_name, session)
        follow = "true" if follow else "false"
        url += "/v2/tenants/{}/envs/{}/services/{}/log?podName={}&containerName={}&follow={}".format(
            tenant_env.tenant_name, tenant_env.env_name, service_alias, pod_name, container_name, follow)
        self._set_headers(token)
        resp, _ = self._get(session, url, self._set_headers(token), region=region_name, preload_content=False)
        return resp

    def get_region_info(self, session, region_name):
        return session.execute(select(RegionConfig).where(
            RegionConfig.region_name == region_name)).scalars().first()

    def __get_region_access_info(self, session, tenant_name, region):
        """获取一个团队在指定数据中心的身份认证信息"""
        # 如果团队所在企业所属数据中心信息不存在则使用通用的配置(兼容未申请数据中心token的企业)
        # 管理后台数据需要及时生效，对于数据中心的信息查询使用直接查询原始数据库
        region_info = self.get_region_info(session=session, region_name=region)
        if region_info is None:
            raise ServiceHandleException("region not found", "数据中心不存在", 404, 404)
        url = region_info.url
        token = region_info.token
        return url, token

    def change_application_volumes(self, session, tenant_env, region_name, region_app_id):
        url, token = self.__get_region_access_info(session, tenant_env.tenant_name, region_name)
        url = url + "/v2/tenants/{}/envs/{}/apps/{}/volumes".format(tenant_env.tenant_name, tenant_env.env_name,
                                                                    region_app_id)
        self._set_headers(token)
        resp, _ = self._put(session, url, self._set_headers(token), region=region_name)
        return resp

    def get_helm_chart_apps(self, session, region_name, tenant_env, body):
        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/helm/{}/apps".format(body["helm_namespace"])

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_name)
        return body["list"]

    def service_backup(self, session, region_name, tenant_env, service_alias, body):
        """组件备份"""

        url, token = get_region_access_info(region_name, session)

        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/backup".format(tenant_env.tenant_name, tenant_env.env_name,
                                                                          service_alias)

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body), timeout=20)
        return body

    def service_restore(self, session, region_name, tenant_env, service_alias, body):
        """组件恢复"""

        url, token = get_region_access_info(region_name, session)

        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/restore".format(tenant_env.tenant_name, tenant_env.env_name,
                                                                           service_alias)

        self._set_headers(token)
        res, body = self._post(session, url, self.default_headers, region=region_name, body=json.dumps(body), timeout=20)
        return body

    def get_service_backup_list(self, session, region_name, tenant_env, service_alias):
        """获取组件备份列表"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/backup/records".format(tenant_env.tenant_name,
                                                                                  tenant_env.env_name,
                                                                                  service_alias)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_name)
        return body["list"]

    def get_service_restore_list(self, session, region_name, tenant_env, service_alias):
        """获取组件恢复列表"""

        url, token = get_region_access_info(region_name, session)
        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/restore/records".format(tenant_env.tenant_name,
                                                                                   tenant_env.env_name,
                                                                                   service_alias)

        self._set_headers(token)
        res, body = self._get(session, url, self.default_headers, region=region_name)
        return body["list"]

    def delete_service_backup_records(self, session, region, tenant_env, service_alias, backup_id):
        """删除组件备份记录"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/backup/{3}".format(tenant_env.tenant_name,
                                                                              tenant_env.env_name,
                                                                              service_alias,
                                                                              backup_id)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region)
        return body

    def delete_service_restore_records(self, session, region, tenant_env, service_alias, restore_id):
        """删除组件恢复记录"""

        url, token = get_region_access_info(region, session)

        url = url + "/v2/tenants/{0}/envs/{1}/services/{2}/restore/{3}".format(tenant_env.tenant_name,
                                                                               tenant_env.env_name,
                                                                               service_alias,
                                                                               restore_id)

        self._set_headers(token)
        res, body = self._delete(session, url, self.default_headers, region=region)
        return body


remote_component_client = RemoteComponentClient()
