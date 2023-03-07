from appstore.app_store_client import get_market_client


class AppStore(object):

    def get_slug_hub_info(self, store=None, app_id=None):
        image_config = {"ftp_host": None, "ftp_port": None, "namespace": None, "ftp_username": None, "ftp_password": None}
        if store:
            store_client = get_market_client(store.access_key, store.url)
            data = store_client.get_app_hub_info(app_id=app_id, market_domain=store.domain, _return_http_data_only=True)
            image_config["ftp_host"] = data.hub_url
            image_config["ftp_username"] = data.hub_user
            image_config["ftp_password"] = data.hub_password
            image_config["namespace"] = data.namespace
        return image_config

    def get_app_hub_info(self, session, store=None, app_id=None):
        image_config = {
            "hub_url": None,
            "hub_user": None,
            "hub_password": None,
            "namespace": None,
        }
        return image_config


app_store = AppStore()
