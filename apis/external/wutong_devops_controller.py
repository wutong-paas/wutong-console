import pickle
import time
from typing import Optional, Any

from fastapi import Depends, APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from fastapi_pagination import Params, paginate
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.responses import JSONResponse
from xpinyin import Pinyin

from apis.manage.user.user_manage_controller import create_access_token
from core import deps
from core.setting import settings
from core.utils.dependencies import DALGetter
from core.utils.return_message import general_message, error_message
from core.utils.validation import is_qualified_name
from database.session import SessionClass
from exceptions.bcode import ErrQualifiedName, ErrNamespaceExists
from exceptions.exceptions import GroupNotExistError
from exceptions.main import ServiceHandleException, AbortRequest, ResourceNotEnoughException, AccountOverdueException
from models.teams import RegionConfig
from models.users.users import UserAccessKey, Users
from repository.application.app_repository import app_repo
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.devops.devops_repo import devops_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.expressway.hunan_expressway_repo import hunan_expressway_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.team_repo import team_repo
from repository.teams.team_roles_repo import TeamRolesRepository
from repository.users.user_oauth_repo import oauth_repo, oauth_user_repo
from repository.users.user_repo import user_repo
from schemas.components import BuildSourceParam, DeployBusinessParams
from schemas.market import MarketAppModelParam, DevopsMarketAppCreateParam
from schemas.response import Response
from schemas.team import CreateTeamParam, CreateTeamUserParam, DeleteTeamUserParam
from schemas.user import CreateAccessTokenParam, CreateUserParam
from schemas.wutong_team_app import DevOpsTeamAppCreateParam
from service.app_actions.app_deploy import app_deploy_service
from service.app_actions.exception import ErrServiceSourceNotFound
from service.app_config.app_relation_service import dependency_service
from service.application_service import application_service
from service.market_app_service import market_app_service
from service.region_service import region_services
from service.team_service import team_services
from service.user_service import user_svc

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token/")


@router.post("/v1.0/devops/access_token", response_model=Response, name="获取token")
async def create_access_devops_token(
        params: Optional[CreateAccessTokenParam] = CreateAccessTokenParam(),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    # 用户
    user = session.execute(select(Users).where(
        Users.nick_name == 'admin')).scalars().first()
    if not params.note:
        raise ServiceHandleException(msg="note can't be null", msg_show="注释不能为空")

    user_access_key = session.execute(select(UserAccessKey).where(
        UserAccessKey.note == params.note)).scalars().first()
    if user_access_key:
        return JSONResponse(general_message(200, None, None, bean=jsonable_encoder(user_access_key)), status_code=200)
    try:
        if params.age:
            second_time = time.time() + float(params.age)
            struct_time = time.localtime(second_time)  # 得到结构化时间格式
            expire_time = time.strftime("%Y-%m-%d %H:%M:%S", struct_time)
        else:
            second_time = None
            expire_time = None
        key = create_access_token(user, second_time)
        add_model: UserAccessKey = UserAccessKey(note=params.note, user_id=user.user_id,
                                                 expire_time=expire_time, access_key=key)
        session.add(add_model)
        session.flush()
        return JSONResponse(general_message(200, None, None, bean=jsonable_encoder(add_model)), status_code=200)
    except ValueError as e:
        logger.exception(e)
        raise ServiceHandleException(msg="params error", msg_show="请检查参数是否合法")
    except IntegrityError:
        raise ServiceHandleException(msg="note duplicate", msg_show="令牌用途不能重复")


@router.post("/v1.0/devops/add_team", response_model=Response, name="创建团队")
async def add_team(
        request: Request,
        params: Optional[CreateTeamParam] = CreateTeamParam(),
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    user = user_svc.devops_get_current_user(session=session, token=authorization)
    team_alias = params.team_name
    useable_regions = params.useable_regions
    namespace = params.namespace
    if not is_qualified_name(namespace):
        raise ErrQualifiedName(msg="invalid namespace name", msg_show="命名空间只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")
    enterprise_id = user.enterprise_id

    if not team_alias:
        result = general_message(400, "failed", "团队名不能为空")
        return JSONResponse(status_code=400, content=result)

    regions = []
    if useable_regions:
        regions = useable_regions.split(",")

    team = team_repo.team_is_exists_by_team_name(session, team_alias, enterprise_id)
    if team:
        result = general_message(200, "success", "该团队已存在", jsonable_encoder(team))
        return JSONResponse(status_code=200, content=result)

    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    if not enterprise:
        result = general_message(500, "user's enterprise is not found", "无企业信息")
        return JSONResponse(status_code=500, content=result)

    team = team_repo.create_team(session, user, enterprise, regions, team_alias, namespace)
    exist_namespace_region_names = []

    for r in regions:
        try:
            region_services.create_tenant_on_region(session=session, enterprise_id=enterprise.enterprise_id,
                                                    team_name=team.tenant_name, region_name=r, namespace=team.namespace)
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
        return JSONResponse(
            general_message(400, "success", "团队在集群【{} 】中已存在命名空间 {}".format(exist_namespace_region, team.namespace),
                            bean=jsonable_encoder(team)))
    request.app.state.redis.set("team_%s" % team.tenant_name, pickle.dumps(team), settings.REDIS_CACHE_TTL)
    result = general_message(200, "success", "团队添加成功", bean=jsonable_encoder(team))
    return JSONResponse(status_code=200, content=result)


@router.post("/v1.0/devops/add_member", response_model=Response, name="成员注册")
async def add_users(
        request: Request,
        params: Optional[CreateUserParam] = CreateUserParam(),
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    user_name = params.user_name
    email = params.email
    password = params.password
    re_password = params.re_password
    phone = params.phone
    real_name = params.realname
    oauth_user_id = params.oauth_user_id

    if len(password) < 8:
        result = general_message(400, "len error", "密码长度最少为8位")
        return JSONResponse(result, status_code=400)

    # check user info
    user = user_svc.devops_get_current_user(session, authorization)
    if user_svc.get_user_by_email(session, email):
        register_user = session.execute(select(Users).where(
            Users.email == email,
            Users.enterprise_id == user.enterprise_id
        )).scalars().first()
        return JSONResponse(
            general_message(200, "email already exists", "邮箱{0}已存在".format(email),
                            bean=jsonable_encoder(register_user)), status_code=200)
    try:
        res = user_svc.devops_check_params(session, user_name, email, password, re_password, user.enterprise_id, phone)
        if res:
            register_user = session.execute(select(Users).where(
                Users.nick_name == user_name,
                Users.enterprise_id == user.enterprise_id
            )).scalars().first()
            result = general_message(200, "success", "注册成功", bean=jsonable_encoder(register_user))
            return JSONResponse(result, status_code=200)
    except AbortRequest as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    client_ip = user_svc.get_client_ip(request)
    # create user
    oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)

    if oauth_instance:
        user = user_svc.create_enterprise_center_user_set_password(session, user_name, email, password, "admin add",
                                                                   user.enterprise_id,
                                                                   client_ip, phone, real_name, oauth_instance)
    else:
        user = user_svc.create_user_set_password(session, user_name, email, password, "admin add", user.enterprise_id,
                                                 client_ip,
                                                 phone,
                                                 real_name)
    session.add(user)
    session.flush()
    user_id = user.user_id
    idaas_oauth_service = oauth_repo.get_idaas_oauth_service(session)
    oauth_user = oauth_user_repo.user_oauth_exists(session=session, service_id=idaas_oauth_service.ID, oauth_user_id=oauth_user_id)
    link_user = oauth_repo.get_user_oauth_by_user_id(session=session, service_id=idaas_oauth_service.ID, user_id=user_id)
    if link_user is not None and link_user.oauth_user_id != oauth_user_id:
        logger.warning("该用户已绑定其他账号")

    if oauth_user is not None:
        oauth_user.user_id = user_id
    else:
        oauth_user_repo.save_oauth(
            session=session,
            oauth_user_id=oauth_user_id,
            oauth_user_name=user_name,
            oauth_user_email=user.email,
            user_id=user_id,
            code="",
            service_id=idaas_oauth_service.ID,
            access_token="",
            refresh_token="",
            is_authenticated=True,
            is_expired=False,
        )
    result = general_message(200, "success", "注册成功", bean=jsonable_encoder(user))
    return JSONResponse(result, status_code=200)


@router.get("/v1.0/devops/team_roles", response_model=Response, name="团队角色获取")
async def get_team_roles_lc(
        request: Request,
        authorization: Optional[str] = Depends(oauth2_scheme),
        dal: TeamRolesRepository = Depends(DALGetter(TeamRolesRepository)),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    team_code = request.query_params.get("team_code")
    roles = dal.get_role_by_team_name(session, "team", team_code)
    data = []
    for row in roles:
        data.append({"name": row.name, "id": row.ID})
    result = general_message(200, "success", None, list=data)
    return JSONResponse(result, status_code=200)


@router.post("/v1.0/devops/teams/{team_code}/add_team_user", response_model=Response, name="添加团队成员")
async def add_team_user(
        request: Request,
        params: CreateTeamUserParam,
        authorization: Optional[str] = Depends(oauth2_scheme),
        team_code: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    try:
        user_ids = params.user_ids
        role_id = params.role_id
        if not user_ids:
            return JSONResponse(general_message(400, "failed", "用户名为空"), status_code=400)
        if not role_id:
            return JSONResponse(general_message(400, "failed", "角色ID为空"), status_code=400)
        try:
            user_ids = [int(user_id) for user_id in user_ids.split(",")]
            role_ids = [int(user_id) for user_id in role_id.split(",")]
        except Exception as e:
            code = 400
            logger.exception(e)
            result = general_message(code, "Incorrect parameter format", "参数格式不正确")
            return JSONResponse(result, status_code=result["code"])

        team = team_services.devops_get_tenant(tenant_name=team_code, session=session)

        if not team:
            return JSONResponse(general_message(400, "tenant not exist", "{}团队不存在".format(team_code)),
                                status_code=400)

        user_id = team_services.user_is_exist_in_team(session=session, user_list=user_ids, tenant_name=team_code)
        if user_id:
            user_obj = user_repo.get_user_by_user_id(session=session, user_id=user_id)
            code = 400
            result = general_message(code, "user already exist", "用户{}已经存在".format(user_obj.nick_name))
            return JSONResponse(result, status_code=result["code"])

        code = 200
        team_services.add_user_role_to_team(session=session, tenant=team, user_ids=user_ids, role_ids=role_ids)
        result = general_message(code, "success", "用户添加到{}成功".format(team_code))
    except ServiceHandleException as e:
        code = 404
        result = general_message(code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.delete("/v1.0/devops/teams/{team_code}/del_team_user", response_model=Response, name="删除团队成员")
async def delete_team_user(
        request: Request,
        authorization: Optional[str] = Depends(oauth2_scheme),
        team_code: Optional[str] = None,
        params: Optional[DeleteTeamUserParam] = DeleteTeamUserParam(),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    """
            删除租户内的用户
            (可批量可单个)
            ---
            parameters:
                - name: team_name
                  description: 团队名称
                  required: true
                  type: string
                  paramType: path
                - name: user_ids
                  description: 用户名 user_id1,user_id2 ...
                  required: true
                  type: string
                  paramType: body
            """
    try:
        user_ids = params.user_ids
        if not user_ids:
            return JSONResponse(general_message(400, "failed", "删除成员不能为空"), status_code=400)

        user = user_svc.devops_get_current_user(session=session, token=authorization)

        if user.user_id in user_ids:
            return JSONResponse(general_message(400, "failed", "不能删除自己"), status_code=400)

        team = team_services.devops_get_tenant(tenant_name=team_code, session=session)
        if not team:
            return JSONResponse(general_message(400, "tenant not exist", "{}团队不存在".format(team_code)), status_code=400)

        for user_id in user_ids:
            if user_id == team.creater:
                return JSONResponse(general_message(400, "failed", "不能删除团队创建者！"), 400)
        try:
            team_services.batch_delete_users(request=request, session=session, tenant_name=team_code,
                                             user_id_list=user_ids)
            result = general_message(200, "delete the success", "删除成功")
        except ServiceHandleException as e:
            logger.exception(e)
            result = general_message(400, e.msg, e.msg_show)
        except Exception as e:
            logger.exception(e)
            result = error_message()
        return JSONResponse(result, status_code=result["code"])
    except Exception as e:
        logger.exception(e)
        result = error_message()
    return JSONResponse(result, status_code=result["code"])


@router.post("/v1.0/devops/teams/application", response_model=Response, name="创建应⽤")
async def create_app(
        request: Request,
        params: DevOpsTeamAppCreateParam,
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    if len(params.note) > 2048:
        result = general_message(400, "node too long", "应用备注长度限制2048")
        return JSONResponse(result, status_code=result["code"])
    # 查询当前用户
    user: Users = user_svc.devops_get_current_user(session=session, token=authorization)
    # 查询当前团队
    tenant = team_services.devops_get_tenant(tenant_name=params.team_code, session=session)
    p = Pinyin()
    k8s_app = p.get_pinyin(params.application_name)
    app_template_name = None
    app_store_name = None
    app_store_url = None
    version = None
    if k8s_app and not is_qualified_name(k8s_app):
        raise ErrQualifiedName(msg_show="应用英文名称只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")

    if application_repo.is_k8s_app_duplicate(session, tenant.tenant_id, params.region_code, k8s_app, 0):
        app = application_repo.get_app_by_k8s_app(session, tenant.tenant_id, params.region_code, k8s_app)
        res = jsonable_encoder(app)
        res["group_id"] = app.ID
        res['application_id'] = app.ID
        res['application_name'] = app.group_name
        result = general_message(200, "success", "应用已存在", bean=res)
        return JSONResponse(result, status_code=result["code"])

    try:
        data = application_service.create_app(
            session=session,
            tenant=tenant,
            region_name=params.region_code,
            app_name=params.application_name,
            note=params.note,
            username=user.get_username(),
            app_store_name=app_store_name,
            app_store_url=app_store_url,
            app_template_name=app_template_name,
            version=version,
            eid=user.enterprise_id,
            logo=params.logo,
            k8s_app=k8s_app
        )
    except ServiceHandleException as e:
        session.rollback()
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    result = general_message(200, "success", "创建成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=result["code"])


@router.get("/v1.0/devops/base_component_models", response_model=Response, name="获取本地市场应用列表")
async def app_models(
        params: Optional[MarketAppModelParam] = MarketAppModelParam(),
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    page = params.page
    page_size = params.page_size
    if page < 1:
        page = 1
    tags = []
    is_complete = None
    need_install = False
    app_name = None
    scope = "enterprise"
    user = user_svc.devops_get_current_user(session=session, token=authorization)
    apps, count = market_app_service.get_visiable_apps(session, user, user.enterprise_id, scope,
                                                       app_name, tags, is_complete,
                                                       page,
                                                       page_size, need_install)

    return JSONResponse(
        general_message(200, "success", msg_show="查询成功", list=jsonable_encoder(apps), total=count,
                        next_page=int(page) + 1),
        status_code=200)


@router.get("/v1.0/devops/teams/{team_code}/components", response_model=Response, name="组件列表")
async def get_app_state(
        request: Request,
        authorization: Optional[str] = Depends(oauth2_scheme),
        team_code: Optional[str] = None,
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
        if application_id is None or not application_id.isdigit():
            code = 400
            result = general_message(code, "group_id is missing or not digit!", "group_id缺失或非数字")
            return JSONResponse(result, status_code=code)
        # region_name = request.headers.get("X_REGION_NAME")
        team = team_services.devops_get_tenant(tenant_name=team_code, session=session)
        if not team:
            result = general_message(400, "tenant not exist", "{}团队不存在".format(team_code))
            return JSONResponse(result, status_code=400)
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        # region_name = request.headers.get("X_REGION_NAME")
        region_name = region.region_name

        if application_id == "-1":
            # query service which not belong to any app
            no_group_service_list = service_info_repo.get_no_group_service_status_by_group_id(
                session=session,
                team_name=team_code,
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
            team_name=team_code,
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
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    page_num = 1
    page_size = 99
    team_code = request.query_params.get("team_code")
    search_key = None
    condition = None
    tenant = team_services.devops_get_tenant(tenant_name=team_code, session=session)
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


@router.post("/v1.0/devops/teams/{team_code}/applications/{application_id}/build", response_model=Response,
             name="部署业务组件")
async def deploy_business_component(
        params: DeployBusinessParams,
        team_code: Optional[str] = None,
        application_id: Optional[str] = None,
        authorization: Optional[str] = Depends(oauth2_scheme),
        session: SessionClass = Depends(deps.get_session)) -> Any:
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
        # 查询当前团队
        tenant = team_services.devops_get_tenant(tenant_name=team_code, session=session)
        if not tenant:
            return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)
        region = team_region_repo.get_region_by_tenant_id(session, tenant.tenant_id)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        region_name = region.region_name
        application = application_repo.get_by_primary_key(session=session, primary_key=application_id)
        if application and application.tenant_id != tenant.tenant_id:
            return JSONResponse(general_message(400, "not found app at team", "应用不属于该团队"), status_code=400)
        # 查询当前用户
        user: Users = user_svc.devops_get_current_user(session=session, token=authorization)

        code, msg_show, new_service = application_service.create_docker_run_app(session=session,
                                                                                region_name=region_name,
                                                                                tenant=tenant,
                                                                                user=user,
                                                                                service_cname=params.component_name,
                                                                                docker_cmd=params.docker_image,
                                                                                image_type=image_type,
                                                                                k8s_component_name=k8s_component_name)
        if code != 200:
            return JSONResponse(general_message(code, "service create fail", msg_show), status_code=200)

        # 添加username,password信息
        if params.registry_password or params.registry_user:
            application_service.create_service_source_info(session=session, tenant=tenant, service=new_service,
                                                           user_name=params.registry_user,
                                                           password=params.registry_password)

        code, msg_show = application_service.add_component_to_app(session=session, tenant=tenant,
                                                                  region_name=region_name,
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
                                                  env_variables.desc, user, tenant, new_service)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        if params.dep_service_ids is not None:
            result = devops_repo.add_dep(session, user, tenant, new_service, params.dep_service_ids)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        session.flush()
        result = devops_repo.component_build(session, user, tenant, new_service)
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        session.rollback()
        return JSONResponse(general_message(10410, "resource is not enough", re), status_code=10410)
    return JSONResponse(result, status_code=result["code"])


@router.post("/v1.0/devops/teams/{team_code}/buildsource", response_model=Response, name="构建组件")
async def deploy_component(
        request: Request,
        params: BuildSourceParam,
        authorization: Optional[str] = Depends(oauth2_scheme),
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
        logger.debug("code ===== " + params.component_code)
        result = general_message(200, "success", "成功")
        user = user_svc.devops_get_current_user(session=session, token=authorization)
        tenant = team_services.devops_get_tenant(tenant_name=team_code, session=session)
        service = service_info_repo.get_service(session, params.component_code, tenant.tenant_id)
        oauth_instance, _ = user_svc.check_user_is_enterprise_center_user(session, user.user_id)
        logger.debug("service_alias ==== {0} 111111 service.service_source ==== {1}", service.service_alias,
                     service.service_source)
        if params.docker_image is not None:
            devops_repo.modify_source(session, service, params.docker_image,
                                      params.registry_user, params.registry_password)
        logger.debug("service_alias ==== {0} 222222 service.service_source ==== {1}", service.service_alias,
                     service.service_source)
        if params.env_variables is not None:
            for env_variables in params.env_variables:
                if env_variables.key is not None:
                    result = devops_repo.add_envs(session, env_variables.key, env_variables.value,
                                                  env_variables.desc, user, tenant, service)

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
            result = devops_repo.delete_dependency_component(session, user, tenant, service,
                                                             params.delete_dep_service_ids)

        if result["code"] != 200:
            session.rollback()
            return JSONResponse(result, status_code=result["code"])

        session.flush()
        group_version = None
        logger.debug("service_alias ==== {0} 333333 service.service_source ==== {1}", service.service_alias,
                     service.service_source)
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
        session: SessionClass = Depends(deps.get_session),
        authorization: Optional[str] = Depends(oauth2_scheme)
) -> Any:
    """
    部署基础组件
    """
    install_from_cloud = False
    is_deploy = True
    market_name = ""
    # 查询当前用户
    user: Users = user_svc.devops_get_current_user(session=session, token=authorization)
    if not user:
        return JSONResponse(general_message(400, "not found user", "用户不存在"), status_code=400)
    # 查询当前团队
    tenant = team_services.devops_get_tenant(tenant_name=params.team_code, session=session)
    if not tenant:
        return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, tenant.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    region_info = session.execute(select(RegionConfig).where(
        RegionConfig.region_name == region.region_name
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


@router.get("/v1.0/devops/teams/{team_name}/regions", response_model=Response, name="查询团队绑定集群")
async def get_team_regions(
        request: Request,
        authorization: Optional[str] = Depends(oauth2_scheme),
        team=Depends(deps.get_current_team),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    region_info_map = []
    region_name_list = team_repo.get_team_region_names(session, team.tenant_id)
    if region_name_list:
        region_infos = region_repo.get_region_by_region_names(session, region_name_list)
        if region_infos:
            for region in region_infos:
                region_info_map.append(
                    {"id": region.ID, "region_name": region.region_name, "region_alias": region.region_alias})
    return JSONResponse(general_message(200, "success", "查询成功", data=region_info_map), status_code=200)


@router.get("/v1.0/devops/teams/{team_name}/checkResource", response_model=Response, name="检查应用及组件是否存在")
async def check_resource(
        request: Request,
        application_code: Optional[int] = -1,
        component_code: Optional[str] = None,
        authorization: Optional[str] = Depends(oauth2_scheme),
        team=Depends(deps.get_current_team),
        session: SessionClass = Depends(deps.get_session)
) -> Any:
    is_app = True
    is_component = True
    app = hunan_expressway_repo.get_app_by_app_id(session, application_code)
    if not app:
        is_app = False
    service = service_info_repo.get_service_by_tenant_and_alias(session, team.tenant_id, component_code)
    if not service:
        is_component = False
    data = {
        "is_app": is_app,
        "is_component": is_component
    }
    return JSONResponse(general_message(200, "success", "查询成功", bean=data), status_code=200)


@router.delete("/v1.0/devops/teams/{team_name}/users/batch/delete", response_model=Response, name="删除团队成员")
async def delete_team_user(request: Request,
                           team_name: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           authorization: Optional[str] = Depends(oauth2_scheme),
                           team=Depends(deps.get_current_team)) -> Any:
    """
            删除租户内的用户
            (可批量可单个)

            """
    try:
        from_data = await request.json()
        user_ids = from_data["user_ids"]
        if not user_ids:
            return JSONResponse(general_message(400, "failed", "删除成员不能为空"), status_code=400)

        user: Users = user_svc.devops_get_current_user(session=session, token=authorization)
        if user.user_id in user_ids:
            return JSONResponse(general_message(400, "failed", "不能删除自己"), status_code=400)

        for user_id in user_ids:
            if user_id == team.creater:
                return JSONResponse(general_message(400, "failed", "不能删除团队创建者！"), 400)
        try:
            team_services.batch_delete_users(request=request, session=session, tenant_name=team_name,
                                             user_id_list=user_ids)
            result = general_message(200, "delete the success", "删除成功")
        except ServiceHandleException as e:
            logger.exception(e)
            result = general_message(400, e.msg, e.msg_show)
        except Exception as e:
            logger.exception(e)
            result = error_message()
        return JSONResponse(result, status_code=result["code"])
    except Exception as e:
        logger.exception(e)
        result = error_message()
    return JSONResponse(result, status_code=result["code"])
