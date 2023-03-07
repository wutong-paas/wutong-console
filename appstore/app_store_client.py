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
