import json
import os

from fastapi.encoders import jsonable_encoder
from loguru import logger

from common.api_base_http_client import ApiBaseHttpClient
from common.base_client_service import get_region_access_info, get_tenant_region_info, \
    get_region_access_info_by_enterprise_id


class RemoteMigrateClient(ApiBaseHttpClient):
    """
    RemoteMigrateClient
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

    def export_app(self, session, region, enterprise_id, data):
        """导出应用"""
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url += "/v2/app/export"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data).encode('utf-8'))
        return res, body

    def get_app_export_status(self, session, region, enterprise_id, event_id):
        """查询应用导出状态"""
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url = url + "/v2/app/export/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def import_app_2_enterprise(self, session, region, enterprise_id, data):
        """ import app to enterprise"""
        url, token = get_region_access_info_by_enterprise_id(enterprise_id, region, session)
        url += "/v2/app/import"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def import_app(self, session, region, tenant_name, data):
        """导入应用"""
        url, token = get_region_access_info(tenant_name, region, session)
        url += "/v2/app/import"
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return res, body

    def get_app_import_status(self, session, region, tenant_name, event_id):
        """查询导入状态"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_enterprise_app_import_status(self, session, region, eid, event_id):
        """

        :param region:
        :param eid:
        :param event_id:
        :return:
        """
        url, token = get_region_access_info_by_enterprise_id(eid, region, session)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_enterprise_import_file_dir(self, session, region, eid, event_id):
        """

        :param region:
        :param eid:
        :param event_id:
        :return:
        """
        url, token = get_region_access_info_by_enterprise_id(eid, region, session)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def get_import_file_dir(self, session, region, tenant_name, event_id):
        """查询导入目录"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return res, body

    def delete_enterprise_import(self, session, region, eid, event_id):
        """

        :param region:
        :param eid:
        :param event_id:
        :return:
        """
        url, token = get_region_access_info_by_enterprise_id(eid, region, session)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def delete_import(self, session, region, tenant_name, event_id):
        """删除导入"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/app/import/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def create_import_file_dir(self, session, region, tenant_name, event_id):
        """创建导入目录"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region)
        return res, body

    def delete_enterprise_import_file_dir(self, session, region, eid, event_id):
        """

        :param region:
        :param eid:
        :param event_id:
        :return:
        """
        url, token = get_region_access_info_by_enterprise_id(eid, region, session)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def delete_import_file_dir(self, session, region, tenant_name, event_id):
        """删除导入目录"""
        url, token = get_region_access_info(tenant_name, region, session)
        url = url + "/v2/app/import/ids/" + event_id
        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return res, body

    def backup_group_apps(self, session, region, tenant_name, body):
        """

        :param region:
        :param tenant_name:
        :param body:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(body))
        return body

    def get_backup_status_by_backup_id(self, session, region, tenant_name, backup_id):
        """

        :param region:
        :param tenant_name:
        :param backup_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + str(backup_id)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def delete_backup_by_backup_id(self, session, region, tenant_name, backup_id):
        """

        :param region:
        :param tenant_name:
        :param backup_id:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + str(backup_id)

        self._set_headers(token)
        res, body = self._delete(url, self.default_headers, region=region)
        return body

    def get_backup_status_by_group_id(self, session, region, tenant_name, group_uuid):
        """

        :param region:
        :param tenant_name:
        :param group_uuid:
        :return:
        """
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups?group_id=" + str(group_uuid)

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def star_apps_migrate_task(self, session, region, tenant_name, backup_id, data):
        """发起迁移命令"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" + backup_id + "/restore"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return body

    def get_apps_migrate_status(self, session, region, tenant_name, backup_id, restore_id):
        """获取迁移结果"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backups/" \
              + backup_id + "/restore/" + restore_id

        self._set_headers(token)
        res, body = self._get(url, self.default_headers, region=region)
        return body

    def copy_backup_data(self, session, region, tenant_name, data):
        """数据中心备份数据进行拷贝"""
        url, token = get_region_access_info(tenant_name, region, session)
        tenant_region = get_tenant_region_info(tenant_name, region, session)
        url = url + "/v2/tenants/" + tenant_region.region_tenant_name + "/groupapp/backupcopy"

        self._set_headers(token)
        res, body = self._post(url, self.default_headers, region=region, body=json.dumps(data))
        return body


remote_migrate_client_api = RemoteMigrateClient()
