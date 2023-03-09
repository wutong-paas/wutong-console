from clients.remote_component_client import remote_component_client
from exceptions.main import ServiceHandleException
from models.component.models import TeamComponentInfo
from repository.base import BaseRepository


class TeamComponentRepository(BaseRepository[TeamComponentInfo]):
    def get_count_by_region(self, session, enterprise_id, region_name):
        try:
            data = remote_component_client.get_all_services_status(session, enterprise_id,
                                                                   region_name,
                                                                   test=True)
            if data:
                service_running_num = len(data["running_services"])
                service_unrunning_num = len(data["unrunning_services"])
                service_abnormal_num = len(data["abnormal_services"])
                service_total_num = service_running_num + service_unrunning_num + service_abnormal_num
                return service_total_num
            else:
                raise ServiceHandleException(msg="get region service error", msg_show="获取集群组件状态异常")
        except (remote_component_client.CallApiError, ServiceHandleException) as e:
            raise ServiceHandleException(msg="get region service error", msg_show="获取集群组件状态异常")


team_component_repo = TeamComponentRepository(TeamComponentInfo)
