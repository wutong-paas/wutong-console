from typing import Any, Optional

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

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

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.get_virtual_port_gateway(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(
            200, "get virtual machine port gateway success", "获取虚拟机端口网关成功", bean=data
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
