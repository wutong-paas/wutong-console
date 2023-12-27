import json
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from service.tenant_env_service import env_services


class AlarmStrategyService:

    def get_alarm_strategy_data(self, session, alarm_strategy):
        team_code = alarm_strategy.team_code
        env_code = alarm_strategy.env_code
        alarm_objects = json.loads(alarm_strategy.alarm_object)
        alarm_rules = json.loads(alarm_strategy.alarm_rules)
        alarm_notice = json.loads(alarm_strategy.alarm_notice)

        env = env_services.get_env_by_team_code(session, team_code, env_code)
        if not env:
            raise ServiceHandleException(msg_show="目标环境不存在", msg="not found tar env", status_code=404)

        team_name = env.team_alias
        env_name = env.env_alias

        alarm_object_data = []
        for alarm_object in alarm_objects:
            app_code = alarm_object.get("app")
            service_code = alarm_object.get("serviceAlias")
            app = application_repo.get_app_by_k8s_app(session, env.env_id, env.region_code, app_code, None)
            service = service_info_repo.get_service(session, service_code, env.env_id)
            if not app or not service:
                raise ServiceHandleException(msg_show="应用或组件不存在", msg="param error", status_code=404)
            app_name = app.group_name
            service_name = service.service_cname
            alarm_object_data.append({
                "app": app_code,
                "app_name": app_name,
                "component": service.k8s_component_name,
                "serviceId": service.service_id,
                "serviceAlias": service_code,
                "service_name": service_name,
                "projectId": app.project_id,
            })

        data = {
            "strategy_name": alarm_strategy.strategy_name,
            "strategy_code": alarm_strategy.strategy_code,
            "desc": alarm_strategy.desc,
            "enable": alarm_strategy.enable,
            "obs_uid": alarm_strategy.obs_uid,
            "team_code": alarm_strategy.team_code,
            "team_name": team_name,
            "env_code": alarm_strategy.env_code,
            "env_name": env_name,
            "alarm_object": alarm_object_data,
            "alarm_rules": alarm_rules,
            "alarm_notice": alarm_notice
        }
        return data


alarm_strategy_service = AlarmStrategyService()
