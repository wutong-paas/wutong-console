from typing import Optional, Any
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.region.region_info_repo import region_repo
from schemas.response import Response
from service.expressway.hunan_expressway_service import hunan_expressway_service
from clients.remote_component_client import remote_component_client
from repository.teams.env_repo import env_repo

router = APIRouter()


@router.get("/plat/monitor/cluster", response_model=Response, name="获取集群资源信息")
async def get_store(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取集群资源信息
    """

    service_total = 0
    service_abnormal = 0
    result_bean = {}
    node_info = []
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
    usable_regions = region_repo.get_new_usable_regions(session=session)
    for region in usable_regions:
        region_code = region.region_name
        hunan_expressway_service.get_all_region_info(session, region_code, result_bean, node_info, store, pod)

        data = remote_component_client.get_all_services_status(session,
                                                               region_code,
                                                               test=True)
        if data:
            service_running_num = len(data["running_services"])
            service_unrunning_num = len(data["unrunning_services"])
            service_abnormal_num = len(data["abnormal_services"])
            service_total_num = service_running_num + service_unrunning_num + service_abnormal_num
            service_total += service_total_num
            service_abnormal += service_abnormal_num

    store["used_disk"] = round(store["used_disk"], 2)
    store["total_memory"] = round(store["total_memory"], 2)
    store["total_disk"] = round(store["total_disk"], 2)
    store["used_cpu"] = round(store["used_cpu"], 2)
    store["used_memory"] = round(store["used_memory"], 2)

    info = {
        "store": store,
        "pod": pod,
        "region_num": len(usable_regions),
        "node_num": len(node_info),
        "service_num": service_total,
        "service_abnormal_num": service_abnormal
    }

    return JSONResponse(general_message(200, "success", "获取成功", bean=info), status_code=200)


@router.get("/plat/monitor/{region_id}/teams", response_model=Response, name="获取团队资源使用量排行")
async def get_team_memory_config(
        query: Optional[str] = "memory_request",
        region_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取团队资源使用量排行
    """

    team_infos = {}
    team_info_list = []
    envs, total = env_repo.get_envs_list_by_region(session, region_id, None, None, 1, 9999)

    for env in envs:
        team_name = env.get("team_name")
        current_memory = 0
        current_cpu = 0
        if team_name in team_infos.keys():
            current_memory = team_infos[team_name]["memory_request"]
            current_cpu = team_infos[team_name]["cpu_request"]
        team_infos.update({
            team_name: {
                "memory_request": env.get("memory_request", 0) + current_memory,
                "cpu_request": env.get("cpu_request", 0) + current_cpu
            }
        })
    for team_name in team_infos.keys():
        value = team_infos[team_name]
        team_info_list.append({
            "team_name": team_name,
            "memory_request": value["memory_request"],
            "cpu_request": value["cpu_request"]
        })
    team_info_list = sorted(team_info_list, key=lambda x: x[query], reverse=True)
    result = general_message(200, "success", "获取成功", list=team_info_list[:10])
    return JSONResponse(result, status_code=200)
