from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from core import deps
from core.utils.reqparse import parse_argument, parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.bcode import ErrLastRecordUnfinished
from models.application.models import ApplicationUpgradeRecordType
from repository.application.app_upgrade_repo import upgrade_repo
from repository.application.application_repo import application_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.market_app_service import market_app_service
from service.region_service import region_services
from service.upgrade_service import upgrade_service
from repository.region.region_info_repo import region_repo

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records", response_model=Response,
            name="查询升级记录集合")
async def get_app_model(request: Request,
                        group_id: Optional[str] = None,
                        env=Depends(deps.get_current_team_env),
                        session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    查询升级记录集合
    """

    region_name = env.region_code
    page = parse_argument(request, 'page', value_type=int, default=1)
    page_size = parse_argument(request, 'page_size', value_type=int, default=10)
    records, total = upgrade_service.list_records(session=session, tenant_env=env, region_name=region_name,
                                                  app_id=group_id,
                                                  record_type=ApplicationUpgradeRecordType.UPGRADE.value, page=page,
                                                  page_size=page_size)
    return JSONResponse(
        general_message(code=200, msg_show="查询成功", msg="success", bean={"total": total}, list=records), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records", response_model=Response,
             name="升级应用模型")
async def upgrade_app_model(
        request: Request,
        group_id: Optional[str] = None,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    app = application_repo.get_group_by_id(session, group_id)
    upgrade_group_id = await parse_item(request, 'upgrade_group_id', required=True)
    try:
        record = upgrade_service.create_upgrade_record(session, env, app, upgrade_group_id)
    except ErrLastRecordUnfinished as e:
        return JSONResponse(
            general_message(msg=e.msg, msg_show=e.msg_show, code=e.status_code), status_code=e.status_code)
    return JSONResponse(
        general_message(code=200, msg_show="升级成功", msg="success", bean=record), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/last-upgrade-record", response_model=Response,
            name="查询上一次升级记录")
async def get_app_ver(request: Request,
                      group_id: Optional[str] = None,
                      env=Depends(deps.get_current_team_env),
                      session: SessionClass = Depends(deps.get_session)) -> Any:
    app = application_repo.get_group_by_id(session, group_id)
    upgrade_group_id = parse_argument(request, "upgrade_group_id")
    record_type = parse_argument(request, "record_type")
    record = upgrade_service.get_latest_upgrade_record(session=session, tenant_env=env, app=app,
                                                       upgrade_group_id=upgrade_group_id, record_type=record_type)
    return JSONResponse(
        general_message(code=200, msg_show="查询成功", msg="success",
                        bean=record), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-info", response_model=Response,
            name="查询某云市应用下组件的更新信息")
async def get_cloud_upgrade(request: Request,
                            group_id: Optional[str] = None,
                            env=Depends(deps.get_current_team_env),
                            session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user)) -> Any:
    upgrade_group_id = parse_argument(
        request, 'upgrade_group_id', default=None, value_type=int, error='upgrade_group_id is a required parameter')
    version = parse_argument(request, 'version', value_type=str, required=True, error='version is a required parameter')

    region = region_repo.get_region_by_region_name(session, env.region_code)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    application = application_repo.get_by_primary_key(session=session, primary_key=group_id)
    changes = upgrade_service.get_property_changes(session, env, region, user, application,
                                                   upgrade_group_id, version)
    return JSONResponse(
        general_message(code=200, msg_show="查询成功", msg="success", list=changes), status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/apps/{upgrade_group_id}", response_model=Response,
            name="查询某个升级应用的详情")
async def get_app_upgrade_info(request: Request,
                               env=Depends(deps.get_current_team_env),
                               session: SessionClass = Depends(deps.get_session)) -> Any:
    record_id = parse_argument(
        request, 'record_id', value_type=str, required=True, error='record_id is a required parameter')
    record = upgrade_repo.get_by_record_id(session, record_id)
    # get app model upgrade versions
    versions = market_app_service.list_app_upgradeable_versions(session, record)
    return JSONResponse(
        general_message(code=200, msg_show="查询成功", msg="success",
                        bean={'record': record.to_dict(), 'versions': versions}), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records/{record_id}/upgrade",
             response_model=Response,
             name="升级组件")
async def upgrade_component(
        request: Request,
        group_id: Optional[str] = None,
        record_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
        user=Depends(deps.get_current_user)
) -> Any:
    version = await parse_item(request, "version", required=True)
    # It is not yet possible to upgrade based on services, which is user-specified attribute changes
    components = await parse_item(request, "services", default=[])
    component_keys = [cpt["service"]["service_key"] for cpt in components]

    region = region_repo.get_region_by_region_name(session, env.region_code)
    application = application_repo.get_by_primary_key(session=session, primary_key=group_id)
    app_upgrade_record = upgrade_repo.get_by_record_id(session, record_id)
    record, _ = upgrade_service.upgrade(
        session,
        env,
        region,
        user,
        application,
        version,
        app_upgrade_record,
        component_keys,
    )
    return JSONResponse(general_message("0", msg="success", msg_show="升级成功", bean=jsonable_encoder(record)),
                        status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records/{record_id}", response_model=Response,
            name="查询某一条升级记录")
async def get_upgrade_log(
        record_id: Optional[str] = None,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)) -> Any:

    record = upgrade_service.get_app_upgrade_record(session, env, env.region_code, record_id)
    return JSONResponse(general_message("0", msg="success", msg_show="查询成功", bean=jsonable_encoder(record)),
                        status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records/{record_id}/deploy",
             response_model=Response,
             name="重试组件升级")
async def retry_upgrade(
        record_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
        user=Depends(deps.get_current_user)) -> Any:

    app_upgrade_record = upgrade_repo.get_by_record_id(session, record_id)
    upgrade_service.deploy(session, env, env.region_code, user, app_upgrade_record)
    return JSONResponse(general_message("0", msg="success", msg_show="部署成功"), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records/{record_id}/rollback",
             response_model=Response,
             name="回滚某一条升级记录")
async def rollback_upgrade(
        group_id: Optional[str] = None,
        record_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env),
        user=Depends(deps.get_current_user)) -> Any:

    region = region_repo.get_region_by_region_name(session, env.region_code)
    app_upgrade_record = upgrade_repo.get_by_record_id(session, record_id)
    application = application_repo.get_by_primary_key(session=session, primary_key=group_id)
    record, _ = upgrade_service.restore(session, env, region, user, application, app_upgrade_record)
    return JSONResponse(general_message("0", msg="success", msg_show="回滚成功", bean=jsonable_encoder(record)),
                        status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/groups/{group_id}/upgrade-records/{record_id}/rollback-records",
            response_model=Response,
            name="查看回滚记录")
async def get_rollback_upgrade(
        record_id: Optional[str] = None,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    app_upgrade_record = upgrade_repo.get_by_record_id(session, record_id)
    records = upgrade_service.list_rollback_record(session, app_upgrade_record)
    return JSONResponse(general_message("0", msg="success", msg_show="获取成功", list=records), status_code=200)
