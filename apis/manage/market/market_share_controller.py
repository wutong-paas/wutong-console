from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select, func, not_, update

from core import deps
from core.enum.component_enum import is_singleton
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.application.models import ServiceShareRecord, ServiceShareRecordEvent
from models.application.plugin import PluginShareRecordEvent
from models.market.models import CenterApp, CenterAppVersion
from repository.component.service_share_repo import component_share_repo, component_share_event_repo
from repository.market.center_repo import center_app_repo, center_app_version_repo
from repository.plugin.plugin_share_repo import plugin_share_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.market import MarketShareUpdateParam, MarketAppShareInfoCreateParam
from schemas.response import Response
from service.app_actions.app_log import event_service
from service.market_app_service import market_app_service
from service.share_services import share_service

router = APIRouter()


@router.get("/teams/{team_name}/groups/{group_id}/share/record/{record_id}", response_model=Response, name="查询分享记录详情")
async def get_record_detail(group_id: Optional[str] = None,
                            record_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    data = None
    share_record = component_share_repo.get_by_primary_key(session=session, primary_key=record_id)
    if share_record:
        app_model_name = None
        app_model_id = None
        version = None
        version_alias = None
        upgrade_time = None
        store_name = None
        store_version = "1.0"
        store_id = share_record.share_app_market_name
        scope = share_record.scope
        if store_id:
            extend, market = market_app_service.get_app_market(session=session,
                                                               enterprise_id=team.enterprise_id,
                                                               market_name=share_record.share_app_market_name,
                                                               extend="true", raise_exception=True)
            if market:
                store_name = market.name
                store_version = extend.get("version", store_version)
        app = center_app_repo.get_one_by_model(session=session, query_model=CenterApp(app_id=share_record.app_id,
                                                                                      enterprise_id=team.enterprise_id))
        if app:
            app_model_id = share_record.app_id
            app_model_name = app.app_name
        app_version = center_app_version_repo.get_one_by_model(session=session,
                                                               query_model=CenterAppVersion(record_id=share_record.ID))

        if app_version:
            version = app_version.version
            version_alias = app_version.version_alias
            upgrade_time = app_version.upgrade_time
        data = {
            "app_model_id": app_model_id,
            "app_model_name": app_model_name,
            "version": version,
            "version_alias": version_alias,
            "scope": scope,
            "create_time": share_record.create_time,
            "upgrade_time": upgrade_time,
            "step": share_record.step,
            "is_success": share_record.is_success,
            "status": share_record.status,
            "scope_target": {
                "store_name": store_name,
                "store_id": store_id,
                "store_version": store_version
            },
            "record_id": share_record.ID,
        }
    return JSONResponse(general_message(200, "success", None, bean=jsonable_encoder(data)), status_code=200)


@router.put("/teams/{team_name}/groups/{group_id}/share/record/{record_id}", response_model=Response, name="更新分享记录")
async def update_record(session: SessionClass = Depends(deps.get_session),
                        params: Optional[MarketShareUpdateParam] = MarketShareUpdateParam(),
                        group_id: Optional[str] = None,
                        record_id: Optional[str] = None) -> Any:
    status = params.status
    share_record = component_share_repo.get_by_primary_key(session=session, primary_key=record_id)
    if share_record and status:
        share_record.status = status
        return general_message(200, "success", None, bean=jsonable_encoder(share_record))


@router.delete("/teams/{team_name}/groups/{group_id}/share/record/{record_id}", response_model=Response,
               name="删除分享记录")
async def delete_record(session: SessionClass = Depends(deps.get_session),
                        group_id: Optional[str] = None,
                        record_id: Optional[str] = None) -> Any:
    session.execute(update(ServiceShareRecord).where(
        ServiceShareRecord.group_id == group_id,
        ServiceShareRecord.ID == record_id).values({"status": 3}))
    return JSONResponse(general_message(200, "success", None), status_code=200)


@router.get("/teams/{team_name}/share/{share_id}/info", response_model=Response, name="查询分享的所有应用信息和插件信息")
async def get_share_info(scope: Optional[str] = None,
                         share_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    data = dict()
    share_record = component_share_repo.get_by_primary_key(session=session, primary_key=share_id)

    if not share_record:
        return JSONResponse(general_message(404, "share record not found", "分享流程不存在，请退出重试"), status_code=404)
    if share_record.is_success or share_record.step >= 3:
        return JSONResponse(general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享"), status_code=400)
    if not scope:
        scope = share_record.scope
    service_info_list = share_service.query_share_service_info(session=session, team=team,
                                                               group_id=share_record.group_id,
                                                               scope=scope)
    data["share_service_list"] = service_info_list
    plugins = share_service.get_group_services_used_plugins(group_id=share_record.group_id, session=session)
    data["share_plugin_list"] = plugins
    return JSONResponse(general_message(200, "query success", "获取成功", bean=jsonable_encoder(data)), status_code=200)


@router.post("/teams/{team_name}/share/{share_id}/info", response_model=Response, name="生成分享应用实体，向数据中心发送分享任务")
async def create_share_info(params: Optional[MarketAppShareInfoCreateParam] = None,
                            use_force: Optional[bool] = False,
                            share_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user),
                            team=Depends(deps.get_current_team)) -> Any:
    if not team:
        return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name

    share_record = component_share_repo.get_by_primary_key(session=session, primary_key=share_id)
    if not share_record:
        return JSONResponse(general_message(404, "share record not found", "分享流程不存在，请退出重试"), status_code=404)
    if share_record.is_success or share_record.step >= 3:
        return JSONResponse(general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享"), status_code=400)

    if not params:
        return JSONResponse(general_message(400, "share info can not be empty", "分享信息不能为空"), status_code=400)
    app_version_info = params.app_version_info
    share_app_info = params.share_service_list
    if not app_version_info or not share_app_info:
        return JSONResponse(general_message(400, "share info can not be empty", "分享应用基本信息或应用信息不能为空"), status_code=400)
    if not app_version_info.app_model_id:
        return JSONResponse(general_message(400, "share app model id can not be empty", "分享应用信息不全"), status_code=400)

    if share_app_info:
        for app in share_app_info:
            extend_method = app.get("extend_method", "")
            if is_singleton(extend_method):
                extend_method_map = app.get("extend_method_map")
                if extend_method_map and extend_method_map.get("max_node", 1) > 1:
                    return JSONResponse(general_message(400, "service type do not allow multiple node", "分享应用不支持多实例"),
                                        status_code=400)

    # 继续给app_template_incomplete赋值
    code, msg, bean = share_service.create_share_info(session=session,
                                                      tenant=team,
                                                      region_name=region_name,
                                                      share_record=share_record,
                                                      share_team=team,
                                                      share_user=user,
                                                      share_info=params,
                                                      use_force=use_force)
    return JSONResponse(general_message(code, "create share info", msg, bean=jsonable_encoder(bean)), status_code=code)


@router.get("/teams/{team_name}/groups/{group_id}/shared/apps", response_model=Response, name="分享应用列表")
async def shared_apps(scope: Optional[str] = None,
                      market_id: Optional[str] = None,
                      group_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      team=Depends(deps.get_current_team)) -> Any:
    if not team:
        return JSONResponse(general_message(400, "not found team", "团队不存在"), status_code=400)

    data = share_service.get_last_shared_app_and_app_list(enterprise_id=team.enterprise_id, tenant=team,
                                                          group_id=group_id, scope=scope,
                                                          market_name=market_id, session=session)
    return JSONResponse(general_message(
        200, "get shared apps list complete", None, bean=jsonable_encoder(data["last_shared_app"]),
        list=jsonable_encoder(data["app_model_list"])),
        status_code=200)


@router.get("/teams/{team_name}/share/{share_id}/events", response_model=Response, name="获取分享事件")
async def get_share_event(team_name: Optional[str] = None,
                          share_id: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
        if not share_record:
            result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
            return JSONResponse(result, status_code=404)
        if share_record.is_success or share_record.step >= 3:
            result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
            return JSONResponse(result, status_code=400)
        events = component_share_event_repo.list_by_model(session=session,
                                                          query_model=ServiceShareRecordEvent(record_id=share_id))
        if not events:
            result = general_message(404, "not exist", "分享事件不存在")
            return JSONResponse(result, status_code=404)
        result = {}
        result["event_list"] = list()
        for event in events:
            if event.event_status != "success":
                result["is_compelte"] = False
            service_event_map = event.__dict__
            service_event_map["type"] = "service"
            result["event_list"].append(service_event_map)
        # 查询插件分享事件
        plugin_events = plugin_share_repo.list_by_model(session=session,
                                                        query_model=PluginShareRecordEvent(record_id=share_id))
        for plugin_event in plugin_events:
            if plugin_event.event_status != "success":
                result["is_compelte"] = False
            plugin_event_map = jsonable_encoder(plugin_event)
            plugin_event_map["type"] = "plugin"
            result["event_list"].append(plugin_event_map)
        result = general_message(200, "query success", "获取成功", bean=jsonable_encoder(result))
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
        return JSONResponse(result, status_code=500)


@router.post("/teams/{team_name}/share/{share_id}/events/{event_id}", response_model=Response,
             name="分享应用")
async def share_event(team_name: Optional[str] = None,
                      share_id: Optional[str] = None,
                      event_id: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      user=Depends(deps.get_current_user),
                      team=Depends(deps.get_current_team)) -> Any:
    try:
        share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
        if not share_record:
            result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
            return JSONResponse(result, status_code=404)
        if share_record.is_success or share_record.step >= 3:
            result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
            return JSONResponse(result, status_code=400)
        event = component_share_event_repo.get_by_primary_key(session=session, primary_key=event_id)
        if not event:
            result = general_message(404, "not exist", "分享事件不存在")
            return JSONResponse(result, status_code=404)

        region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        record_event = share_service.sync_event(session, user, response_region, team_name, event)
        bean = jsonable_encoder(record_event) if record_event is not None else None
        result = general_message(200, "sync share event", "分享完成", bean=bean)
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        result = error_message("分享失败")
        return JSONResponse(result, status_code=500)


@router.get("/teams/{team_name}/share/{share_id}/events/{event_id}", response_model=Response,
            name="获取分享进度")
async def get_share_info(team_name: Optional[str] = None,
                         share_id: Optional[str] = None,
                         event_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    try:
        region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
        if not share_record:
            result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
            return JSONResponse(result, status_code=404)
        if share_record.is_success or share_record.step >= 3:
            result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
            return JSONResponse(result, status_code=400)
        event = component_share_event_repo.get_by_primary_key(session=session, primary_key=event_id)
        if not event:
            result = general_message(404, "not exist", "分享事件不存在")
            return JSONResponse(result, status_code=404)
        if event.event_status == "success":
            result = general_message(200, "get sync share event result", "查询成功", bean=jsonable_encoder(event))
            return JSONResponse(result, status_code=200)
        bean = share_service.get_sync_event_result(session, response_region, team_name, event)
        result = general_message(200, "get sync share event result", "查询成功", bean=jsonable_encoder(bean))
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        result = error_message("获取失败")
        return JSONResponse(result, status_code=500)


@router.delete("/teams/{team_name}/share/{share_id}/giveup", response_model=Response,
               name="放弃应用分享操作，放弃时删除分享记录")
async def delete_share_info(team_name: Optional[str] = None,
                            share_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    放弃应用分享操作，放弃时删除分享记录
    ---
    parameter:
        - name: team_name
          description: 团队名
          required: true
          type: string
          paramType: path
        - name: share_id
          description: 分享订单ID
          required: true
          type: string
          paramType: path
    """
    try:
        share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
        if not share_record:
            result = general_message(404, "share record not found", "分享流程不存在，不能放弃")
            return JSONResponse(result, status_code=404)
        if share_record.is_success or share_record.step >= 3:
            result = general_message(400, "share record is complete", "分享流程已经完成，无法放弃")
            return JSONResponse(result, status_code=400)
        app = share_service.get_app_by_key(session=session, key=share_record.group_share_id)
        if app and not app.is_complete:
            share_service.delete_app(session=session, key=share_record.group_share_id)
        share_service.delete_record(session=session, ID=share_id, team_name=team_name)
        result = general_message(200, "delete success", "放弃成功")
        return JSONResponse(result, status_code=200)
    except ServiceHandleException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        result = error_message("放弃失败")
        return JSONResponse(result, status_code=500)


@router.post("/teams/{team_name}/share/{share_id}/complete", response_model=Response,
             name="发布应用")
async def share_app(team_name: Optional[str] = None,
                    share_id: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    user=Depends(deps.get_current_user),
                    team=Depends(deps.get_current_team)) -> Any:
    share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
    if not share_record:
        result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
        return JSONResponse(result, status_code=404)
    if share_record.is_success or share_record.step >= 3:
        result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
        return JSONResponse(result, status_code=400)
    # 验证是否所有同步事件已完成
    count = session.execute(select(func.count(ServiceShareRecordEvent.ID)).where(
        ServiceShareRecordEvent.record_id == share_id,
        not_(ServiceShareRecordEvent.event_status == "success")
    )).first()[0]
    plugin_count = session.execute(select(func.count(PluginShareRecordEvent.ID)).where(
        PluginShareRecordEvent.record_id == share_id,
        not_(PluginShareRecordEvent.event_status == "success")
    )).first()[0]
    if count > 0 or plugin_count > 0:
        result = general_message(415, "share complete can not do", "组件或插件同步未全部完成")
        return JSONResponse(result, status_code=415)
    app_market_url = share_service.complete(session, team, user, share_record)
    result = general_message(200, "share complete", "应用分享完成", bean=jsonable_encoder(share_record),
                             app_market_url=app_market_url)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/events/{event_id}/log", response_model=Response,
            name="获取作用对象的event事件")
async def get_object_log(event_id: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
    获取作用对象的event事件
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: eventId
          description: 事件ID
          required: true
          type: string
          paramType: path
    """
    try:
        if event_id == "":
            result = general_message(200, "error", "event_id is required")
            return JSONResponse(result, status_code=result["code"])
        region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        log_content = event_service.get_event_log(session, team, response_region, event_id)
        result = general_message(200, "success", "查询成功", list=log_content)
    except Exception as e:
        logger.exception(e)
        result = error_message("failed")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/share/{share_id}/events/{event_id}/plugin", response_model=Response,
             name="分享插件")
async def share_plugin(
        team_name: Optional[str] = None,
        share_id: Optional[str] = None,
        event_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
    if not share_record:
        result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
        return JSONResponse(result, status_code=404)
    if share_record.is_success or share_record.step >= 3:
        result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
        return JSONResponse(result, status_code=400)
    events = session.execute(select(PluginShareRecordEvent).where(
        PluginShareRecordEvent.record_id == share_id,
        PluginShareRecordEvent.ID == event_id
    )).scalars().all()
    if not events:
        result = general_message(404, "not exist", "分享事件不存在")
        return JSONResponse(result, status_code=404)

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name

    bean = share_service.sync_service_plugin_event(session, user, response_region, team.tenant_name, share_id,
                                                   events[0])
    if not bean:
        result = general_message(400, "sync share event", "插件不存在无需发布")
    else:
        result = general_message(200, "sync share event", "分享成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/share/{share_id}/events/{event_id}/plugin", response_model=Response,
            name="获取分享插件进度")
async def get_share_plugin(
        team_name: Optional[str] = None,
        share_id: Optional[str] = None,
        event_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    share_record = share_service.get_service_share_record_by_ID(session=session, ID=share_id, team_name=team_name)
    if not share_record:
        result = general_message(404, "share record not found", "分享流程不存在，请退出重试")
        return JSONResponse(result, status_code=404)
    if share_record.is_success or share_record.step >= 3:
        result = general_message(400, "share record is complete", "分享流程已经完成，请重新进行分享")
        return JSONResponse(result, status_code=400)

    plugin_events = session.execute(select(PluginShareRecordEvent).where(
        PluginShareRecordEvent.record_id == share_id,
        PluginShareRecordEvent.ID == event_id
    ).order_by(PluginShareRecordEvent.ID.asc())).scalars().all()
    if not plugin_events:
        result = general_message(404, "not exist", "分享事件不存在")
        return JSONResponse(result, status_code=404)

    if plugin_events[0].event_status == "success":
        result = general_message(200, "get sync share event result", "查询成功", bean=jsonable_encoder(plugin_events[0]))
        return JSONResponse(result, status_code=200)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    bean = share_service.get_sync_plugin_events(session, response_region, team_name, plugin_events[0])
    result = general_message(200, "get sync share event result", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=200)
