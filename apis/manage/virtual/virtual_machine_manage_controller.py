from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse
from service.region_service import region_services
from clients.remote_virtual_client import remote_virtual_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.team_region_repo import team_region_repo
from repository.virtual.virtual_image_repo import virtual_image_repo
from schemas.response import Response
from schemas.virtual import (
    CreateVirtualParam,
    UpdateVirtualParam,
)

router = APIRouter()


@router.get(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}",
    response_model=Response,
    name="查询单个虚拟机",
)
async def get_virtual_machine(
        request: Request,
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    查询单个虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    data = remote_virtual_client.get_virtual_machine(
        session, region.region_name, env, vm_id
    )

    port_info = remote_virtual_client.get_virtual_port_gateway(
        session, region.region_name, env, vm_id
    )

    gateway_host = []
    ports = port_info["ports"]
    if ports:
        for port in ports:
            protocol = port.get("protocol", 'http')
            gateways = port.get("gateways", [])
            gateway_enabled = port.get("gatewayEnabled", False)
            if gateways and gateway_enabled:
                for gateway in gateways:
                    if protocol == 'http':
                        gateway_host.append("http://" + gateway["gatewayHost"] + gateway["gatewayPath"])
                    else:
                        host_ip = region.tcpdomain if gateway["gatewayIP"] == "0.0.0.0" else gateway["gatewayIP"]
                        gateway_host.append(host_ip + ":" + str(gateway["gatewayPort"]))

    data["gateway_host_list"] = gateway_host
    return JSONResponse(
        general_message(200, "get virtual machine success", "获取虚拟机成功", bean=data),
        status_code=200,
    )


@router.get(
    "/teams/{team_name}/env/{env_id}/vms", response_model=Response, name="查询虚拟机列表"
)
async def get_virtual_machine_list(
        page: int = Query(default=1, ge=1, le=9999),
        page_size: int = Query(default=10, ge=1, le=500),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    查询虚拟机列表
    """

    start = (page - 1) * page_size
    end = page * page_size

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.get_virtual_machine_list(
        session, region.region_name, env
    )
    total = len(data) if data else 0
    pages = int(total / page_size)
    if pages == 0:
        pages = 1
    return JSONResponse(
        general_message(
            200,
            "get virtual machine success",
            "获取虚拟机列表成功",
            list=data[start:end] if data else [],
            total=total,
            current=page, pages=pages, size=page_size
        ),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms", response_model=Response, name="创建虚拟机"
)
async def create_virtual_machine(
        param: CreateVirtualParam = CreateVirtualParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    创建虚拟机
    """

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    image = virtual_image_repo.get_virtual_image_by_os_name(session, param.os_name,
                                                            param.os_version)

    body = {
        "name": param.name,
        "displayName": param.display_name,
        "desc": param.desc,
        "osSourceFrom": image.image_type,
        "osSourceURL": image.image_address,
        "osName": param.os_name,
        "osVersion": param.os_version,
        "osDiskSize": param.os_disk_size,
        "requestCPU": param.request_cpu,
        "requestMemory": param.request_memory,
        "user": param.user,
        "password": param.password,
        "operator": user.nick_name,
        "nodeSelectorLabels": param.node_selector_labels,
        "running": param.running
    }
    data = remote_virtual_client.create_virtual_machine(
        session, region.region_name, env, body
    )
    return JSONResponse(
        general_message(200, "create virtual machine success", "创建虚拟机成功", bean=data),
        status_code=200,
    )


@router.put(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}", response_model=Response, name="更新虚拟机"
)
async def update_virtual_machine(
        vm_id: Optional[str] = None,
        param: UpdateVirtualParam = UpdateVirtualParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    更新虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    body = {
        "displayName": param.display_name,
        "desc": param.desc,
        "requestCPU": param.request_cpu,
        "requestMemory": param.request_memory,
        "defaultLoginUser": param.default_login_user,
        "operator": user.nick_name,
        "nodeSelectorLabels": param.node_selector_labels
    }
    data = remote_virtual_client.update_virtual_machine(
        session, region.region_name, env, vm_id, body
    )
    return JSONResponse(
        general_message(200, "update virtual machine success", "更新虚拟机成功", bean=data),
        status_code=200,
    )


@router.delete(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}", response_model=Response, name="删除虚拟机"
)
async def delete_virtual_machine(
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    删除虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    remote_virtual_client.delete_virtual_machine(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(200, "delete virtual machine success", "删除虚拟机成功"),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/start",
    response_model=Response,
    name="启动虚拟机",
)
async def start_virtual_machine(
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    启动虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.start_virtual_machine(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(200, "start virtual machine success", "启动虚拟机成功", bean=data),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/stop",
    response_model=Response,
    name="停止虚拟机",
)
async def stop_virtual_machine(
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    停止虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.stop_virtual_machine(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(200, "stop virtual machine success", "停止虚拟机成功", bean=data),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/restart",
    response_model=Response,
    name="重启虚拟机",
)
async def restart_virtual_machine(
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    重启虚拟机
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.restart_virtual_machine(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(200, "restart virtual machine success", "重启虚拟机成功", bean=data),
        status_code=200,
    )
