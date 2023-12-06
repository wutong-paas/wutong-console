from typing import Any, Optional
from clients.remote_build_client import remote_build_client
from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse
from service.region_service import region_services
from clients.remote_virtual_client import remote_virtual_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from schemas.virtual import (DeleteGatewayParam, PortsGatewayParam,
                             UpdateGatewayParam, VirtualPortsParam)

router = APIRouter()


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/port",
    response_model=Response,
    name="添加虚拟机端口",
)
async def add_virtual_machine_ports(
        vm_id: Optional[str] = None,
        param: VirtualPortsParam = VirtualPortsParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    添加虚拟机端口
    """

    if not vm_id or not param.vm_port or not param.protocol:
        return JSONResponse(
            general_message(400, "param error", "参数错误"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    body = {"vmPort": param.vm_port, "protocol": param.protocol}
    data = remote_virtual_client.add_virtual_machine_port(
        session, region.region_name, env, vm_id, body
    )
    return JSONResponse(
        general_message(200, "create virtual machine success", "添加虚拟机端口成功", bean=data),
        status_code=200,
    )


@router.delete(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/port",
    response_model=Response,
    name="删除虚拟机端口",
)
async def delete_virtual_machine_ports(
        vm_id: Optional[str] = None,
        param: VirtualPortsParam = VirtualPortsParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    删除虚拟机端口
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    if not param.vm_port or not param.protocol:
        return JSONResponse(
            general_message(400, "param error", "参数错误"), status_code=400
        )

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    body = {"vmPort": param.vm_port, "protocol": param.protocol}
    data = remote_virtual_client.delete_virtual_machine_port(
        session, region.region_name, env, vm_id, body
    )
    return JSONResponse(
        general_message(
            200, "delete virtual machine ports success", "删除虚拟机端口成功", bean=data
        ),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/gateway",
    response_model=Response,
    name="创建虚拟机端口网关",
)
async def create_virtual_port_gateway(
        vm_id: Optional[str] = None,
        param: PortsGatewayParam = PortsGatewayParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    创建虚拟机端口网关
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
        "vmPort": param.vm_port,
        "protocol": param.protocol,
        "gatewayID": param.gateway_id,
        "gatewayIP": param.gateway_ip,
        "gatewayPort": param.gateway_port,
        "gatewayHost": param.gateway_host,
        "gatewayPath": param.gateway_path,
    }
    data = remote_virtual_client.create_virtual_port_gateway(
        session, region.region_name, env, vm_id, body
    )
    return JSONResponse(
        general_message(
            200,
            "create virtual machine ports gateway success",
            "创建虚拟机端口网关成功",
            bean=data,
        ),
        status_code=200,
    )


@router.get(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/gateway",
    response_model=Response,
    name="获取虚拟机端口网关",
)
async def get_virtual_port_gateway(
        request: Request,
        vm_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    获取虚拟机端口网关
    """

    if not vm_id:
        return JSONResponse(
            general_message(400, "not found vm", "虚拟机id不存在"), status_code=400
        )

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    port_gateways = remote_virtual_client.get_virtual_port_gateway(
        session, region.region_name, env, vm_id
    )
    ports = port_gateways["ports"]
    if ports:
        for port in ports:
            protocol = port.get("protocol", 'http')
            gateways = port.get("gateways", [])
            if gateways:
                for gateway in gateways:
                    if protocol == 'http':
                        gateway.update({"gatewayUrl": "http://" + gateway["gatewayHost"] + gateway["gatewayPath"]})
                    else:
                        host_ip = region.tcpdomain if gateway["gatewayIP"] == "0.0.0.0" else gateway["gatewayIP"]
                        gateway.update({"gatewayUrl": host_ip + ":" + str(gateway["gatewayPort"])})
    return JSONResponse(
        general_message(
            200, "get virtual machine port gateway success", "获取虚拟机端口网关成功", bean=port_gateways
        ),
        status_code=200,
    )


@router.put(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/gateway",
    response_model=Response,
    name="更新虚拟机端口网关",
)
async def update_virtual_port_gateway(
        vm_id: Optional[str] = None,
        param: UpdateGatewayParam = UpdateGatewayParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    更新虚拟机端口网关
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
        "gatewayIP": param.gateway_ip,
        "gatewayPort": param.gateway_port,
        "gatewayHost": param.gateway_host,
        "gatewayPath": param.gateway_path,
    }
    data = remote_virtual_client.update_virtual_port_gateway(
        session, region.region_name, env, vm_id, param.gateway_id, body
    )
    return JSONResponse(
        general_message(
            200, "update virtual machine port gateway success", "更新虚拟机端口网关成功", bean=data
        ),
        status_code=200,
    )


@router.delete(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/gateway",
    response_model=Response,
    name="删除虚拟机端口网关",
)
async def delete_virtual_port_gateway(
        vm_id: Optional[str] = None,
        param: DeleteGatewayParam = DeleteGatewayParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    删除虚拟机端口网关
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

    data = remote_virtual_client.delete_virtual_port_gateway(
        session, region.region_name, env, vm_id, param.gateway_id
    )
    return JSONResponse(
        general_message(
            200, "delete virtual machine port gateway success", "删除虚拟机端口网关成功", bean=data
        ),
        status_code=200,
    )


@router.post(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/ports/enable",
    response_model=Response,
    name="开启/关闭端口对外服务",
)
async def open_port_external_service(
        vm_id: Optional[str] = None,
        operate: Optional[str] = None,
        param: VirtualPortsParam = VirtualPortsParam(),
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
) -> Any:
    """
    开启/关闭端口对外服
    """

    if not vm_id or not param.vm_port or not param.protocol:
        return JSONResponse(
            general_message(400, "param error", "参数错误"), status_code=400
        )

    body = {
        "vmPort": param.vm_port,
        "protocol": param.protocol
    }
    if operate == "open":
        data = remote_virtual_client.open_port_external_service(
            session, env, vm_id, body
        )
    else:
        data = remote_virtual_client.close_port_external_service(
            session, env, vm_id, body
        )
    return JSONResponse(
        general_message(
            200,
            "operate success",
            "操作成功",
            bean=data,
        ),
        status_code=200,
    )


@router.get(
    "/teams/{team_name}/env/{env_id}/get-available-port",
    response_model=Response,
    name="获取当前可用端口",
)
async def get_available_port(
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)
) -> Any:
    """
    获取当前可用端口
    """
    res, data = remote_build_client.get_port(session, env.region_code, env, True)
    if int(res.status) != 200:
        return JSONResponse(
            general_message(500, "get port error", "请求数据中心当前可用端口失败"), status_code=501
        )
    return JSONResponse(
        general_message(
            200,
            "get available port success",
            "获取当前可用端口成功",
            bean={"port": data["bean"]},
        ),
        status_code=200,
    )
