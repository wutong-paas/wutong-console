from typing import Optional, Any

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from service import env_delete_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.delete("/cube-team/{team_code}")
async def delete_cube_team(team_code: Optional[str] = None, user=Depends(deps.get_current_user),
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    if not team_code:
        return JSONResponse(general_message(400, "team code not null", "团队编码不能为空"), status_code=400)
    envs = env_services.get_envs_by_tenant_name(session, team_code)
    if envs:
        for env in envs:
            env_delete_service.logic_delete_by_env_id(session=session, user=user, env=env, region_code=env.region_code)
    result = general_message("0", "delete a team successfully", "删除团队成功")
    return JSONResponse(result, status_code=200)
