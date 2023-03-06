import datetime

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from common.api_base_http_client import ApiBaseHttpClient
from core.utils.return_message import general_message
from exceptions.bcode import ErrComponentBuildFailed
from exceptions.main import AbortRequest, ErrInsufficientResource
from models.component.models import ComponentEnvVar
from repository.component.component_repo import service_source_repo
from service.app_actions.app_log import event_service
from service.app_actions.app_manage import app_manage_service
from service.app_config.app_relation_service import dependency_service
from service.app_config.port_service import port_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.application_service import application_service


class DevopsRepository:
    @staticmethod
    def delete_dependency_component(session, user, tenant_env, service, dep_service_ids):
        """
        删除组件的某个依赖
        """
        dep_service_list = dep_service_ids.split(",")
        for dep_id in dep_service_list:
            code, msg, dependency = dependency_service.delete_service_dependency(session=session, tenant_env=tenant_env,
                                                                                 service=service, dep_service_id=dep_id,
                                                                                 user_name=user.nick_name)
            if code != 200:
                return general_message(code, "delete dependency error", msg)

        return general_message("0", "success", "删除成功")

    @staticmethod
    def delete_envs(session, user, tenant_env, service, key):
        """
        删除组件的某个环境变量
        """
        env = session.execute(select(ComponentEnvVar).where(
            ComponentEnvVar.tenant_env_id == tenant_env.env_id,
            ComponentEnvVar.service_id == service.service_id,
            ComponentEnvVar.attr_name == key
        )).scalars().first()

        if not env:
            return general_message(200, "delete env not found", "需要删除的环境变量未找到")
        env_var_service.delete_env_by_env_id(session=session, tenant_env=tenant_env, service=service, env_id=env.ID,
                                             user_name=user.nick_name)
        return general_message("0", "success", "删除成功")

    @staticmethod
    def modify_env(session, user, tenant_env, service, key, name, attr_value):
        """
        修改组件环境变量
        """
        env = session.execute(select(ComponentEnvVar).where(
            ComponentEnvVar.tenant_env_id == tenant_env.env_id,
            ComponentEnvVar.service_id == service.service_id,
            ComponentEnvVar.attr_name == key
        )).scalars().first()

        if not env:
            return general_message(400, "update env not found", "需要更新的环境变量未找到")

        code, msg, env = env_var_service.update_env_by_env_id(session=session, tenant_env=tenant_env, service=service,
                                                              env_id=str(env.ID), name=name, attr_value=attr_value,
                                                              user_name=user.nick_name)
        if code != 200:
            raise AbortRequest(msg="update value error", msg_show=msg, status_code=code)

        return general_message("0", "success", "更新成功", bean=jsonable_encoder(env))

    @staticmethod
    def component_build(session, user, tenant_env, service):
        """
        组件构建
        """
        is_deploy = True

        try:
            if service.service_source == "third_party":
                is_deploy = False
                # create third component from region
                new_service = application_service.create_third_party_service(session=session, tenant_env=tenant_env,
                                                                             service=service, user_name=user.nick_name)
            else:
                # 数据中心创建组件
                new_service = application_service.create_region_service(session=session, tenant_env=tenant_env,
                                                                        service=service,
                                                                        user_name=user.nick_name)

            service = new_service
            if is_deploy:
                try:
                    app_manage_service.deploy(session=session, tenant_env=tenant_env, service=service, user=user)
                except ErrInsufficientResource as e:
                    return general_message(e.error_code, e.msg, e.msg_show)
                except Exception as e:
                    logger.exception(e)
                    err = ErrComponentBuildFailed()
                    return general_message(err.error_code, e, err.msg_show)
                # 添加组件部署关系
                application_service.create_deploy_relation_by_service_id(session=session, service_id=service.service_id)

            return general_message("0", "success", "部署成功", bean={"service_alias": service.service_alias})
        except ApiBaseHttpClient.RemoteInvokeError as e:
            logger.exception(e)
            if e.status == 403:
                result = general_message(10407, "no cloud permission", e.message)
            elif e.status == 400:
                if "is exist" in e.message.get("body", ""):
                    result = general_message(400, "the service is exist in region", "该组件在数据中心已存在，你可能重复创建？")
                else:
                    result = general_message(400, "call cloud api failure", e.message)
            else:
                result = general_message(400, "call cloud api failure", e.message)
        # 删除probe
        # 删除region端数据
        # if probe:
        #     probe_service.delete_service_probe(tenant, service, probe.probe_id)
        if service.service_source != "third_party":
            event_service.delete_service_events(session=session, service=service)
            port_service.delete_region_port(session=session, tenant_env=tenant_env, service=service)
            volume_service.delete_region_volumes(session=session, tenant_env=tenant_env, service=service)
            env_var_service.delete_region_env(session=session, tenant_env=tenant_env, service=service)
            dependency_service.delete_region_dependency(session=session, tenant_env=tenant_env, service=service)
            app_manage_service.delete_region_service(session=session, tenant_env=tenant_env, service=service)
        service.create_status = "checked"
        return result

    @staticmethod
    def modify_source(session, service, image, user_name, password):
        """
        修改构建源
        ---
        """
        try:
            cmd = None
            service_source_user = service_source_repo.get_service_source(
                session=session, env_id=service.tenant_env_id, service_id=service.service_id)

            if not service_source_user:
                service_source_info = {
                    "service_id": service.service_id,
                    "team_id": service.tenant_env_id,
                    "user_name": user_name,
                    "password": password,
                    "create_time": datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                }
                service_source_repo.create_service_source(session, **service_source_info)
            else:
                service_source_user.user_name = user_name
                service_source_user.password = password
            if image:
                version = image.split(':')[-1]
                if not version:
                    version = "latest"
                    image = image + ":" + version
                service.image = image
                service.version = version
            service.cmd = cmd
        except Exception as e:
            logger.exception(e)

    @staticmethod
    def add_envs(session, attr_name, attr_value, name, user, tenant_env, service):
        scope = "inner"
        is_change = True
        if not scope or not attr_name:
            return general_message(400, "params error", "参数异常")
        if scope not in ("inner", "outer"):
            return general_message(400, "params error", "scope范围只能是inner或outer")
        code, msg, data = env_var_service.add_service_env_var(session=session, tenant_env=tenant_env, service=service,
                                                              container_port=0, name=name, attr_name=attr_name,
                                                              attr_value=attr_value,
                                                              is_change=is_change, scope=scope,
                                                              user_name=user.nick_name)
        if code != 200:
            result = general_message(code, "add env error", msg)
            return result
        result = general_message(code, msg, "环境变量添加成功", bean=jsonable_encoder(data))
        return result

    @staticmethod
    def add_dep(session, user, tenant_env, service, dep_service_ids):
        if service.is_third_party():
            raise AbortRequest(msg="third-party components cannot add dependencies", msg_show="第三方组件不能添加依赖组件")
        dep_service_list = dep_service_ids.split(",")
        code, msg = dependency_service.patch_add_dependency(session=session, tenant_env=tenant_env, service=service,
                                                            dep_service_ids=dep_service_list, user_name=user.nick_name)
        if code != 200:
            return general_message(code, "add dependency error", msg)
        return general_message(code, msg, "依赖添加成功")


devops_repo = DevopsRepository()
