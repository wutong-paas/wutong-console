import os
import openapi_client as store_client
from openapi_client.configuration import Configuration as storeConfiguration


def get_market_client(access_key, host=None):
    configuration = storeConfiguration()
    configuration.client_side_validation = False
    configuration.host = host if host else os.environ.get('APP_CLOUD_API', 'http://api.goodrain.com:80')
    if access_key:
        configuration.api_key['Authorization'] = access_key
    return store_client.MarketOpenapiApi(store_client.ApiClient(configuration))


class AppStoreClient(object):

    def get_app(self, store, app_id):
        store_client = get_market_client(store.access_key, store.url)
        data = store_client.get_user_app_detail(app_id=app_id, market_domain=store.domain, _return_http_data_only=True)
        return data

    def get_app_version(self, store, app_id, version, for_install=False, get_template=False):
        store_client = get_market_client(store.access_key, store.url)
        data = store_client.get_user_app_version_detail(
            app_id=app_id, version=version, market_domain=store.domain, for_install=for_install, get_template=get_template)
        return data


app_store_client = AppStoreClient()
