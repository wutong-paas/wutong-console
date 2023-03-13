from typing import Optional, Any
from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response

router = APIRouter()


@router.get("/obs/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/pods", response_model=Response, name="obs获取组件实例信息")
async def get_pods_info(
        env_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        pod_name: Optional[str] = "all",
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
     obs获取组件实例
     ---
     parameters:
         - name: tenantName
           description: 租户名
           required: true
           type: string
           paramType: path
         - name: serviceAlias
           description: 组件别名
           required: true
           type: string
           paramType: path
     """
    pods_info = {}
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    if not service:
        return JSONResponse(general_message(400, "not service", "组件不存在"), status_code=400)
    service_pods_info = remote_component_client.get_service_pods(session,
                                                                 service.service_region,
                                                                 env,
                                                                 service.service_alias)
    if service_pods_info["bean"]:

        def foobar(data):
            if data is None:
                return
            res = {}
            container_dict = {}
            for d in data:
                pod_info = {}
                pod_memory_usage = 0
                pod_usage_rate = 0
                pod_cpu_usage = 0
                pod_cpu_rate = 0
                container = d["container"]
                for key, val in list(container.items()):
                    if key == "POD":
                        continue
                    container_dict = dict()
                    memory_limit = float(val["memory_limit"]) / 1024 / 1024
                    memory_usage = float(val["memory_usage"]) / 1024 / 1024
                    cpu_limit = float(val["cpu_limit"])
                    cpu_usage = float(val["cpu_usage"])
                    usage_rate = memory_usage * 100 / memory_limit if memory_limit else 0
                    cpu_rate = cpu_usage * 100 / cpu_limit if cpu_limit else 0
                    if key == service.k8s_component_name:
                        pod_memory_usage += memory_usage
                        pod_usage_rate += usage_rate
                        pod_cpu_usage += cpu_usage
                        pod_cpu_rate += cpu_rate

                pod_info["memory_usage"] = round(pod_memory_usage, 2)
                pod_info["memory_rate"] = round(pod_usage_rate, 2)
                pod_info["cpu_usage"] = round(pod_cpu_usage, 2)
                pod_info["cpu_rate"] = round(pod_cpu_rate, 2)
                container_dict[d["pod_name"]] = pod_info
                res.update(container_dict)
            return res

        pods = service_pods_info["bean"]
        pods_info = foobar(pods.get("new_pods", None))
    if pod_name != "all":
        result = general_message("0", "success", "操作成功", bean=pods_info.get(pod_name))
    else:
        total_memory_usage = 0
        total_usage_rate = 0
        total_cpu_usage = 0
        total_cpu_rate = 0
        if pods_info:
            for value in pods_info.values():
                total_memory_usage += value["memory_usage"]
                total_usage_rate += value["memory_rate"]
                total_cpu_usage += value["cpu_usage"]
                total_cpu_rate += value["cpu_rate"]
        pod_dict = {"memory_usage": total_memory_usage, "memory_rate": total_usage_rate, "cpu_usage": total_cpu_usage,
                    "cpu_rate": total_cpu_rate}
        result = general_message("0", "success", "操作成功", bean=pod_dict)
    return JSONResponse(result, status_code=200)
