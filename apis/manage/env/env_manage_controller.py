from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.utils.return_message import general_message, error_message
from core.utils.validation import is_qualified_name
from database.session import SessionClass
from exceptions.bcode import ErrQualifiedName, ErrNamespaceExists
from exceptions.main import ServiceHandleException
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.region_service import region_services
from service.env_service import env_services

router = APIRouter()


@router.post("/teams/{team_name}/add-env", response_model=Response, name="新建环境")
async def add_env(request: Request,
                  team_name: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user)) -> Any:
    from_data = await request.json()
    env_alias = from_data["env_alias"]
    useable_regions = from_data["useable_regions"]
    namespace = from_data["namespace"]
    if not is_qualified_name(namespace):
        raise ErrQualifiedName(msg="invalid namespace name", msg_show="命名空间只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")
    enterprise_id = user.enterprise_id

    if not env_alias:
        result = general_message(400, "failed", "环境名不能为空")
        return JSONResponse(status_code=400, content=result)

    regions = []
    if useable_regions:
        regions = useable_regions.split(",")

    env = env_repo.env_is_exists_by_env_name(session, env_alias, enterprise_id)
    if env:
        result = general_message(400, "failed", "该环境名已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_namespace(session, namespace, enterprise_id)
    if env:
        result = general_message(400, "failed", "该环境英文名已存在")
        return JSONResponse(status_code=400, content=result)

    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    if not enterprise:
        result = general_message(500, "user's enterprise is not found", "无企业信息")
        return JSONResponse(status_code=500, content=result)

    env = env_repo.create_env(session, user, enterprise, env_alias, team_name, namespace)
    exist_namespace_region_names = []

    for r in regions:
        try:
            region_services.create_env_on_region(session=session, enterprise_id=enterprise.enterprise_id,
                                                 env=env, region_name=r, namespace=env.namespace)
        except ErrNamespaceExists:
            exist_namespace_region_names.append(r)
        except ServiceHandleException as e:
            logger.error(e)
        except Exception as e:
            logger.error(e)
    if len(exist_namespace_region_names) > 0:
        exist_namespace_region = ""
        for region_name in exist_namespace_region_names:
            region = region_repo.get_region_by_region_name(session, region_name)
            exist_namespace_region += " {}".format(region.region_alias)
        session.rollback()
        return JSONResponse(
            general_message(400, "success", "环境在集群【{} 】中已存在命名空间 {}".format(exist_namespace_region, env.namespace),
                            bean=jsonable_encoder(env)))
    result = general_message(200, "success", "环境添加成功", bean=jsonable_encoder(env))
    return JSONResponse(status_code=200, content=result)


@router.delete("/teams/{team_name}/delete-env", response_model=Response, name="删除环境")
async def delete_env(request: Request,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    删除环境
    """
    data = await request.json()
    env_id = data.get("env_id", None)
    if not env_id:
        return JSONResponse(general_message(403, "env id is not null", "环境id不能为空"), status_code=403)
    env = env_services.get_env_by_env_id(session, env_id)
    try:
        env_services.delete_by_env_id(session=session, user=user, env=env)
        result = general_message(200, "delete a team successfully", "删除环境成功")
        return JSONResponse(result, status_code=result["code"])
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.put("/teams/{team_name}/modify-env", response_model=Response, name="修改环境配置")
async def modify_env(request: Request,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    修改环境配置
    """
    data = await request.json()
    env_id = data.get("env_id", None)
    env_name = data.get("env_name", None)
    region_name = data.get("region_name", None)
    desc = data.get("desc", None)
    if not env_id:
        return JSONResponse(general_message(403, "env id is not null", "环境id不能为空"), status_code=403)
    env = env_services.get_env_by_env_id(session, env_id)

    env.env_alias = env_name
    env.desc = desc

    result = general_message(200, "delete a team successfully", "修改环境成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/env/query", response_model=Response, name="查询团队下环境")
async def get_query(
        team_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询团队下环境
    """
    try:
        envs = env_services.get_envs_by_tenant_name(session, team_name)
        result = general_message(200, "success", "查询成功", list=envs)
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/env/{env_id}", response_model=Response, name="查询单个环境")
async def get_env_by_envid(
        request: Request,
        env_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询单个环境
    """
    try:
        if not env_id:
            return JSONResponse(general_message(403, "env id is not null", "环境id不能为空"), status_code=403)
        env = env_services.get_env_by_env_id(session, env_id)
        result = general_message(200, "success", "查询成功", bean=jsonable_encoder(env))
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
    return JSONResponse(result, status_code=result["code"])
