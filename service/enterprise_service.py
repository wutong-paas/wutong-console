from loguru import logger
from clients.remote_component_client import remote_component_client
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo


class EnterpriseServices(object):
    """
    企业组件接口，提供以企业为中心的操作集合，企业在云帮体系中为最大业务隔离单元，企业下有团队（也就是tenant）
    """

    def get_enterprise_runing_service(self, session: SessionClass, regions, team_ids):

        app_total_num = 0
        app_running_num = 0
        component_total_num = 0
        component_running_num = 0

        if not team_ids:
            return {
                "service_groups": {
                    "total": 0,
                    "running": 0,
                    "closed": 0
                },
                "components": {
                    "total": 0,
                    "running": 0,
                    "closed": 0
                }
            }
        region_names = [region.region_name for region in regions]
        apps = application_repo.get_apps_in_multi_team(session, team_ids, region_names)

        app_total_num = len(apps)

        app_ids = [app.ID for app in apps]
        app_relations = app_component_relation_repo.get_service_group_relation_by_groups(session, app_ids)
        component_total_num = len(app_relations)

        # 3. get all running component
        # attention, component maybe belong to any other enterprise
        running_component_ids = []
        for region in regions:
            data = None
            try:
                data = remote_component_client.get_enterprise_running_services(session,
                                                                               region.region_name,
                                                                               test=True)
            except (remote_component_client.CallApiError, ServiceHandleException) as e:
                logger.exception("get region:'{0}' running failed: {1}".format(region.region_name, e))
            if data and data.get("service_ids"):
                running_component_ids.extend(data.get("service_ids"))

        # 4 get all running app
        component_and_app = dict()
        for relation in app_relations:
            component_and_app[relation.service_id] = relation.group_id

        running_apps = []
        running_component_ids = list(set(running_component_ids))
        for running_component in running_component_ids:
            # if this running component belong to this enterprise
            app = component_and_app.get(running_component)
            if app:
                component_running_num += 1
                if app not in running_apps:
                    running_apps.append(app)
        app_running_num = len(running_apps)
        data = {
            "service_groups": {
                "total": app_total_num,
                "running": app_running_num,
                "closed": app_total_num - app_running_num
            },
            "components": {
                "total": component_total_num,
                "running": component_running_num,
                "closed": component_total_num - component_running_num
            }
        }
        return data


enterprise_services = EnterpriseServices()
