from clients.remote_app_client import remote_app_client
from repository.expressway.hunan_expressway_repo import hunan_expressway_repo
from repository.region.region_app_repo import region_app_repo
from loguru import logger
from exceptions.main import ServiceHandleException
from clients.remote_expressway_client import hunan_expressway_client


class HunanExpresswayService(object):

    def get_all_app(self, session, region_name):
        return hunan_expressway_repo.get_all_app(session, region_name)

    def get_app_status(self, session, tenant_env, region_name, app_id):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        status = remote_app_client.get_app_status(session, region_name, tenant_env, region_app_id)
        if status.get("status") == "NIL":
            status["status"] = None
        overrides = status.get("overrides", [])
        if overrides:
            status["overrides"] = [{override.split("=")[0]: override.split("=")[1]} for override in overrides]
        return status

    def get_tenant_by_app_id(self, session, app_id):
        app = hunan_expressway_repo.get_app_by_app_id(session, app_id)
        tenant_env_id = app.tenant_env_id
        return hunan_expressway_repo.get_tenant_by_tenant_env_id(session, tenant_env_id)

    def get_groups_by_service_id(self, session, service_ids):
        return hunan_expressway_repo.get_groups_by_service_id(session, service_ids)

    def get_services_by_tenant_env_id(self, session, tenant_env_id):
        return hunan_expressway_repo.get_services_by_tenant_env_id(session, tenant_env_id)

    def get_all_region_info(self, session, region_code, result_bean, node_info, store, pod):

        try:
            res, body = hunan_expressway_client.get_region_cluster(session, region_code)
            result_bean = body["bean"]
            status = res["status"]
            if status != 200:
                raise ServiceHandleException("failed", "获取集群节点信息失败", status, status)
        except Exception as e:
            logger.exception(e)

        for node in result_bean['node_resources']:
            # node_info.append(node)
            node_info.append({
                "name": node["node_name"],
                "total_cpu": round(node["capacity_cpu"], 0),
                "used_cpu": round(node["used_cpu"], 0),
                "total_memory": round(node["capacity_mem"], 0),
                "used_memory": round(node["used_mem"], 0),
                "total_pod": round(node["capacity_pod"], 0),
                "used_pod": round(node["used_pod"], 0)
            })

        store["total_cpu"] += result_bean["cap_cpu"]
        store["used_cpu"] += result_bean["req_cpu"]
        store["total_memory"] += result_bean["cap_mem"]
        store["used_memory"] += result_bean["req_mem"]
        store["total_disk"] += result_bean["total_capacity_storage"]
        store["used_disk"] += result_bean["total_used_storage"]

        pod["total"] += result_bean['total_capacity_pods']
        pod["used_pod"] += result_bean['total_used_pods']
        pod["free_pod"] += result_bean['total_capacity_pods'] - result_bean['total_used_pods']


hunan_expressway_service = HunanExpresswayService()
