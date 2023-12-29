import uuid
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from core import deps
from core.api.team_api import team_api
from core.utils.return_message import general_message, error_message
from core.utils.validation import is_qualified_code
from database.session import SessionClass
from exceptions.bcode import ErrQualifiedName, ErrNamespaceExists
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.env.user_env_auth_repo import user_env_auth_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.env import CreateEnvParam, UpdateEnvParam, DeleteEnvParam
from schemas.response import Response
from service.application_service import application_visit_service
from service.env_delete_service import stop_env_resource
from service.region_service import region_services
from service.tenant_env_service import env_services

router = APIRouter()


@router.post("/teams/{team_name}/add-env", response_model=Response, name="新建环境")
async def add_env(
        team_name: Optional[str] = None,
        params: Optional[CreateEnvParam] = CreateEnvParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    if len(params.env_name) > 31:
        result = general_message(400, "env_code too long", "环境标识长度限制31")
        return JSONResponse(result, status_code=result["code"])

    if not is_qualified_code(params.env_name):
        raise ErrQualifiedName(msg="invalid namespace name",
                               msg_show="环境标识只支持小写字母、数字、以及短横杠“-”组成，标识只能以小写字母开头，不能以数字开头且短横杠不能位于首尾")

    namespace = team_name + "-" + params.env_name
    namespace = namespace.lower().replace("_", "-")

    region = region_repo.get_region_by_region_name(session, params.region_name)
    if not region:
        return JSONResponse(general_message(404, "region not found", "集群不存在"), status_code=404)

    if not params.env_alias:
        result = general_message(400, "env name not null", "环境名不能为空")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_env_name(session, params.tenant_id, params.env_alias)
    if env:
        result = general_message(400, "env name is exist", "环境名称已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_env_code(session, params.tenant_id, params.env_name)
    if env:
        result = general_message(400, "env namespace is exist", "环境标识已存在")
        return JSONResponse(status_code=400, content=result)

    env = env_repo.env_is_exists_by_namespace(session, params.tenant_id, namespace)
    if env:
        index = str(uuid.uuid1())
        namespace = namespace + "-" + index[:8]

    env = env_repo.create_env(session, user, region.region_alias, params.region_name, params.env_name, params.env_alias,
                              params.tenant_id,
                              team_name, params.team_alias, namespace, params.desc)
    # 创建环境用户关系表
    env_repo.create_env_rel(session, env.env_id, params.user_names)

    exist_namespace_region_names = []

    try:
        region_services.create_env_on_region(session=session, env=env, region_name=params.region_name,
                                             namespace=env.namespace,
                                             team_id=params.tenant_id,
                                             team_name=team_name)
    except ErrNamespaceExists:
        exist_namespace_region_names.append(params.region_name)
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
async def delete_env(
        env_id: Optional[str] = None,
        params: Optional[DeleteEnvParam] = DeleteEnvParam(),
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    删除环境
    """
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if env.env_alias != params.env_alias:
        return JSONResponse(general_message(400, "env name error", "环境名不匹配"), status_code=400)
    try:
        # env_services.delete_by_env_id(session=session, user_nickname=user.nick_name, env=env)
        stop_env_resource(session=session, user=user, env=env, region_code=env.region_code)
        # 删除环境用户关系表
        env_repo.delete_env_rel(session, env.env_id)
        result = general_message("0", "delete a team successfully", "删除环境成功")
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.put("/teams/{team_name}/env/{env_id}/modify-env", response_model=Response, name="修改环境配置")
async def modify_env(
        env_id: Optional[str] = None,
        params: Optional[UpdateEnvParam] = UpdateEnvParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    修改环境配置
    """
    if not params.env_alias:
        return JSONResponse(general_message(400, "env name not null", "环境名不能为空"), status_code=400)
    env = env_services.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    # 同步更新应用表及应用访问记录表
    if env.env_alias != params.env_alias:
        groups = application_repo.get_groups_by_env_id(session, env_id)
        for group in groups:
            group.env_name = params.env_alias

        app_visits = application_visit_service.get_app_visit_record_by_env_id(session, env_id)
        for app_visit in app_visits:
            app_visit.tenant_env_alias = params.env_alias

    env.env_alias = params.env_alias
    env.desc = params.desc

    # 更新环境用户关系表
    env_repo.update_env_rel(session, env.env_id, params.user_names)

    result = general_message("0", "delete a team successfully", "修改环境成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/query/envs", response_model=Response, name="查询团队下环境")
async def get_team_envs(
        team_name: Optional[str] = None,
        team_id: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询团队下环境
    """
    if not team_id:
        return JSONResponse(general_message(400, "failed", "参数错误"), status_code=400)
    try:
        env_list = []
        envs = env_services.get_envs_by_tenant_name(session, team_name)
        is_team_admin = team_api.get_user_env_auth(user, team_id, "3")
        is_super_admin = team_api.get_user_env_auth(user, None, "1")
        if is_team_admin or is_super_admin:
            env_list = envs
        else:
            for env in envs:
                is_auth = user_env_auth_repo.is_auth_in_env(session, env.env_id, user.user_name)
                if is_auth:
                    env_list.append(env)
        result = general_message("0", "success", "查询成功", list=jsonable_encoder(env_list))
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
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询单个环境
    """
    try:
        env_rel = env_repo.get_env_rel_by_env_id(session, env_id)
        res = jsonable_encoder(env)
        res["user_names"] = env_rel.user_names
        result = general_message("0", "success", "查询成功", bean=res)
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
        return JSONResponse(result, status_code=result["code"])
    return JSONResponse(result, status_code=200)


@router.get("/team/env/user/auth", response_model=Response, name="查询用户是否有环境权限")
async def get_user_env_auth(
        team_id: Optional[str] = None,
        env_id: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询用户是否有环境权限
    """
    if not team_id or not env_id:
        return JSONResponse(general_message(400, "failed", "参数错误"), status_code=400)
    is_team_admin = team_api.get_user_env_auth(user, team_id, "3")
    is_super_admin = team_api.get_user_env_auth(user, None, "1")
    if is_team_admin or is_super_admin:
        return JSONResponse(general_message("0", "success", "查询成功", bean={"is_auth": True}), status_code=200)
    else:
        is_auth = user_env_auth_repo.is_auth_in_env(session, env_id, user.user_name)
        return JSONResponse(general_message("0", "success", "查询成功", bean={"is_auth": is_auth}), status_code=200)
