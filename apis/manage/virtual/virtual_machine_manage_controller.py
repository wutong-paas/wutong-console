from typing import Any

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from clients.remote_virtual_client import remote_virtual_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from schemas.virtual import CreateVirtualParam

router = APIRouter()


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
