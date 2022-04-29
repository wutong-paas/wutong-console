import os
from functools import wraps

from loguru import logger
import openapi_client as store_client
from openapi_client import ApiException
from openapi_client.configuration import Configuration as storeConfiguration
from exceptions.main import ServiceHandleException, StoreNoPermissionsError
from service.region_service import EnterpriseConfigService


def get_market_client(access_key, host=None):
    configuration = storeConfiguration()
    configuration.client_side_validation = False
    configuration.host = host if host else os.environ.get('APP_CLOUD_API', 'http://api.goodrain.com:80')
    if access_key:
        configuration.api_key['Authorization'] = access_key
    return store_client.MarketOpenapiApi(store_client.ApiClient(configuration))


def apiException(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            if e.status == 401:
                raise ServiceHandleException(
                    msg="no store auth token", msg_show="缺少云应用市场token", status_code=401, error_code=10421)
            if e.status == 403:
                raise StoreNoPermissionsError(bean={"name": args[1].name})
            if e.status == 404:
                raise ServiceHandleException(msg=e.body, msg_show="资源不存在", status_code=404)
            if str(e.status)[0] == '4':
                raise ServiceHandleException(msg=e.body, msg_show="获取数据失败，参数错误", status_code=e.status)
            raise ServiceHandleException(msg=e.body, msg_show="请求失败，请检查网络和配置", status_code=400)
        except ValueError as e:
            logger.debug(e)
            raise ServiceHandleException(
                msg="store return data can`t be serializer", msg_show="应用市场返回数据序列化失败，请检查配置或参数是否正确", status_code=400)

    return wrapper


class AppStore(object):

    @apiException
    def get_app_hub_info(self, session, store=None, app_id=None, enterprise_id=None):
        image_config = {
            "hub_url": None,
            "hub_user": None,
            "hub_password": None,
            "namespace": None,
        }
        data = None
        if store:
            store_client = get_market_client(store.access_key, store.url)
            data = store_client.get_app_hub_info(app_id=app_id, market_domain=store.domain, _return_http_data_only=True)
            image_config["hub_url"] = data.hub_url
            image_config["hub_user"] = data.hub_user
            image_config["hub_password"] = data.hub_password
            image_config["namespace"] = data.namespace
        if not data:
            data = EnterpriseConfigService(enterprise_id).get_config_by_key(session, "APPSTORE_IMAGE_HUB")
            if data and data.enable:
                image_config_dict = eval(data.value)
                namespace = (
                    image_config_dict.get("namespace") if image_config_dict.get("namespace") else data.enterprise_id)
                if image_config_dict["hub_url"]:
                    image_config["hub_url"] = image_config_dict.get("hub_url", None)
                    image_config["hub_user"] = image_config_dict.get("hub_user", None)
                    image_config["hub_password"] = image_config_dict.get("hub_password", None)
                    image_config["namespace"] = namespace
        return image_config

    def is_no_multiple_region_hub(self, session, enterprise_id):
        data = EnterpriseConfigService(enterprise_id).get_config_by_key(session, "APPSTORE_IMAGE_HUB")
        if data and data.enable:
            image_config_dict = eval(data.value)
            if image_config_dict["hub_url"]:
                return False
        return True


app_store = AppStore()
