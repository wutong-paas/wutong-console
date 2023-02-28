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
from service.tenant_env_service import env_services

router = APIRouter()


@router.post("/teams/{team_name}/add-env", response_model=Response, name="新建环境")
async def add_env(request: Request,
                  team_name: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user)) -> Any:
    try:
        from_data = await request.json()
    except:
        result = general_message(400, "failed", "参数错误")
        return JSONResponse(status_code=403, content=result)
    env_alias = from_data["env_alias"]
    useable_regions = from_data["useable_regions"]
    env_name = from_data["env_name"]
    namespace = team_name + "-" + env_name
    tenant_id = from_data["tenant_id"]
    desc = from_data.get("desc", "")
    if not is_qualified_name(env_name):
        raise ErrQualifiedName(msg="invalid namespace name", msg_show="环境标识只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")
    enterprise_id = user.enterprise_id

    if not env_alias:
        result = general_message(400, "env name not null", "环境名不能为空")
        return JSONResponse(status_code=400, content=result)

    regions = []
    if useable_regions:
        regions = useable_regions.split(",")

    env = env_repo.env_is_exists_by_env_name(session, tenant_id, env_alias, enterprise_id)
    if env:
        result = general_message(400, "env name is exist", "该环境名已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_namespace(session, tenant_id, namespace, enterprise_id)
    if env:
        result = general_message(400, "env namespace is exist", "该环境英文名已存在")
        return JSONResponse(status_code=400, content=result)

    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    if not enterprise:
        result = general_message(500, "user's enterprise is not found", "无企业信息")
        return JSONResponse(status_code=500, content=result)

    env = env_repo.create_env(session, user, enterprise, env_name, env_alias, tenant_id, team_name, namespace, desc)
    exist_namespace_region_names = []

    for r in regions:
        try:
            region_services.create_env_on_region(session=session, env=env, region_name=r, namespace=env.namespace,
                                                 team_id=tenant_id,
                                                 team_name=team_name)
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


@router.delete("/teams/{team_name}/env/{env_id}/delete-env", response_model=Response, name="删除环境")
async def delete_env(request: Request,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    删除环境
    """
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(403, "env not exist", "环境不存在"), status_code=400)
    try:
        env_services.delete_by_env_id(session=session, user=user, env=env)
        result = general_message(200, "delete a team successfully", "删除环境成功")
        return JSONResponse(result, status_code=result["code"])
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.put("/teams/{team_name}/env/{env_id}/modify-env", response_model=Response, name="修改环境配置")
async def modify_env(request: Request,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    修改环境配置
    """
    data = await request.json()
    env_name = data.get("env_name", None)
    region_name = data.get("region_name", None)
    desc = data.get("desc", None)
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(403, "env not exist", "环境不存在"), status_code=400)

    env.env_alias = env_name
    env.desc = desc

    result = general_message(200, "delete a team successfully", "修改环境成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/query/envs", response_model=Response, name="查询团队下环境")
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


@router.get("/pallet/all/envs", response_model=Response, name="查询全部环境")
async def get_all_env(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询团队下环境
    """
    try:
        envs = env_services.get_all_envs(session)
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
