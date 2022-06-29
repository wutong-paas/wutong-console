import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from urllib3.exceptions import MaxRetryError

from clients.remote_component_client import remote_component_client
from common.response import MessageResponse
from core import deps
from core.enum.app import GovernanceModeEnum
from core.utils.crypt import make_uuid
from core.utils.reqparse import parse_argument, parse_item
from core.utils.return_message import general_message, error_message, general_data
from core.utils.validation import is_qualified_name
from database.session import SessionClass
from exceptions.bcode import ErrQualifiedName, ErrLastRecordUnfinished
from exceptions.main import ServiceHandleException, AbortRequest, ResourceNotEnoughException, AccountOverdueException
from models.application.models import Application, ComponentApplicationRelation, ApplicationUpgradeRecordType
from models.users.users import Users
from repository.application.application_repo import application_repo
from repository.component.compose_repo import compose_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_share_repo import component_share_repo
from repository.market.center_repo import center_app_repo
from repository.region.region_app_repo import region_app_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from schemas.wutong_application import CommonOperation
from schemas.wutong_team_app import TeamAppCreateRequest
from service.app_actions.app_manage import app_manage_service
from service.app_config_group import app_config_group_service
from service.application_service import application_service
from service.component_service import component_check_service
from service.compose_service import compose_service
from service.helm_app_service import helm_app_service
from service.market_app_service import market_app_service
from service.share_services import share_service
from service.upgrade_service import upgrade_service

router = APIRouter()


def check_services(session: SessionClass, app_id, req_service_ids):
    services = application_service.get_group_services(session=session, group_id=app_id)
    service_ids = [service.service_id for service in services]

    # Judge whether the requested service ID is correct
    if req_service_ids is not None:
        for sid in req_service_ids:
            if sid not in service_ids:
                raise AbortRequest(
                    msg="The serviceID is not in the serviceID of the current application binding",
                    msg_show="请求的组件ID不在当前应用绑定的组件ID中",
                    status_code=404)


@router.post("/teams/{team_name}/groups", response_model=Response, name="新建团队应用")
async def create_app(params: TeamAppCreateRequest,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    新建团队应用
    :param session:
    :param params:
    :return:
    """
    if len(params.note) > 2048:
        result = general_message(400, "node too long", "应用备注长度限制2048")
        return JSONResponse(result, status_code=result["code"])

    k8s_app = params.k8s_app
    if not k8s_app and params.app_name:
        k8s_app = params.app_name
    if k8s_app and not is_qualified_name(k8s_app):
        raise ErrQualifiedName(msg_show="应用英文名称只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")
    try:
        data = application_service.create_app(
            session=session,
            tenant=team,
            region_name=params.region_name,
            app_name=params.app_name,
            note=params.note,
            username=user.get_username(),
            app_store_name=params.app_store_name,
            app_store_url=params.app_store_url,
            app_template_name=params.app_template_name,
            version=params.version,
            eid=user.enterprise_id,
            logo=params.logo,
            k8s_app=k8s_app
        )
    except ServiceHandleException as e:
        session.rollback()
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    result = general_message(200, "success", "创建成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{app_id}", response_model=Response, name="团队应用详情")
async def get_app_detail(app_id: Optional[int] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
    查询应用详情
    :param app_id:
    :return:
    """
    if not team:
        raise ServiceHandleException(msg="not found team", msg_show="团队不存在", status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        raise ServiceHandleException(msg="not found region", msg_show="数据中心不存在", status_code=400)
    region_name = region.region_name
    app = application_service.get_app_detail(session=session, tenant=team, region_name=region_name, app_id=app_id)
    result = general_message(200, "success", "success", bean=jsonable_encoder(app))
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/groups/{app_id}", response_model=Response, name="更新团队应用")
async def update_app(request: Request,
                     app_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    app_name = data.get("app_name", None)
    note = data.get("note", "")
    logo = data.get("logo", "")
    if note and len(note) > 2048:
        return JSONResponse(general_message(400, "node too long", "应用备注长度限制2048"), status_code=400)
    username = data.get("username", None)
    overrides = data.get("overrides", [])
    version = data.get("version", "")
    revision = data.get("revision", 0)

    # response_region = request.headers.get("X_REGION_NAME")
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    application_service.update_group(
        session,
        team,
        response_region,
        app_id,
        app_name,
        note,
        username,
        overrides=overrides,
        version=version,
        revision=revision,
        logo=logo)
    result = general_message(200, "success", "修改成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/groups/{app_id}", response_model=Response, name="删除团队应用")
async def delete_app(app_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     team=Depends(deps.get_current_team)) -> Any:
    # todo
    """
    删除应用
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: group_id
          description: 组id
          required: true
          type: string
          paramType: path
    """
    if not team:
        raise ServiceHandleException(msg="not found team", msg_show="团队不存在", status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        raise ServiceHandleException(msg="not found region", msg_show="数据中心不存在", status_code=400)
    region_name = region.region_name
    app_type = session.query(Application.app_type).filter(Application.ID == app_id).first()[0]
    try:
        application_service.delete_app(session=session, tenant=team, region_name=region_name, app_id=app_id,
                                       app_type=app_type)
        result = general_message(200, "success", "删除成功")
    except AbortRequest as e:
        result = general_message(e.status_code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{app_id}/status", response_model=Response, name="查询应用状态")
async def get_app_status(app_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    if not team:
        return general_message(400, "not found team", "团队不存在")
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    region_name = region.region_name
    status = application_service.get_app_status(session=session, tenant=team, region_name=region_name, app_id=app_id)
    result = general_message(200, "success", "查询成功", list=status)

    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{app_id}/upgradable_num", response_model=Response, name="查询待升级组件数量")
async def get_upgradable_num(app_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    data = dict()
    data['upgradable_num'] = 0
    try:
        if not team:
            return general_message(400, "not found team", "团队不存在")
        region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
        if not region:
            return general_message(400, "not found region", "数据中心不存在")
        region_name = region.region_name
        data['upgradable_num'] = market_app_service.count_upgradeable_market_apps(tenant=team,
                                                                                  region_name=region_name,
                                                                                  app_id=app_id,
                                                                                  session=session)
    except MaxRetryError as e:
        logger.warning("get the number of upgradable app: {}".format(e))
    except ServiceHandleException as e:
        logger.warning("get the number of upgradable app: {}".format(e))
        if e.status_code != 404:
            raise e

    result = general_message(200, "success", "success", bean=data)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{app_id}/visit", response_model=Response, name="visit")
async def get_visit(app_id: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    team=Depends(deps.get_current_team)) -> Any:
    if not team:
        return general_message(400, "not found team", "团队不存在")
    result = application_service.list_access_info(tenant=team, app_id=app_id, session=session)
    return general_message(200, "success", "查询成功", list=result)


@router.put("/teams/{team_name}/groups/{app_id}/volumes", response_model=Response, name="批量修改该应用下有状态组件的存储路径")
async def modify_storage_dir(app_id: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    # region_name = request.headers.get("X_REGION_NAME")
    region_name = region.region_name

    region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
    remote_component_client.change_application_volumes(session, team.tenant_name, region_name, region_app_id)
    result = general_message(200, "success", "存储路径修改成功")
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/groups/{group_id}/common_operation", response_model=Response, name="应用操作")
async def common_operation(params: CommonOperation,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user),
                           team=Depends(deps.get_current_team)) -> Any:
    action = params.action
    group_id = int(params.group_id)
    services = session.query(ComponentApplicationRelation).filter(
        ComponentApplicationRelation.group_id == group_id).all()

    if not services:
        result = general_message(400, "not service", "当前组内无组件，无法操作")
        return JSONResponse(result, status_code=result["code"])
    service_ids = [service.service_id for service in services]
    if action not in ("stop", "start", "upgrade", "deploy"):
        return general_message(400, "param error", "操作类型错误")
    # 去除掉第三方组件
    for service_id in service_ids:
        service_obj = service_info_repo.get_service_by_service_id(session, service_id)
        if service_obj and service_obj.service_source == "third_party":
            service_ids.remove(service_id)

    # if action == "stop":
    #     self.has_perms([300006, 400008])
    # if action == "start":
    #     self.has_perms([300005, 400006])
    # if action == "upgrade":
    #     self.has_perms([300007, 400009])
    # if action == "deploy":
    #     self.has_perms([300008, 400010])
    if not team:
        return general_message(400, "not found team", "团队不存在")
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    region_name = region.region_name
    # 批量操作
    app_manage_service.batch_operations(tenant=team, region_name=region_name, user=user, action=action,
                                        service_ids=service_ids, session=session)
    result = general_message(200, "success", "操作成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{group_id}/share/record", response_model=Response, name="应用发布")
async def app_share_record(request: Request,
                           page: int = Query(default=1, ge=1, le=9999),
                           page_size: int = Query(default=10, ge=1, le=500),
                           team_name: Optional[str] = None,
                           group_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    data = []
    market = dict()
    cloud_app = dict()
    # page = int(request.query_params.get("page", 1))
    # page_size = int(request.query_params.get("page_size", 10))
    total, share_records = component_share_repo.get_service_share_records_by_groupid(
        session=session, team_name=team_name, group_id=group_id, page=page, page_size=page_size)
    if not share_records:
        result = general_message(200, "success", "获取成功", bean={'total': total}, list=data)
        return JSONResponse(result, status_code=200)
    for share_record in share_records:
        app_model_name = share_record.share_app_model_name
        app_model_id = share_record.app_id
        upgrade_time = None
        store_name = share_record.share_store_name
        store_id = share_record.share_app_market_name
        scope = share_record.scope
        if scope != "goodrain" and not app_model_name:
            app = center_app_repo.get_wutong_app_by_app_id(session=session, eid=team.enterprise_id,
                                                           app_id=share_record.app_id)
            app_model_name = app.app_name if app else ""
            app_version = center_app_repo.get_wutong_app_version_by_record_id(session=session,
                                                                              record_id=share_record.ID)
            if app_version:
                upgrade_time = app_version.upgrade_time
                share_record.share_version_alias = app_version.version_alias
                share_record.share_app_version_info = app_version.app_version_info
            share_record.share_app_model_name = app_model_name
            session.flush()
        if scope == "goodrain" and store_id and share_record.app_id and not app_model_name:
            try:
                mkt = market.get(share_record.share_app_market_name, None)
                if not mkt:
                    mkt = market_app_service.get_app_market_by_name(session=session,
                                                                    enterprise_id=team.enterprise_id,
                                                                    name=share_record.share_app_market_name,
                                                                    raise_exception=True)
                    market[share_record.share_app_market_name] = mkt

                c_app = cloud_app.get(share_record.app_id, None)
                if not c_app:
                    c_app = market_app_service.get_market_app_model(session=session, market=mkt,
                                                                    app_id=share_record.app_id, extend=True)
                    cloud_app[share_record.app_id] = c_app
                store_name = c_app.market_name
                app_model_name = c_app.app_name
                share_record.share_app_model_name = app_model_name
                share_record.share_store_name = store_name
                # share_record.save()
            except ServiceHandleException:
                app_model_id = share_record.app_id
        data.append({
            "app_model_id": app_model_id,
            "app_model_name": app_model_name,
            "version": share_record.share_version,
            "version_alias": share_record.share_version_alias,
            "scope": scope,
            "create_time": share_record.create_time,
            "upgrade_time": upgrade_time,
            "step": share_record.step,
            "is_success": share_record.is_success,
            "status": share_record.status,
            "scope_target": {
                "store_name": store_name,
                "store_id": store_id,
            },
            "record_id": share_record.ID,
            "app_version_info": share_record.share_app_version_info,
        })
    result = general_message(200, "success", "获取成功", bean={'total': total}, list=jsonable_encoder(data))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/groups/{group_id}/share/record", response_model=Response, name="应用发布到组件库")
async def app_share(request: Request,
                    team_name: Optional[str] = None,
                    group_id: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    team=Depends(deps.get_current_team)) -> Any:
    """
    生成分享订单，会验证是否能够分享
    ---
    parameter:
        - name: team_name
          description: 团队名
          required: true
          type: string
          paramType: path
        - name: group_id
          description: 应用id
          required: true
          type: string
          paramType: path
    """
    data = await request.json()
    scope = data.get("scope")
    market_name = None
    if scope == "goodrain":
        target = data.get("target")
        market_name = target.get("store_id")
        if market_name is None:
            result = general_message(400, "fail", "参数不全")
            return JSONResponse(result, status_code=result.get("code", 200))
    try:
        if group_id == "-1":
            code = 400
            result = general_message(400, "group id error", "未分组应用不可分享")
            return JSONResponse(result, status_code=code)
        team_id = team.tenant_id
        region = team_region_repo.get_region_by_tenant_id(session, team_id)
        if not region:
            return general_message(400, "not found region", "数据中心不存在")
        response_region = region.region_name

        group_count = application_repo.get_group_count_by_team_id_and_group_id(session=session, team_id=team_id,
                                                                               group_id=group_id)
        if group_count == 0:
            code = 202
            result = general_message(code, "group is not yours!", "当前组已删除或您无权限查看!", bean={})
            return JSONResponse(result, status_code=200)
        # 判断是否满足分享条件
        data = share_service.check_service_source(session=session,
                                                  team=team, team_name=team_name, group_id=group_id,
                                                  region_name=response_region)
        if data and data["code"] == 400:
            return JSONResponse(data, status_code=data["code"])
        fields_dict = {
            "group_share_id": make_uuid(),
            "group_id": group_id,
            "team_name": team_name,
            "is_success": False,
            "step": 1,
            "share_app_market_name": market_name,
            "scope": scope,
            "create_time": datetime.datetime.now(),
            "update_time": datetime.datetime.now(),
        }
        service_share_record = share_service.create_service_share_record(**fields_dict, session=session)
        result = general_message(200, "create success", "创建成功", bean=jsonable_encoder(service_share_record))
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
        return JSONResponse(result, status_code=500)


@router.get("/teams/{team_name}/groups/{group_id}/apps", response_model=Response, name="查询当前应用下的应用模版列表及可升级性")
async def get_app_model(group_id: Optional[str] = None, session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    response_region = region.region_name
    group_id = int(group_id)
    group = application_service.get_group_service(session=session, tenant_id=team.tenant_id,
                                                  response_region=response_region, group_id=group_id)
    if not group:
        return JSONResponse(general_message(msg="Group does not exist", msg_show="应用不存在", code=400), status_code=400)
    apps = []
    try:
        apps = market_app_service.get_market_apps_in_app(session=session, region_name=response_region, tenant=team,
                                                         app_id=group.ID)
    except ServiceHandleException as e:
        if e.status_code != 404:
            raise e
    return JSONResponse(general_message(200, "success", "创建成功", list=apps), status_code=200)


@router.get("/teams/{team_name}/groups/{group_id}/upgrade-records", response_model=Response, name="查询升级记录集合")
async def get_app_model(request: Request,
                        team_name: Optional[str] = None,
                        group_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    region_name = region.region_name
    page = parse_argument(request, 'page', value_type=int, default=1)
    page_size = parse_argument(request, 'page_size', value_type=int, default=10)
    records, total = upgrade_service.list_records(session=session, tenant_name=team_name, region_name=region_name,
                                                  app_id=group_id,
                                                  record_type=ApplicationUpgradeRecordType.UPGRADE.value, page=page,
                                                  page_size=page_size)
    return MessageResponse(msg="success", bean={"total": total}, list=records)


@router.post("/teams/{team_name}/groups/{group_id}/upgrade-records", response_model=Response, name="升级应用模型")
async def upgrade_app_model(request: Request,
                            group_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user),
                            team=Depends(deps.get_current_team)) -> Any:
    app = application_repo.get_group_by_id(session, group_id)
    upgrade_group_id = await parse_item(request, 'upgrade_group_id', required=True)
    try:
        record = upgrade_service.create_upgrade_record(session, user.enterprise_id, team, app, upgrade_group_id)
    except ErrLastRecordUnfinished as e:
        return JSONResponse(
            general_message(msg=e.msg, msg_show=e.msg_show, code=e.status_code), status_code=e.status_code)
    return MessageResponse(msg="success", bean=record)


@router.get("/teams/{team_name}/groups/{group_id}/last-upgrade-record", response_model=Response, name="查询上一次升级记录")
async def get_app_ver(request: Request,
                      group_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      team=Depends(deps.get_current_team)) -> Any:
    app = application_repo.get_group_by_id(session, group_id)
    upgrade_group_id = parse_argument(request, "upgrade_group_id")
    record_type = parse_argument(request, "record_type")
    record = upgrade_service.get_latest_upgrade_record(session=session, tenant=team, app=app,
                                                       upgrade_group_id=upgrade_group_id, record_type=record_type)
    return MessageResponse(msg="success", bean=record)


@router.get("/teams/{team_name}/groups/{group_id}/configgroups", response_model=Response, name="查询应用配置")
async def get_config_groups(request: Request,
                            page: int = Query(default=1, ge=1, le=9999),
                            page_size: int = Query(default=10, ge=1, le=500),
                            group_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    # try:
    #     page = int(request.query_params.get("page", 1))
    # except ValueError:
    #     page = 1
    # try:
    #     page_size = int(request.query_params.get("page_size", 10))
    # except ValueError:
    #     page_size = 10
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    query = request.query_params.get("query", None)
    acg, total = app_config_group_service.list_config_groups(session=session, region_name=region_name, app_id=group_id,
                                                             page=page, page_size=page_size, query=query)
    return JSONResponse(
        general_message(msg="success", msg_show="成功", list=jsonable_encoder(acg), total=total, code=200),
        status_code=200)


@router.post("/teams/{team_name}/groups/{group_id}/configgroups", response_model=Response, name="修改应用配置")
async def add_config_group(request: Request,
                           team_name: Optional[str] = None,
                           group_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    params = await request.json()
    try:
        service_ids = params["service_ids"]
    except:
        service_ids = []
    check_services(session, group_id, service_ids)
    acg = app_config_group_service.create_config_group(session=session, app_id=group_id,
                                                       config_group_name=params["config_group_name"],
                                                       config_items=params["config_items"],
                                                       deploy_type=params["deploy_type"], enable=params["enable"],
                                                       service_ids=service_ids,
                                                       region_name=params["region_name"], team_name=team_name)
    return JSONResponse(general_data(bean=jsonable_encoder(acg)), status_code=200)


@router.get("/teams/{team_name}/groups/{group_id}/configgroups/{name}", response_model=Response, name="获取应用配置组信息")
async def get_config_group(group_id: Optional[str] = None,
                           name: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    acg = app_config_group_service.get_config_group(session=session, region_name=region_name, app_id=group_id,
                                                    config_group_name=name)
    return JSONResponse(general_data(bean=jsonable_encoder(acg)), status_code=200)


@router.put("/teams/{team_name}/groups/{group_id}/configgroups/{name}", response_model=Response, name="修改应用配置组信息")
async def modify_config_group(request: Request,
                              team_name: Optional[str] = None,
                              group_id: Optional[str] = None,
                              name: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    params = await request.json()
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    check_services(session, group_id, params["service_ids"])
    acg = app_config_group_service.update_config_group(session=session, region_name=region_name, app_id=group_id,
                                                       config_group_name=name, config_items=params["config_items"],
                                                       enable=params["enable"], service_ids=params["service_ids"],
                                                       team_name=team_name)
    return JSONResponse(general_data(bean=jsonable_encoder(acg)), status_code=200)


@router.delete("/teams/{team_name}/groups/{group_id}/configgroups/{name}", response_model=Response, name="删除应用配置组")
async def delete_config_group(team_name: Optional[str] = None,
                              group_id: Optional[str] = None,
                              name: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    acg = app_config_group_service.delete_config_group(session=session, region_name=region_name, team_name=team_name,
                                                       app_id=group_id, config_group_name=name)
    return JSONResponse(general_data(bean=acg), status_code=200)


@router.put("/teams/{team_name}/groups/{app_id}/governancemode", response_model=Response, name="切换治理模式")
async def app_governance_mode(request: Request,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    governance_mode = await parse_item(request, "governance_mode", required=True)
    if governance_mode not in GovernanceModeEnum.names():
        raise AbortRequest("governance_mode not in ({})".format(GovernanceModeEnum.names()))

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    region_name = region.region_name
    application_service.update_governance_mode(session, team, region_name, app_id, governance_mode)
    result = general_message(200, "success", "更新成功", bean={"governance_mode": governance_mode})
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/groups/{app_id}/governancemode/check", response_model=Response, name="切换治理模式")
async def app_governance_mode(request: Request,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    governance_mode = request.query_params.get("governance_mode", "")
    if governance_mode not in GovernanceModeEnum.names():
        raise AbortRequest("governance_mode not in ({})".format(GovernanceModeEnum.names()))

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    region_name = region.region_name
    try:
        application_service.check_governance_mode(session, team, region_name, app_id, governance_mode)
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
    result = general_message(200, "success", "更新成功", bean={"governance_mode": governance_mode})
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/groups/{app_id}/k8sservices", response_model=Response, name="查询k8s信息")
async def app_governance_mode(app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    res = application_service.list_kubernetes_services(session, team.tenant_id, region_name, app_id)
    result = general_message(200, "success", "查询成功", list=res)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/groups/{app_id}/k8sservices", response_model=Response, name="设置k8s信息")
async def set_governance_mode(request: Request,
                              app_id: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    k8s_services = await request.json()
    # data validation
    for k8s_service in k8s_services:
        if not k8s_service.get("service_id"):
            raise AbortRequest("the field 'service_id' is required")
        if not k8s_service.get("port"):
            raise AbortRequest("the field 'port' is required")
        if not k8s_service.get("port_alias"):
            raise AbortRequest("the field 'port_alias' is required")

    app = application_repo.get_by_primary_key(session=session, primary_key=app_id)

    application_service.update_kubernetes_services(session, team, region_name, app, k8s_services)

    result = general_message(200, "success", "更新成功", list=k8s_services)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/groups/{app_id}/helmapp-components", response_model=Response, name="获取服务实例")
async def get_helm_app_components(app_id: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  user=Depends(deps.get_current_user),
                                  team=Depends(deps.get_current_team)) -> Any:
    app = application_repo.get_group_by_id(session, app_id)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    components, err = helm_app_service.list_components(session, team, region_name, user, app)
    return JSONResponse(general_message(err.get("code", 200), err.get("msg", "success"), "查询成功", list=components),
                        status_code=200)


@router.get("/teams/{team_name}/groups/{app_id}/releases", response_model=Response, name="获取应用升级记录")
async def get_app_releases(team_name: Optional[str] = None,
                           app_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session),
                           team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    releases = application_service.list_releases(session, region_name, team_name, app_id)
    return JSONResponse(general_message(200, "success", "查询成功", list=releases), status_code=200)


@router.get("/teams/{team_name}/groups/{group_id}/get_check_uuid", response_model=Response, name="获取应用检测uuid")
async def get_check_uuid(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
) -> Any:
    compose_id = request.query_params.get("compose_id", None)
    if not compose_id:
        return JSONResponse(general_message(400, "params error", "参数错误，请求参数应该包含compose ID"), status_code=400)
    group_compose = compose_service.get_group_compose_by_compose_id(session, compose_id)
    if group_compose:
        result = general_message(200, "success", "获取成功", bean={"check_uuid": group_compose.check_uuid})
    else:
        result = general_message(404, "success", "compose不存在", bean={"check_uuid": ""})
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/groups/{group_id}/check", response_model=Response, name="检测任务发送")
async def send_check_task(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    compose_id = data.get("compose_id", None)
    if not compose_id:
        return JSONResponse(general_message(400, "params error", "需要检测的compose ID "), status_code=400)

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    response_region = region.region_name
    code, msg, compose_bean = compose_service.check_compose(session, response_region, team, compose_id)
    if code != 200:
        return JSONResponse(general_message(code, "check compose error", msg))
    result = general_message(code, "compose check task send success", "检测任务发送成功", bean=compose_bean)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/groups/{group_id}/check", response_model=Response, name="获取compose文件检测信息")
async def get_compose_check_info(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team),
        user: Users = Depends(deps.get_current_user)) -> Any:
    sid = None
    try:
        check_uuid = request.query_params.get("check_uuid", None)
        compose_id = request.query_params.get("compose_id", None)
        if not check_uuid:
            return JSONResponse(general_message(400, "params error", "参数错误，请求参数应该包含请求的ID"), status_code=400)
        if not compose_id:
            return JSONResponse(general_message(400, "params error", "参数错误，请求参数应该包含compose ID"), status_code=400)

        region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name

        group_compose = compose_service.get_group_compose_by_compose_id(session, compose_id)
        code, msg, data = component_check_service.get_service_check_info(session, team, response_region, check_uuid)
        logger.debug("start save compose info ! {0}".format(group_compose.create_status))
        save_code, save_msg, service_list = compose_service.save_compose_services(session,
                                                                                  team, user,
                                                                                  response_region, group_compose,
                                                                                  data)
        if save_code != 200:
            data["check_status"] = "failure"
            save_error = {
                "error_type": "check info save error",
                "solve_advice": "修改相关信息后重新尝试",
                "error_info": "{}".format(save_msg)
            }
            if data["error_infos"]:
                data["error_infos"].append(save_error)
            else:
                data["error_infos"] = [save_error]
        compose_check_brief = compose_service.wrap_compose_check_info(data)
        result = general_message(200, "success", "请求成功", bean=compose_check_brief,
                                 list=[jsonable_encoder(s) for s in service_list])
    except ResourceNotEnoughException as re:
        raise re
    except AccountOverdueException as re:
        logger.exception(re)
        return JSONResponse(general_message(10410, "resource is not enough", "失败"), status_code=412)
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/groups/{group_id}/delete", response_model=Response, name="放弃compose创建应用")
async def delete_compose_create(
        request: Request,
        group_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    compose_id = data.get("compose_id", None)
    try:
        group_id = int(group_id)
    except ValueError:
        raise ServiceHandleException(msg="group id is invalid", msg_show="参数不合法")
    if group_id:
        if group_id < 1:
            return JSONResponse(general_message(400, "params error", "所在组参数错误 "), status_code=400)
    else:
        return JSONResponse(general_message(400, "params error", "请指明需要删除的组标识 "), status_code=400)
    if not compose_id:
        return JSONResponse(general_message(400, "params error", "请指明需要删除的compose ID "), status_code=400)
    compose_service.give_up_compose_create(session, team, group_id, compose_id)
    result = general_message(200, "compose delete success", "删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/compose/{compose_id}/content", response_model=Response, name="获取compose文件内容")
async def get_compose_info(
        compose_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    group_compose = compose_repo.get_group_compose_by_compose_id(session, compose_id)
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(group_compose))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/compose/{compose_id}/services", response_model=Response, name="获取compose组下的组件")
async def get_compose_services(
        compose_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    services = compose_service.get_compose_services(session, compose_id)
    s_list = [jsonable_encoder(s) for s in services]
    result = general_message(200, "success", "查询成功", list=s_list)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/groups/{group_id}/install", response_model=Response, name="安装应用市场app")
async def install_market_app(
        request: Request,
        group_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    data = await request.json()
    overrides = data.get("overrides")
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    application_service.install_app(session, team, region_name, group_id, overrides)
    result = general_message(200, "success", "安装成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/groups/{group_id}/pods/{pod_name}", response_model=Response, name="查询实例信息")
async def get_pod_view(
        pod_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    pod = application_service.get_pod(session, team, region_name, pod_name)
    result = general_message(200, "success", "查询成功", bean=pod)
    return JSONResponse(result, status_code=200)
