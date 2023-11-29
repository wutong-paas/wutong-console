import re
from datetime import datetime

from loguru import logger
from sqlalchemy import select

from clients.remote_component_client import remote_component_client
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import EnvAlreadyExist, InvalidEnvName, AbortRequest
from models.component.models import ComponentEnvVar, TeamComponentPort
from repository.teams.team_service_env_var_repo import env_var_repo
from repository.component.env_var_repo import env_var_repo as service_env_var_repo


class AppEnvVarService(object):
    SENSITIVE_ENV_NAMES = ('SERVICE_EXTEND_METHOD', 'SLUG_URL', 'DEPEND_SERVICE', 'REVERSE_DEPEND_SERVICE', 'POD_ORDER',
                           'PATH',
                           'POD_NET_IP', 'LOG_MATCH',
                           "POD_IP", "HOST_IP", "POD_NAMESPACE")

    def create_env_var(self, session, service, container_port, name, attr_name, attr_value, is_change=False,
                       scope="outer"):
        """
        raise: EnvAlreadyExist
        raise: InvalidEnvName
        """
        self.check_env(session, service, attr_name, attr_value)
        if len(str(attr_value)) > 65532:
            attr_value = str(attr_value)[:65532]
        tenantServiceEnvVar = {}
        tenantServiceEnvVar["tenant_env_id"] = service.tenant_env_id
        tenantServiceEnvVar["service_id"] = service.service_id
        tenantServiceEnvVar['container_port'] = container_port
        tenantServiceEnvVar["name"] = name
        tenantServiceEnvVar["attr_name"] = attr_name
        tenantServiceEnvVar["attr_value"] = attr_value
        tenantServiceEnvVar["is_change"] = is_change
        tenantServiceEnvVar["scope"] = scope
        tse = ComponentEnvVar(**tenantServiceEnvVar)
        session.add(tse)
        session.flush()
        return tse

    def check_env(self, session, component, attr_name, attr_value):
        if env_var_repo.get_service_env_by_attr_name(session, component.tenant_env_id, component.service_id, attr_name):
            raise EnvAlreadyExist()
        attr_name = str(attr_name).strip()
        attr_value = str(attr_value).strip()
        is_pass, msg = self.check_env_attr_name(session, attr_name)
        if not is_pass:
            raise InvalidEnvName(msg)

    def get_env_by_container_port(self, session: SessionClass, tenant_env, service, container_port):
        data = env_var_repo.get_service_env_by_port(session, tenant_env.env_id, service.service_id, container_port)
        return data

    def get_self_define_env(self, session: SessionClass, service):
        if service:
            envs = env_var_repo.get_service_env(session, service.tenant_env_id, service.service_id)
            # todo exclude
            # data = envs.exclude(container_port=-1, scope="outer")
            # return data
            return envs

    def add_service_env_var(self, session: SessionClass,
                            tenant_env,
                            service,
                            container_port,
                            name,
                            attr_name,
                            attr_value,
                            is_change,
                            scope="outer",
                            user_name=''):
        attr_name = str(attr_name).strip()
        attr_value = str(attr_value).strip()
        is_pass, msg = self.check_env_attr_name(session=session, attr_name=attr_name)
        if not is_pass:
            return 400, msg, None
        if len(str(attr_value)) > 65532:
            attr_value = str(attr_value)[:65532]
        tenant_service_env_var = {"tenant_env_id": service.tenant_env_id, "service_id": service.service_id,
                                  'container_port': container_port, "name": name, "attr_name": attr_name,
                                  "attr_value": attr_value, "is_change": is_change, "scope": scope}
        env = (session.execute(
            select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == service.tenant_env_id,
                                          ComponentEnvVar.service_id == service.service_id,
                                          ComponentEnvVar.attr_name == attr_name))
        ).scalars().first()

        if env:
            return 412, "环境变量{0}已存在".format(attr_name), env
        # 判断是否需要再region端添加
        if service.create_status == "complete":
            attr = {
                "container_port": container_port,
                "tenant_env_id": service.tenant_env_id,
                "service_id": service.service_id,
                "name": name,
                "attr_name": attr_name,
                "attr_value": str(attr_value),
                "is_change": True,
                "scope": scope,
                "env_name": attr_name,
                "env_value": str(attr_value),
                "operator": user_name
            }
            remote_component_client.add_service_env(session,
                                                    service.service_region, tenant_env,
                                                    service.service_alias, attr)
        add_model: ComponentEnvVar = ComponentEnvVar(**tenant_service_env_var)
        session.add(add_model)
        session.flush()
        return 200, 'success', add_model

    def check_env_attr_name(self, session: SessionClass, attr_name):
        if attr_name in self.SENSITIVE_ENV_NAMES:
            return False, "不允许的变量名{0}".format(attr_name)

        if not re.match(r"^[-._a-zA-Z][-._a-zA-Z0-9]*$", attr_name):
            return False, "变量名称{0}不符合规范".format(attr_name)
        return True, "success"

    def delete_env_by_container_port(self, session: SessionClass, tenant_env, service, container_port, user_name=''):
        """
        根据端口删除环境变量
        """
        envs = env_var_repo.get_service_env_by_port(session, tenant_env.env_id, service.service_id, container_port)
        if service.create_status == "complete":
            for env in envs:
                data = {"env_name": env.attr_name, "operator": user_name}
                remote_component_client.delete_service_env(session,
                                                           service.service_region, tenant_env,
                                                           service.service_alias, data)
        env_var_repo.delete_service_env_by_port(session, tenant_env.env_id, service.service_id, container_port)

    def get_service_build_envs(self, session: SessionClass, service):
        if service:
            return env_var_repo.get_service_env_by_scope(session, service.tenant_env_id, service.service_id, "build")

    def add_service_build_env_var(self, session: SessionClass, service, container_port, name, attr_name, attr_value,
                                  is_change,
                                  scope="build"):
        attr_name = str(attr_name).strip()
        attr_value = str(attr_value).strip()
        is_pass, msg = self.check_env_attr_name(session=session, attr_name=attr_name)
        if not is_pass:
            return 400, msg, None
        if len(str(attr_value)) > 65532:
            attr_value = str(attr_value)[:65532]

        tenant_service_env_var = dict()
        tenant_service_env_var["tenant_env_id"] = service.tenant_env_id
        tenant_service_env_var["service_id"] = service.service_id
        tenant_service_env_var['container_port'] = container_port
        tenant_service_env_var["name"] = name
        tenant_service_env_var["attr_name"] = attr_name
        tenant_service_env_var["attr_value"] = attr_value
        tenant_service_env_var["is_change"] = is_change
        tenant_service_env_var["scope"] = scope

        new_env: ComponentEnvVar = ComponentEnvVar(**tenant_service_env_var)
        session.add(new_env)
        session.flush()
        return 200, 'success', new_env

    def delete_region_env(self, session: SessionClass, tenant_env, service):
        if service:
            envs = env_var_repo.get_service_env(session, service.tenant_env_id, service.service_id)
            for env in envs:
                data = {"env_name": env.attr_name}
                try:
                    remote_component_client.delete_service_env(session,
                                                               service.service_region, tenant_env,
                                                               service.service_alias, data)
                except Exception as e:
                    logger.exception(e)

    def delete_env_by_env_id(self, session: SessionClass, tenant_env, service, env_id, user_name=''):
        env = env_var_repo.get_by_primary_key(session=session, primary_key=env_id)
        if env:
            env_var_repo.delete_service_env_by_attr_name(session, tenant_env.env_id, service.service_id, env.attr_name)
            if service.create_status == "complete":
                remote_component_client.delete_service_env(session,
                                                           service.service_region,
                                                           tenant_env, service.service_alias,
                                                           {
                                                               "env_name": env.attr_name,
                                                               "operator": user_name
                                                           })

    def patch_env_scope(self, session: SessionClass, tenant_env, service, env_id, scope, user_name=''):
        env = env_var_repo.get_by_primary_key(session=session, primary_key=env_id)
        if env:
            if service.create_status == "complete":
                body = {"env_name": env.attr_name, "env_value": env.attr_value, "scope": scope, "operator": user_name}
                remote_component_client.update_service_env(session,
                                                           service.service_region, tenant_env,
                                                           service.service_alias, body)
            env_var_repo.change_service_env_scope(env, scope)
            return env
        else:
            raise AbortRequest(msg="Environment variable with ID {} not found".format(env_id),
                               msg_show="环境变量`{}`不存在".format(env_id),
                               status_code=404,
                               error_code=400)

    def update_env_by_env_id(self, session: SessionClass, tenant_env, service, env_id, name, attr_value, user_name=''):
        if not isinstance(env_id, int):
            env_id = env_id.strip()
        attr_value = attr_value.strip()
        env = env_var_repo.get_by_primary_key(session=session, primary_key=env_id)
        if not env:
            return 404, "环境变量不存在", None
        update_params = {"ID": env.ID, "name": name, "attr_value": attr_value,
                         "tenant_env_id": tenant_env.env_id, "service_id": service.service_id,
                         "attr_name": env.attr_name}
        if service.create_status == "complete":
            body = {"env_name": env.attr_name, "env_value": attr_value, "scope": env.scope, "operator": user_name}
            remote_component_client.update_service_env(session,
                                                       service.service_region, tenant_env,
                                                       service.service_alias, body)
        env_var_repo.update_by_primary_key(session=session, update_model=ComponentEnvVar(**update_params))
        env.name = name
        env.attr_value = attr_value
        return 200, "success", env

    def create_port_env(self, port: TeamComponentPort, name, attr_name_suffix, attr_value):
        """创建端口环境变量"""
        return ComponentEnvVar(
            tenant_env_id=port.tenant_env_id,
            service_id=port.service_id,
            container_port=port.container_port,
            name=name,
            attr_name=port.port_alias + "_" + attr_name_suffix,
            attr_value=attr_value,
            is_change=False,
            scope="outer",
            create_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

    def batch_update_service_env(self, session, row_datas, env, service, is_change, scope, user):
        attr_names = []
        row = 0
        for row_data in row_datas:
            if row_data:
                row += 1
                attr_name = None
                attr_value = ""
                name = ""
                row_data_list = row_data.split("|")
                env_len = len(row_data_list)
                if env_len == 3:
                    attr_name = row_data_list[0]
                    attr_value = row_data_list[1]
                    name = row_data_list[2]
                elif env_len == 2:
                    attr_name = row_data_list[0]
                    attr_value = row_data_list[1]
                elif env_len == 1:
                    attr_name = row_data_list[0]
                else:
                    return general_message(400, "params error", "格式解析错误")
                if attr_name:
                    attr_names.append(attr_name)
                    service_env_var = env_var_repo.get_service_env_by_attr_name(session=session,
                                                                                tenant_env_id=env.env_id,
                                                                                service_id=service.service_id,
                                                                                attr_name=attr_name)
                    if not service_env_var:
                        code, msg, data = env_var_service.add_service_env_var(session=session, tenant_env=env,
                                                                              service=service,
                                                                              container_port=0, name=name,
                                                                              attr_name=attr_name,
                                                                              attr_value=attr_value,
                                                                              is_change=is_change, scope=scope,
                                                                              user_name=user.nick_name)
                        if code != 200:
                            return general_message(code, "add env error", msg)
                    else:
                        code, msg, service_env = env_var_service.update_env_by_env_id(session=session,
                                                                                      tenant_env=env,
                                                                                      service=service,
                                                                                      env_id=service_env_var.ID,
                                                                                      name=name,
                                                                                      attr_value=attr_value,
                                                                                      user_name=user.nick_name)
                        if code != 200:
                            raise AbortRequest(msg="update value error", msg_show=msg, status_code=code)
                else:
                    return general_message(400, "params error", "第" + row + "行变量名不能为空")

        # 删除操作
        service_env_vars = service_env_var_repo.get_service_env_by_tenant_env_id_and_service_id(session=session,
                                                                                                tenant_env_id=env.env_id,
                                                                                                service_id=service.service_id)
        for service_env_var in service_env_vars:
            old_attr_name = service_env_var.attr_name
            if not (old_attr_name in attr_names):
                env_var_service.delete_env_by_env_id(session=session, tenant_env=env, service=service,
                                                     env_id=service_env_var.ID,
                                                     user_name=user.nick_name)
        return None


env_var_service = AppEnvVarService()
