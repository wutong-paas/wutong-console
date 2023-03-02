# -*- coding: utf8 -*-
from clients.remote_build_client import remote_build_client
from repository.region.region_app_repo import region_app_repo


class MonitorService(object):
    @staticmethod
    def get_monitor_metrics(session, region_name, tenant_env, target, app_id="", component_id=""):
        region_app_id = ""
        if app_id:
            region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        data = remote_build_client.get_monitor_metrics(session, region_name, tenant_env, target, region_app_id, component_id)
        if not data:
            return None
        return data.get("list", [])


monitor_service = MonitorService()
