import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_tenant_region_info, get_enterprise_region_info, \
    get_region_access_info_by_enterprise_id
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams import RegionConfig
from repository.region.region_config_repo import region_config_repo


class RemoteBuildClient(ApiBaseHttpClient):
    """
    RemoteBuildClient
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

    def service_source_check(self, session, region, tenant_name, body):
        """组件源检测"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/servicecheck"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def get_service_check_info(self, session, region, tenant_name, uuid):
        """组件源检测信息获取"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/servicecheck/" + str(uuid)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def service_chargesverify(self, session, region, tenant_name, data):
        """组件扩大资源申请接口"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + \
              "/chargesverify?quantity={0}&reason={1}&eid={2}".format(data["quantity"], data["reason"], data["eid"])
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def get_services_pods(self, session, region, tenant_name, service_id_list, enterprise_id):
        """获取多个组件的pod信息"""
        service_ids = ",".join(service_id_list)
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/pods?enterprise_id=" \
              + enterprise_id + "&service_ids=" + service_ids

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, None, region=region, timeout=10)
        return body

    def get_service_build_versions(self, session, region, tenant_name, service_alias):
        """获取组件的构建版本"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
              + service_alias + "/build-list"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def delete_service_build_version(self, session, region, tenant_name, service_alias, version_id):
        """删除组件的某次构建版本"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
              + service_alias + "/build-version/" + version_id

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def get_service_build_version_by_id(self, session, region, tenant_name, service_alias, version_id):
        """查询组件的某次构建版本"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" \
              + service_alias + "/build-version/" + version_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_team_services_deploy_version(self, session, region, tenant_name, data):
        """查询指定组件的部署版本"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/deployversions"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def get_service_deploy_version(self, session, region, tenant_name, service_alias):
        """查询指定组件的部署版本"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/deployversions"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def delete_maven_setting(self, session, enterprise_id, region, name):
        """

        :param enterprise_id:
        :param region:
        :param name:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._delete(url, self.default_headers, region=region_info.region_name)
        return res, body

    def add_maven_setting(self, session, enterprise_id, region, body):
        """

        :param enterprise_id:
        :param region:
        :param body:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting"
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def get_maven_setting(self, session, enterprise_id, region, name):
        """

        :param enterprise_id:
        :param region:
        :param name:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._get(url, self.default_headers, region=region_info.region_name)
        return res, body

    def update_maven_setting(self, session, enterprise_id, region, name, body):
        """

        :param enterprise_id:
        :param region:
        :param name:
        :param body:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting/{0}".format(name)
        res, body = self._put(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def list_maven_settings(self, session, enterprise_id, region):
        """

        :param enterprise_id:
        :param region:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/cluster/builder/mavensetting"
        res, body = self._get(url, self.default_headers, region=region_info.region_name)
        return res, body

    def get_enterprise_api_version_v2(self, session, enterprise_id, region, **kwargs):
        """获取api版本-v2"""
        kwargs["retries"] = 1
        kwargs["timeout"] = 1
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, **kwargs)
        return res, body

    def get_region_resources(self, session, enterprise_id, **kwargs):
        """

        :param enterprise_id:
        :param kwargs:
        :return:
        """
        region_name = kwargs.get("region")
        if kwargs.get("test"):
            self.get_enterprise_api_version_v2(session, enterprise_id, region=region_name)
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region_name, session)
        url += "/v2/cluster"
        self._set_headers(token)
        kwargs["retries"] = 1
        kwargs["timeout"] = 3
        res, body = self._get(url, self.default_headers, **kwargs)
        return res, body

    def test_region_api(self, region_data):
        region = RegionConfig(**region_data)
        url = region.url + "/v2/show"
        return self._get(url, self.default_headers, region=region, for_test=True, retries=1, timeout=1)

    def check_region_api(self, session, enterprise_id, region):
        """

        :param enterprise_id:
        :param region:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        try:
            url = region_info.url + "/v2/show"
            _, body = self._get(url, self.default_headers, region=region_info.region_name, retries=1, timeout=1)
            return body
        except Exception as e:
            logger.exception(e)
            return None

    def list_tenants(self, session, enterprise_id, region, page=1, page_size=10):
        """list tenants"""
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants?page={0}&pageSize={1}&eid={2}".format(page, page_size, enterprise_id)
        try:
            res, body = self._get(url, self.default_headers, region=region_info.region_name)
            return res, body
        except ApiBaseHttpClient.CallApiError as e:
            return {'status': e.message['httpcode']}, e.message['body']

    def set_tenant_limit_memory(self, session, enterprise_id, tenant_name, region, body):
        """

        :param enterprise_id:
        :param tenant_name:
        :param region:
        :param body:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/limit_memory".format(tenant_name)
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def create_service_monitor(self, session, enterprise_id, region, tenant_name, service_alias, body):
        """

        :param enterprise_id:
        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors".format(tenant_name, service_alias)
        res, body = self._post(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def update_service_monitor(self, session, enterprise_id, region, tenant_name, service_alias, name, body):
        """

        :param enterprise_id:
        :param region:
        :param tenant_name:
        :param service_alias:
        :param name:
        :param body:
        :return:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors/{2}".format(tenant_name, service_alias, name)
        res, body = self._put(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))
        return res, body

    def delete_service_monitor(self, session, enterprise_id, region, tenant_name, service_alias, name, body):
        """

        :param enterprise_id:
        :param region:
        :param tenant_name:
        :param service_alias:
        :param name:
        :param body:
        """
        region_info = get_enterprise_region_info(region, session)
        if not region_info:
            raise ServiceHandleException("region not found")
        url = region_info.url
        url += "/v2/tenants/{0}/services/{1}/service-monitors/{2}".format(tenant_name, service_alias, name)
        res, body = self._delete(url, self.default_headers, region=region_info.region_name, body=json.dumps(body))

    def get_pod(self, session, region_name, tenant_name, pod_name):
        """

        :param region_name:
        :param tenant_name:
        :param pod_name:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/pods/" + pod_name

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body["bean"]

    def get_monitor_metrics(self, session, region_name, tenant, target, app_id, component_id):
        """

        :param region_name:
        :param tenant:
        :param target:
        :param app_id:
        :param component_id:
        :return:
        """
        url, token = get_region_access_info(tenant.tenant_name, region_name, session)
        url += "/v2/monitor/metrics?target={target}&tenant={tenant_id}&app={app_id}&component={component_id}".format(
            target=target, tenant_id=tenant.tenant_id, app_id=app_id, component_id=component_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body

    def check_resource_name(self, session, tenant_name, region_name, rtype, name):
        """

        :param tenant_name:
        :param region_name:
        :param rtype:
        :param name:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        tenant_region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/checkResourceName"

        self._set_headers(token)
        _, body = self._post(
            url, self.default_headers, region=region_name, body=json.dumps({
                "type": rtype,
                "name": name,
            }))
        return body["bean"]

    def get_region_license_feature(self, session, tenant, region_name):
        """

        :param tenant:
        :param region_name:
        :return:
        """
        url, token = get_region_access_info(tenant.tenant_name, region_name, session)
        url += "/license/features"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return body

    def list_app_statuses_by_app_ids(self, session, tenant_name, region_name, body):
        """

        :param tenant_name:
        :param region_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        url += "/v2/tenants/{tenant_name}/appstatuses".format(tenant_name=tenant_name)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, body=json.dumps(body), region=region_name)
        return body

    def list_scaling_records(self, session, region, tenant_name, service_alias, page=None, page_size=None):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param page:
        :param page_size:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparecords"

        if page is not None and page_size is not None:
            url += "?page={}&page_size={}".format(page, page_size)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def create_xpa_rule(self, session, region, tenant_name, service_alias, data):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param data:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparules"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, body=json.dumps(data), region=region)
        return body

    def update_xpa_rule(self, session, region, tenant_name, service_alias, data):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param data:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/xparules"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(data), region=region)
        return body

    def update_ingresses_by_certificate(self, session, region_name, tenant_name, body):
        """

        :param region_name:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region_name, session)
        region = get_tenant_region_info(tenant_name, region_name, session)
        url = url + "/v2/tenants/" + region.region_tenant_name + "/gateway/certificate"
        self._set_headers(token)
        res, body = self._put(url, self.default_headers, body=json.dumps(body), region=region_name)
        return res, body

    def get_tenant_resources(self, session, region, tenant_name, enterprise_id):
        """获取指定租户的资源使用情况"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/resources?enterprise_id=" + enterprise_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10)
        return body

    def get_region_publickey(self, session, tenant_name, region, enterprise_id, tenant_id):
        """

        :param tenant_name:
        :param region:
        :param enterprise_id:
        :param tenant_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/builder/publickey/" + tenant_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_event_log(self, session, region, tenant_name, service_alias, body):
        """获取事件日志"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/event-log"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body), timeout=10)
        return res, body

    def get_target_events_list(self, session, region, tenant_name, target, target_id, page, page_size):
        """获取作用对象事件日志列表"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/events" + "?target={0}&target-id={1}&page={2}&size={3}".format(target, target_id, page,
                                                                                        page_size)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=20)
        return res, body

    def get_events_log(self, session, tenant_name, region, event_id):
        """获取作用对象事件日志内容"""
        url, token = get_region_access_info(tenant_name, region, session)
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

    def get_api_version_v2(self, session, tenant_name, region_name):
        """获取api版本-v2"""
        url, token = get_region_access_info(tenant_name, region_name, session)
        url += "/v2/show"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region_name)
        return res, body

    def get_region_tenants_resources(self, session, region, data, enterprise_id=""):
        """获取租户在数据中心下的资源使用情况"""
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url += "/v2/resources/tenants"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(data), region=region, timeout=15.0)
        return body

    def get_service_resources(self, session, tenant_name, region, data):
        """获取一批组件的资源使用情况"""
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/resources/services"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(data), region=region, timeout=10.0)
        return body

    def share_service(self, session, region, tenant_name, service_alias, body):
        """分享应用"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = "{0}/v2/tenants/{1}/services/{2}/share".format(url, tenant_region.region_tenant_name, service_alias)
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    def share_service_result(self, session, region, tenant_name, service_alias, region_share_id):
        """查询分享应用状态"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = "{0}/v2/tenants/{1}/services/{2}/share/{3}".format(url, tenant_region.region_tenant_name, service_alias,
                                                                 region_share_id)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_port(self, session, region, tenant_name, lock=False):
        """

        :param region:
        :param tenant_name:
        :param lock:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/gateway/ports?lock={}".format(lock)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_ips(self, session, region, tenant_name):
        """

        :param region:
        :param tenant_name:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/gateway/ips"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_query_data(self, session, region, tenant_name, params):
        """获取监控数据"""

        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_service_access(self, session, region, tenant_name, params):
        """获取团队下组件访问量排序"""

        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_domain_access(self, session, region, tenant_name, params):
        """获取团队下域名访问量排序"""

        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/api/v1/query" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_query_range_data(self, session, region, tenant_name, params):
        """获取监控范围数据"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/api/v1/query_range" + params
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, timeout=10, retries=1)
        return res, body

    def get_service_publish_status(self, session, region, tenant_name, service_key, app_version):
        """

        :param region:
        :param tenant_name:
        :param service_key:
        :param app_version:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/builder/publish/service/{0}/version/{1}".format(service_key, app_version)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_tenant_events(self, session, region, tenant_name, event_ids):
        """获取多个事件的状态"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/event"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region, body=json.dumps({"event_ids": event_ids}),
                              timeout=10)
        return body

    def get_events_by_event_ids(self, region_name, event_ids, session=SessionClass()):
        """获取多个event的事件"""
        region_info = region_config_repo.get_region_config_by_region_name(session=session, region_name=region_name)
        url = region_info.url + "/v2/event"
        self._set_headers(region_info.token)
        res, body = self._get(
            url, self.default_headers, region=region_name, body=json.dumps({"event_ids": event_ids}), timeout=10)
        return body

    def get_protocols(self, session, region, tenant_name):
        """
        @ 获取当前数据中心支持的协议
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/protocols"
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    # 获取数据中心应用异常信息

    def get_app_abnormal(self, url, token, region, start_stamp, end_stamp):
        """

        :param url:
        :param token:
        :param region:
        :param start_stamp:
        :param end_stamp:
        :return:
        """
        url += "/v2/notificationEvent?start={0}&end={1}".format(start_stamp, end_stamp)
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 第三方注册api注册方式添加endpoints
    def put_third_party_service_endpoints(self, session, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方注册api注册方式添加endpoints
    def post_third_party_service_endpoints(self, session, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方注册api注册方式添加endpoints
    def delete_third_party_service_endpoints(self, session, region, tenant_name, service_alias, data):
        """第三方组件endpoint操作"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    # 第三方组件endpoint数据
    def get_third_party_service_pods(self, session, region, tenant_name, service_alias):
        """获取第三方组件endpoint数据"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/endpoints"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 获取第三方组件健康检测信息
    def get_third_party_service_health(self, session, region, tenant_name, service_alias):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/3rd-party/probe"

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    # 修改第三方组件健康检测信息
    def put_third_party_service_health(self, session, region, tenant_name, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/3rd-party/probe"

        self._set_headers(token)
        res, body = self._put(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    # 5.1版本组件批量操作
    def batch_operation_service(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/batchoperation"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return res, body

    # 修改网关自定义配置项
    def upgrade_configuration(self, session, region, tenant_name, service_alias, body):
        """

        :param region:
        :param tenant_name:
        :param service_alias:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        body["tenant_id"] = tenant_region.region_tenant_id
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + "/rule-config"
        self._set_headers(token)
        res, body = self._put(url, self.default_headers, json.dumps(body), region=region)
        logger.debug('-------1111--body----->{0}'.format(body))
        return res, body

    def restore_properties(self, session, region, tenant_name, service_alias, uri, body):
        """When the upgrade fails, restore the properties of the service"""

        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/services/" + service_alias + uri

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, json.dumps(body), region=region)
        return body


remote_build_client = RemoteBuildClient()
