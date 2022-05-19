import json

from loguru import logger
from sqlalchemy import delete

from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.enum.component_enum import ComponentType
from core.utils.constants import AppConstants
from database.session import SessionClass
from exceptions.bcode import ErrComponentPortExists
from exceptions.main import ServiceHandleException, ErrVolumePath
from models.component.models import ComponentEnvVar, TeamComponentEnv, TeamComponentPort, TeamComponentVolume
from repository.component.group_service_repo import service_repo
from repository.region.region_info_repo import region_repo
from service.app_config.domain_service import domain_service
from service.app_config.env_service import compile_env_service
from service.app_config.port_service import port_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.label_service import label_service
from service.region_service import region_services


class ComponentCheckService(object):

    def get_service_check_info(self, session: SessionClass, tenant, region, check_uuid):
        rt_msg = dict()
        try:
            res, body = remote_build_client.get_service_check_info(session, region, tenant.tenant_name, check_uuid)
            bean = body["bean"]
            if not bean["check_status"]:
                bean["check_status"] = "checking"
            bean["check_status"] = bean["check_status"].lower()
            rt_msg = bean
        except remote_build_client.CallApiError as e:
            rt_msg["error_infos"] = [{
                "error_type": "api invoke error",
                "solve_advice": "重新尝试",
                "error_info": "{}".format(e.message)
            }]
            rt_msg["check_status"] = "failure"
            rt_msg["service_info"] = []
            logger.exception(e)

        return 200, "success", rt_msg

    def update_service_check_info(self, session: SessionClass, tenant, service, data):
        if data["check_status"] != "success":
            return
        sid = None
        try:
            # sid = transaction.savepoint()
            # 删除原有build类型env，保存新检测build类型env
            self.upgrade_service_env_info(session, tenant, service, data)
            # 重新检测后对端口做加法
            try:
                self.add_service_check_port(session=session, tenant=tenant, service=service, data=data)
            except ErrComponentPortExists:
                logger.error('upgrade component port by code check failure due to component port exists')
            lang = data["service_info"][0]["language"]
            if lang == "dockerfile":
                service.cmd = ""
            elif service.service_source == AppConstants.SOURCE_CODE:
                service.cmd = "start web"
            service.language = lang
            service.save()
            # transaction.savepoint_commit(sid)
        except Exception as e:
            logger.exception(e)
            if sid:
                # transaction.savepoint_rollback(sid)
                logger.info("")
            raise ServiceHandleException(status_code=400, msg="handle check service code info failure",
                                         msg_show="处理检测结果失败")

    def upgrade_service_env_info(self, session: SessionClass, tenant, service, data):
        # 更新构建时环境变量
        if data["check_status"] == "success":
            service_info_list = data["service_info"]
            self.upgrade_service_info(session, tenant, service, service_info_list[0])

    def add_service_check_port(self, session: SessionClass, tenant, service, data):
        # 更新构建时环境变量
        if data["check_status"] == "success":
            service_info_list = data["service_info"]
            self.add_check_ports(session=session, tenant=tenant, service=service,
                                 check_service_info=service_info_list[0])

    def add_check_ports(self, session: SessionClass, tenant, service, check_service_info):
        service_info = check_service_info
        ports = service_info.get("ports", None)
        if not ports:
            return
        # 更新构建时环境变量
        self.__save_check_port(session=session, tenant=tenant, service=service, ports=ports)

    def upgrade_service_info(self, session: SessionClass, tenant, service, check_service_info):
        service_info = check_service_info
        envs = service_info["envs"]
        # 更新构建时环境变量
        self.__upgrade_env(session, tenant, service, envs)

    def __save_check_port(self, session: SessionClass, tenant, service, ports):
        if not ports:
            return
        for port in ports:
            code, msg, port_data = port_service.add_service_port(session=session, tenant=tenant, service=service,
                                                                 container_port=int(port["container_port"]),
                                                                 protocol=port["protocol"],
                                                                 port_alias=service.service_alias.upper() + str(
                                                                     port["container_port"]))
            if code != 200:
                logger.error("save service check info port error {0}".format(msg))

    def __upgrade_env(self, session: SessionClass, tenant, service, envs):
        if envs:
            # 删除原有的build类型环境变量
            session.execute(
                delete(ComponentEnvVar).where(ComponentEnvVar.tenant_id == tenant.tenant_id,
                                              ComponentEnvVar.service_id == service.service_id,
                                              ComponentEnvVar.scope == "build")
            )

            SENSITIVE_ENV_NAMES = (
                'TENANT_ID', 'SERVICE_ID', 'TENANT_NAME', 'SERVICE_NAME', 'SERVICE_VERSION', 'MEMORY_SIZE',
                'SERVICE_EXTEND_METHOD', 'SLUG_URL', 'DEPEND_SERVICE', 'REVERSE_DEPEND_SERVICE', 'POD_ORDER',
                'PATH', 'PORT', 'POD_NET_IP', 'LOG_MATCH')
            for env in envs:
                if env["name"] in SENSITIVE_ENV_NAMES:
                    continue
                # BUILD_开头的env保存为build类型的环境变量
                elif env["name"].startswith("BUILD_"):
                    code, msg, data = env_var_service.add_service_build_env_var(session=session, service=service,
                                                                                container_port=0, name=env["name"],
                                                                                attr_name=env["name"],
                                                                                attr_value=env["value"], is_change=True)
                    if code != 200:
                        logger.error("save service check info env error {0}".format(msg))

    def wrap_service_check_info(self, session: SessionClass, service, data):
        rt_info = dict()
        rt_info["check_status"] = data["check_status"]
        rt_info["error_infos"] = data["error_infos"]
        if data["service_info"] and len(data["service_info"]) > 1:
            rt_info["is_multi"] = True
        else:
            rt_info["is_multi"] = False
        service_info_list = data["service_info"]
        service_list = []
        if service_info_list:
            service_info = service_info_list[0]
            service_list = self.wrap_check_info(session=session, service=service, service_info=service_info)

            # service_middle_ware_bean = {}
            # sub_bean_list.append(service_middle_ware_bean)
            # service_list.append(sub_bean_list)

        rt_info["service_info"] = service_list
        return rt_info

    def wrap_check_info(self, session: SessionClass, service, service_info):
        service_attr_list = []
        if service_info["ports"]:
            service_port_bean = {
                "type": "ports",
                "key": "端口信息",
                "value": [str(port["container_port"]) + "(" + port["protocol"] + ")" for port in service_info["ports"]]
            }
            service_attr_list.append(service_port_bean)
        if service_info["volumes"]:
            service_volume_bean = {
                "type": "volumes",
                "key": "持久化目录",
                "value": [volume["volume_path"] + "(" + volume["volume_type"] + ")" for volume in
                          service_info["volumes"]]
            }
            service_attr_list.append(service_volume_bean)
        service_code_from = {}
        service_language = {}
        if service.service_source == AppConstants.SOURCE_CODE:
            service_code_from = {
                "type": "source_from",
                "key": "源码信息",
                "value": "{0}  branch: {1}".format(service.git_url, service.code_version)
            }
            service_language = {"type": "language", "key": "代码语言", "value": service_info["language"]}
        elif service.service_source == AppConstants.DOCKER_RUN or service.service_source == AppConstants.DOCKER_IMAGE:
            service_code_from = {"type": "source_from", "key": "镜像名称", "value": service.image}
            if service.cmd:
                service_attr_list.append({"type": "source_from", "key": "镜像启动命令", "value": service.cmd})
        if service_language:
            service_attr_list.append(service_language)
        if service_code_from:
            service_attr_list.append(service_code_from)
        return service_attr_list

    def save_service_check_info(self, session: SessionClass, tenant, service, data):
        # save the detection properties but does not throw any exception.
        if data["check_status"] == "success" and service.create_status == "checking":
            logger.debug("checking service info install,save info into database")
            service_info_list = data["service_info"]
            sid = None
            try:
                # sid = transaction.savepoint() todo
                self.save_service_info(session, tenant, service, service_info_list[0])
                # save service info, checked 表示检测完成
                service.create_status = "checked"
                # todo
                service_repo.save_service(session=session, service=service)
                # transaction.savepoint_commit(sid)
            except Exception as e:
                if sid:
                    # transaction.savepoint_rollback(sid)
                    logger.info("")
                logger.exception(e)

    def save_service_info(self, session: SessionClass, tenant, service, check_service_info):
        service_info = check_service_info
        service.language = service_info.get("language", "")
        memory = service_info.get("memory", 128)
        service.min_memory = memory - memory % 32
        service.min_cpu = 0
        # Set the deployment type based on the test results
        logger.debug("save svc extend_method {0}".format(
            service_info.get("service_type", ComponentType.stateless_multiple.value)))
        service.extend_method = service_info.get("service_type", ComponentType.stateless_multiple.value)
        args = service_info.get("args", None)
        if args:
            service.cmd = " ".join(args)
        else:
            service.cmd = ""
        image = service_info.get("image", None)
        if image:
            service_image = image["name"] + ":" + image["tag"]
            service.image = service_image
            service.version = image["tag"]
        envs = service_info.get("envs", None)
        ports = service_info.get("ports", None)
        volumes = service_info.get("volumes", None)
        service_runtime_os = service_info.get("os", "linux")
        if service_runtime_os == "windows":
            label_service.set_service_os_label(session=session, tenant=tenant, service=service, os=service_runtime_os)
        self.__save_compile_env(session, tenant, service, service.language)
        # save env
        self.__save_env(session, tenant, service, envs)
        self.__save_port(session, tenant, service, ports)
        self.__save_volume(session, tenant, service, volumes)

    def __save_compile_env(self, session: SessionClass, tenant, service, language):
        # 删除原有 compile env
        logger.debug("save tenant {0} compile service env {1}".format(tenant.tenant_name, service.service_cname))
        session.execute(
            delete(TeamComponentEnv).where(TeamComponentEnv.service_id == service.service_id)
        )

        if not language:
            language = False
        check_dependency = {
            "language": language,
        }
        check_dependency_json = json.dumps(check_dependency)
        # 添加默认编译环境
        user_dependency = compile_env_service.get_service_default_env_by_language(language)
        user_dependency_json = json.dumps(user_dependency)
        compile_env_service.save_compile_env(session=session, service=service, language=language,
                                             check_dependency=check_dependency_json,
                                             user_dependency=user_dependency_json)

    def __save_env(self, session: SessionClass, tenant, service, envs):
        if envs:
            # 删除原有env
            session.execute(
                delete(ComponentEnvVar).where(ComponentEnvVar.tenant_id == tenant.tenant_id,
                                              ComponentEnvVar.service_id == service.service_id))

            # 删除原有的build类型环境变量
            session.execute(
                delete(ComponentEnvVar).where(ComponentEnvVar.tenant_id == tenant.tenant_id,
                                              ComponentEnvVar.service_id == service.service_id,
                                              ComponentEnvVar.scope == "build"))

            SENSITIVE_ENV_NAMES = (
                'TENANT_ID', 'SERVICE_ID', 'TENANT_NAME', 'SERVICE_NAME', 'SERVICE_VERSION', 'MEMORY_SIZE',
                'SERVICE_EXTEND_METHOD', 'SLUG_URL', 'DEPEND_SERVICE', 'REVERSE_DEPEND_SERVICE', 'POD_ORDER',
                'PATH', 'POD_NET_IP')
            for env in envs:
                if env["name"] in SENSITIVE_ENV_NAMES:
                    continue
                # BUILD_开头的env保存为build类型的环境变量
                elif env["name"].startswith("BUILD_"):
                    code, msg, data = env_var_service.add_service_build_env_var(session=session, service=service,
                                                                                container_port=0, name=env["name"],
                                                                                attr_name=env["name"],
                                                                                attr_value=env["value"], is_change=True)
                    if code != 200:
                        logger.error("save service check info env error {0}".format(msg))
                else:
                    code, msg, env_data = env_var_service.add_service_env_var(session=session, tenant=tenant,
                                                                              service=service,
                                                                              container_port=0, name=env["name"],
                                                                              attr_name=env["name"],
                                                                              attr_value=env["value"], is_change=True,
                                                                              scope="inner")
                    if code != 200:
                        logger.error("save service check info env error {0}".format(msg))

    def __save_port(self, session: SessionClass, tenant, service, ports):
        if not tenant or not service:
            return
        if ports:
            # delete ports before add
            session.execute(
                delete(TeamComponentPort).where(TeamComponentPort.tenant_id == tenant.tenant_id,
                                                TeamComponentPort.service_id == service.service_id))

            for port in ports:
                code, msg, port_data = port_service.add_service_port(
                    session=session, tenant=tenant, service=service, container_port=int(port["container_port"]),
                    protocol=port["protocol"],
                    port_alias=service.service_alias.upper() + str(port["container_port"]))
                if code != 200:
                    logger.error("save service check info port error {0}".format(msg))
        else:
            if service.service_source == AppConstants.SOURCE_CODE:
                session.execute(
                    delete(TeamComponentPort).where(TeamComponentPort.tenant_id == tenant.tenant_id,
                                                    TeamComponentPort.service_id == service.service_id))

                _, _, t_port = port_service.add_service_port(session=session, tenant=tenant, service=service,
                                                             container_port=5000, protocol="http",
                                                             port_alias=service.service_alias.upper() + str(5000),
                                                             is_inner_service=False,
                                                             is_outer_service=True)
                region_info = region_repo.get_enterprise_region_by_region_name(session=session,
                                                                               enterprise_id=tenant.enterprise_id,
                                                                               region_name=service.service_region)
                if region_info:
                    domain_service.create_default_gateway_rule(session=session, tenant=tenant, region_info=region_info,
                                                               service=service, port=t_port)
                else:
                    logger.error("get region {0} from enterprise {1} failure".format(tenant.enterprise_id,
                                                                                     service.service_region))

        return 200, "success"

    def __save_volume(self, session: SessionClass, tenant, service, volumes):
        if volumes:
            session.execute(
                delete(TeamComponentVolume).where(TeamComponentVolume.service_id == service.service_id)
            )

            index = 0
            for volume in volumes:
                index += 1
                volume_name = service.service_alias.upper() + "_" + str(index)
                if "file_content" in list(volume.keys()):
                    volume_service.add_service_volume(session=session, tenant=tenant, service=service,
                                                      volume_path=volume["volume_path"],
                                                      volume_type=volume["volume_type"],
                                                      volume_name=volume_name, file_content=volume["file_content"])
                else:
                    settings = {}
                    settings["volume_capacity"] = volume["volume_capacity"]
                    try:
                        volume_service.add_service_volume(session=session, tenant=tenant, service=service,
                                                          volume_path=volume["volume_path"],
                                                          volume_type=volume["volume_type"],
                                                          volume_name=volume_name, file_content=None, settings=settings)
                    except ErrVolumePath:
                        logger.warning("Volume Path {0} error".format(volume["volume_path"]))


class ComponentLogService(object):
    @staticmethod
    def get_component_log_stream(session, tenant_name, region_name, service_alias, pod_name, container_name, follow):
        r = remote_component_client.get_component_log(session, tenant_name, region_name, service_alias, pod_name,
                                                      container_name, follow)
        for chunk in r.stream(1024):
            yield chunk


component_log_service = ComponentLogService()
component_check_service = ComponentCheckService()
