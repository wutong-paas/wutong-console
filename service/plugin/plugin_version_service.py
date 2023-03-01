import datetime

from loguru import logger

from clients.remote_plugin_client import remote_plugin_client
from database.session import SessionClass
from repository.plugin.plugin_version_repo import plugin_version_repo

REGION_BUILD_STATUS_MAP = {
    "failure": "build_fail",
    "complete": "build_success",
    "building": "building",
    "timeout": "time_out",
}


class PluginBuildVersionService(object):
    def create_build_version(self, session: SessionClass,
                             region,
                             plugin_id,
                             tenant_id,
                             user_id,
                             update_info,
                             build_status,
                             min_memory,
                             build_cmd="",
                             image_tag="latest",
                             code_version="master",
                             build_version=None,
                             min_cpu=None):
        """创建插件版本信息"""
        if min_cpu is None or type(min_cpu) != int:
            min_cpu = 0
        if not build_version:
            build_version = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

        build_version_params = {
            "plugin_id": plugin_id,
            "tenant_id": tenant_id,
            "region": region,
            "user_id": user_id,
            "update_info": update_info,
            "build_version": build_version,
            "build_status": build_status,
            "min_memory": min_memory,
            "min_cpu": min_cpu,
            "build_cmd": build_cmd,
            "image_tag": image_tag,
            "code_version": code_version,
        }
        return plugin_version_repo.create_plugin_build_version(session, **build_version_params)

    def get_newest_usable_plugin_version(self, session: SessionClass, tenant_id, plugin_id):
        pbvs = plugin_version_repo.get_plugin_versions(session,
                                                       plugin_id)  # .filter(build_status="build_success")
        if pbvs:
            return pbvs[0]
        return None

    def get_by_id_and_version(self, session: SessionClass, tenant_id, plugin_id, plugin_version):
        return plugin_version_repo.get_by_id_and_version(session, plugin_id, plugin_version)

    def get_plugin_version_by_id(self, session: SessionClass, tenant_id, plugin_id):
        return plugin_version_repo.get_plugin_version_by_id(session, tenant_id, plugin_id)

    def delete_build_version_by_id_and_version(self, session, tenant_id, plugin_id, build_version, force=False):
        plugin_build_version = plugin_version_repo.get_by_id_and_version(session, plugin_id, build_version)
        if not plugin_build_version:
            return 404, "插件不存在"
        if not force:
            count_of_version = plugin_version_repo.get_plugin_versions(session=session,
                                                                       plugin_id=plugin_id).count()
            if count_of_version == 1:
                return 409, "至少保留插件的一个版本"
        plugin_version_repo.delete_build_version(session, tenant_id, plugin_id, build_version)
        return 200, "删除成功"

    def get_region_plugin_build_status(self, session, region, tenant_env, plugin_id, build_version):
        try:
            body = remote_plugin_client.get_build_status(session, region, tenant_env, plugin_id, build_version)
            status = body["bean"]["status"]
            rt_status = REGION_BUILD_STATUS_MAP[status]
        except remote_plugin_client.CallApiError as e:
            if e.status == 404:
                rt_status = "unbuild"
            else:
                rt_status = "unknown"
        return rt_status

    def update_plugin_build_status(self, session, region, tenant_env):
        logger.debug("start thread to update build status")
        pbvs = plugin_version_repo.get_plugin_build_version_by_tenant_and_region(
            session, tenant_env.tenant_id, region)
        if pbvs:
            for pbv in pbvs:
                status = self.get_region_plugin_build_status(session, region, tenant_env, pbv.plugin_id,
                                                             pbv.build_version)
                pbv.build_status = status

    def get_plugin_build_status(self, session, region, tenant_env, plugin_id, build_version):
        pbv = plugin_version_repo.get_by_id_and_version(session, plugin_id, build_version)

        if pbv.build_status == "building":
            status = self.get_region_plugin_build_status(session, region, tenant_env, pbv.plugin_id,
                                                         pbv.build_version)
            pbv.build_status = status
            # pbv.save()
        return pbv


plugin_version_service = PluginBuildVersionService()
