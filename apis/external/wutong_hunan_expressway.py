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
from schemas.response import Response
from service.expressway.hunan_expressway_service import hunan_expressway_service
from service.team_service import team_services

router = APIRouter()


@router.get("/v1.0/expressway/{region_name}/{enterprise_id}/cluster", response_model=Response, name="获取集群节点信息")
async def get_store(
        region_name: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    result_bean = {}
    node_info = []
    try:
        res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
        result_bean = body["bean"]
        status = res["status"]
        if status != 200:
            return JSONResponse(general_message(400, "failed", "获取集群节点信息失败"), status_code=400)
    except Exception as e:
        logger.exception(e)
    store = {
        "total_cpu": result_bean["cap_cpu"],
        "used_cpu": result_bean["req_cpu"],
        "total_memory": round(result_bean["cap_mem"] / 1024, 2),
        "used_memory": round(result_bean["req_mem"] / 1024, 2),
        "total_disk": result_bean["total_capacity_storage"],
        "used_disk": result_bean["total_used_storage"]
    }
    total_pod = result_bean['total_capacity_pods'] + result_bean['total_used_pods']
    pod = {
        "total": total_pod,
        "used_pod": result_bean['total_used_pods'],
        "free_pod": result_bean['total_capacity_pods'],
    }

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

    info = {
        "store": store,
        "pod": pod,
        "node": {
            "total": len(node_info),
            "info": node_info
        }
    }

    return JSONResponse(general_message(200, "success", "获取成功", bean=info), status_code=200)


@router.get("/v1.0/expressway/{region_name}/{enterprise_id}/overview/app", response_model=Response, name="总览-应用信息")
async def overview_app(
        region_name: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    apps = hunan_expressway_service.get_all_app(session, region_name)
    app_total_num = len(apps)
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
            service_info.update({
                "total": service_total_num,
                "running": service_running_num,
                "unrunning": service_unrunning_num,
                "abnormal": service_abnormal_num
            })
            groups_rel_list = hunan_expressway_service.get_groups_by_service_id(session, service_abnormal_ids)
            app_ids = [group_rel.group_id for group_rel in groups_rel_list]
            app_ids = list(set(app_ids))
            app_abnormal_num = len(app_ids)
            groups_rel_list = hunan_expressway_service.get_groups_by_service_id(session, service_close_ids)
            app_ids = [group_rel.group_id for group_rel in groups_rel_list]
            app_ids = list(set(app_ids))
            app_unrunning_num = len(app_ids)
            app_running_num = app_total_num - app_abnormal_num - app_unrunning_num
            group_info = {
                "total": app_total_num,
                "running": app_running_num,
                "unrunning": app_unrunning_num,
                "abnormal": app_abnormal_num
            }

    except (remote_component_client.CallApiError, ServiceHandleException) as e:
        logger.exception("get region services_status:'{0}' running failed: {1}".format(region_name, e))

    info = {
        "group_info": group_info,
        "service_info": service_info
    }

    result = general_message(200, "success", "查询成功", bean=info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/v1.0/expressway/{region_name}/{enterprise_id}/tenant/info", response_model=Response, name="总览-团队信息")
async def overview_tenant(
        region_name: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    tenant_pods = {}
    tenant_info = []
    try:
        res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
        tenant_pods = body["bean"]["tenant_pods"]
        status = res["status"]
        if status != 200 and tenant_pods:
            return JSONResponse(general_message(400, "failed", "获取集群团队信息失败"), status_code=400)
    except Exception as e:
        logger.exception(e)

    tenant_pods = sorted(tenant_pods.items(), key=lambda x: x[1])[-4:]

    for tenant_tuple in tenant_pods:
        pods_num = tenant_tuple[1]
        tenant = team_services.get_team_by_team_id(session, tenant_tuple[0])

        team_service_num = service_info_repo.get_team_service_num_by_team_id(
            session=session, team_id=tenant.tenant_id, region_name=region_name)
        groups = application_repo.get_tenant_region_groups(session, tenant.tenant_id, region_name)

        tenant_info.append({
            "tenant_name": tenant.tenant_alias,
            "apps": len(groups),
            "services": team_service_num,
            "pods": pods_num
        })

    result = general_message(200, "success", "查询成功", bean=tenant_info)
    return JSONResponse(result, status_code=result["code"])


@router.get("/v1.0/expressway/{region_name}/{enterprise_id}/event", response_model=Response, name="集群事件统计")
async def get_region_event(
        region_name: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    events = []
    result_bean = {}
    try:
        res, body = hunan_expressway_client.get_region_cluster(session, region_name, enterprise_id)
        result_bean = body["bean"]
        status = res["status"]
        if status != 200:
            return JSONResponse(general_message(400, "failed", "获取集群节点信息失败"), status_code=400)
    except Exception as e:
        logger.exception(e)

    now = datetime.datetime.now()
    now_time = now.strftime("%Y-%m-%d %H:%M:%S")
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
        storage_percent = used_storage / total_storage
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
