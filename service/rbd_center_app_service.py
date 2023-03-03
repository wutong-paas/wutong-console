import json

from exceptions.main import RecordNotFound, RbdAppNotFound
from repository.application.app_repository import app_repo


class RbdCenterAppService(object):
    def get_version_app(self, version, service_source):
        """
        Get the specified version of the rainbond center(market) application
        raise: RecordNotFound
        raise: RbdAppNotFound
        """
        rain_app = app_repo.get_enterpirse_app_by_key_and_version(service_source.group_key, version)
        if rain_app is None:
            raise RecordNotFound("Group key: {0}; version: {1}; \
                RainbondCenterApp not found.".format(service_source.group_key, version))

        apps_template = json.loads(rain_app.app_template)
        apps = apps_template.get("apps")

        def func(x):
            result = x.get("service_share_uuid", None) == service_source.service_share_uuid\
                or x.get("service_key", None) == service_source.service_share_uuid
            return result

        app = next(iter([x for x in apps if func(x)]), None)
        if app is None:
            fmt = "Group key: {0}; version: {1}; service_share_uuid: {2}; Rainbond app not found."
            raise RbdAppNotFound(fmt.format(service_source.group_key, version, service_source.service_share_uuid))

        return app


rbd_center_app_service = RbdCenterAppService()
