import json
from typing import Any, Optional

from fastapi import APIRouter, Path, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select

from core import deps
from core.utils.crypt import make_uuid
from core.utils.dependencies import DALGetter
from core.utils.return_message import general_message, error_message
from core.utils.validation import validate_name
from database.session import SessionClass
from exceptions.main import RegionNotFound, AbortRequest
from models.market.models import CenterAppTag
from models.teams import PermRelTenant, RegionConfig
from models.teams.enterprise import TeamEnterprise
from models.users.users import Users
from repository.application.app_repository import app_tag_repo
from repository.market.center_app_tag_repo import center_app_tag_repo
from repository.market.center_repo import CenterRepository
from repository.region.region_config_repo import region_config_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_enterprise_repo import tenant_enterprise_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.team_repo import team_repo
from schemas import CenterAppCreate
from schemas.market import MarketAppTemplateUpdateParam, MarketAppCreateParam
from schemas.response import Response
from service.app_import_and_export_service import import_service, export_service
from service.market_app_service import market_app_service
from service.region_service import region_services
from service.team_service import team_services
from service.user_service import user_svc

router = APIRouter()


@router.get("/enterprise/{enterprise_id}/create-app-teams", response_model=Response, name="安装应用-团队列表")
async def create_app_teams(enterprise_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user)) -> Any:
    if not user:
        return general_message(400, "not found user", "用户不存在")
    teams = list()
    tenants = []
    enterprise = tenant_enterprise_repo.get_one_by_model(session=session,
                                                         query_model=TeamEnterprise(enterprise_id=enterprise_id))
    if enterprise:
        tenant_ids = (
            session.execute(select(PermRelTenant.tenant_id).where(PermRelTenant.enterprise_id == enterprise.ID,
                                                                  PermRelTenant.user_id == user.user_id))
        ).scalars().all()
        tenant_ids = set(tenant_ids)
        for tenant_id in tenant_ids:
            tn = team_repo.get_by_primary_key(session=session, primary_key=tenant_id)
            if tn:
                tenants.append(tn)

    if tenants:
        for tenant in tenants:
            perms = user_svc.list_user_team_perms(session, user, tenant)
            # todo 权限控制
            if 200001 not in perms or 300002 not in perms or 400002 not in perms:
                continue
            region_teams = team_services.team_with_region_info(session=session, tenant=tenant, request_user=user)
            teams.append(region_teams)
    return general_message(200, "success", "查询成功", list=teams)


@router.post("/teams/{team_name}/apps/market_create", response_model=Response, name="安装市场应用")
async def market_create(params: Optional[MarketAppCreateParam] = MarketAppCreateParam(),
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user),
                        team=Depends(deps.get_current_team)) -> Any:
    """
    创建应用市场应用
    """
    if not user:
        return JSONResponse(general_message(400, "not found user", "用户不存在"), status_code=400)
    if not team:
        return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    region_info = region_config_repo.get_one_by_model(session=session,
                                                      query_model=RegionConfig(region_name=region.region_name))
    market_app_service.install_app(session=session, tenant=team, region=region_info, user=user,
                                   app_id=params.group_id,
                                   app_model_key=params.app_id, version=params.app_version,
                                   market_name=params.market_name,
                                   install_from_cloud=params.install_from_cloud, is_deploy=params.is_deploy)

    market_app_service.update_wutong_app_install_num(session=session, enterprise_id=region.enterprise_id,
                                                     app_id=params.app_id, app_version=params.app_version)

    return JSONResponse(general_message(200, "success", "创建成功"), status_code=200)


@router.get("/enterprise/{enterprise_id}/app-model/{app_id}", response_model=Response, name="获取应用模版")
async def get_app_template(page: Optional[int] = 1,
                           page_size: Optional[int] = 10,
                           enterprise_id: Optional[str] = None,
                           app_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    app, versions, total = market_app_service.get_wutong_app_and_versions(session,
                                                                          enterprise_id, app_id, page,
                                                                          page_size)
    # todo
    # todo
    return JSONResponse(
        general_message(200, "success", "查询成功", list=jsonable_encoder(versions), bean=jsonable_encoder(app),
                        total=total), status_code=200)


# todo
@router.put("/enterprise/{enterprise_id}/app-model/{app_id}", response_model=Response, name="更新应用模版")
async def update_app_template(params: Optional[MarketAppTemplateUpdateParam] = MarketAppTemplateUpdateParam(),
                              enterprise_id: Optional[str] = None,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    name = params.name
    if not validate_name(name):
        return general_message(400, "error params", "应用名称只支持中文、字母、数字和-_组合,并且必须以中文、字母、数字开始和结束")
    describe = params.describe
    pic = params.pic
    details = params.details
    dev_status = params.dev_status
    tag_ids = params.tag_ids
    scope = params.scope
    create_team = params.create_team
    if scope == "team" and not create_team:
        return JSONResponse(general_message(400, "please select team", "请选择团队"), status_code=400)

    app_info = {
        "name": name,
        "describe": describe,
        "pic": pic,
        "details": details,
        "dev_status": dev_status,
        "tag_ids": tag_ids,
        "scope": scope,
        "create_team": create_team,
    }
    market_app_service.update_rainbond_app(session, enterprise_id, app_id, app_info)
    return JSONResponse(general_message(200, "success", None), status_code=200)


@router.delete("/enterprise/{enterprise_id}/app-model/{app_id}", response_model=Response, name="删除应用模版")
async def delete_app_template(enterprise_id: Optional[str] = None,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    market_app_service.delete_rainbond_app_all_info_by_id(session, enterprise_id, app_id)
    return JSONResponse(general_message(200, "success", None), status_code=200)


# 获取本地市场应用列表
@router.get("/enterprise/{enterprise_id}/app-models", response_model=Response, name="获取本地市场应用列表")
async def app_models(request: Request,
                     enterprise_id: str = Path(..., title="enterprise_id"),
                     page: Optional[int] = 1,
                     page_size: Optional[int] = 10,
                     session: SessionClass = Depends(deps.get_session),
                     user: Users = Depends(deps.get_current_user)) -> Any:
    """
    查询数据库
    :param session:
    :param user:
    :param page:
    :param page_size:
    :param enterprise_id:
    :return:
    """
    if page < 1:
        page = 1
    is_complete = request.query_params.get("is_complete", None)
    need_install = request.query_params.get("need_install", "false")
    scope = request.query_params.get("scope", None)
    tags = request.query_params.get("tags", [])
    app_name = request.query_params.get("app_name", None)

    if tags:
        tags = json.loads(tags)

    apps, count = market_app_service.get_visiable_apps(session, user, enterprise_id, scope, app_name, tags, is_complete,
                                                       page,
                                                       page_size, need_install)

    return JSONResponse(
        general_message(200, "success", msg_show="查询成功", list=jsonable_encoder(apps), total=count,
                        next_page=int(page) + 1),
        status_code=200)


@router.post("/enterprise/{enterprise_id}/app-models", response_model=Response, name="增加本地市场应用")
async def add_app_models(request: Request,
                         enterprise_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    name = data.get("name")
    describe = data.get("describe", 'This is a default description.')
    pic = data.get("pic")
    details = data.get("details")
    dev_status = data.get("dev_status")
    tag_ids = data.get("tag_ids")
    scope = data.get("scope", "enterprise")
    scope_target = data.get("scope_target")
    source = data.get("source", "local")
    create_team = data.get("create_team", data.get("team_name", None))
    if scope == "team" and not create_team:
        result = general_message(400, "please select team", "请选择团队")
        return JSONResponse(result, status_code=400)
    if scope not in ["team", "enterprise", "market"]:
        result = general_message(400, "parameter error", "scope 参数不正确")
        return JSONResponse(result, status_code=400)
    if not name:
        result = general_message(400, "error params", "请填写应用名称")
        return JSONResponse(result, status_code=400)
    if not validate_name(name):
        result = general_message(400, "error params", "应用名称只支持中文、字母、数字和-_组合,并且必须以中文、字母、数字开始和结束")
        return JSONResponse(result, status_code=400)
    app_info = {
        "app_name": name,
        "describe": describe,
        "pic": pic,
        "details": details,
        "dev_status": dev_status,
        "tag_ids": tag_ids,
        "scope": scope,
        "scope_target": scope_target,
        "source": source,
        "create_team": create_team,
        "create_user": user.user_id,
        "create_user_name": user.nick_name
    }
    market_app_service.create_wutong_app(session, enterprise_id, app_info, make_uuid())

    result = general_message(200, "success", None)
    return JSONResponse(result, status_code=200)


@router.post("/enterprise/{enterprise_id}/app-models/tag", response_model=Response, name="tag")
async def update_tag(request: Request,
                     enterprise_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    name = data.get("name", None)
    result = general_message(200, "success", "创建成功")
    if not name:
        result = general_message(400, "fail", "参数不正确")
    try:
        rst = app_tag_repo.create_tag(session, enterprise_id, name)
        if not rst:
            result = general_message(400, "fail", "标签已存在")
    except Exception as e:
        logger.debug(e)
        result = general_message(400, "fail", "创建失败")
    return JSONResponse(result, status_code=result.get("code", 200))


@router.get("/enterprise/{enterprise_id}/app-models/tag", response_model=Response, name="tag")
async def get_tag(enterprise_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    data = []
    app_tag_list = center_app_tag_repo.list_by_model(session=session,
                                                     query_model=CenterAppTag(enterprise_id=enterprise_id,
                                                                              is_deleted=False))
    if app_tag_list:
        for app_tag in app_tag_list:
            data.append({"name": app_tag.name, "tag_id": app_tag.ID})
    result = general_message(200, "success", None, list=data)
    return JSONResponse(result, status_code=result["code"])


# 创建应用市场应用
@router.post("/{enterprise_id}/app-models/{app_id}", response_model=Response, name="创建应用市场应用")
async def create_center_app(*,
                            params: CenterAppCreate,
                            dal: CenterRepository = Depends(DALGetter(CenterRepository)),
                            session: SessionClass = Depends(deps.get_session)
                            ) -> Any:
    """
    :param params:
    :return:
    """
    dal.create_center_app(session=session, params=params)
    result = general_message(200, "success", None, None)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/app-models/import", response_model=Response, name="创建新的导入记录")
async def add_app_models(enterprise_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user)) -> Any:
    """
    查询导入记录，如果有未完成的记录返回未完成的记录，如果没有，创建新的导入记录
    ---
    parameters:
        - name: tenantName
          description: 团队名称
          required: true
          type: string
          paramType: path

    """
    unfinished_records = import_service.get_user_not_finish_import_record_in_enterprise(session, enterprise_id, user)
    new = False
    if unfinished_records:
        r = unfinished_records[len(unfinished_records) - 1]
        region = region_services.get_region_by_region_name(session, r.region)
        if not region:
            logger.warning("not found region for old import recoder")
            new = True
    else:
        new = True
    if new:
        try:
            r = import_service.create_app_import_record_2_enterprise(session, enterprise_id, user.nick_name)
        except RegionNotFound:
            return JSONResponse(general_message(200, "success", "查询成功", bean={"region_name": ''}), status_code=200)
    upload_url = import_service.get_upload_url(session, r.region, r.event_id)
    region = region_repo.get_region_by_region_name(session, r.region)
    data = {
        "status": r.status,
        "source_dir": r.source_dir,
        "event_id": r.event_id,
        "upload_url": upload_url,
        "region_name": region.region_alias if region else '',
    }
    return JSONResponse(general_message(200, "success", "查询成功", bean=data), status_code=200)


@router.get("/enterprise/{enterprise_id}/app-models/import/{event_id}", response_model=Response, name="查询应用包导入状态")
async def get_app_import(event_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询应用包导入状态
    ---
    parameters:
        - name: tenantName
          description: 团队名称
          required: true
          type: string
          paramType: path
        - name: event_id
          description: 事件ID
          required: true
          type: string
          paramType: path
    """
    try:
        record, apps_status = import_service.get_and_update_import_by_event_id(session, event_id)
        result = general_message(200, 'success', "查询成功", bean=jsonable_encoder(record), list=apps_status)
    except Exception as e:
        raise e
    return JSONResponse(result, status_code=result["code"])


@router.get("/enterprise/{enterprise_id}/app-models/import/{event_id}/dir", response_model=Response, name="查询应用包目录")
async def get_app_dir(event_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询应用包目录
    ---
    parameters:
        - name: tenantName
          description: 团队名称
          required: true
          type: string
          paramType: path
        - name: event_id
          description: 事件ID
          required: true
          type: string
          paramType: query
    """
    if not event_id:
        return JSONResponse(general_message(400, "event id is null", "请指明需要查询的event id"), status_code=400)

    apps = import_service.get_import_app_dir(session, event_id)
    result = general_message(200, "success", "查询成功", list=apps)
    return JSONResponse(result, status_code=result["code"])


@router.put("/enterprise/{enterprise_id}/app-model/{app_id}/version/{version}", response_model=Response, name="编辑应用模版")
async def set_app_template(request: Request,
                           enterprise_id: Optional[str] = None, app_id: Optional[str] = None,
                           version: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    dev_status = data.get("dev_status", "")
    version_alias = data.get("version_alias", None)
    app_version_info = data.get("app_version_info", None)

    body = {
        "release_user_id": user.user_id,
        "dev_status": dev_status,
        "version_alias": version_alias,
        "app_version_info": app_version_info
    }
    version = market_app_service.update_wutong_app_version_info(session, enterprise_id, app_id, version, **body)
    result = general_message(200, "success", "更新成功", bean=jsonable_encoder(version))
    return JSONResponse(result, status_code=result.get("code", 200))


@router.delete("/enterprise/{enterprise_id}/app-model/{app_id}/version/{version}", response_model=Response,
               name="删除应用模版")
async def delete_app_template(enterprise_id: Optional[str] = None,
                              app_id: Optional[str] = None,
                              version: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    result = general_message(200, "success", "删除成功")
    market_app_service.delete_wutong_app_version(session, enterprise_id, app_id, version)
    return JSONResponse(result, status_code=result.get("code", 200))


@router.get("/enterprise/{enterprise_id}/app-models/export", response_model=Response, name="获取应用导出状态")
async def get_app_export_status(
        request: Request,
        enterprise_id: str = Path(..., title="enterprise_id"),
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user)) -> Any:
    """
    获取应用导出状态
    ---
    parameters:
        - name: tenantName
          description: 团队名称
          required: true
          type: string
          paramType: path
    """
    app_id = request.query_params.get("app_id", None)
    app_version = request.query_params.get("app_version", None)
    if not app_id or not app_version:
        return JSONResponse(general_message(400, "app id is null", "请指明需要查询的应用"), status_code=400)

    result_list = []
    app_version_list = app_version.split("#")
    for version in app_version_list:
        app, app_version = market_app_service.get_wutong_app_and_version(session, user.enterprise_id, app_id, version)
        if not app or not app_version:
            return JSONResponse(general_message(404, "not found", "云市应用不存在"), status_code=404)
        result = export_service.get_export_status(session, enterprise_id, app, app_version)
        result_list.append(result)

    result = general_message(200, "success", "查询成功", list=result_list)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/app-models/export", response_model=Response, name="导出应用市场应用")
async def export_app_models(
        request: Request,
        enterprise_id: str = Path(..., title="enterprise_id"),
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user)) -> Any:
    """
    导出应用市场应用
    ---
    parameters:
        - name: tenantName
          description: 团队名称
          required: true
          type: string
          paramType: path
        - name: format
          description: 导出类型 rainbond-app | docker-compose
          required: true
          type: string
          paramType: form
    """
    data = await request.json()
    app_id = data.get("app_id", None)
    app_versions = data.get("app_versions", [])
    export_format = data.get("format", None)
    if not app_id or not app_versions:
        return JSONResponse(general_message(400, "app id is null", "请指明需要导出的应用"), status_code=400)
    if not export_format or export_format not in ("wutong-app", "docker-compose"):
        return JSONResponse(general_message(400, "export format is illegal", "请指明导出格式"), status_code=400)

    new_export_record_list = []
    record = export_service.export_app(session, enterprise_id, app_id, app_versions[0], export_format)
    new_export_record_list.append(jsonable_encoder(record))

    result = general_message(200, "success", "操作成功，正在导出", list=new_export_record_list)
    return JSONResponse(result, status_code=result["code"])


@router.post("/enterprise/{enterprise_id}/app-models/import/{event_id}", response_model=Response, name="应用包导入")
async def import_app(
        request: Request,
        enterprise_id: Optional[str] = None,
        event_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    scope = data.get("scope", None)
    file_name = data.get("file_name", None)
    team_name = data.get("tenant_name", None)
    if not scope:
        raise AbortRequest(msg="select the scope", msg_show="请选择导入应用可见范围")
    if scope == "team" and not team_name:
        raise AbortRequest(msg="select the team", msg_show="请选择要导入的团队")
    if not file_name:
        raise AbortRequest(msg="file name is null", msg_show="请选择要导入的文件")
    if not event_id:
        raise AbortRequest(msg="event is not found", msg_show="参数错误，未提供事件ID")
    files = file_name.split(",")
    import_service.start_import_apps(session, scope, event_id, files, team_name, enterprise_id)
    result = general_message(200, 'success', "操作成功，正在导入")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/enterprise/{enterprise_id}/app-models/import/{event_id}", response_model=Response, name="放弃应用包导入")
async def delete_import_app(
        event_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        import_service.delete_import_app_dir_by_event_id(session, event_id)
        result = general_message(200, "success", "操作成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
    return JSONResponse(result, status_code=result["code"])
