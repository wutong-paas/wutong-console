from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from core import deps
from core.utils.reqparse import parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.extend_service import extend_service
from service.autoscaler_service import autoscaler_service, scaling_records_service
from service.region_service import region_services

router = APIRouter()


async def validate_parameter(data):
    xpa_type = await parse_item(data, key="xpa_type", required=True)
    if xpa_type not in ["hpa"]:
        raise AbortRequest(msg="unsupported xpa_type: " + xpa_type)

    await parse_item(data, key="enable", required=True)

    min_replicas = await parse_item(data, key="min_replicas", required=True)
    if min_replicas <= 0 or min_replicas > 65535:
        raise AbortRequest(msg="the range of min_replicas is (0, 65535]")

    max_replicas = await parse_item(data, key="max_replicas", required=True)
    if max_replicas <= 0 or max_replicas > 65535:
        raise AbortRequest(msg="the range of max_replicas is (0, 65535]")
    if max_replicas < min_replicas:
        raise AbortRequest(msg="max_replicas must be greater than min_replicas")

    metrics = await parse_item(data, key="metrics", required=True)
    if len(metrics) < 1:
        raise AbortRequest(msg="need at least one metric")
    for metric in metrics:
        metric_type = await parse_item(metric, key="metric_type", required=True)
        if metric_type not in ["resource_metrics"]:
            raise AbortRequest(msg="unsupported metric type: {}".format(metric_type))
        metric_name = await parse_item(metric, key="metric_name", required=True)
        # The metric_name of resource_metrics can only be cpu or memory
        if metric_name not in ["cpu", "memory"]:
            raise AbortRequest(msg="resource_metrics does not support metric name: {}".format(metric_name))
        metric_target_type = await parse_item(metric, key="metric_target_type", required=True)
        if metric_target_type not in ["utilization", "average_value"]:
            raise AbortRequest(msg="unsupported metric target type: {}".format(metric_target_type))
        metric_target_value = await parse_item(metric, key="metric_target_value", required=True)
        if metric_target_value < 0 or metric_target_value > 65535:
            raise AbortRequest(msg="the range of metric_target_value is [0, 65535]")


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/xparules", response_model=Response, name="查询组件伸缩规则")
async def get_xparuler(serviceAlias: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       env=Depends(deps.get_current_team_env)) -> Any:
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    rules = autoscaler_service.list_autoscaler_rules(session=session, service_id=service.service_id)
    result = general_message("0", "success", "查询成功", list=rules)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/xparules", response_model=Response, name="添加组件伸缩规则")
async def set_xparuler(request: Request,
                       serviceAlias: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       env=Depends(deps.get_current_team_env),
                       user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    await validate_parameter(data)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    data["service_id"] = service.service_id
    res = autoscaler_service.create_autoscaler_rule(session, region_name, env,
                                                    service.service_alias,
                                                    data, user.nick_name)
    result = general_message("0", "success", "创建成功", bean=res)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/xparecords", response_model=Response, name="查询组件伸缩规则")
async def get_xparecords(request: Request,
                         serviceAlias: Optional[str] = None,
                         env=Depends(deps.get_current_team_env),
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    data = scaling_records_service.list_scaling_records(session=session, region_name=region_name,
                                                        tenant_env=env,
                                                        service_alias=service.service_alias, page=page,
                                                        page_size=page_size)
    result = general_message("0", "success", "查询成功", bean=data)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/extend_method", response_model=Response,
            name="获取组件扩展方式")
async def get_extend_method(serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件扩展方式
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 服务别名
          required: true
          type: string
          paramType: path
    """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    node_list, memory_list = extend_service.get_app_extend_method(session=session, service=service)
    bean = {
        "node_list": node_list,
        "memory_list": memory_list,
        "current_node": service.min_node,
        "current_memory": service.min_memory,
        "current_gpu": service.container_gpu,
        "current_gpu_type": service.gpu_type,
        "extend_method": service.extend_method,
        "current_cpu": service.min_cpu,
        "gpu_type_list": [
            "nvidia.com/gpu",
            "amd.com/gpu"
        ]
    }
    result = general_message("0", "success", "操作成功", bean=bean)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/xparules/{rule_id}", response_model=Response,
            name="查询组件伸缩指标")
async def get_xparules_index(rule_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session)) -> Any:
    res = autoscaler_service.get_by_rule_id(session, rule_id)
    result = general_message("0", "success", "查询成功", bean=res)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/xparules/{rule_id}", response_model=Response,
            name="创建组件伸缩指标")
async def set_xparules_index(request: Request,
                             serviceAlias: Optional[str] = None,
                             rule_id: Optional[str] = None,
                             env=Depends(deps.get_current_team_env),
                             session: SessionClass = Depends(deps.get_session),
                             user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    await validate_parameter(data)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    res = autoscaler_service.update_autoscaler_rule(session, region_name, env,
                                                    service.service_alias,
                                                    rule_id, data, user.nick_name)

    result = general_message("0", "success", "创建成功", bean=res)
    return Response(data=result, status=200)
