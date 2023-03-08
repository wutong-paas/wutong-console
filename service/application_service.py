import base64
import json
import pickle
import random
import re
import string
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select, delete, update
from clients.remote_app_client import remote_app_client
from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.enum.app import AppType, GovernanceModeEnum
from core.enum.component_enum import ComponentType
from core.idaasapi import idaas_api
from core.setting import settings
from core.utils.constants import AppConstants, PluginImage, SourceCodeType
from core.utils.crypt import make_uuid
from core.utils.status_translate import get_status_info_map
from core.utils.validation import validate_endpoints_info, validate_endpoint_address
from database.session import SessionClass
from exceptions.bcode import ErrUserNotFound, ErrK8sAppExists, ErrApplicationNotFound
from exceptions.main import ServiceHandleException, AbortRequest
from models.application.models import Application, ComponentApplicationRelation, ApplicationUpgradeRecord, \
    GroupAppMigrateRecord, ApplicationVisitRecord
from models.component.models import TeamComponentPort, ThirdPartyComponentEndpoints, Component, \
    DeployRelation, ComponentSourceInfo, ComponentEnvVar, TeamComponentMountRelation
from models.region.models import RegionApp
from models.teams import ServiceDomainCertificate
from repository.application.app_backup_repo import backup_record_repo
from repository.application.application_repo import application_repo, app_market_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.component_repo import service_source_repo
from repository.component.compose_repo import compose_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import app_config_group_repo, dep_relation_repo, \
    port_repo, volume_repo, mnt_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_group_relation_repo import service_group_relation_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_share_repo import component_share_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.region.region_app_repo import region_app_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_service_env_var_repo import env_var_repo as team_env_var_repo
from service.app_config.port_service import port_service
from service.app_config.service_monitor_service import service_monitor_service
from service.base_services import base_service, baseService
from service.label_service import label_service
from service.probe_service import probe_service


class ApplicationService(object):
    """
    团队应用service
    """

    def __init_source_code_app(self, region):
        """
        初始化源码创建的组件默认数据,未存入数据库
        """
        tenant_service = Component()
        tenant_service.service_region = region
        tenant_service.service_key = "application"
        tenant_service.desc = "application info"
        tenant_service.category = "application"
        tenant_service.image = PluginImage.RUNNER
        tenant_service.cmd = ""
        tenant_service.setting = ""
        tenant_service.extend_method = ComponentType.stateless_multiple.value
        tenant_service.env = ""
        tenant_service.min_node = 1
        tenant_service.min_memory = 128
        tenant_service.min_cpu = baseService.calculate_service_cpu(region, 128)
        tenant_service.inner_port = 5000
        tenant_service.version = "81701"
        tenant_service.namespace = "wutong"
        tenant_service.update_version = 1
        tenant_service.port_type = "multi_outer"
        tenant_service.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenant_service.deploy_version = ""
        tenant_service.git_project_id = 0
        tenant_service.service_type = "application"
        tenant_service.total_memory = 128
        tenant_service.volume_mount_path = ""
        tenant_service.host_path = ""
        tenant_service.service_source = AppConstants.SOURCE_CODE
        tenant_service.create_status = "creating"
        return tenant_service

    def init_repositories(self, service, user, service_code_from, service_code_clone_url, service_code_id,
                          service_code_version,
                          check_uuid, event_id, oauth_service_id, git_full_name):
        if service_code_from == SourceCodeType.GITLAB_MANUAL or service_code_from == SourceCodeType.GITLAB_DEMO:
            service_code_id = "0"

        if service_code_from in (SourceCodeType.GITLAB_EXIT, SourceCodeType.GITLAB_MANUAL, SourceCodeType.GITLAB_DEMO):
            if not service_code_clone_url or not service_code_id:
                return 403, "代码信息不全"
            service.git_project_id = service_code_id
            service.git_url = service_code_clone_url
            service.code_from = service_code_from
            service.code_version = service_code_version
            # service.save()
        elif service_code_from == SourceCodeType.GITHUB:
            if not service_code_clone_url:
                return 403, "代码信息不全"
            service.git_project_id = service_code_id
            service.git_url = service_code_clone_url
            service.code_from = service_code_from
            service.code_version = service_code_version
            # service.save()
            code_user = service_code_clone_url.split("/")[3]
            code_project_name = service_code_clone_url.split("/")[4].split(".")[0]
            # gitHubClient.createReposHook(code_user, code_project_name, user.github_token)
        elif service_code_from.split("oauth_")[-1] in list(settings.source_code_types.keys()):

            if not service_code_clone_url:
                return 403, "代码信息不全"
            if check_uuid:
                service.check_uuid = check_uuid
            if event_id:
                service.check_event_id = event_id
            service.git_project_id = service_code_id
            service.git_url = service_code_clone_url
            service.code_from = service_code_from
            service.code_version = service_code_version
            service.oauth_service_id = oauth_service_id
            service.git_full_name = git_full_name
            # service.save()

        return 200, "success"

    def create_source_code_app(self,
                               session,
                               region,
                               tenant_env,
                               user,
                               service_code_from,
                               service_cname,
                               service_code_clone_url,
                               service_code_id,
                               service_code_version,
                               server_type,
                               check_uuid=None,
                               event_id=None,
                               oauth_service_id=None,
                               git_full_name=None,
                               k8s_component_name=""):
        service_cname = service_cname.rstrip().lstrip()
        is_pass, msg = self.check_service_cname(service_cname)
        if not is_pass:
            return 412, msg, None
        new_service = self.__init_source_code_app(region)
        new_service.tenant_env_id = tenant_env.env_id
        new_service.service_cname = service_cname
        service_id = make_uuid(tenant_env.env_id)
        service_alias = self.create_service_alias(session, service_id)
        new_service.service_id = service_id
        new_service.service_alias = service_alias
        new_service.creater = user.user_id
        new_service.server_type = server_type
        new_service.k8s_component_name = k8s_component_name if k8s_component_name else service_alias
        session.add(new_service)
        session.flush()
        code, msg = self.init_repositories(new_service, user, service_code_from, service_code_clone_url,
                                           service_code_id,
                                           service_code_version, check_uuid, event_id, oauth_service_id, git_full_name)
        if code != 200:
            return code, msg, new_service
        logger.debug("service.create, user:{0} create service from source code".format(user.nick_name))
        ts = session.execute(select(Component).where(
            Component.service_id == new_service.service_id,
            Component.tenant_env_id == new_service.tenant_env_id
        )).scalars().first()

        return 200, "创建成功", ts

    @staticmethod
    def get_pod(session, tenant_env, region_name, pod_name):
        return remote_build_client.get_pod(session, region_name, tenant_env, pod_name)

    def install_app(self, session, tenant_env, region_name, app_id, overrides):
        if overrides:
            overrides = self._parse_overrides(overrides)

        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        remote_app_client.install_app(session, region_name, tenant_env, region_app_id, {
            "overrides": overrides,
        })

    def get_service_group_info(self, session, service_id):
        return app_component_relation_repo.get_group_info_by_service_id(session, service_id)

    def add_service_default_porbe(self, session, tenant_env, service):
        ports = port_service.get_service_ports(session, service)
        port_length = len(ports)
        if port_length >= 1:
            container_port = ports[0].container_port
            for p in ports:
                if p.is_outer_service:
                    container_port = p.container_port
            data = {
                "service_id": service.service_id,
                "scheme": "tcp",
                "path": "",
                "port": container_port,
                "cmd": "",
                "http_header": "",
                "initial_delay_second": 4,
                "period_second": 3,
                "timeout_second": 5,
                "failure_threshold": 3,
                "success_threshold": 1,
                "is_used": True,
                "probe_id": make_uuid(),
                "mode": "readiness"
            }
            return probe_service.add_service_probe(session, tenant_env, service, data)
        return 200, "success", None

    def update_check_app(self, session, tenant_env, service, data):

        service_source = service_source_repo.get_service_source(session, tenant_env.env_id, service.service_id)
        service_cname = data.get("service_cname", service.service_cname)
        image = data.get("image", service.image)
        cmd = data.get("cmd", service.cmd)
        docker_cmd = data.get("docker_cmd", service.docker_cmd)
        git_url = data.get("git_url", service.git_url)
        min_memory = data.get("min_memory", service.min_memory)
        min_memory = int(min_memory)
        min_cpu = data.get("min_cpu")
        if isinstance(min_cpu, str):
            min_cpu = int(min_cpu)
        if type(min_cpu) != int or min_cpu < 0:
            min_cpu = baseService.calculate_service_cpu(service.service_region, min_memory)

        extend_method = data.get("extend_method", service.extend_method)

        service.service_cname = service_cname
        service.min_memory = min_memory
        service.min_cpu = min_cpu
        service.extend_method = extend_method
        service.image = image
        service.cmd = cmd
        service.git_url = git_url
        service.docker_cmd = docker_cmd

        user_name = data.get("user_name", None)
        password = data.get("password", None)
        if user_name is not None:
            if not service_source:
                params = {
                    "team_id": tenant_env.env_id,
                    "service_id": service.service_id,
                    "user_name": user_name,
                    "password": password,
                }
                service_source_repo.create_service_source(session, **params)
            else:
                service_source.user_name = user_name
                service_source.password = password
        return 200, "success"

    def add_service_to_group(self, session, tenant_env, region_name, group_id, service_id):
        if group_id:
            group_id = int(group_id)
            if group_id > 0:
                group = application_repo.get_by_primary_key(session=session, primary_key=group_id)
                if not group:
                    return 404, "应用不存在"
                app_component_relation_repo.add_service_group_relation(session, group_id, service_id, tenant_env.env_id,
                                                                       region_name)
        return 200, "success"

    def get_app_market_by_name(self, session, name, raise_exception=False):
        return app_market_repo.get_app_market_by_name(session, name, raise_exception=raise_exception)

    def list_components_by_upgrade_group_id(self, session, group_id, upgrade_group_id):
        gsr = app_component_relation_repo.get_services_by_group(session, group_id)
        service_ids = [gs.service_id for gs in gsr]
        return service_info_repo.list_by_ids_upgrade_group_id(session, service_ids, upgrade_group_id)

    def get_wutong_services(self, session, group_id, group_key, upgrade_group_id=None):
        """获取云市应用下的所有组件"""
        tenant_service_group = []
        gsr = app_component_relation_repo.get_services_by_group(session, group_id)
        service_ids = [service.service_id for service in gsr]
        components = service_info_repo.get_services_by_service_ids_and_group_key(session, group_key, service_ids)
        if upgrade_group_id:
            for component in components:
                if component.tenant_service_group_id == upgrade_group_id:
                    tenant_service_group.append(component)
            return tenant_service_group
        return components

    @staticmethod
    def check_app_name(session: SessionClass, env_id, region_name, group_name, app: Application = None,
                       k8s_app=""):
        """
        检查应用名称
        :param tenant:
        :param region_name:
        :param group_name:
        :param app:
        :return:
        """
        if not group_name:
            raise ServiceHandleException(msg="app name required", msg_show="应用名不能为空")
        if len(group_name) > 128:
            raise ServiceHandleException(msg="app_name illegal", msg_show="应用名称最多支持128个字符")
        r = re.compile('^[a-zA-Z0-9_\\.\\-\\u4e00-\\u9fa5]+$')
        if not r.match(group_name):
            raise ServiceHandleException(msg="app_name illegal", msg_show="应用名称只支持中英文, 数字, 下划线, 中划线和点")
        exist_app = application_repo.get_group_by_unique_key(session=session, tenant_env_id=env_id,
                                                             region_name=region_name, group_name=group_name)
        app_id = app.app_id if app else 0
        if application_repo.is_k8s_app_duplicate(session, env_id, region_name, k8s_app, app_id):
            raise ErrK8sAppExists
        if not exist_app:
            return
        if not app or exist_app.app_id != app.app_id:
            raise ServiceHandleException(msg="app name exist", msg_show="应用名称已存在")

    def create_app(self, session: SessionClass,
                   tenant_env,
                   project_id,
                   region_name,
                   app_name,
                   tenant_name,
                   project_name="",
                   note="",
                   username="",
                   app_store_name="",
                   app_store_url="",
                   app_template_name="",
                   version="",
                   logo="",
                   k8s_app=""):
        """
        创建团队应用
        :param tenant_env:
        :param region_name:
        :param app_name:
        :param note:
        :param username:
        :param app_store_name:
        :param app_store_url:
        :param app_template_name:
        :param version:
        :param logo:
        :return:
        """
        self.check_app_name(session, tenant_env.env_id, region_name, app_name, k8s_app=k8s_app)
        # check parameter for helm app
        app_type = AppType.wutong.name
        if app_store_name or app_template_name or version:
            app_type = AppType.helm.name
            if not app_store_name:
                raise AbortRequest("the field 'app_store_name' is required")
            if not app_store_url:
                raise AbortRequest("the field 'app_store_url' is required")
            if not app_template_name:
                raise AbortRequest("the field 'app_template_name' is required")
            if not version:
                raise AbortRequest("the field 'version' is required")

        app = Application(
            tenant_env_id=tenant_env.env_id,
            project_id=project_id,
            tenant_name=tenant_name,
            env_name=tenant_env.env_alias,
            project_name=project_name,
            region_name=region_name,
            group_name=app_name,
            note=note,
            is_default=False,
            username=username,
            update_time=datetime.now(),
            create_time=datetime.now(),
            app_type=app_type,
            app_store_name=app_store_name,
            app_store_url=app_store_url,
            app_template_name=app_template_name,
            version=version,
            logo=logo,
            k8s_app=k8s_app
        )
        application_repo.create(session=session, model=app)
        self.create_region_app(session=session, env=tenant_env, region_name=region_name, app=app)

        res = jsonable_encoder(app)
        # compatible with the old version
        res["group_id"] = app.ID
        res['application_id'] = app.ID
        res['application_name'] = app.group_name
        return res

    @staticmethod
    def create_region_app(session: SessionClass, env, region_name, app):
        """
        创建集群资源
        :param tenant:
        :param region_name:
        :param app:
        """
        region_app = remote_app_client.create_application(
            session,
            region_name, env, {
                "app_name": app.group_name,
                "app_type": app.app_type,
                "app_store_name": app.app_store_name,
                "app_store_url": app.app_store_url,
                "app_template_name": app.app_template_name,
                "version": app.version,
                "k8s_app": app.k8s_app
            })

        # record the dependencies between region app and console app
        model = RegionApp(region_name=region_name, region_app_id=region_app["app_id"], app_id=app.ID)
        region_app_repo.insert(session=session, model=model)
        # 集群端创建完应用后，再更新控制台的应用名称
        app.k8s_app = region_app["k8s_app"]
        session.merge(app)

    def get_app_detail(self, session: SessionClass, tenant_env, region_name, app_id):
        # app metadata
        app = application_repo.get_by_primary_key(session=session, primary_key=app_id)

        if not app:
            raise ServiceHandleException(msg="not found application", msg_show="应用不存在", status_code=400)

        self.sync_app_services(session=session, tenant_env=tenant_env, region_name=region_name, app_id=app_id)

        res = app.__dict__
        res['app_id'] = app.ID
        res['app_name'] = app.group_name
        res['app_type'] = app.app_type
        res['service_num'] = app_component_relation_repo.count_service_by_app_id(session, app_id)
        res['backup_num'] = backup_record_repo.count_by_app_id(session=session, app_id=app_id)
        res['share_num'] = component_share_repo.count_by_app_id(session=session, app_id=app_id)
        res['ingress_num'] = self.count_ingress_by_app_id(session=session, tenant_env_id=tenant_env.env_id,
                                                          region_name=region_name, app_id=app_id)
        res['config_group_num'] = app_config_group_repo.count_by_region_and_app_id(session, region_name, app_id)
        res['logo'] = app.logo
        res['k8s_app'] = app.k8s_app
        res['can_edit'] = True
        components = app_component_relation_repo.get_services_by_group(session, app_id)
        running_components = remote_component_client.get_dynamic_services_pods(session, region_name, tenant_env,
                                                                               [component.service_id for component in
                                                                                components])
        if running_components.get("list") and len(running_components["list"]) > 0:
            res['can_edit'] = False

        try:
            principal = idaas_api.get_user_info("username", app.username)
            res['principal'] = principal.get_name()
            res['email'] = principal.email
        except ErrUserNotFound:
            res['principal'] = app.username

        res["create_status"] = "complete"
        res["compose_id"] = None
        if app_id != -1:
            compose_group = compose_repo.get_group_compose_by_group_id(session, app_id)
            if compose_group:
                res["create_status"] = compose_group.create_status
                res["compose_id"] = compose_group.compose_id

        return res

    def count_ingress_by_app_id(self, session: SessionClass, tenant_env_id, region_name, app_id):
        # list service_ids
        service_ids = app_component_relation_repo.list_serivce_ids_by_app_id(session, tenant_env_id, region_name,
                                                                             app_id)
        if not service_ids:
            return 0

        region = region_repo.get_by_region_name(session, region_name)

        # count ingress
        count_http_domain = domain_repo.count_by_service_ids(session, region.region_id, service_ids)
        count_tcp_domain = tcp_domain_repo.count_by_service_ids(session, region.region_id, service_ids)
        return count_http_domain + count_tcp_domain

    @staticmethod
    def sync_app_services(tenant_env, session: SessionClass, region_name, app_id):
        """
        同步应用组件
        :param tenant:
        :param region_name:
        :param app_id:
        """
        group_services = base_service.get_group_services_list(session=session, env_id=tenant_env.env_id,
                                                              region_name=region_name, group_id=app_id)
        service_ids = []
        if group_services:
            for service in group_services:
                service_ids.append(service["service_id"])
        app = application_repo.get_group_by_id(session, app_id)
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        if region_app_id:
            body = {"service_ids": service_ids}
            remote_app_client.batch_update_service_app_id(session, region_name, tenant_env, region_app_id, body)
        else:
            create_body = {"app_name": app.group_name, "service_ids": service_ids}
            if app.k8s_app:
                create_body["k8s_app"] = app.k8s_app
            bean = remote_app_client.create_application(session, region_name, tenant_env, create_body)
            model = RegionApp(region_name=region_name, region_app_id=bean["app_id"], app_id=app_id)
            region_app_repo.insert(session=session, model=model)
            app.k8s_app = bean["k8s_app"]
        if not app.k8s_app:
            status = remote_app_client.get_app_status(session, region_name, tenant_env, region_app_id)
            app.k8s_app = status["k8s_app"] if status.get("k8s_app") else ""

    def get_service_status(self, session: SessionClass, tenant_env, service):
        """获取组件状态"""
        start_time = ""
        try:
            body = remote_component_client.check_service_status(
                session,
                service.service_region,
                tenant_env,
                service.service_alias)
            bean = body["bean"]
            status = bean["cur_status"]
            start_time = bean["start_time"]
        except Exception as e:
            logger.exception(e)
            status = "unKnow"
        status_info_map = get_status_info_map(status)
        status_info_map["start_time"] = start_time
        return status_info_map

    @staticmethod
    def list_access_info(session: SessionClass, tenant_env, app_id):
        components = application_service.list_components(session=session, app_id=app_id)
        result = []
        for cpt in components:
            access_type, data = port_service.get_access_info(session=session, tenant_env=tenant_env, service=cpt)
            result.append({
                "access_type": access_type,
                "access_info": data,
            })
        return result

    def create_docker_run_app(self, session: SessionClass, region_name, tenant_env, user, service_cname, docker_cmd,
                              image_type, k8s_component_name):
        is_pass, msg = self.check_service_cname(service_cname=service_cname)
        if not is_pass:
            return 412, msg, None
        new_service = self.__init_docker_image_app(region_name=region_name)
        new_service.tenant_env_id = tenant_env.env_id
        new_service.service_cname = service_cname
        new_service.service_source = image_type
        service_id = make_uuid(tenant_env.env_id)
        service_alias = self.create_service_alias(session, service_id)
        new_service.service_id = service_id
        new_service.service_alias = service_alias
        new_service.creater = user.user_id
        new_service.host_path = "/wtdata/tenant/" + tenant_env.env_id + "/service/" + service_id
        new_service.docker_cmd = docker_cmd
        new_service.image = ""
        new_service.k8s_component_name = k8s_component_name if k8s_component_name else service_alias

        session.add(new_service)
        session.flush()
        logger.debug("service.create", "user:{0} create service from docker run command !".format(user.nick_name))
        ts = (
            session.execute(
                select(Component).where(Component.service_id == new_service.service_id,
                                        Component.tenant_env_id == new_service.tenant_env_id))
        ).scalars().first()

        return 200, "创建成功", ts

    def is_k8s_component_name_duplicate(self, session, app_id, k8s_component_name, component_id=""):
        components = []
        component_list = service_group_relation_repo.get_components_by_app_id(session, app_id)
        component_ids = [component.service_id for component in component_list]
        if len(component_ids) > 0:
            components = service_info_repo.list_by_ids(session, component_ids)
        for component in components:
            if component.k8s_component_name == k8s_component_name and component.service_id != component_id:
                return True
        return False

    def check_service_cname(self, service_cname):
        if not service_cname:
            return False, "组件名称不能为空"
        if len(service_cname) > 100:
            return False, "组件名称最多支持100个字符"
        return True, "success"

    def create_service_alias(self, session: SessionClass, service_id):
        service_alias = "wt" + service_id[-6:]
        svc = (
            session.execute(
                select(Component).where(Component.service_alias == service_alias))
        ).scalars().first()

        if svc is None:
            return service_alias
        service_alias = self.create_service_alias(session, make_uuid(service_id))
        return service_alias

    def __init_docker_image_app(self, region_name):
        """
        初始化docker image创建的组件默认数据,未存入数据库
        """
        tenant_service = Component()
        tenant_service.service_region = region_name
        tenant_service.service_key = "0000"
        tenant_service.desc = "docker run application"
        tenant_service.category = "app_publish"
        tenant_service.setting = ""
        tenant_service.extend_method = ComponentType.stateless_multiple.value
        tenant_service.env = ","
        tenant_service.min_node = 1
        tenant_service.min_memory = 0
        tenant_service.min_cpu = base_service.calculate_service_cpu(0)
        tenant_service.inner_port = 0
        tenant_service.version = "latest"
        tenant_service.namespace = "wutong"
        tenant_service.update_version = 1
        tenant_service.port_type = "multi_outer"
        tenant_service.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenant_service.deploy_version = ""
        tenant_service.git_project_id = 0
        tenant_service.service_type = "application"
        tenant_service.total_memory = 0
        tenant_service.volume_mount_path = ""
        tenant_service.host_path = ""
        tenant_service.code_from = "image_manual"
        tenant_service.language = "docker-image"
        tenant_service.create_status = "creating"
        return tenant_service

    def create_service_source_info(self, session: SessionClass, tenant_env, service, user_name, password):
        params = {
            "tenant_env_id": tenant_env.env_id,
            "service_id": service.service_id,
            "user_name": user_name,
            "password": password,
        }
        add_model: ComponentSourceInfo = ComponentSourceInfo(**params)
        session.add(add_model)
        session.flush()

    def __get_service_region_type(self, service_source):
        if service_source == AppConstants.SOURCE_CODE:
            return "sourcecode"
        elif service_source == AppConstants.DOCKER_RUN or service_source == AppConstants.DOCKER_IMAGE:
            return "docker-run"
        elif service_source == AppConstants.THIRD_PARTY:
            return "third-party-service"

    def __get_service_source(self, service):
        if service.service_source:
            return service.service_source
        else:
            if service.category == "application":
                return AppConstants.SOURCE_CODE
            if service.category == "app_publish":
                return AppConstants.MARKET
            if service.language == "docker-compose":
                return AppConstants.DOCKER_COMPOSE
            if service.language == "docker-image":
                return AppConstants.DOCKER_IMAGE
            return AppConstants.DOCKER_RUN

    def check_service(self, session: SessionClass, tenant_env, service, is_again, user=None):
        body = dict()
        body["tenant_env_id"] = tenant_env.env_id
        body["source_type"] = self.__get_service_region_type(service_source=service.service_source)
        source_body = ""
        service_source = (
            session.execute(select(ComponentSourceInfo).where(ComponentSourceInfo.tenant_env_id == tenant_env.env_id,
                                                              ComponentSourceInfo.service_id == service.service_id))
        ).scalars().first()

        user_name = ""
        password = ""
        service.service_source = self.__get_service_source(service=service)
        if service_source:
            user_name = service_source.user_name
            password = service_source.password
        if service.service_source == AppConstants.SOURCE_CODE:
            service_code_clone_url = service.git_url

            sb = {
                "server_type": service.server_type,
                "repository_url": service_code_clone_url,
                "branch": service.code_version,
                "user": user_name,
                "password": password,
                "tenant_env_id": tenant_env.env_id
            }
            source_body = json.dumps(sb)
        elif service.service_source == AppConstants.DOCKER_RUN or service.service_source == AppConstants.DOCKER_IMAGE:
            source_body = service.docker_cmd
        elif service.service_source == AppConstants.THIRD_PARTY:
            # endpoints信息
            service_endpoints = (
                session.execute(select(ThirdPartyComponentEndpoints).where(
                    ThirdPartyComponentEndpoints.service_id == service.service_id))
            ).scalars().first()

            if service_endpoints and service_endpoints.endpoints_type == "discovery":
                source_body = service_endpoints.endpoints_info

        body["username"] = user_name
        body["password"] = password
        body["source_body"] = source_body
        res, body = remote_build_client.service_source_check(session, service.service_region, tenant_env, body)
        bean = body["bean"]
        service.check_uuid = bean["check_uuid"]
        service.check_event_id = bean["event_id"]
        # 更新创建状态
        if not is_again:
            service.create_status = "checking"

        #
        session.merge(service)

        bean = dict()
        bean.update(service.__dict__)
        bean.update({"user_name": user_name, "password": password})
        bean.update(self.__wrap_check_service(service=service))
        return 200, "success", bean

    def __wrap_check_service(self, service):
        return {
            "service_code_from": service.code_from,
            "service_code_clone_url": service.git_url,
            "service_code_version": service.code_version,
        }

    def create_third_party_service(self, session: SessionClass, tenant_env, service, user_name, is_inner_service=False):
        data = self.__init_third_party_data(tenant_env=tenant_env, service=service, user_name=user_name)
        # env var
        envs_info = (
            session.execute(
                select(ComponentEnvVar.container_port, ComponentEnvVar.name, ComponentEnvVar.attr_name,
                       ComponentEnvVar.attr_value, ComponentEnvVar.is_change, ComponentEnvVar.scope).where(
                    ComponentEnvVar.tenant_env_id == tenant_env.env_id,
                    ComponentEnvVar.service_id == service.service_id))
        ).scalars().all()
        if envs_info:
            data["envs_info"] = list(envs_info)
        # 端口
        ports_info = (
            session.execute(
                select(TeamComponentPort).where(
                    TeamComponentPort.tenant_env_id == tenant_env.env_id,
                    TeamComponentPort.service_id == service.service_id))
        ).scalars().all()

        if ports_info:
            data["ports_info"] = list(jsonable_encoder(ports_info))

        # endpoints
        endpoints = (
            session.execute(
                select(ThirdPartyComponentEndpoints).where(
                    ThirdPartyComponentEndpoints.service_id == service.service_id))
        ).scalars().first()

        if endpoints:
            if endpoints.endpoints_type == "static":
                eps = json.loads(endpoints.endpoints_info)
                validate_endpoints_info(eps)
            endpoints_dict = dict()
            # endpoint source config
            endpoints_dict[endpoints.endpoints_type] = json.loads(endpoints.endpoints_info)
            data["endpoints"] = endpoints_dict
        data["kind"] = service.service_source
        # etcd keys
        data["etcd_key"] = service.check_uuid
        # 数据中心创建
        app_id = (
            session.execute(
                select(ComponentApplicationRelation.group_id).where(
                    ComponentApplicationRelation.service_id == service.service_id,
                    ComponentApplicationRelation.tenant_env_id == service.tenant_env_id,
                    ComponentApplicationRelation.region_name == service.service_region))
        ).scalars().first()

        region_app_id = (
            session.execute(
                select(RegionApp.region_app_id).where(RegionApp.region_name == service.service_region,
                                                      RegionApp.app_id == app_id))
        ).scalars().first()

        data["app_id"] = region_app_id
        if not service.k8s_component_name:
            service.k8s_component_name = service.service_alias
        data["k8s_component_name"] = service.k8s_component_name
        logger.debug('create third component from region, data: {0}'.format(data))
        remote_component_client.create_service(session, service.service_region, tenant_env, data)
        # 将组件创建状态变更为创建完成
        service.create_status = "complete"
        session.merge(service)

        return service

    def __init_third_party_data(self, tenant_env, service, user_name):
        data = dict()
        data["tenant_env_id"] = tenant_env.env_id
        data["service_id"] = service.service_id
        data["service_alias"] = service.service_alias
        data["protocol"] = service.protocol
        data["ports_info"] = []
        data["operator"] = user_name
        data["namespace"] = service.namespace
        data["service_key"] = service.service_key
        data["port_type"] = service.port_type
        return data

    def __init_create_data(self, tenant_env, service, user_name, do_deploy, dep_sids):
        data = dict()
        data["tenant_env_id"] = tenant_env.env_id
        data["service_id"] = service.service_id
        data["service_key"] = service.service_key
        data["comment"] = service.desc
        data["image_name"] = service.image
        data["container_cpu"] = int(service.min_cpu)
        data["container_gpu"] = int(service.container_gpu)
        data["container_memory"] = int(service.min_memory)
        data["volume_path"] = "vol" + service.service_id[0:10]
        data["extend_method"] = service.extend_method
        data["status"] = 0
        data["replicas"] = service.min_node
        data["service_alias"] = service.service_alias
        data["service_version"] = service.version
        data["container_env"] = service.env
        data["container_cmd"] = service.cmd
        data["node_label"] = ""
        data["deploy_version"] = service.deploy_version if do_deploy else None
        data["domain"] = tenant_env.env_name
        data["category"] = service.category
        data["operator"] = user_name
        data["service_type"] = service.service_type
        data["extend_info"] = {"ports": [], "envs": []}
        data["namespace"] = service.namespace
        data["code_from"] = service.code_from
        data["dep_sids"] = dep_sids
        data["port_type"] = service.port_type
        data["ports_info"] = []
        data["envs_info"] = []
        data["volumes_info"] = []
        data["service_name"] = service.service_name
        return data

    def create_region_service(self, session: SessionClass, tenant_env, service, user_name, do_deploy=True,
                              dep_sids=None):
        data = self.__init_create_data(tenant_env=tenant_env, service=service, user_name=user_name, do_deploy=do_deploy,
                                       dep_sids=dep_sids)
        service_dep_relations = dep_relation_repo.get_service_dependencies(session, tenant_env.env_id,
                                                                           service.service_id)
        # handle dependencies attribute
        depend_ids = [{
            "dep_order": dep.dep_order,
            "dep_service_type": dep.dep_service_type,
            "depend_service_id": dep.dep_service_id,
            "service_id": dep.service_id,
            "tenant_env_id": dep.tenant_env_id
        } for dep in service_dep_relations]
        data["depend_ids"] = depend_ids
        # handle port attribute
        ports = port_repo.get_service_ports(session, tenant_env.env_id, service.service_id)
        ports_info = []
        for port in ports:
            ports_info.append({
                'container_port': port.container_port,
                'mapping_port': port.mapping_port,
                'protocol': port.protocol,
                'port_alias': port.port_alias,
                'is_inner_service': port.is_inner_service,
                'is_outer_service': port.is_outer_service,
                'k8s_service_name': port.k8s_service_name

            })

        if ports_info:
            data["ports_info"] = ports_info
        # handle env attribute
        envs_info = []
        envs_info_list = team_env_var_repo.get_service_env(session, tenant_env.env_id, service.service_id)
        for envs in envs_info_list:
            envs_info.append({
                'container_port': envs.container_port,
                'name': envs.name,
                'attr_name': envs.attr_name,
                'attr_value': envs.attr_value,
                'is_change': envs.is_change,
                'scope': envs.scope
            })
        if envs_info:
            data["envs_info"] = envs_info
        # handle volume attribute
        volume_info = volume_repo.get_service_volumes_with_config_file(session, service.service_id)
        if volume_info:
            volume_list = []
            for volume in volume_info:
                volume_info = jsonable_encoder(volume)
                if volume.volume_type == "config-file":
                    config_file = volume_repo.get_service_config_file(session, volume)
                    if config_file:
                        volume_info.update({"file_content": config_file.file_content})
                volume_list.append(volume_info)
            data["volumes_info"] = volume_list

        logger.debug(tenant_env.tenant_name + " start create_service:" + datetime.now().strftime('%Y%m%d%H%M%S'))
        # handle dep volume attribute
        mnt_info = mnt_repo.get_service_mnts(session, service.tenant_env_id, service.service_id)
        if mnt_info:
            data["dep_volumes_info"] = [{
                "dep_service_id": mnt.dep_service_id,
                "volume_path": mnt.mnt_dir,
                "volume_name": mnt.mnt_name
            } for mnt in mnt_info]

        # etcd keys
        data["etcd_key"] = service.check_uuid

        # runtime os name
        data["os_type"] = label_service.get_service_os_name(session=session, service=service)

        # app id
        app_id = service_group_relation_repo.get_group_id_by_service(session, service)
        region_app_id = region_app_repo.get_region_app_id(session, service.service_region, app_id)
        data["app_id"] = region_app_id

        # handle component monitor
        monitors = []
        monitors_list = service_monitor_service.get_component_service_monitors(session=session,
                                                                               tenant_env_id=tenant_env.env_id,
                                                                               service_id=service.service_id)
        for monitor in monitors_list:
            monitors.append({
                'name': monitor.name,
                'service_show_name': monitor.service_show_name,
                'path': monitor.path,
                'port': monitor.port,
                'interval': monitor.interval
            })
        if monitors:
            data["component_monitors"] = monitors

        # handle component probe
        # .values(
        #     'service_id', 'probe_id', 'mode', 'scheme', 'path', 'port', 'cmd', 'http_header', 'initial_delay_second',
        #     'period_second', 'timeout_second', 'is_used', 'failure_threshold', 'success_threshold')
        probes = probe_repo.get_service_probe(session, service.service_id)
        if probes:
            probes = probes
            for i in range(len(probes)):
                probes[i]['is_used'] = 1 if probes[i]['is_used'] else 0
            data["component_probes"] = probes
        # handle gateway rules
        http_rules = domain_repo.get_service_domains(session, service.service_id)
        if http_rules:
            rule_data = []
            for rule in http_rules:
                rule_data.append(self.__init_http_rule_for_region(session, tenant_env, service, rule, user_name))
            data["http_rules"] = rule_data

        stream_rule = tcp_domain_repo.get_service_tcpdomains(session, service.service_id)
        if stream_rule:
            rule_data = []
            for rule in stream_rule:
                rule_data.append(self.__init_stream_rule_for_region(service, rule))
            data["tcp_rules"] = rule_data
        if not service.k8s_component_name:
            service.k8s_component_name = service.service_alias
        data["k8s_component_name"] = service.k8s_component_name
        # create in region
        remote_component_client.create_service(session, service.service_region, tenant_env, data)
        # conponent install complete
        service.create_status = "complete"
        # service_repo.save_service(service)
        return service

    def __init_stream_rule_for_region(self, service, rule):

        data = dict()
        data["tcp_rule_id"] = rule.tcp_rule_id
        data["service_id"] = service.service_id
        data["container_port"] = rule.container_port
        hp = rule.end_point.split(":")
        if len(hp) == 2:
            data["ip"] = hp[0]
            data["port"] = int(hp[1])
        if rule.rule_extensions:
            rule_extensions = []
            for ext in rule.rule_extensions.split(","):
                ext_info = ext.split(":")
                if len(ext_info) == 2:
                    rule_extensions.append({"key": ext_info[0], "value": ext_info[1]})
            data["rule_extensions"] = rule_extensions
        return data

    def __init_http_rule_for_region(self, session: SessionClass, tenant_env, service, rule, user_name):
        certificate_info = None
        if rule.certificate_id:
            certificate_info = (
                session.execute(
                    select(ServiceDomainCertificate).where(ServiceDomainCertificate.ID == int(rule.certificate_id)))
            ).scalars().first()

        data = dict()
        data["uuid"] = make_uuid(rule.domain_name)
        data["domain"] = rule.domain_name
        data["service_id"] = service.service_id
        data["tenant_env_id"] = tenant_env.env_id
        data["env_name"] = tenant_env.env_name
        data["protocol"] = rule.protocol
        data["container_port"] = int(rule.container_port)
        data["add_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data["add_user"] = user_name
        data["http_rule_id"] = rule.http_rule_id
        data["path"] = rule.domain_path
        data["cookie"] = rule.domain_cookie
        data["header"] = rule.domain_heander
        data["weight"] = rule.the_weight
        if rule.rule_extensions:
            rule_extensions = []
            for ext in rule.rule_extensions.split(","):
                ext_info = ext.split(":")
                if len(ext_info) == 2:
                    rule_extensions.append({"key": ext_info[0], "value": ext_info[1]})
            data["rule_extensions"] = rule_extensions
        data["certificate"] = ""
        data["private_key"] = ""
        data["certificate_name"] = ""
        data["certificate_id"] = ""
        if certificate_info:
            data["certificate"] = base64.b64decode(certificate_info.certificate).decode()
            data["private_key"] = certificate_info.private_key
            data["certificate_name"] = certificate_info.alias
            data["certificate_id"] = certificate_info.certificate_id
        data["path_rewrite"] = rule.path_rewrite
        data["rewrites"] = json.loads(rule.rewrites if rule.rewrites else "[]")
        return data

    def get_service_mnts_filter_volume_type(self, session: SessionClass, tenant_env_id, service_id):
        query = "mnt.tenant_env_id = '%s' and mnt.service_id = '%s'" % (tenant_env_id, service_id)
        sql = """
        select mnt.mnt_name,
            mnt.mnt_dir,
            mnt.dep_service_id,
            mnt.service_id,
            mnt.tenant_env_id,
            volume.volume_type,
            volume.ID as volume_id
        from tenant_service_mnt_relation as mnt
                 inner join tenant_service_volume as volume
                            on mnt.dep_service_id = volume.service_id and mnt.mnt_name = volume.volume_name
        where {};
        """.format(query)
        result = (
            session.execute(sql)
        ).scalars().all()

        dep_mnts = []
        for real_dep_mnt in result:
            mnt = TeamComponentMountRelation(
                tenant_env_id=real_dep_mnt.get("tenant_env_id"),
                service_id=real_dep_mnt.get("service_id"),
                dep_service_id=real_dep_mnt.get("dep_service_id"),
                mnt_name=real_dep_mnt.get("mnt_name"),
                mnt_dir=real_dep_mnt.get("mnt_dir"))
            mnt.volume_type = real_dep_mnt.get("volume_type")
            mnt.volume_id = real_dep_mnt.get("volume_id")
            dep_mnts.append(mnt)
        return dep_mnts

    def create_deploy_relation_by_service_id(self, session: SessionClass, service_id):
        deploy_relation = (
            session.execute(select(DeployRelation).where(DeployRelation.service_id == service_id))
        ).scalars().first()

        if not deploy_relation:
            secretkey = ''.join(random.sample(string.ascii_letters + string.digits, 8))
            secret_key = base64.b64encode(pickle.dumps({"secret_key": secretkey}))
            add_model: DeployRelation = DeployRelation(service_id=service_id, secret_key=secret_key, key_type="")
            session.add(add_model)
            session.flush()

    def create_kubernetes_endpoints(self, session: SessionClass, tenant_env, component, service_name, namespace):
        endpoints = (
            session.execute(
                select(ThirdPartyComponentEndpoints).where(
                    ThirdPartyComponentEndpoints.service_id == component.service_id))
        ).scalars().first()
        if endpoints:
            return
        data = {
            "tenant_env_id": tenant_env.env_id,
            "service_id": component.service_id,
            "service_cname": component.service_cname,
            "endpoints_info": json.dumps({
                'serviceName': service_name,
                'namespace': namespace
            }),
            "endpoints_type": "kubernetes"
        }
        add_model: ThirdPartyComponentEndpoints = ThirdPartyComponentEndpoints(**data)
        session.add(add_model)
        # session.flush()

        return add_model

    @staticmethod
    def check_endpoints(endpoints):
        if not endpoints:
            return ["parameter error"], False
        total_errs = []
        is_domain = False
        for endpoint in endpoints:
            # TODO: ipv6
            if "https://" in endpoint:
                endpoint = endpoint.partition("https://")[2]
            if "http://" in endpoint:
                endpoint = endpoint.partition("http://")[2]
            if ":" in endpoint:
                endpoint = endpoint.rpartition(":")[0]
            errs, domain_ip = validate_endpoint_address(endpoint)
            if domain_ip:
                is_domain = True
            total_errs.extend(errs)
        if len(endpoints) > 1 and is_domain:
            logger.error("endpoint: {}; do not support multi domain endpoint".format(endpoint))
            return ["do not support multi domain endpoint"], is_domain
        elif len(endpoints) == 1 and is_domain:
            return [], is_domain
        else:
            return total_errs, False

    def create_third_party_app(self,
                               session: SessionClass,
                               region,
                               tenant_env,
                               user,
                               service_cname,
                               static_endpoints,
                               endpoints_type,
                               source_config=None,
                               k8s_component_name=""):
        if source_config is None:
            source_config = {}
        new_service = self._create_third_component(session, tenant_env, region, user, service_cname, k8s_component_name)
        session.add(new_service)
        session.flush()
        if endpoints_type == "kubernetes":
            self.create_kubernetes_endpoints(session, tenant_env, new_service, source_config["service_name"],
                                             source_config["namespace"])
        if endpoints_type == "static" and static_endpoints:
            errs, is_domain = self.check_endpoints(static_endpoints)
            if errs:
                return 400, "组件地址不合法", None
            port_list = []
            prefix = ""
            protocol = "tcp"
            for endpoint in static_endpoints:
                if 'https://' in endpoint:
                    endpoint = endpoint.split('https://')[1]
                    prefix = "https"
                    protocol = "http"
                if 'http://' in endpoint:
                    endpoint = endpoint.split('http://')[1]
                    prefix = "http"
                    protocol = "http"
                if ':' in endpoint:
                    port_list.append(endpoint.split(':')[1])
            if len(port_list) == 0 and is_domain is True and prefix != "":
                port_list.append(443 if prefix == "https" else 80)
            port_re = list(set(port_list))
            if len(port_re) == 1:
                port = int(port_re[0])
                if port:
                    port_alias = new_service.service_alias.upper().replace("-", "_") + str(port)
                    service_port = {
                        "tenant_env_id": tenant_env.env_id,
                        "service_id": new_service.service_id,
                        "container_port": port,
                        "mapping_port": port,
                        "protocol": protocol,
                        "port_alias": port_alias,
                        "is_inner_service": False,
                        "is_outer_service": False,
                        "k8s_service_name": new_service.service_alias + "-" + str(port),
                    }
                    port_repo.add_service_port(session, **service_port)
            self.update_or_create_endpoints(session, tenant_env, new_service, static_endpoints)

        ts = (
            session.execute(
                select(Component).where(Component.service_id == new_service.service_id,
                                        Component.tenant_env_id == new_service.tenant_env_id))
        ).scalars().first()

        return ts

    def update_or_create_endpoints(self, session: SessionClass, tenant_env, service, service_endpoints):
        endpoints = (
            session.execute(
                select(ThirdPartyComponentEndpoints).where(
                    ThirdPartyComponentEndpoints.service_id == service.service_id))
        ).scalars().first()
        if not service_endpoints:
            session.execute(
                delete(ThirdPartyComponentEndpoints).where(ThirdPartyComponentEndpoints.ID == endpoints.ID)
            )
        elif endpoints:
            endpoints.endpoints_info = json.dumps(service_endpoints)
        else:
            data = {
                "tenant_env_id": tenant_env.env_id,
                "service_id": service.service_id,
                "service_cname": service.service_cname,
                "endpoints_info": json.dumps(service_endpoints),
                "endpoints_type": "static"
            }
            endpoints = ThirdPartyComponentEndpoints(**data)
            session.add(endpoints)

        return endpoints

    def _create_third_component(self, session: SessionClass, tenant_env, region_name, user, service_cname,
                                k8s_component_name=""):
        service_cname = service_cname.rstrip().lstrip()
        is_pass, msg = self.check_service_cname(service_cname=service_cname)
        if not is_pass:
            raise ServiceHandleException(msg=msg, msg_show="组件名称不合法", status_code=400, error_code=400)
        component = self.__init_third_party_app(region_name)
        component.tenant_env_id = tenant_env.env_id
        component.service_cname = service_cname
        service_id = make_uuid(tenant_env.env_id)
        service_alias = self.create_service_alias(session, service_id)
        component.service_id = service_id
        component.service_alias = service_alias
        component.creater = user.user_id
        component.server_type = ''
        component.protocol = 'tcp'
        component.k8s_component_name = k8s_component_name if k8s_component_name else service_alias
        return component

    def __init_third_party_app(self, region):
        """
        初始化创建外置组件的默认数据,未存入数据库
        """
        tenant_service = Component()
        tenant_service.service_region = region
        tenant_service.service_key = "application"
        tenant_service.desc = "third party service"
        tenant_service.category = "application"
        tenant_service.image = "third_party"
        tenant_service.cmd = ""
        tenant_service.setting = ""
        tenant_service.extend_method = ComponentType.stateless_multiple.value
        tenant_service.env = ""
        tenant_service.min_node = 0
        tenant_service.min_memory = 0
        tenant_service.min_cpu = 0
        tenant_service.version = "81701"
        tenant_service.namespace = "third_party"
        tenant_service.update_version = 1
        tenant_service.port_type = "multi_outer"
        tenant_service.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenant_service.deploy_version = ""
        tenant_service.git_project_id = 0
        tenant_service.service_type = "application"
        tenant_service.total_memory = 0
        tenant_service.volume_mount_path = ""
        tenant_service.host_path = ""
        tenant_service.service_source = AppConstants.THIRD_PARTY
        tenant_service.create_status = "creating"
        return tenant_service

    def list_releases(self, session, region_name: str, tenant_env, app_id: int):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        return remote_app_client.list_app_releases(session, region_name, tenant_env, region_app_id)

    def get_region_app_statuses(self, session: SessionClass, tenant_env, region_name, app_ids):
        # Obtain the application ID of the cluster and
        # record the corresponding relationship of the console application ID
        region_apps = region_app_repo.list_by_app_ids(session, region_name, app_ids)
        region_app_ids = []
        app_id_rels = dict()
        for region_app in region_apps:
            region_app_ids.append(region_app.region_app_id)
            app_id_rels[region_app.app_id] = region_app.region_app_id
        # Get the status of cluster application
        resp = remote_build_client.list_app_statuses_by_app_ids(session, tenant_env, region_name,
                                                                {"app_ids": region_app_ids})
        app_statuses = resp.get("list", [])
        # The relationship between cluster application ID and state
        # is transformed into that between console application ID and state
        # Returns the relationship between console application ID and status
        app_id_status_rels = dict()
        region_app_id_status_rels = dict()
        if app_statuses:
            for app_status in app_statuses:
                region_app_id_status_rels[app_status.get("app_id", "")] = app_status
        for app_id in app_ids:
            if not app_id_rels.get(app_id):
                continue
            app_id_status_rels[app_id] = region_app_id_status_rels.get(app_id_rels[app_id])
        return app_id_status_rels

    def get_multi_apps_all_info(self, session: SessionClass, app_ids, region, tenant_env, status="all"):
        count = {
            "running": 0,
            "closed": 0,
            "abnormal": 0,
            "nil": 0,
            "starting": 0,
            "deployed": 0,
            "unknown": 0,
            "": 0
        }
        app_list = application_repo.get_multi_app_info(session, app_ids)
        service_list = service_info_repo.get_services_in_multi_apps_with_app_info(session, app_ids)
        service_ids = [service.service_id for service in service_list]
        status_list = base_service.status_multi_service(session=session, region=region, tenant_env=tenant_env,
                                                        service_ids=service_ids)
        service_status = dict()
        if status_list is None:
            raise ServiceHandleException(msg="query status failure", msg_show="查询组件状态失败")
        for status_dict in status_list:
            service_status[status_dict["service_id"]] = status_dict
        app_id_statuses = self.get_region_app_statuses(session=session, tenant_env=tenant_env, region_name=region,
                                                       app_ids=app_ids)
        apps = dict()
        for app in app_list:
            app_status = app_id_statuses.get(app.ID)
            if app_status:
                count[app_status["status"].lower()] += 1
                if status == "all" or app_status["status"] == status.upper():
                    apps[app.ID] = {
                        "group_id": app.ID,
                        "update_time": app.update_time,
                        "create_time": app.create_time,
                        "group_name": app.group_name,
                        "group_note": app.note,
                        "service_list": [],
                        "used_mem": app_status.get("memory", 0) if app_status else 0,
                        "status": app_status.get("status", "UNKNOWN") if app_status else "UNKNOWN",
                        "logo": app.logo,
                        "accesses": [],
                    }
        # 获取应用下组件的访问地址
        accesses = port_service.list_access_infos(session=session, tenant_env=tenant_env, services=service_list)
        for service in service_list:
            svc_sas = service_status.get(service.service_id, {"status": "failure",
                                                              "used_mem": 0})
            if service.group_id in apps.keys():
                apps[service.group_id]["service_list"].append({"status": svc_sas["status"],
                                                               "min_memory": service.min_memory})
                apps[service.group_id]["accesses"].append(accesses[service.service_id])

        re_app_list = []
        for a in app_list:
            app = apps.get(a.ID)
            if app:
                app["services_num"] = len(app["service_list"])
                if not app.get("run_service_num"):
                    app["run_service_num"] = 0
                if not app.get("used_mem"):
                    app["used_mem"] = 0
                if not app.get("allocate_mem"):
                    app["allocate_mem"] = 0
                for svc in app["service_list"]:
                    app["allocate_mem"] += svc["min_memory"]
                    if svc["status"] in ["running", "upgrade", "starting", "some_abnormal"]:
                        # if is running used_mem ++
                        app["run_service_num"] += 1
                if app["used_mem"] > app["allocate_mem"]:
                    app["allocate_mem"] = app["used_mem"]
                app.pop("service_list")
                re_app_list.append(app)
        return re_app_list, count

    def get_groups_and_services(self, session: SessionClass, tenant_env, region, query="", app_type=""):
        groups = application_repo.get_tenant_region_groups(session, tenant_env.env_id, region, query, app_type)
        services = service_info_repo.get_tenant_region_services(session, region, tenant_env.env_id)

        sl = []
        for ser in services:
            s = {"service_id": ser.service_id, "service_cname": ser.service_cname, "service_alias": ser.service_alias}
            sl.append(s)

        service_id_map = {s["service_id"]: s for s in sl}
        service_group_relations = app_component_relation_repo.get_service_group_relation_by_groups(
            session, [g.ID for g in groups])
        service_group_map = {sgr.service_id: sgr.group_id for sgr in service_group_relations}
        group_services_map = dict()
        for k, v in list(service_group_map.items()):
            service_list = group_services_map.get(v, None)
            service_info = service_id_map.get(k, None)
            if service_info:
                if not service_list:
                    group_services_map[v] = [service_info]
                else:
                    service_list.append(service_info)
                service_id_map.pop(k)

        result = []
        for g in groups:
            bean = dict()
            bean["group_id"] = g.ID
            bean["group_name"] = g.group_name
            bean["service_list"] = group_services_map.get(g.ID)
            result.insert(0, bean)

        return result

    def create_default_app(self, session: SessionClass, tenant_env, region_name):
        app = application_repo.get_or_create_default_group(session, tenant_env.env_id, region_name)
        self.create_region_app(session=session, env=tenant_env, region_name=region_name, app=app)
        return jsonable_encoder(app)

    @staticmethod
    def get_app_status(session: SessionClass, tenant_env, region_name, app_id):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        status = remote_app_client.get_app_status(session, region_name, tenant_env, region_app_id)
        if status.get("status") == "NIL":
            status["status"] = None
        overrides = status.get("overrides", [])
        if overrides:
            status["overrides"] = [{override.split("=")[0]: override.split("=")[1]} for override in overrides]
        return status

    @staticmethod
    def get_component_and_resource_by_group_ids(session: SessionClass, app_id, group_ids):
        gsr = app_component_relation_repo.get_services_by_group(session, app_id)
        gsr_service_ids = [service.service_id for service in gsr]
        components = service_info_repo.get_services_by_service_group_ids(session, gsr_service_ids, group_ids)
        service_ids = [component.service_id for component in components]
        data = service_source_repo.get_service_sources_by_service_ids(session, service_ids)
        return components, data

    def get_services_group_name(self, session: SessionClass, service_ids):
        return app_component_relation_repo.get_group_by_service_ids(session, service_ids)

    @staticmethod
    def list_components(session: SessionClass, app_id):
        service_groups = app_component_relation_repo.get_services_by_group(session, app_id)
        result = service_info_repo.list_by_ids(session=session, service_ids=[sg.service_id for sg in service_groups])
        return result

    def check_governance_mode(self, session, tenant_env, region_name, app_id, governance_mode):
        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        return remote_app_client.check_app_governance_mode(session,
                                                           region_name, tenant_env, region_app_id,
                                                           governance_mode)

    def get_app_by_app_id(self, session, app_id):
        return session.execute(select(Application).where(
            Application.ID == app_id
        )).scalars().first()

    def delete_app(self, session: SessionClass, tenant_env, region_name, app_id, app_type):
        if app_type == AppType.helm.name:
            self._delete_helm_app(session, tenant_env, region_name, app_id)

            return
        self._delete_wutong_app(session, tenant_env, region_name, app_id)

    def _delete_helm_app(self, session: SessionClass, tenant_env, region_name, app_id, user=None):
        """
        For helm application,  can be delete directly, regardless of whether there are components
        """
        # delete components
        components = self.list_components(session=session, app_id=app_id)
        session.execute(
            delete(ComponentApplicationRelation).where(ComponentApplicationRelation.group_id == app_id)
        )
        # avoid circular import
        from service.app_actions.app_manage import app_manage_service
        app_manage_service.delete_components(session=session, tenant_env=tenant_env, components=components, user=user)
        self._delete_app(session, tenant_env, region_name, app_id)

    def _delete_wutong_app(self, session: SessionClass, tenant_env, region_name, app_id):
        """
        For wutong application, with components, cannot be deleted directly
        """
        service = (
            session.execute(
                select(ComponentApplicationRelation).where(ComponentApplicationRelation.group_id == app_id))
        ).scalars().first()

        if service:
            raise AbortRequest(msg="the app still has components", msg_show="当前应用内存在组件，无法删除")

        self._delete_app(session, tenant_env, region_name, app_id)

    def _delete_app(self, session: SessionClass, tenant_env, region_name, app_id):

        # 删除group
        session.execute(
            delete(Application).where(Application.ID == app_id)
        )
        # 级联删除升级记录
        session.execute(
            delete(ApplicationUpgradeRecord).where(ApplicationUpgradeRecord.group_id == app_id)
        )

        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        if not region_app_id:
            return
        keys = []
        migrate_record = (
            session.execute(
                select(GroupAppMigrateRecord).where(GroupAppMigrateRecord.original_group_id == app_id))
        ).scalars().all()

        if migrate_record:
            for record in migrate_record:
                keys.append(record.restore_id)
        remote_app_client.delete_app(session, region_name, tenant_env, region_app_id, {"etcd_keys": keys})

    def add_component_to_app(self, session: SessionClass, tenant_env, region_name, app_id, component_id):
        if not app_id:
            return
        app_id = int(app_id)
        if app_id > 0:
            group = (
                session.execute(select(Application).where(Application.ID == app_id))
            ).scalars().first()

            if not group:
                raise ErrApplicationNotFound
            add_model: ComponentApplicationRelation = ComponentApplicationRelation(service_id=component_id,
                                                                                   group_id=app_id,
                                                                                   tenant_env_id=tenant_env.env_id,
                                                                                   region_name=region_name)
            session.add(add_model)
            session.flush()
        return 200, "success"

    def delete_service_group_relation_by_service_id(self, session: SessionClass, service_id):
        app_component_relation_repo.delete_relation_by_service_id(session, service_id)

    def update_or_create_service_group_relation(self, session: SessionClass, tenant_env, service, group_id):
        gsr = app_component_relation_repo.get_group_by_service_id(session, service.service_id)
        if gsr:
            gsr.group_id = group_id
            app_component_relation_repo.save(session=session, gsr=gsr)
        else:
            params = {
                "service_id": service.service_id,
                "group_id": group_id,
                "tenant_env_id": tenant_env.env_id,
                "region_name": service.service_region
            }
            app_component_relation_repo.create_service_group_relation(session, **params)

    def get_group_by_id(self, session: SessionClass, tenant_env, region, group_id):
        principal_info = dict()
        principal_info["email"] = ""
        principal_info["is_delete"] = False
        group = application_repo.get_by_primary_key(session=session, primary_key=group_id)
        if not group:
            raise ServiceHandleException(status_code=404, msg="app not found", msg_show="目标应用不存在")
        try:
            user = idaas_api.get_user_info("username", group.username)
            principal_info["real_name"] = user.real_name
            principal_info["username"] = user.nick_name
            principal_info["email"] = user.email
        except ErrUserNotFound:
            principal_info["is_delete"] = True
            principal_info["real_name"] = group.username
            principal_info["username"] = group.username
        return {"group_id": group.ID, "group_name": group.group_name, "group_note": group.note,
                "principal": principal_info}

    def get_group_services(self, session: SessionClass, group_id):
        """查询某一应用下的组件"""
        gsr = app_component_relation_repo.get_services_by_group(session, group_id)
        service_ids = [gs.service_id for gs in gsr]
        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        return services

    def get_group_service(self, session: SessionClass, tenant_env_id, response_region, group_id):
        """查询某一应用下的组件"""
        gsr = app_component_relation_repo.get_services_by_tenant_env_id_and_group(session,
                                                                                  tenant_env_id,
                                                                                  response_region,
                                                                                  group_id)
        return gsr

    def sync_envs(self, session, tenant_name, region_name, region_app_id, components, envs):
        # make sure attr_value is string.
        for env in envs:
            if type(env.attr_value) != str:
                env.attr_value = str(env.attr_value)

        new_components = []
        for cpt in components:
            if cpt.create_status != "complete":
                continue

            component_base = jsonable_encoder(cpt)
            component_base["component_id"] = component_base["service_id"]
            component_base["component_name"] = component_base["service_name"]
            component_base["component_alias"] = component_base["service_alias"]
            component_base["container_cpu"] = cpt.min_cpu
            component_base["container_memory"] = cpt.min_memory
            component_base["replicas"] = cpt.min_node
            component = {
                "component_base": component_base,
                "envs": [jsonable_encoder(env) for env in envs if env.service_id == cpt.component_id]
            }
            new_components.append(component)

        if not new_components:
            return

        body = {
            "components": new_components,
        }
        remote_app_client.sync_components(session, tenant_name, region_name, region_app_id, body)

    def update_governance_mode(self, session, tenant_env, region_name, app_id, governance_mode):
        # update the value of host env. eg. MYSQL_HOST
        component_ids = app_component_relation_repo.list_serivce_ids_by_app_id(session=session,
                                                                               tenant_env_id=tenant_env.env_id,
                                                                               region_name=region_name, app_id=app_id)

        components = service_info_repo.list_by_ids(session=session, service_ids=component_ids)
        components = {cpt.component_id: cpt for cpt in components}

        ports = port_repo.list_inner_ports_by_service_ids(session, tenant_env.env_id, component_ids)
        ports = {port.service_id + str(port.container_port): port for port in ports}

        envs = env_var_repo.list_envs_by_component_ids(session, tenant_env.env_id, component_ids)
        for env in envs:
            if not env.is_host_env():
                continue
            cpt = components.get(env.service_id)
            if not cpt:
                continue
            port = ports.get(env.service_id + str(env.container_port))
            if not port:
                continue
            if governance_mode in GovernanceModeEnum.use_k8s_service_name_governance_modes():
                env.attr_value = port.k8s_service_name if port.k8s_service_name else cpt.service_alias + "-" + str(
                    port.container_port)
            else:
                env.attr_value = "127.0.0.1"
        session.add_all(envs)
        application_repo.update_governance_mode(session, tenant_env.env_id, region_name, app_id, governance_mode)

        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        self.sync_envs(session, tenant_env.tenant_name, region_name, region_app_id, components.values(), envs)
        remote_app_client.update_app(session, region_name, tenant_env, region_app_id,
                                     {"governance_mode": governance_mode})

    def list_kubernetes_services(self, session, tenant_env_id, region_name, app_id):
        # list service_ids
        service_ids = app_component_relation_repo.list_serivce_ids_by_app_id(session=session,
                                                                             tenant_env_id=tenant_env_id,
                                                                             region_name=region_name, app_id=app_id)
        if not service_ids:
            return []
        # service_id to service_alias
        services = service_info_repo.list_by_ids(session=session, service_ids=service_ids)
        service_aliases = {service.service_id: service.service_alias for service in services}
        service_cnames = {service.service_id: service.service_cname for service in services}

        ports = port_repo.list_inner_ports_by_service_ids(session, tenant_env_id, service_ids)
        # build response
        k8s_services = []
        for port in ports:
            # set service_alias_container_port as default kubernetes service name
            k8s_service_name = port.k8s_service_name if port.k8s_service_name else service_aliases[
                                                                                       port.service_id] + "-" + str(
                port.container_port)
            k8s_services.append({
                "service_id": port.service_id,
                "service_cname": service_cnames[port.service_id],
                "port": port.container_port,
                "port_alias": port.port_alias,
                "k8s_service_name": k8s_service_name,
            })

        return k8s_services

    def update_kubernetes_services(self, session, tenant_env, region_name, app, k8s_services):
        port_service.check_k8s_service_names(session, tenant_env.env_id, k8s_services)

        # check if the given k8s_services belong to the app based on app_id
        app_component_ids = app_component_relation_repo.list_serivce_ids_by_app_id(session=session,
                                                                                   tenant_env_id=tenant_env.env_id,
                                                                                   region_name=region_name,
                                                                                   app_id=app.app_id)
        component_ids = []
        for k8s_service in k8s_services:
            if k8s_service["service_id"] not in app_component_ids:
                raise AbortRequest("service({}) not belong to app({})".format(k8s_service["service_id"], app.app_id))
            component_ids.append(k8s_service["service_id"])

        port_service.update_by_k8s_services(session, tenant_env, region_name, app, k8s_services)

    def _parse_overrides(self, overrides):
        new_overrides = []
        for key in overrides:
            val = overrides[key]
            if type(val) == int:
                val = str(val)
            if type(val) != str:
                raise AbortRequest("wrong override value which type is {}".format(type(val)))
            new_overrides.append(key + "=" + val)
        return new_overrides

    def update_group(self,
                     session,
                     tenant_env,
                     region_name,
                     app_id,
                     app_name,
                     note="",
                     username=None,
                     overrides="",
                     version="",
                     revision=0,
                     logo="",
                     k8s_app=""):
        # check app id
        if not app_id or not str.isdigit(app_id) or int(app_id) < 0:
            raise ServiceHandleException(msg="app id illegal", msg_show="应用ID不合法")
        data = {
            "note": note,
            "logo": logo,
        }
        if username:
            # check username
            try:
                data["username"] = username
                idaas_api.get_user_info("username", username)
            except ErrUserNotFound:
                raise ServiceHandleException(msg="user not exists", msg_show="用户不存在,请选择其他应用负责人", status_code=404)

        app = application_repo.get_group_by_id(session, app_id)

        # check app name
        if app_name:
            self.check_app_name(session, tenant_env.env_id, region_name, app_name, app,
                                k8s_app=k8s_app)
        if overrides:
            overrides = self._parse_overrides(overrides)

        if app_name:
            data["group_name"] = app_name
        if version:
            data["version"] = version

        region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
        bean = remote_app_client.update_app(session, region_name, tenant_env, region_app_id, {
            "overrides": overrides,
            "version": version,
            "revision": revision,
            "k8s_app": k8s_app
        })
        data["k8s_app"] = bean["k8s_app"]
        application_repo.update(session, app_id, **data)

    def get_apps_by_plat(self, session, env_id, project_id, app_name):
        sql = "select ID, group_name, k8s_app, note, logo, tenant_name, env_name, project_name " \
              "from service_group where 1"
        params = {
            "env_id": env_id,
            "project_id": project_id,
            "app_name": app_name
        }
        if env_id:
            sql += " and tenant_env_id=:env_id"
        if project_id:
            sql += " and project_id=:project_id"
        if app_name:
            sql += " and group_name like '%' :app_name '%'"

        apps = session.execute(sql, params).fetchall()
        return apps


class ApplicationVisitService(object):
    def create_app_visit_record(self, session, **params):
        app_visit_record = ApplicationVisitRecord(**params)
        session.add(app_visit_record)
        session.flush()

    def update_app_visit_record_by_user_app(self, session, user_id, app_id):
        session.execute(update(ApplicationVisitRecord).where(
            ApplicationVisitRecord.user_id == user_id,
            ApplicationVisitRecord.app_id == app_id
        ))

    def get_app_visit_record_by_user(self, session, user_id):
        return session.execute(select(ApplicationVisitRecord).where(
            ApplicationVisitRecord.user_id == user_id
        ).order_by(ApplicationVisitRecord.visit_time.asc()).limit(5)).scalars().all()

    def get_app_visit_record_by_user_app(self, session, user_id, app_id):
        return session.execute(select(ApplicationVisitRecord).where(
            ApplicationVisitRecord.user_id == user_id,
            ApplicationVisitRecord.app_id == app_id
        )).scalars().first()


application_service = ApplicationService()
application_visit_service = ApplicationVisitService()
