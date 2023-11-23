from typing import Any, Optional

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from clients.remote_virtual_client import remote_virtual_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from schemas.virtual import (
    CreateVirtualParam,
    UpdateVirtualParam,
    VirtualConnectSSHParam,
)

router = APIRouter()


@router.get(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}",
    response_model=Response,
    name="查询单个虚拟机",
)
async def get_virtual_machine(
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

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.get_virtual_machine(
        session, region.region_name, env, vm_id
    )
    return JSONResponse(
        general_message(200, "get virtual machine success", "获取虚拟机成功", bean=data),
        status_code=200,
    )


@router.get(
    "/teams/{team_name}/env/{env_id}/vms", response_model=Response, name="查询虚拟机列表"
)
async def get_virtual_machine_list(
    session: SessionClass = Depends(deps.get_session),
    env=Depends(deps.get_current_team_env),
) -> Any:
    """
    查询虚拟机列表
    """

    region = team_region_repo.get_region_by_env_id(session, env.env_id)
    if not region:
        return JSONResponse(
            general_message(400, "not found region", "数据中心不存在"), status_code=400
        )

    data = remote_virtual_client.get_virtual_machine_list(
        session, region.region_name, env
    )
    return JSONResponse(
        general_message(
            200,
            "get virtual machine success",
            "获取虚拟机列表成功",
            list=data,
            total=len(data) if data else 0,
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

    body = {
        "name": param.name,
        "displayName": param.display_name,
        "desc": param.desc,
        "osSourceFrom": param.os_source_from,
        "osSourceURL": param.os_source_url,
        "osDiskSize": param.os_disk_size,
        "requestCPU": param.request_cpu,
        "requestMemory": param.request_memory,
        "user": param.user,
        "password": param.password,
        "operator": user.nick_name,
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


@router.get(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/docker_virtctl_console",
    response_model=Response,
    name="虚拟机连接 virtctl-console",
)
async def virtctl_console(
    vm_id: Optional[str] = None,
    session: SessionClass = Depends(deps.get_session),
    env=Depends(deps.get_current_team_env),
) -> Any:
    """
    虚拟机连接 virtctl-console
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

    body = {"vmID": vm_id, "vmNamespace": env.namespace}

    region_info = region_repo.get_region_by_region_name(
        session, region_name=region.region_name
    )
    data = remote_virtual_client.connect_virtctl_console(session, region_info, body)
    return JSONResponse(
        general_message(
            200, "connect virtctl-console success", "连接virtctl-console成功", bean=data
        ),
        status_code=200,
    )


@router.get(
    "/teams/{team_name}/env/{env_id}/vms/{vm_id}/docker_vm_ssh",
    response_model=Response,
    name="虚拟机连接 ssh",
)
async def virtual_connect_ssh(
    vm_id: Optional[str] = None,
    param: VirtualConnectSSHParam = VirtualConnectSSHParam(),
    session: SessionClass = Depends(deps.get_session),
    env=Depends(deps.get_current_team_env),
) -> Any:
    """
    虚拟机连接 ssh
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
        "vmID": vm_id,
        "vmNamespace": env.namespace,
        "vmUser": param.vm_user,
        "vmPort": param.vm_port,
    }

    region_info = region_repo.get_region_by_region_name(
        session, region_name=region.region_name
    )
    data = remote_virtual_client.virtual_connect_shh(session, region_info, body)
    return JSONResponse(
        general_message(200, "connect ssh success", "虚拟机连接ssh成功", bean=data),
        status_code=200,
    )
