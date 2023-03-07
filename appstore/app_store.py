

class AppStore(object):

    def get_app_hub_info(self, session, store=None, app_id=None):
        image_config = {
            "hub_url": None,
            "hub_user": None,
            "hub_password": None,
            "namespace": None,
        }
        return image_config


app_store = AppStore()
