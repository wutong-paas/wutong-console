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

    def create_virtual_machine(self, session, region_name, tenant_env, body):
        """
        创建虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

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
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return body["bean"]

    def get_virtual_machine(self, session, region_name, tenant_env, vm_id):
        """
        获取单个虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

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
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]

    def get_virtual_machine_list(self, session, region_name, tenant_env):
        """
        获取虚拟机列表
        :param session:
        :param region_name:
        :param tenant_env:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

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
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]["vms"]

    def update_virtual_machine(self, session, region_name, tenant_env, vm_id, body):
        """
        更新虚拟机列表
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

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
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return body["bean"]

    def delete_virtual_machine(self, session, region_name, tenant_env, vm_id):
        """
        删除虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

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
            session, url, self.default_headers, region=region_name
        )
        return None

    def start_virtual_machine(self, session, region_name, tenant_env, vm_id):
        """
        启动虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/start"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]

    def stop_virtual_machine(self, session, region_name, tenant_env, vm_id):
        """
        停止虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/stop"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]

    def restart_virtual_machine(self, session, region_name, tenant_env, vm_id):
        """
        重启虚拟机
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/restart"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]

    def add_virtual_machine_port(self, session, region_name, tenant_env, vm_id, body):
        """
        添加虚拟机端口
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/ports"
        )

        self._set_headers(token)
        self._post(
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return None

    def delete_virtual_machine_port(self, session, region_name, tenant_env, vm_id, body):
        """
        删除虚拟机端口
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/ports"
        )

        self._set_headers(token)
        self._delete(
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return None

    def create_virtual_port_gateway(self, session, region_name, tenant_env, vm_id, body):
        """
        创建虚拟机端口网关
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/gateways"
        )

        self._set_headers(token)
        self._post(
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return None

    def get_virtual_port_gateway(self, session, region_name, tenant_env, vm_id):
        """
        获取虚拟机端口网关
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/ports"
        )

        self._set_headers(token)
        res, body = self._get(
            session, url, self.default_headers, region=region_name
        )
        return body["bean"]

    def update_virtual_port_gateway(self, session, region_name, tenant_env, vm_id, gateway_id, body):
        """
        更新虚拟机端口网关
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param gateway_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/gateways/"
                + gateway_id
        )

        self._set_headers(token)
        self._put(
            session, url, self.default_headers, json.dumps(body), region=region_name
        )
        return None

    def delete_virtual_port_gateway(self, session, region_name, tenant_env, vm_id, gateway_id):
        """
        删除虚拟机端口网关
        :param session:
        :param region_name:
        :param tenant_env:
        :param vm_id:
        :param gateway_id:
        :return:
        """
        url, token = get_region_access_info(region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/gateways/"
                + gateway_id
        )

        self._set_headers(token)
        self._delete(
            session, url, self.default_headers, region=region_name
        )
        return None

    def connect_virtctl_console(self, session, region, body):
        """
        虚拟机连接 virtctl-console
        :param session:
        :param region:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region.region_name, session)

        url = (
                region.wsurl
                + "/docker_virtctl_console"
        )

        self._set_headers(token)
        self._get(
            session, url, self.default_headers, json.dumps(body), region=region.region_name
        )
        return None

    def virtual_connect_shh(self, session, region, body):
        """
        虚拟机连接 ssh
        :param session:
        :param region:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region.region_name, session)

        url = (
                region.wsurl
                + "/docker_vm_ssh"
        )

        self._set_headers(token)
        self._get(
            session, url, self.default_headers, json.dumps(body), region=region.region_name
        )
        return None

    def get_virtual_label(self, session, region):
        """
        获取虚拟机调度标签
        :param session:
        :param region:
        :return:
        """
        url, token = get_region_access_info(region.region_name, session)

        url = (
                url
                + "/v2/cluster/nodes/vm-selector-labels"
        )

        self._set_headers(token)
        res, body = self._get(
            session, url, self.default_headers, region=region.region_name
        )
        return body["list"]

    def open_port_external_service(self, session, tenant_env, region, vm_id, body):
        """
        开启端口对外服务
        :param session:
        :param tenant_env:
        :param region:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region.region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/ports/enable"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, json.dumps(body), region=region.region_name
        )
        return body["list"]

    def close_port_external_service(self, session, tenant_env, region, vm_id, body):
        """
        关闭端口对外服务
        :param session:
        :param tenant_env:
        :param region:
        :param vm_id:
        :param body:
        :return:
        """
        url, token = get_region_access_info(region.region_name, session)

        url = (
                url
                + "/v2/tenants/"
                + tenant_env.tenant_name
                + "/envs/"
                + tenant_env.env_name
                + "/vms/"
                + vm_id
                + "/ports/disable"
        )

        self._set_headers(token)
        res, body = self._post(
            session, url, self.default_headers, json.dumps(body), region=region.region_name
        )
        return body["list"]


remote_virtual_client = RemoteVirtualClient()
