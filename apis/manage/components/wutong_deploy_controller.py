from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ResourceNotEnoughException, AccountOverdueException
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from service.app_actions.app_deploy import app_deploy_service
from service.app_actions.exception import ErrServiceSourceNotFound

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/deploy", response_model=Response, name="获取组件依赖的组件")
async def deploy_component(request: Request,
                           serviceAlias: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user),
                           env=Depends(deps.get_current_team_env)) -> Any:
    """
    部署组件
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
    try:
        service = service_info_repo.get_service(session, serviceAlias, env.env_id)
        oauth_instance, _ = None, None

        data = await request.json()
        group_version = data.get("group_version", None)
        code, msg, _ = app_deploy_service.deploy(
            session, env, service, user, version=group_version, oauth_instance=oauth_instance)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "deploy app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ErrServiceSourceNotFound as e:
        logger.exception(e)
        return JSONResponse(general_message(412, "not found source", "无法找到云市应用的构建源"), status_code=412)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "构建失败"), status_code=412)
    return JSONResponse(result, status_code=200)
