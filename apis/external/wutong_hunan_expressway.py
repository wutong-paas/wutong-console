import datetime
from typing import Optional, Any
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from loguru import logger

from clients.remote_component_client import remote_component_client
from clients.remote_expressway_client import hunan_expressway_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_info_repo import region_repo
from schemas.response import Response
from service.expressway.hunan_expressway_service import hunan_expressway_service
from service.team_service import team_services

router = APIRouter()


@router.get("/v1.0/metrics/{enterprise_id}/cluster", response_model=Response, name="获取集群节点信息")
async def get_store(
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    result_bean = {}
    node_info = []
    pod = []
    store = {
        "total_cpu": 0,
        "used_cpu": 0,
        "total_memory": 0,
        "used_memory": 0,
        "total_disk": 0,
        "used_disk": 0
    }
    pod = {
        "total": 0,
        "used_pod": 0,
        "free_pod": 0
    }
    usable_regions = region_repo.get_usable_regions_by_enterprise_id(session=session, enterprise_id=enterprise_id)
    for r in usable_regions:
        region_name = r.region_name
        try:
            res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
            result_bean = body["bean"]
            status = res["status"]
            if status != 200:
                return JSONResponse(general_message(400, "failed", "获取集群节点信息失败"), status_code=400)
        except Exception as e:
            logger.exception(e)

        for node in result_bean['node_resources']:
            # node_info.append(node)
            node_info.append({
                "name": node["node_name"],
                "total_cpu": node["capacity_cpu"],
                "used_cpu": node["used_cpu"],
                "total_memory": node["capacity_mem"],
                "used_memory": node["used_mem"],
                "total_pod": node["capacity_pod"],
                "used_pod": node["used_pod"]
            })

        store["total_cpu"] += result_bean["cap_cpu"]
        store["used_cpu"] += result_bean["req_cpu"]
        store["total_memory"] += result_bean["cap_mem"]
        store["used_memory"] += result_bean["req_mem"]
        store["total_disk"] += result_bean["total_capacity_storage"]
        store["used_disk"] += result_bean["total_used_storage"]

        total_pod = result_bean['total_capacity_pods'] + result_bean['total_used_pods']
        pod["total"] += total_pod
        pod["used_pod"] += result_bean['total_used_pods']
        pod["free_pod"] += result_bean['total_capacity_pods']

    store["used_disk"] = round(store["used_disk"], 2)
    info = {
        "store": store,
        "pod": pod,
        "node": {
            "total": len(node_info),
            "info": node_info
        }
    }

    return JSONResponse(general_message(200, "success", "获取成功", bean=info), status_code=200)


@router.get("/v1.0/metrics/{enterprise_id}/overview/app", response_model=Response, name="总览-应用信息")
async def overview_app(
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    service_info = {
        "total": 0,
        "running": 0,
        "unrunning": 0,
        "abnormal": 0
    }
    group_info = {
        "total": 0,
        "running": 0,
        "unrunning": 0,
        "abnormal": 0
    }
    usable_regions = region_repo.get_usable_regions_by_enterprise_id(session=session, enterprise_id=enterprise_id)
    for r in usable_regions:
        region_name = r.region_name
        apps = hunan_expressway_service.get_all_app(session, region_name)
        app_total_num = len(apps)

        try:
            data = remote_component_client.get_all_services_status(session, enterprise_id,
                                                                   region_name,
                                                                   test=True)
            if data:
                service_abnormal_ids = data["abnormal_services"]
                service_close_ids = data["unrunning_services"]
                service_running_num = len(data["running_services"])
                service_unrunning_num = len(data["unrunning_services"])
                service_abnormal_num = len(data["abnormal_services"])
                service_total_num = service_running_num + service_unrunning_num + service_abnormal_num
                service_info["total"] += service_total_num
                service_info["running"] += service_running_num
                service_info["unrunning"] += service_unrunning_num
                service_info["abnormal"] += service_abnormal_num
                groups_rel_list = hunan_expressway_service.get_groups_by_service_id(session, service_abnormal_ids)
                app_ids = [group_rel.group_id for group_rel in groups_rel_list]
                app_ids = list(set(app_ids))
                app_abnormal_num = len(app_ids)
                groups_rel_list = hunan_expressway_service.get_groups_by_service_id(session, service_close_ids)
                app_ids = [group_rel.group_id for group_rel in groups_rel_list]
                app_ids = list(set(app_ids))
                app_unrunning_num = len(app_ids)
                app_running_num = app_total_num - app_abnormal_num - app_unrunning_num
                group_info["total"] += app_total_num
                group_info["running"] += app_running_num
                group_info["unrunning"] += app_unrunning_num
                group_info["abnormal"] += app_abnormal_num

        except (remote_component_client.CallApiError, ServiceHandleException) as e:
            logger.exception("get region services_status:'{0}' running failed: {1}".format(region_name, e))

    info = {
        "group_info": group_info,
        "service_info": service_info
    }

    result = general_message(200, "success", "查询成功", bean=info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/v1.0/metrics/{enterprise_id}/tenant/info", response_model=Response, name="总览-团队信息")
async def overview_tenant(
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    tenant_pods_info = {}
    tenant_pods = {}
    tenant_info = []
    usable_regions = region_repo.get_usable_regions_by_enterprise_id(session=session, enterprise_id=enterprise_id)
    for r in usable_regions:
        region_name = r.region_name
        try:
            res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
            tenant_pods = body["bean"]["tenant_pods"]
            status = res["status"]
            if status != 200 and tenant_pods:
                return JSONResponse(general_message(400, "failed", "获取集群团队信息失败"), status_code=400)
        except Exception as e:
            logger.exception(e)

        tenant_pods_info.update(sorted(tenant_pods.items(), key=lambda x: x[1])[-4:])

    tenant_pods_info = sorted(tenant_pods_info.items(), key=lambda x: x[1])[-4:]

    for tenant_tuple in tenant_pods_info:
        pods_num = tenant_tuple[1]
        tenant = team_services.get_team_by_team_id(session, tenant_tuple[0])

        team_service_num = service_info_repo.get_hn_team_service_num_by_team_id(
            session=session, team_id=tenant.tenant_id)
        groups = application_repo.get_hn_tenant_region_groups(session, tenant.tenant_id)

        tenant_info.append({
            "tenant_name": tenant.tenant_alias,
            "apps": len(groups),
            "services": team_service_num,
            "pods": pods_num
        })

    result = general_message(200, "success", "查询成功", bean=tenant_info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/v1.0/metrics/{enterprise_id}/event", response_model=Response, name="集群事件统计")
async def get_region_event(
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    events = []
    event_list = []
    result_bean = {}
    usable_regions = region_repo.get_usable_regions_by_enterprise_id(session=session, enterprise_id=enterprise_id)
    for r in usable_regions:
        region_name = r.region_name
        try:
            res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
            result_bean = body["bean"]
            status = res["status"]
            if status != 200:
                return JSONResponse(general_message(400, "failed", "获取集群节点信息失败"), status_code=400)
        except Exception as e:
            logger.exception(e)

        try:
            res, body = hunan_expressway_client.get_region_event(session, region_name, enterprise_id)
            event_list = body["list"]
            status = res["status"]
            if status != 200:
                return JSONResponse(general_message(400, "failed", "获取集群事件失败"), status_code=400)
        except Exception as e:
            logger.exception(e)

        now = datetime.datetime.now()
        now_time = now.strftime("%Y-%m-%d %H:%M:%S")
        for event in event_list:
            events.append({
                "time": now_time,
                "name": "集群事件",
                "mesc": event["message"],
                "level": "警告",
            })

        for node in result_bean['node_resources']:
            name = node["node_name"]
            total_cpu = node["capacity_cpu"]
            used_cpu = node["used_cpu"]
            total_memory = node["capacity_mem"]
            used_memory = node["used_mem"]
            total_pod = node["capacity_pod"]
            used_pod = node["used_pod"]
            total_storage = node["capacity_storage"]
            used_storage = node["used_storage"]
            cpu_percent = used_cpu / total_cpu
            memory_percent = used_memory / total_memory
            pod_percent = used_pod / total_pod
            storage_percent = used_storage / total_storage if total_storage != 0 else 0
            if cpu_percent >= 0.80:
                if cpu_percent >= 1.20:
                    events.append({
                        "time": now_time,
                        "name": "节点CPU",
                        "mesc": name + "节点CPU过高",
                        "level": "紧急",
                    })
                else:
                    events.append({
                        "time": now_time,
                        "name": "节点CPU",
                        "mesc": name + "节点CPU略高",
                        "level": "一般",
                    })
            if memory_percent >= 0.80:
                if cpu_percent >= 0.95:
                    events.append({
                        "time": now_time,
                        "name": "节点内存",
                        "mesc": name + "节点内存严重不足",
                        "level": "紧急",
                    })
                else:
                    events.append({
                        "time": now_time,
                        "name": "节点内存",
                        "mesc": name + "节点内存不足",
                        "level": "一般",
                    })
            if pod_percent >= 0.90:
                events.append({
                    "time": now_time,
                    "name": "节点POD",
                    "mesc": name + "节点分配容器组过多",
                    "level": "紧急",
                })
            if storage_percent >= 0.90:
                events.append({
                    "time": now_time,
                    "name": "节点存储",
                    "mesc": name + "节点存在磁盘存储压力",
                    "level": "紧急",
                })

    result = general_message(200, "success", "查询成功", bean=events)
    return JSONResponse(result, status_code=result["code"])
