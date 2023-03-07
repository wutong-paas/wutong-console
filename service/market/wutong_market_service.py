from core.utils.crypt import make_uuid
from database.session import SessionClass
from models.component.models import TeamApplication
from models.market.models import AppMarket
from repository.market.wutong_market_repo import wutong_market_repo


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


def get_store_list(session: SessionClass):
    store_list = wutong_market_repo.list_by_model(session=session, query_model=AppMarket)
    if store_list:
        result = []
        for store in store_list:
            result.append({"store_id": store.store_id, "store_name": store.name, "market_id": store.ID})
        return result
    else:
        return []
