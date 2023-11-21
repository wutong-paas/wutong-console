import json
import os

from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info


class RemoteVirtualClient(ApiBaseHttpClient):
    """
    RemoteTenantClient
    """

    def __init__(self, *args, **kwargs):
        ApiBaseHttpClient.__init__(self, *args, **kwargs)
        self.default_headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }

    def _set_headers(self, token):
        if not token:
            if os.environ.get("REGION_TOKEN"):
                self.default_headers.update(
                    {"Authorization": os.environ.get("REGION_TOKEN")}
                )
            else:
                self.default_headers.update({"Authorization": ""})
        else:
            self.default_headers.update({"Authorization": token})
        logger.debug("Default headers: {0}".format(self.default_headers))

    def create_virtual_machine(self, session, region, tenant_env, body):
        """
        创建虚拟机
        :param session:
        :param region:
        :param tenant_env:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, json.dumps(body), region=region
        )
        return body["bean"]

    def get_virtual_machine(self, session, region, tenant_env, vm_id):
        """
        获取单个虚拟机
        :param session:
        :param region:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms/"
            + vm_id
        )

        self._set_headers(token)
        res, body = self._get(
            session, url, self.default_headers, region=region
        )
        return body["bean"]

    def get_virtual_machine_list(self, session, region, tenant_env):
        """
        获取虚拟机列表
        :param session:
        :param region:
        :param tenant_env:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms"
        )

        self._set_headers(token)
        res, body = self._get(
            session, url, self.default_headers, region=region
        )
        return body["bean"]["vms"]

    def update_virtual_machine(self, session, region, tenant_env, vm_id, body):
        """
        更新虚拟机列表
        :param session:
        :param region:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms/"
            + vm_id
        )

        self._set_headers(token)
        res, body = self._put(
            session, url, self.default_headers, json.dumps(body), region=region
        )
        return body["bean"]

    def delete_virtual_machine(self, session, region, tenant_env, vm_id):
        """
        更新虚拟机列表
        :param session:
        :param region:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region, session)

        url = (
            url
            + "/v2/tenants/"
            + tenant_env.tenant_name
            + "/envs/"
            + tenant_env.env_name
            + "/vms/"
            + vm_id
        )

        self._set_headers(token)
        self._delete(
            session, url, self.default_headers, region=region
        )
        return None


remote_virtual_client = RemoteVirtualClient()
