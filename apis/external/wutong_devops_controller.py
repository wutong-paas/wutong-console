from typing import Optional, Any
from fastapi import Depends, APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Params, paginate
from loguru import logger
from sqlalchemy import select
from starlette.responses import JSONResponse
from xpinyin import Pinyin
from core import deps
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.exceptions import GroupNotExistError
from exceptions.main import ServiceHandleException, ResourceNotEnoughException, AccountOverdueException
from models.teams import RegionConfig
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.devops.devops_repo import devops_repo
from repository.expressway.hunan_expressway_repo import hunan_expressway_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.components import BuildSourceParam, DeployBusinessParams
from schemas.market import DevopsMarketAppCreateParam
from schemas.response import Response
from service.app_actions.app_deploy import app_deploy_service
from service.app_actions.exception import ErrServiceSourceNotFound
from service.app_config.app_relation_service import dependency_service
from service.application_service import application_service
from service.market_app_service import market_app_service
from service.tenant_env_service import env_services

router = APIRouter()


@router.get("/v1.0/devops/teams/{team_code}/env/{env_id}/components", response_model=Response, name="组件列表")
async def get_app_state(
        request: Request,
        team_code: Optional[str] = None,
        env_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
     应用组件列表、状态展示
     ---
     parameters:
         - name: team_name
           description: 团队名
           required: true
           type: string
           paramType: path
         - name: page
           description: 页数(默认第一页)
           required: false
           type: string
           paramType: query
         - name: page_size
           description: 每页展示个数(默认10个)
           required: false
           type: string
           paramType: query
         - name: group_id
           description: 应用id
           required: true
           type: string
           paramType: query
     """
    try:
        code = 200
        page = 1
        page_size = 99
        application_id = request.query_params.get("application_id")
        region_name = request.query_params.get("region_name")
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        if application_id is None or not application_id.isdigit():
            code = 400
            result = general_message(code, "group_id is missing or not digit!", "group_id缺失或非数字")
            return JSONResponse(result, status_code=code)
        # region_name = request.headers.get("X_REGION_NAME")
        team = env_services.devops_get_tenant(tenant_name=team_code, session=session)
        if not team:
            result = general_message(400, "tenant not exist", "{}团队不存在".format(team_code))
            return JSONResponse(result, status_code=400)

        if application_id == "-1":
            # query service which not belong to any app
            no_group_service_list = service_info_repo.get_no_group_service_status_by_group_id(
                session=session,
                tenant_env=env,
                team_id=team.tenant_id,
                region_name=region_name,
                enterprise_id=team.enterprise_id)
            if page_size == "-1" or page_size == "" or page_size == "0":
                page_size = len(no_group_service_list) if len(no_group_service_list) > 0 else 10
            page_params = Params(page=page, size=page_size)
            pg = paginate(no_group_service_list, page_params)
            total = pg.total
            result = general_message(code, "query success", "应用查询成功", list=pg.items, total=total)
            return JSONResponse(result, status_code=code)

        team_id = team.tenant_id
        group_count = application_repo.get_group_count_by_team_id_and_group_id(session=session, team_id=team_id,
                                                                               group_id=application_id)
        if group_count == 0:
            result = general_message(202, "group is not yours!", "当前组已删除或您无权限查看！", bean={})
            return JSONResponse(result, status_code=202)

        group_service_list = service_info_repo.get_group_service_by_group_id(
            session=session,
            group_id=application_id,
            region_name=region_name,
            team_id=team.tenant_id,
            tenant_env=env,
            enterprise_id=team.enterprise_id)
        params = Params(page=page, size=page_size)
        pg = paginate(group_service_list, params)
        total = pg.total
        result = general_message(code, "query success", "应用查询成功", list=jsonable_encoder(pg.items),
                                 total=total)
        return JSONResponse(result, status_code=200)
    except GroupNotExistError as e:
        logger.exception(e)
        return JSONResponse(general_message(400, "query success", "该应用不存在"), status_code=400)


@router.get("/v1.0/devops/teams/components/dependency", response_model=Response, name="获取组件依赖组件")
async def get_un_dependency(
        request: Request,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    page_num = 1
    page_size = 99
    team_code = request.query_params.get("team_code")
    search_key = None
    condition = None
    tenant = env_services.devops_get_tenant(tenant_name=team_code, session=session)
    dependencies = dependency_service.get_dependencies(session=session, tenant=tenant)
    service_ids = [s.service_id for s in dependencies]
    service_group_map = application_service.get_services_group_name(session=session, service_ids=service_ids)
    dep_list = []
    for dep in dependencies:
        dep_service_info = {
            "group_name": service_group_map[dep.service_id]["group_name"],
            "service_name": dep.service_cname,
            "service_id": dep.service_id,
            "service_code": dep.service_alias
        }

        if search_key is not None and condition:
            if condition == "group_name":
                if search_key.lower() in service_group_map[dep.service_id]["group_name"].lower():
                    dep_list.append(dep_service_info)
            elif condition == "service_name":
                if search_key.lower() in dep.service_cname.lower():
                    dep_list.append(dep_service_info)
            else:
                result = general_message(400, "error", "condition参数错误")
                return JSONResponse(result, status_code=400)
        elif search_key is not None and not condition:
            if search_key.lower() in service_group_map[dep.service_id][
                "group_name"].lower() or search_key.lower() in dep.service_cname.lower():
                dep_list.append(dep_service_info)
        elif search_key is None and not condition:
            dep_list.append(dep_service_info)

    rt_list = dep_list[(page_num - 1) * page_size:page_num * page_size]
    result = general_message(200, "success", "查询成功", list=rt_list, total=len(dep_list))
    return JSONResponse(result, status_code=result["code"])


@router.post("/v1.0/devops/teams/{team_code}/env/{env_id}/applications/{application_id}/build", response_model=Response,
             name="部署业务组件")
async def deploy_business_component(
        request: Request,
        params: DeployBusinessParams,
        env_id: Optional[str] = None,
        team_code: Optional[str] = None,
        application_id: Optional[str] = None,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    result = general_message(200, "success", "成功")
    image_type = "docker_image"
    p = Pinyin()
    k8s_component_name = p.get_pinyin(params.component_name)
    k8s_component_name = k8s_component_name.lower()
    if k8s_component_name and application_service.is_k8s_component_name_duplicate(session,
                                                                                  application_id,
                                                                                  k8s_component_name):
        return JSONResponse(general_message(400, "k8s component name exists", "组件英文名已存在"), status_code=400)
    try:
        if not params.docker_image:
            return JSONResponse(general_message(400, "docker_cmd cannot be null", "参数错误"), status_code=400)
        application = application_repo.get_by_primary_key(session=session, primary_key=application_id)
        if application and application.tenant_id != env.tenant_id:
            return JSONResponse(general_message(400, "not found app at team", "应用不属于该团队"), status_code=400)

        code, msg_show, new_service = application_service.create_docker_run_app(session=session,
                                                                                region_name=params.region_name,
                                                                                tenant=env,
                                                                                user=user,
                                                                                service_cname=params.component_name,
                                                                                docker_cmd=params.docker_image,
                                                                                image_type=image_type,
                                                                                k8s_component_name=k8s_component_name)
        if code != 200:
            return JSONResponse(general_message(code, "service create fail", msg_show), status_code=200)

        # 添加username,password信息
        if params.registry_password or params.registry_user:
            application_service.create_service_source_info(session=session, tenant=env, service=new_service,
                                                           user_name=params.registry_user,
                                                           password=params.registry_password)

        code, msg_show = application_service.add_component_to_app(session=session, tenant=env,
                                                                  region_name=params.region_name,
                                                                  app_id=application_id,
                                                                  component_id=new_service.service_id)
        if code != 200:
            logger.debug("service.create", msg_show)
        session.flush()

        if params.docker_image is not None:
            devops_repo.modify_source(session, new_service, params.docker_image,
                                      params.registry_user, params.registry_password)

        if params.env_variables is not None:
            for env_variables in params.env_variables:
                if env_variables.key is not None:
                    result = devops_repo.add_envs(session, env_variables.key, env_variables.value,
                                                  env_variables.desc, user, env, new_service)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.dep_service_ids is not None:
            result = devops_repo.add_dep(session, user, env, new_service, params.dep_service_ids)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        session.flush()
        result = devops_repo.component_build(session, user, env, new_service)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        session.rollback()
        return JSONResponse(general_message(10410, "resource is not enough", re), status_code=10410)
    return JSONResponse(result, status_code=result["code"])


@router.post("/v1.0/devops/teams/{team_code}/env/{env_id}/buildsource", response_model=Response, name="构建组件")
async def deploy_component(
        request: Request,
        params: BuildSourceParam,
        user=Depends(deps.get_current_user),
        env_id: Optional[str] = None,
        team_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
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
        env = env_repo.get_env_by_env_id(session, env_id)
        if not env:
            return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
        result = general_message(200, "success", "成功")
        tenant = env_services.devops_get_tenant(tenant_name=team_code, session=session)
        service = service_info_repo.get_service(session, params.component_code, tenant.tenant_id)
        oauth_instance, _ = None, None
        if params.docker_image is not None:
            devops_repo.modify_source(session, service, params.docker_image,
                                      params.registry_user, params.registry_password)
        if params.env_variables is not None:
            for env_variables in params.env_variables:
                if env_variables.key is not None:
                    result = devops_repo.add_envs(session, env_variables.key, env_variables.value,
                                                  env_variables.desc, user, env, service)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.update_env_variables is not None:
            for env_variables in params.update_env_variables:
                if env_variables.key is not None:
                    result = devops_repo.modify_env(session, user, tenant, service,
                                                    env_variables.key, env_variables.desc, env_variables.value)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.delete_env_variables is not None:
            for env_variables in params.delete_env_variables:
                if env_variables.key is not None:
                    result = devops_repo.delete_envs(session, user, tenant, service, env_variables.key)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.dep_service_ids is not None:
            result = devops_repo.add_dep(session, user, tenant, service, params.dep_service_ids)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.delete_dep_service_ids is not None:
            result = devops_repo.delete_dependency_component(session, user, env, service,
                                                             params.delete_dep_service_ids)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        session.flush()
        group_version = None
        code, msg, _ = app_deploy_service.deploy(
            session, tenant, service, user, version=group_version, oauth_instance=oauth_instance)
        bean = {}
        if code != 200:
            session.rollback()
            return JSONResponse(general_message(code, "deploy app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "操作成功", bean=bean)
    except ErrServiceSourceNotFound as e:
        logger.exception(e)
        session.rollback()
        return JSONResponse(general_message(412, "not found source", "无法找到云市应用的构建源"), status_code=412)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        session.rollback()
        return JSONResponse(general_message(10410, "resource is not enough", "构建失败"), status_code=412)
    return JSONResponse(result, status_code=result["code"])


@router.post("/v1.0/devops/teams/components/model_create", response_model=Response, name="部署基础组件")
async def market_create(
        request: Request,
        params: DevopsMarketAppCreateParam,
        user=Depends(deps.get_current_user),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
    部署基础组件
    """
    install_from_cloud = False
    is_deploy = True
    market_name = ""
    # 查询当前团队
    tenant = env_services.devops_get_tenant(tenant_name=params.team_code, session=session)
    if not tenant:
        return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)

    region_info = session.execute(select(RegionConfig).where(
        RegionConfig.region_name == params.region_name
    )).scalars().first()

    market_app_service.install_app(session=session, tenant=tenant, region=region_info,
                                   user=user,
                                   app_id=params.application_id,
                                   app_model_key=params.model_app_id,
                                   version=params.model_app_version,
                                   market_name=market_name,
                                   install_from_cloud=install_from_cloud,
                                   is_deploy=is_deploy)
    return JSONResponse(general_message(200, "success", "部署成功"), status_code=200)


@router.get("/v1.0/devops/teams/{team_name}/env/{env_id}/regions", response_model=Response, name="查询团队绑定集群")
async def get_team_regions(
        request: Request,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    region_info_map = []
    region_name_list = env_repo.get_team_region_names(session, env.tenant_id)
    if region_name_list:
        region_infos = region_repo.get_region_by_region_names(session, region_name_list)
        if region_infos:
            for region in region_infos:
                region_info_map.append(
                    {"id": region.ID, "region_name": region.region_name, "region_alias": region.region_alias})
    return JSONResponse(general_message(200, "success", "查询成功", data=region_info_map), status_code=200)


@router.get("/v1.0/devops/teams/{team_name}/env/{env_id}/checkResource", response_model=Response, name="检查应用及组件是否存在")
async def check_resource(
        request: Request,
        application_code: Optional[int] = -1,
        component_code: Optional[str] = None,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    is_app = True
    is_component = True
    app = hunan_expressway_repo.get_app_by_app_id(session, application_code)
    if not app:
        is_app = False
    service = service_info_repo.get_service_by_tenant_and_alias(session, env.tenant_id, component_code)
    if not service:
        is_component = False
    data = {
        "is_app": is_app,
        "is_component": is_component
    }
    return JSONResponse(general_message(200, "success", "查询成功", bean=data), status_code=200)
