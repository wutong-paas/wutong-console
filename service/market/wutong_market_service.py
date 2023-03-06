import json

from clients.wutong_market_client import wutong_market_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import AbortRequest
from models.component.models import TeamApplication
from models.market.models import AppMarket, CenterAppVersion
from models.teams import TeamEnvInfo, RegionConfig
from repository.application.application_repo import application_repo
from repository.market.center_app_version_repo import center_app_version_repo
from repository.market.wutong_market_repo import wutong_market_repo
from repository.region.region_info_repo import region_repo
from repository.teams.env_repo import env_repo
from schemas.market import MarketCreateParam, MarketAppInstallParam
from service.market_app.app_upgrade import AppUpgrade
from service.tenant_env_service import env_services


def get_wutong_markets(session: SessionClass, user: str):

    # 查询用户团队权限下应用店铺
    markets = wutong_market_repo.get_market_list(session=session)
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


def bind_wutong_market(session: SessionClass, params: MarketCreateParam):
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

    # 添加校验
    check_result = wutong_market_client.check_store(session=session, url=params.url, access_key=params.access_key,
                                                    access_secret=params.access_secret)
    if not check_result:
        raise AbortRequest("params error", "店铺信息校验失败,请检查参数", status_code=400, error_code=400)

    # 截取服务地址
    server_address = store_url.split("/wutong-open-market-admin/")[0]

    store = wutong_market_repo.get_one_by_model(session=session, query_model=AppMarket(store_id=store_id))
    if store:
        raise AbortRequest("url error", "店铺已绑定", status_code=409, error_code=409)
    wutong_market_repo.base_create(session=session,
                                   add_model=AppMarket(name=params.name, url=server_address, domain=params.url,
                                                       access_key=params.access_key, access_secret=params.access_secret,
                                                       type=params.type,
                                                       store_id=store_id, scope=params.scope))


def update_wutong_market(session: SessionClass, market_id: str, market_name: str):
    wutong_market_repo.update_by_primary_key(session=session, update_model=AppMarket(ID=market_id, name=market_name))


def create_tenant_service_group(session: SessionClass, region_name, tenant_env_id, group_id, app_key,
                                app_version, app_name):
    group_name = '_'.join(["wt", make_uuid()[-4:]])
    params = {
        "tenant_env_id": tenant_env_id,
        "group_name": group_name,
        "group_alias": app_name,
        "group_key": app_key,
        "group_version": app_version,
        "region_name": region_name,
        "service_group_id": 0 if group_id == -1 else group_id
    }
    add_model: TeamApplication = TeamApplication(**params)
    session.add(add_model)
    session.flush()

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

    wutong_market_client.push_local_app(session=session, param_body=body, market=market, store_id=store_id)


def get_store_list(session: SessionClass):
    store_list = wutong_market_repo.list_by_model(session=session, query_model=AppMarket)
    if store_list:
        result = []
        for store in store_list:
            result.append({"store_id": store.store_id, "store_name": store.name, "market_id": store.ID})
        return result
    else:
        return []
