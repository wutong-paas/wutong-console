import json

from clients.wutong_market_client import wutong_market_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import AbortRequest
from models.component.models import TeamApplication
from models.market.models import AppMarket, CenterAppVersion
from models.teams import TeamInfo, RegionConfig
from models.users.users import Users
from repository.application.application_repo import application_repo
from repository.market.center_app_version_repo import center_app_version_repo
from repository.market.wutong_market_repo import wutong_market_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_repo import team_repo
from schemas.market import MarketCreateParam, MarketAppInstallParam
from service.market_app.app_upgrade import AppUpgrade


def get_wutong_markets(session: SessionClass, enterprise_id: str):
    markets = wutong_market_repo.list_by_model(session=session, query_model=AppMarket(enterprise_id=enterprise_id))
    if not markets:
        return []
    result = []
    for market in markets:
        result.append({
            "ID": market.ID,
            "name": market.name,
            "store_id": market.store_id,
            "url": market.url
        })
    return result


def bind_wutong_market(session: SessionClass, enterprise_id: str, params: MarketCreateParam):
    # 字符串处理
    store_url = params.url

    # 参数截取 /wutong-open-market-admin/

    if store_url.count("/wutong-open-market-admin/") < 1:
        raise AbortRequest("store url error", "url格式错误,未包含云市场网关地址:/wutong-open-market-admin/", status_code=400,
                           error_code=400)
    if store_url.endswith("/"):
        store_url = store_url[:-1]
    store_id = store_url.split("/")[-1]
    if store_url.count("/") < 1 or not store_id:
        raise AbortRequest("store_id not found", "url格式错误,未找到store_id", status_code=400, error_code=400)

    # 截取服务地址
    server_address = store_url.split("/wutong-open-market-admin/")[0]

    store = wutong_market_repo.get_one_by_model(session=session, query_model=AppMarket(store_id=store_id))
    if store:
        raise AbortRequest("url error", "店铺已绑定", status_code=409, error_code=409)
    wutong_market_repo.base_create(session=session,
                                   add_model=AppMarket(name=params.name, url=server_address, domain=params.url,
                                                       access_key=params.access_key, access_secret=params.access_secret,
                                                       enterprise_id=enterprise_id, type=params.type,
                                                       store_id=store_id))


def update_wutong_market(session: SessionClass, enterprise_id: str, market_id: str, market_name: str):
    wutong_market_repo.update_by_primary_key(session=session, update_model=AppMarket(ID=market_id, name=market_name,
                                                                                     enterprise_id=enterprise_id))


def install_cloud_market_app(session: SessionClass, user: Users, enterprise_id: str, market_id: str,
                             params: MarketAppInstallParam):
    # 前置校验
    application = application_repo.get_by_primary_key(session=session, primary_key=params.application_id)
    if not application:
        raise AbortRequest("application not found", "本地应用不存在", status_code=400, error_code=400)
    # 查询云市场应用信息 : 应用ID、应用名称
    market = wutong_market_repo.get_by_primary_key(session=session, primary_key=market_id)
    app_version_detail = wutong_market_client.get_market_app_version_detail(market=market,
                                                                            version_id=params.market_app_version_id)
    # 获取应用模版信息
    app_template = json.loads(app_version_detail.assembly_info)
    # app_template["update_time"] = app_version.update_time

    # 查询团队
    team_info = team_repo.get_one_by_model(session=session, query_model=TeamInfo(tenant_id=application.tenant_id))
    # 查询region
    region = region_repo.get_one_by_model(session=session,
                                          query_model=RegionConfig(region_name=application.region_name))

    # 安装应用
    component_group = create_tenant_service_group(session, application.region_name, application.tenant_id,
                                                  application.ID,
                                                  params.market_app_id, app_version_detail.numbers,
                                                  params.market_app_name)
    app_upgrade = AppUpgrade(
        session,
        enterprise_id,
        team_info,
        region,
        user,
        application,
        app_version_detail.numbers,
        component_group,
        app_template,
        False,
        market.name,
        is_deploy=params.is_deploy)
    app_upgrade.install(session)


def create_tenant_service_group(session: SessionClass, region_name, tenant_id, group_id, app_key,
                                app_version, app_name):
    group_name = '_'.join(["gr", make_uuid()[-4:]])
    params = {
        "tenant_id": tenant_id,
        "group_name": group_name,
        "group_alias": app_name,
        "group_key": app_key,
        "group_version": app_version,
        "region_name": region_name,
        "service_group_id": 0 if group_id == -1 else group_id
    }
    add_model: TeamApplication = TeamApplication(**params)
    session.add(add_model)
    # session.flush()

    return add_model


def push_local_application(session: SessionClass, store_id: str, service_share_record_id: int,
                           service_share_model_name: str):
    # 查询店铺信息
    market = wutong_market_repo.get_one_by_model(session=session, query_model=AppMarket(store_id=store_id))
    if not market:
        raise AbortRequest("market not found", "远程应用市场不存在", status_code=400, error_code=400)
    # 查询应用版本信息
    center_app_version = center_app_version_repo.get_one_by_model(session=session,
                                                                  query_model=CenterAppVersion(
                                                                      record_id=service_share_record_id))
    # 推送
    body = {
        "id": make_uuid(),
        "name": service_share_model_name,
        "version_number": center_app_version.version,
        "assembly_info": center_app_version.app_template
    }

    wutong_market_client.push_local_app(param_body=body, market=market, store_id=store_id)


def get_store_list(session: SessionClass, enterprise_id: str):
    store_list = wutong_market_repo.list_by_model(session=session, query_model=AppMarket(enterprise_id=enterprise_id))
    if store_list:
        result = []
        for store in store_list:
            result.append({"store_id": store.store_id, "store_name": store.name, "market_id": store.ID})
        return result
    else:
        return []
