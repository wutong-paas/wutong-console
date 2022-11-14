from appstore.app_store_client import get_market_client
from service.region_service import EnterpriseConfigService


class AppStore(object):

    def get_slug_hub_info(self, store=None, app_id=None, enterprise_id=None):
        image_config = {"ftp_host": None, "ftp_port": None, "namespace": None, "ftp_username": None, "ftp_password": None}
        data = None
        if store:
            store_client = get_market_client(store.access_key, store.url)
            data = store_client.get_app_hub_info(app_id=app_id, market_domain=store.domain, _return_http_data_only=True)
            image_config["ftp_host"] = data.hub_url
            image_config["ftp_username"] = data.hub_user
            image_config["ftp_password"] = data.hub_password
            image_config["namespace"] = data.namespace
        if not data:
            data = EnterpriseConfigService(enterprise_id).get_config_by_key("APPSTORE_IMAGE_HUB")
            if data:
                image_config_dict = eval(data.value)
                namespace = (image_config_dict.get("namespace") if image_config_dict.get("namespace") else data.enterprise_id)
                image_config["ftp_host"] = image_config_dict.get("hub_url", None)
                image_config["ftp_username"] = image_config_dict.get("hub_user", None)
                image_config["ftp_password"] = image_config_dict.get("hub_password", None)
                image_config["namespace"] = namespace
        return image_config

    def get_app_hub_info(self, session, store=None, app_id=None, enterprise_id=None):
        image_config = {
            "hub_url": None,
            "hub_user": None,
            "hub_password": None,
            "namespace": None,
        }
        data = None
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
