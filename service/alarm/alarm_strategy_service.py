import json

from loguru import logger

from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from repository.alarm.alarm_strategy_repo import alarm_strategy_repo
from repository.region.region_info_repo import region_repo
from service.alarm.alarm_service import alarm_service


class AlarmStrategyService:

    def get_alarm_strategy_data(self, session, alarm_strategy):
        team_code = alarm_strategy.team_code
        env_code = alarm_strategy.env_code
        alarm_objects = json.loads(alarm_strategy.alarm_object)
        alarm_rules = json.loads(alarm_strategy.alarm_rules)
        object_code = alarm_strategy.object_code
        object_type = alarm_strategy.object_type
        alarm_notice = {
            "code": object_code,
            "type": object_type
        }

        env = env_repo.get_env_by_team_code(session, team_code, env_code)
        if not env:
            raise ServiceHandleException(msg_show="目标环境不存在", msg="not found tar env", status_code=404)

        team_name = env.team_alias
        env_name = env.env_alias

        alarm_object_data = []
        for alarm_object in alarm_objects:
            app_code = alarm_object.get("app")
            group_id = alarm_object.get("groupId")
            app = application_repo.get_app_by_k8s_app(session, env.env_id, env.region_code, app_code, None)
            app_name = app.group_name
            components = alarm_object.get("components")
            services = []
            for component in components:
                service_code = component.get("serviceAlias")
                try:
                    service = service_info_repo.get_service(session, service_code, env.env_id)
                except:
                    continue
                if not app or not service:
                    continue
                services.append({
                    "serviceId": service.service_id,
                    "serviceCname": service.service_cname,
                    "serviceAlias": service.service_alias,
                })
            alarm_object_data.append({
                "groupId": group_id,
                "groupName": app_name,
                "projectId": app.project_id,
                "projectName": app.project_name,
                "components": services,
            })

        data = {
            "strategy_name": alarm_strategy.strategy_name,
            "strategy_code": alarm_strategy.strategy_code,
            "desc": alarm_strategy.desc,
            "enable": alarm_strategy.enable,
            "team_code": alarm_strategy.team_code,
            "team_name": team_name,
            "region_code": env.region_code,
            "env_code": alarm_strategy.env_code,
            "env_name": env_name,
            "alarm_object": alarm_object_data,
            "alarm_rules": alarm_rules,
            "alarm_notice": alarm_notice
        }
        return data

    def analysis_object(self, session, objects):
        alarm_objects = []
        for alarm_object in objects:
            alarm_components = []
            group_id = alarm_object.get("groupId")
            app = application_repo.get_group_by_id(session, group_id)
            if not app:
                continue

            app_code = app.k8s_app
            components = alarm_object.get("components")
            for component in components:
                service_id = component.get("serviceId")
                service = service_info_repo.get_service_by_service_id(session, service_id)
                if not service:
                    continue
                service_code = service.k8s_component_name
                component.update({
                    "component": service_code
                })
                alarm_components.append(component)
            alarm_object.update({
                "app": app_code,
                "components": alarm_components
            })
            alarm_objects.append(alarm_object)
        return alarm_objects

    async def update_alarm_strategy_service(self, request, session, env, service):
        strategy_code_data = service.obs_strategy_code
        is_update = False
        if strategy_code_data:
            strategy_code_list = strategy_code_data.split(",")
            region = region_repo.get_region_by_region_name(session, env.region_code)
            for strategy_code in strategy_code_list:
                alarm_strategy = alarm_strategy_repo.get_alarm_strategy_by_code(session, strategy_code)
                if alarm_strategy:
                    alarm_object_list = []
                    alarm_objects = json.loads(alarm_strategy.alarm_object)
                    for alarm_object in alarm_objects:
                        component_list = []
                        components = alarm_object.get("components")
                        for component in components:
                            service_id = component.get("serviceId")
                            if service_id != service.service_id:
                                is_update = True
                                component_list.append(component)
                        if len(component_list) != 0:
                            alarm_object.update({"components": component_list})
                            alarm_object_list.append(alarm_object)
                    alarm_strategy.alarm_object = json.dumps(alarm_object_list)

                    if is_update:
                        # 更新告警策略
                        body = {
                            "title": alarm_strategy.strategy_name,
                            "team": alarm_strategy.team_code,
                            "code": alarm_strategy.strategy_code,
                            "env": alarm_strategy.env_code,
                            "envId": env.env_id,
                            "regionCode": env.region_code,
                            "objects": json.loads(alarm_strategy.alarm_object),
                            "rules": json.loads(alarm_strategy.alarm_rules),
                            "notifies": {
                                "code": alarm_strategy.object_code,
                                "type": alarm_strategy.object_type,
                            },
                        }
                        res = await alarm_service.obs_service_alarm(request, "/v1/alert/rule", body, region, method="PUT")
                        if res["code"] != 200:
                            logger.warning(res["message"])
                    else:
                        # 删除告警策略
                        res = await alarm_service.obs_service_alarm(request,
                                                                    "/v1/alert/rule/" + alarm_strategy.strategy_code, {},
                                                                    region)
                        if res["code"] != 200:
                            logger.warning(res["message"])
                        else:
                            alarm_strategy.enable = False

            service.obs_strategy_code = None


alarm_strategy_service = AlarmStrategyService()
