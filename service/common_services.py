from loguru import logger

from clients.remote_build_client import remote_build_client
from database.session import SessionClass


class CommonServices:
    def get_current_region_used_resource(self, session: SessionClass, env, region_name):
        data = {"tenant_name": [env.tenant_name]}
        try:
            res = remote_build_client.get_region_tenants_resources(session, region_name, data, env.enterprise_id)
            d_list = res["list"]
            if d_list:
                resource = d_list[0]
                return resource
        except Exception as e:
            logger.exception(e)
            return None


common_services = CommonServices()
