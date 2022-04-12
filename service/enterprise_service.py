from loguru import logger

from clients.remote_component_client import remote_component_client
from database.session import SessionClass
from exceptions.bcode import ErrUserNotFound, ErrTenantNotFound
from exceptions.main import ServiceHandleException
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import group_service_relation_repo
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo
from service.team_service import team_services
from service.user_service import user_kind_role_service


class EnterpriseServices(object):
    """
    企业组件接口，提供以企业为中心的操作集合，企业在云帮体系中为最大业务隔离单元，企业下有团队（也就是tenant）
    """

    @staticmethod
    def create_user_roles(session, eid, user_id, tenant_name, role_ids):
        # the user must belong to the enterprise with eid
        user = user_repo.get_enterprise_user_by_id(session, eid, user_id)
        if not user:
            raise ErrUserNotFound
        tenant = team_repo.get_enterprise_team_by_name(session, eid, tenant_name)
        if not tenant:
            raise ErrTenantNotFound
        team_services.add_user_to_team(session, tenant, user.user_id, role_ids=role_ids)
        return user_kind_role_service.get_user_roles(session=session, kind="team", kind_id=tenant.tenant_id, user=user)

    def get_enterprise_runing_service(self, session: SessionClass, enterprise_id, regions):

        app_total_num = 0
        app_running_num = 0
        component_total_num = 0
        component_running_num = 0

        # 1. get all teams
        teams = enterprise_repo.get_enterprise_teams(session, enterprise_id)
        if not teams:
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
        # 2. get all apps in all teams
        team_ids = [team.tenant_id for team in teams]
        region_names = [region.region_name for region in regions]
        apps = application_repo.get_apps_in_multi_team(session, team_ids, region_names)

        app_total_num = len(apps)

        app_ids = [app.ID for app in apps]
        app_relations = group_service_relation_repo.get_service_group_relation_by_groups(session, app_ids)
        component_total_num = len(app_relations)

        # 3. get all running component
        # attention, component maybe belong to any other enterprise
        running_component_ids = []
        for region in regions:
            data = None
            try:
                data = remote_component_client.get_enterprise_running_services(session, enterprise_id,
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
