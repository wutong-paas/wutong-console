import uuid
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
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.env_delete_service import stop_env_resource
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
    region_name = from_data["region_name"]
    env_name = from_data["env_name"]
    tenant_id = from_data["tenant_id"]
    desc = from_data.get("desc", "")
    if not is_qualified_name(env_name):
        raise ErrQualifiedName(msg="invalid namespace name", msg_show="环境标识只支持英文、数字、中横线、下划线组合，只能以英文开头且中横线、下划线不能位于首尾")

    env_ns = env_name.lower().replace("_", "-")
    namespace = team_name + "-" + env_ns

    region = region_repo.get_region_by_region_name(session, region_name)
    if not region:
        return JSONResponse(general_message(404, "region not found", "集群不存在"), status_code=404)

    if not env_alias:
        result = general_message(400, "env name not null", "环境名不能为空")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_env_name(session, tenant_id, env_alias)
    if env:
        result = general_message(400, "env name is exist", "环境名称已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_env_code(session, tenant_id, env_name)
    if env:
        result = general_message(400, "env namespace is exist", "环境标识已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_namespace(session, tenant_id, namespace)
    if env:
        index = str(uuid.uuid1())
        namespace = namespace + "-" + index[:8]

    env = env_repo.create_env(session, user, region.region_alias, region_name, env_name, env_alias, tenant_id,
                              team_name, namespace, desc)
    exist_namespace_region_names = []

    try:
        region_services.create_env_on_region(session=session, env=env, region_name=region_name, namespace=env.namespace,
                                             team_id=tenant_id,
                                             team_name=team_name)
    except ErrNamespaceExists:
        exist_namespace_region_names.append(region_name)
    except ServiceHandleException as e:
        logger.error(e)
        session.rollback()
        return JSONResponse(general_message(400, e.msg, e.msg_show), status_code=400)
    except Exception as e:
        logger.error(e)
        session.rollback()
        return JSONResponse(general_message(400, "failed", "环境在数据中心创建失败"), status_code=400)
    if len(exist_namespace_region_names) > 0:
        exist_namespace_region = ""
        for region_name in exist_namespace_region_names:
            region = region_repo.get_region_by_region_name(session, region_name)
            exist_namespace_region += " {}".format(region.region_alias)
        session.rollback()
        return JSONResponse(
            general_message(400, "success", "环境在集群【{} 】中已存在命名空间 {}".format(exist_namespace_region, env.namespace),
                            bean=jsonable_encoder(env)))
    result = general_message("0", "success", "环境添加成功", bean=jsonable_encoder(env))
    return JSONResponse(status_code=200, content=result)


@router.delete("/teams/{team_name}/env/{env_id}/delete-env", response_model=Response, name="删除环境")
async def delete_env(request: Request,
                     env_id: Optional[str] = None,
                     user=Depends(deps.get_current_user),
                     session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除环境
    """
    data = await request.json()
    env_alias = data.get("env_alias", "")
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if env.env_alias != env_alias:
        return JSONResponse(general_message(400, "env name error", "环境名不匹配"), status_code=400)
    try:
        # env_services.delete_by_env_id(session=session, user_nickname=user.nick_name, env=env)
        stop_env_resource(session=session, user=user, env=env, region_name=env.region_code)
        result = general_message("0", "delete a team successfully", "删除环境成功")
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.put("/teams/{team_name}/env/{env_id}/modify-env", response_model=Response, name="修改环境配置")
async def modify_env(request: Request,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    修改环境配置
    """
    data = await request.json()
    env_alias = data.get("env_alias", None)
    desc = data.get("desc", None)
    if not env_alias:
        return JSONResponse(general_message(400, "env name not null", "环境名不能为空"), status_code=400)
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    env.env_alias = env_alias
    env.desc = desc

    result = general_message("0", "delete a team successfully", "修改环境成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/query/envs", response_model=Response, name="查询团队下环境")
async def get_team_envs(
        team_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询团队下环境
    """
    try:
        envs = env_services.get_envs_by_tenant_name(session, team_name)
        result = general_message("0", "success", "查询成功", list=jsonable_encoder(envs))
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
        return JSONResponse(result, status_code=result["code"])
    return JSONResponse(result, status_code=200)


@router.get("/plat/all/envs", response_model=Response, name="查询全部环境")
async def get_all_envs(
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        envs = env_services.get_all_envs(session)
        result = general_message("0", "success", "查询成功", list=jsonable_encoder(envs))
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
        return JSONResponse(result, status_code=result["code"])
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}", response_model=Response, name="查询单个环境")
async def get_env_by_env_id(
        env_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询单个环境
    """
    try:
        env = env_services.get_env_by_env_id(session, env_id)
        if not env:
            result = general_message(404, "not found env", "环境不存在")
            return JSONResponse(result, status_code=400)
        result = general_message("0", "success", "查询成功", bean=jsonable_encoder(env))
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
        return JSONResponse(result, status_code=result["code"])
    return JSONResponse(result, status_code=200)
