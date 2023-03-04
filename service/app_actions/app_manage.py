import datetime
import json

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select, delete, func, or_
from starlette.responses import JSONResponse

from clients.remote_app_client import remote_app_client
from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.enum.component_enum import ComponentType, is_state, is_singleton
from core.setting import settings
from core.utils import slug_util
from core.utils.constants import AppConstants
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.bcode import ErrThirdComponentStartFailed
from exceptions.exceptions import ErrChangeServiceType, TenantNotExistError, NoAccessKeyErr
from exceptions.main import AbortRequest, ServiceHandleException
from models.application.models import ComponentApplicationRelation, ComposeServiceRelation, ConfigGroupService, \
    ServiceShareRecordEvent, Application
from models.component.models import ComponentEvent, ComponentCreateStep, ComponentAttachInfo, ComponentProbe, \
    TeamComponentInfoDelete, ComponentEnvVar, TeamComponentAuth, TeamComponentMountRelation, TeamComponentPort, \
    TeamComponentVolume, ComponentSourceInfo, ComponentLabels, TeamServiceBackup, \
    ComponentGraph, \
    ComponentMonitor, TeamComponentInfo, TeamComponentEnv, ComponentExtendMethod, TeamApplication, \
    ThirdPartyComponentEndpoints
from models.region.models import RegionApp
from models.relate.models import TeamComponentRelation
from models.teams import ServiceDomain, ServiceTcpDomain, TeamEnvInfo
from repository.application.app_repository import recycle_bin_repo, relation_recycle_bin_repo, delete_service_repo
from repository.application.application_repo import application_repo
from repository.application.config_group_repo import app_config_group_service_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.component_repo import tenant_service_group_repo, service_source_repo
from repository.component.compose_repo import compose_relation_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import dep_relation_repo, mnt_repo, auth_repo, \
    port_repo, volume_repo, service_attach_repo, create_step_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_group_relation_repo import service_group_relation_repo
from repository.component.service_label_repo import service_label_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_share_repo import component_share_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo
from repository.region.region_app_repo import region_app_repo
from service.app_actions.app_log import event_service
from service.app_actions.exception import ErrVersionAlreadyExists
from service.app_config.component_graph import component_graph_service
from service.app_config.port_service import port_service
from service.app_config.service_monitor_service import service_monitor_service
from service.app_config.volume_service import volume_service
from service.app_env_service import env_var_service
from service.application_service import application_service
from service.base_services import baseService
from service.market_app_service import market_app_service


class AppManageBase(object):
    def __init__(self):
        self.MODULES = "Owned_Fee"
        self.START = "restart"
        self.STOP = "stop"
        self.RESTART = "reboot"
        self.DELETE = "delete"
        self.DEPLOY = "deploy"
        self.UPGRADE = "upgrade"
        self.ROLLBACK = "callback"
        self.VERTICAL_UPGRADE = "VerticalUpgrade"
        self.HORIZONTAL_UPGRADE = "HorizontalUpgrade"
        self.TRUNCATE = "truncate"

    def isOwnedMoney(self, tenant):
        if self.MODULES["Owned_Fee"]:
            if tenant.balance < 0 and tenant.pay_type == "payed":
                return True
        return False

    def isExpired(self, tenant, service):
        if service.expired_time is not None:
            if tenant.pay_type == "free" and service.expired_time < datetime.datetime.now():
                if self.MODULES["Owned_Fee"]:
                    return True
        else:
            # 将原有免费用户的组件设置为7天后
            service.expired_time = datetime.datetime.now() + datetime.timedelta(days=7)
        return False

    def cur_service_memory(self, session: SessionClass, tenant_env, cur_service):
        """查询当前组件占用的内存"""
        memory = 0
        try:
            body = remote_component_client.check_service_status(session,
                                                                cur_service.service_region, tenant_env,
                                                                cur_service.service_alias,
                                                                tenant_env.enterprise_id)
            status = body["bean"]["cur_status"]
            # 占用内存的状态
            occupy_memory_status = (
                "starting",
                "running",
            )
            if status not in occupy_memory_status:
                memory = cur_service.min_node * cur_service.min_memory
        except Exception:
            pass
        return memory


class AppManageService(AppManageBase):
    def __init__(self):
        super().__init__()

    def deploy_service(self, session, tenant_obj, service_obj, user, committer_name=None, oauth_instance=None):
        """重新构建"""
        code, msg, event_id = self.deploy(session, tenant_obj, service_obj, user)
        bean = {}
        if code != 200:
            return JSONResponse(general_message(code, "deploy app error", msg, bean=bean), status_code=code)
        result = general_message(code, "success", "重新构建成功", bean=bean)
        return JSONResponse(result, status_code=200)

    def roll_back(self, session, tenant_env, service, user, deploy_version, upgrade_or_rollback):
        if service.create_status == "complete":
            res, data = remote_build_client.get_service_build_version_by_id(session, service.service_region,
                                                                            tenant_env,
                                                                            service.service_alias, deploy_version)
            is_version_exist = data['bean']['status']
            if not is_version_exist:
                return 404, "当前版本可能已被系统清理或删除"
            body = dict()
            body["operator"] = str(user.nick_name)
            body["upgrade_version"] = deploy_version
            body["service_id"] = service.service_id
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.rollback(session, service.service_region, tenant_env, service.service_alias,
                                                 body)
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                return 507, "组件异常"
            except remote_component_client.CallApiFrequentError as e:
                logger.exception(e)
                return 409, "操作过于频繁，请稍后再试"
        return 200, "操作成功"

    def delete_again(self, session, user, tenant_env, service, is_force):
        if not is_force:
            # 如果不是真删除，将数据备份,删除tenant_service表中的数据
            self.move_service_into_recycle_bin(session, service)
            # 组件关系移除
            self.move_service_relation_info_recycle_bin(session, tenant_env, service)
        else:
            try:
                self.really_delete_service(session, tenant_env, service, user)
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(msg="delete component {} failure".format(service.service_alias),
                                             msg_show="组件删除失败")

    def really_delete_service(self, session: SessionClass, tenant_env, service, user=None, ignore_cluster_result=False,
                              not_delete_from_cluster=False):
        ignore_delete_from_cluster = not_delete_from_cluster
        if not not_delete_from_cluster:
            try:
                data = {}
                data["etcd_keys"] = self.get_etcd_keys(session, tenant_env, service)
                remote_component_client.delete_service(session, service.service_region, tenant_env,
                                                       service.service_alias,
                                                       tenant_env.enterprise_id, data)
            except remote_component_client.CallApiError as e:
                if (not ignore_cluster_result) and int(e.status) != 404:
                    logger.error("delete component form cluster failure {}".format(e.body))
                    raise ServiceHandleException(msg="delete component from cluster failure", msg_show="组件从集群删除失败")
            except Exception as e:
                logger.exception(e)
                if not ignore_cluster_result:
                    raise ServiceHandleException(msg="delete component from cluster failure", msg_show="组件从集群删除失败")
                else:
                    ignore_delete_from_cluster = True
        if service.create_status == "complete":
            data = jsonable_encoder(service)
            data.pop("ID")
            data.pop("service_name")
            data.pop("build_upgrade")
            data.pop("oauth_service_id")
            data.pop("is_upgrate")
            data.pop("secret")
            data.pop("open_webhooks")
            data.pop("server_type")
            data.pop("git_full_name")
            data.pop("gpu_type")
        try:
            delete_service_repo.create_delete_service(session, **data)
        except Exception as e:
            logger.exception(e)
            pass
        env_var_repo.delete_service_env(session, tenant_env.env_id, service.service_id)
        auth_repo.delete_service_auth(session, service.service_id)
        domain_repo.delete_service_domain(session, service.service_id)
        tcp_domain_repo.delete_service_tcp_domain(session, service.service_id)
        dep_relation_repo.delete_service_relation(session, tenant_env.env_id, service.service_id)
        relations = dep_relation_repo.get_dependency_by_dep_id(session, tenant_env.env_id, service.service_id)
        if relations:
            dep_relation_repo.delete_dependency_by_dep_id(session, tenant_env.env_id, service.service_id)
        mnt_repo.delete_mnt(session, service.service_id)
        port_repo.delete_service_port(session, tenant_env.env_id, service.service_id)
        volume_repo.delete_service_volumes(session, service.service_id)
        app_component_relation_repo.delete_relation_by_service_id(session, service.service_id)
        service_attach_repo.delete_service_attach(session, service.service_id)
        create_step_repo.delete_create_step(session, service.service_id)
        event_service.delete_service_events(session, service)
        probe_repo.delete_service_probe(session, service.service_id)
        service_source_repo.delete_service_source(session=session, env_id=tenant_env.env_id,
                                                  service_id=service.service_id)
        compose_relation_repo.delete_relation_by_service_id(session, service.service_id)
        service_label_repo.delete_service_all_labels(session, service.service_id)
        component_share_repo.delete_tenant_service_plugin_relation(session, service.service_id)
        service_monitor_service.delete_by_service_id(session, service.service_id)
        component_graph_service.delete_by_component_id(session, service.service_id)
        app_config_group_service_repo.delete_effective_service(session=session, service_id=service.service_id)
        if service.tenant_service_group_id > 0:
            count = len(service_info_repo.get_services_by_service_group_id(session=session,
                                                                           service_group_id=service.tenant_service_group_id))
            if count <= 1:
                tenant_service_group_repo.delete_tenant_service_group_by_pk(session=session,
                                                                            pk=service.tenant_service_group_id)
        self.__create_service_delete_event(session=session, tenant=tenant_env, service=service, user=user)
        return ignore_delete_from_cluster

    def delete_components(self, session: SessionClass, tenant, components, user=None):
        # Batch delete considers that the preconditions have been met,
        # and no longer judge the preconditions
        for cpt in components:
            self.truncate_service(session, tenant, cpt, user)

    # todo 事物
    def truncate_service(self, session: SessionClass, tenant_env, service, user=None):
        """彻底删除组件"""
        try:
            data = {"etcd_keys": self.get_etcd_keys(session=session, tenant=tenant_env, service=service)}
            remote_component_client.delete_service(session, service.service_region, tenant_env,
                                                   service.service_alias,
                                                   tenant_env.enterprise_id,
                                                   data)
        except remote_component_client.CallApiError as e:
            if int(e.status) != 404:
                logger.exception(e)
                return 500, "删除组件失败 {0}".format(e.message)

        self._truncate_service(session=session, tenant=tenant_env, service=service, user=user)

        # 如果这个组件属于应用, 则删除应用最后一个组件后同时删除应用
        # 如果这个组件属于模型安装应用, 则删除最后一个组件后同时删除安装应用关系。
        if service.tenant_service_group_id > 0:
            count = (
                session.execute(select(func.count(TeamComponentInfo.ID)).where(
                    TeamComponentInfo.tenant_service_group_id == service.tenant_service_group_id))
            ).first()[0]

            if count <= 1:
                session.execute(
                    delete(TeamApplication).where(TeamApplication.ID == service.tenant_service_group_id)
                )

        return 200, "success"

    def _truncate_service(self, session: SessionClass, tenant, service, user=None):
        if service.create_status == "complete":
            data = jsonable_encoder(service)
            data.pop("ID")
            data.pop("service_name")
            data.pop("build_upgrade")
            data.pop("oauth_service_id")
            data.pop("is_upgrate")
            data.pop("secret")
            data.pop("open_webhooks")
            data.pop("server_type")
            data.pop("git_full_name")
            data.pop("gpu_type")
        try:
            add_model: TeamComponentInfoDelete = TeamComponentInfoDelete(**data)
            session.add(add_model)
            session.flush()
        except Exception as e:
            logger.exception(e)
            pass

        service_id = service.service_id

        session.execute(
            delete(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant.tenant_env_id,
                                          ComponentEnvVar.service_id == service_id)
        )

        session.execute(
            delete(TeamComponentAuth).where(TeamComponentAuth.service_id == service_id)
        )

        session.execute(
            delete(ServiceDomain).where(ServiceDomain.service_id == service_id)
        )

        session.execute(
            delete(ServiceTcpDomain).where(ServiceTcpDomain.service_id == service_id)
        )

        session.execute(
            delete(TeamComponentRelation).where(TeamComponentRelation.tenant_env_id == tenant.tenant_env_id,
                                                TeamComponentRelation.service_id == service_id)
        )

        session.execute(
            delete(TeamComponentMountRelation).where(TeamComponentMountRelation.service_id == service_id)
        )

        session.execute(
            delete(TeamComponentPort).where(TeamComponentPort.tenant_env_id == tenant.tenant_env_id,
                                            TeamComponentPort.service_id == service_id)
        )

        session.execute(
            delete(TeamComponentVolume).where(TeamComponentVolume.service_id == service_id)
        )

        session.execute(
            delete(ComponentApplicationRelation).where(ComponentApplicationRelation.service_id == service_id)
        )

        session.execute(
            delete(ComponentAttachInfo).where(ComponentAttachInfo.service_id == service_id)
        )

        session.execute(
            delete(ComponentCreateStep).where(ComponentCreateStep.service_id == service_id)
        )

        session.execute(
            delete(ComponentEvent).where(ComponentEvent.service_id == service_id)
        )

        session.execute(
            delete(ComponentProbe).where(ComponentProbe.service_id == service_id)
        )

        session.execute(
            delete(ComponentSourceInfo).where(ComponentSourceInfo.tenant_env_id == tenant.tenant_env_id,
                                              ComponentSourceInfo.service_id == service_id)
        )

        session.execute(
            delete(ComposeServiceRelation).where(ComposeServiceRelation.service_id == service_id)
        )

        session.execute(
            delete(ComponentLabels).where(ComponentLabels.service_id == service_id)
        )

        session.execute(
            delete(TeamServiceBackup).where(TeamServiceBackup.tenant_env_id == service.tenant_env_id,
                                            TeamServiceBackup.service_id == service_id)
        )

        session.execute(
            delete(ComponentGraph).where(ComponentGraph.component_id == service_id)
        )

        session.execute(
            delete(ConfigGroupService).where(ConfigGroupService.service_id == service_id)
        )

        session.execute(
            delete(ComponentMonitor).where(ComponentMonitor.service_id == service_id)
        )

        self.__create_service_delete_event(session=session, tenant=tenant, service=service, user=user)
        service_info_repo.delete_service(session, service.ID)

    def get_etcd_keys(self, session: SessionClass, tenant, service):
        logger.debug("ready delete etcd data while delete service")
        keys = []
        # 删除代码检测的etcd数据
        keys.append(service.check_uuid)
        # 删除分享应用的etcd数据
        events = (
            session.execute(
                select(ServiceShareRecordEvent).where(ServiceShareRecordEvent.service_id == service.service_id))
        ).scalars().all()

        if events and events[0].region_share_id:
            logger.debug("ready for delete etcd service share data")
            for event in events:
                keys.append(event.region_share_id)
        return keys

    def __create_service_delete_event(self, session: SessionClass, tenant, service, user):
        if not user:
            return None
        try:
            event_info = {
                "event_id": make_uuid(),
                "service_id": service.service_id,
                "tenant_env_id": tenant.tenant_env_id,
                "type": "truncate",
                "old_deploy_version": "",
                "user_name": user.nick_name,
                "start_time": datetime.datetime.now(),
                "message": service.service_cname,
                "final_status": "complete",
                "status": "success",
                "region": service.service_region,
                "deploy_version": "",
                "code_version": "",
                "old_code_version": ""
            }
            event_add: ComponentEvent = ComponentEvent(**event_info)
            session.add(event_add)

        except Exception as e:
            logger.exception(e)
            return None

    # 5.1新版批量操作（启动，关闭，构建）
    def batch_operations(self, session: SessionClass, tenant_env, region_name, user, action, service_ids):
        services = (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.service_id.in_(service_ids)))
        ).scalars().all()

        if not services:
            return
        # 获取所有组件信息
        body = dict()
        data = ''
        code = 200
        if action == "start":
            code, data = self.start_services_info(session=session, body=body, services=services, tenant=tenant_env,
                                                  user=user)
        elif action == "stop":
            code, data = self.stop_services_info(session=session, body=body, services=services, tenant=tenant_env,
                                                 user=user)
        elif action == "upgrade":
            code, data = self.upgrade_services_info(session=session, body=body, services=services, tenant=tenant_env,
                                                    user=user)
        elif action == "deploy":
            code, data = self.deploy_services_info(session=session, body=body, services=services, tenant_env=tenant_env,
                                                   user=user)
        if code != 200:
            raise AbortRequest(415, "failed to get component", "组件信息获取失败")
        # 获取数据中心信息
        try:
            _, body = remote_build_client.batch_operation_service(session, region_name, tenant_env, data)
            events = body["bean"]["batch_result"]
            return events
        except remote_build_client.CallApiError as e:
            logger.exception(e)
            raise AbortRequest(500, "failed to request region api", "数据中心操作失败")

    def start_services_info(self, session: SessionClass, body, services, tenant, user):
        body["operation"] = "start"
        start_infos_list = []
        body["start_infos"] = start_infos_list
        # request_memory = base_service.get_not_run_services_request_memory(tenant, services)
        for service in services:
            if service.service_source == "":
                continue
            service_dict = dict()
            if service.create_status == "complete":
                service_dict["service_id"] = service.service_id
                start_infos_list.append(service_dict)
        return 200, body

    def stop_services_info(self, session: SessionClass, body, services, tenant, user):
        body["operation"] = "stop"
        stop_infos_list = []
        body["stop_infos"] = stop_infos_list
        for service in services:
            service_dict = dict()
            if service.create_status == "complete":
                service_dict["service_id"] = service.service_id
                stop_infos_list.append(service_dict)
        return 200, body

    def upgrade_services_info(self, session: SessionClass, body, services, tenant, user):
        body["operation"] = "upgrade"
        upgrade_infos_list = []
        body["upgrade_infos"] = upgrade_infos_list
        # request_memory =base_service.get_not_run_services_request_memory(tenant, services)
        for service in services:
            service_dict = dict()
            if service.create_status == "complete":
                service_dict["service_id"] = service.service_id
                upgrade_infos_list.append(service_dict)
        return 200, body

    def get_build_envs(self, session: SessionClass, tenant_env_id, service_id):
        envs = {}
        build_envs = (
            session.execute(
                select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env_id,
                                              ComponentEnvVar.service_id == service_id,
                                              or_(ComponentEnvVar.scope == "build",
                                                  ComponentEnvVar.attr_name.in_(
                                                      ["COMPILE_ENV", "NO_CACHE", "DEBUG", "PROXY",
                                                       "SBT_EXTRAS_OPTS"]),
                                                  ComponentEnvVar.attr_name.like("BUILD_%"))
                                              ))
        ).scalars().all()

        for benv in build_envs:
            attr_name = benv.attr_name
            if attr_name.startswith("BUILD_"):
                attr_name = attr_name.replace("BUILD_", "", 1)
            envs[attr_name] = benv.attr_value
        compile_env = (session.execute(
            select(TeamComponentEnv).where(TeamComponentEnv.service_id == service_id))).scalars().first()

        if compile_env:
            envs["PROC_ENV"] = compile_env.user_dependency
        return envs

    def __get_service_kind(self, session: SessionClass, service):
        """获取组件种类，兼容老的逻辑"""
        if service.service_source:
            if service.service_source == AppConstants.SOURCE_CODE:
                return "build_from_source_code"
            elif service.service_source == AppConstants.DOCKER_RUN \
                    or service.service_source == AppConstants.DOCKER_COMPOSE \
                    or service.service_source == AppConstants.DOCKER_IMAGE:
                return "build_from_image"
            elif service.service_source == AppConstants.MARKET:
                if slug_util.is_slug(service.image, service.language):
                    return "build_from_market_slug"
                else:
                    return "build_from_market_image"
        else:
            kind = "build_from_image"
            if service.category == "application":
                kind = "build_from_source_code"
            if service.category == "app_publish":
                kind = "build_from_market_image"
                if slug_util.is_slug(service.image, service.language):
                    kind = "build_from_market_slug"
                if service.service_key == "0000":
                    kind = "build_from_image"
            return kind

    def deploy_services_info(self, session: SessionClass, body, services, tenant_env, user, template_apps=None,
                             upgrade=True):
        body["operation"] = "build"
        deploy_infos_list = []
        body["build_infos"] = deploy_infos_list
        app_version_cache = {}
        for service in services:
            service_dict = dict()
            service_dict["service_id"] = service.service_id
            service_dict["action"] = 'deploy'
            if service.build_upgrade:
                service_dict["action"] = 'upgrade'
            envs = self.get_build_envs(session=session, tenant_env_id=tenant_env.env_id, service_id=service.service_id)
            service_dict["envs"] = envs
            kind = self.__get_service_kind(session=session, service=service)
            service_dict["kind"] = kind
            service_source = (
                session.execute(
                    select(ComponentSourceInfo).where(ComponentSourceInfo.tenant_env_id == service.tenant_env_id,
                                                      ComponentSourceInfo.service_id == service.service_id))
            ).scalars().first()

            clone_url = service.git_url

            # 源码
            if kind == "build_from_source_code" or kind == "source":
                source_code = dict()
                service_dict["code_info"] = source_code
                source_code["repo_url"] = clone_url
                source_code["branch"] = service.code_version
                source_code["server_type"] = service.server_type
                source_code["lang"] = service.language
                source_code["cmd"] = service.cmd
                source_code["user"] = service_source.user_name
                source_code["password"] = service_source.password
            # 镜像
            elif kind == "build_from_image":
                source_image = dict()
                source_image["image_url"] = service.image
                source_image["cmd"] = service.cmd
                if service_source and (service_source.user_name or service_source.password):
                    source_image["user"] = service_source.user_name
                    source_image["password"] = service_source.password
                service_dict["image_info"] = source_image

            # local registry or rainstore
            elif service.service_source == "market":
                try:
                    if service_source:
                        apps_template = template_apps
                        if not apps_template:
                            old_extent_info = json.loads(service_source.extend_info)
                            app_version = None
                            # install from cloud
                            install_from_cloud = service_source.is_install_from_cloud()
                            if app_version_cache.get(service_source.group_key + service_source.version):
                                apps_template = app_version_cache.get(service_source.group_key + service_source.version)
                            else:
                                if install_from_cloud:
                                    # TODO:Skip the subcontract structure to avoid loop introduction
                                    logger.info("install from cloud")

                                # install from local cloud
                                else:
                                    _, app_version = market_app_service.get_wutong_app_and_version(
                                        session=session,
                                        enterprise_id=tenant_env.enterprise_id,
                                        app_id=service_source.group_key,
                                        app_version=service_source.version)
                                if app_version:
                                    apps_template = json.loads(app_version.app_template)
                                    app_version_cache[service_source.group_key + service_source.version] = apps_template
                                else:
                                    raise ServiceHandleException(msg="version can not found", msg_show="应用版本不存在，无法构建")
                        if not apps_template:
                            raise ServiceHandleException(msg="version template can not found", msg_show="应用版本不存在，无法构建")
                        apps_list = apps_template.get("apps")
                        if service_source.extend_info:
                            extend_info = json.loads(service_source.extend_info)
                            template_app = None
                            for app in apps_list:
                                if "service_share_uuid" in app and app["service_share_uuid"] == extend_info[
                                    "source_service_share_uuid"]:
                                    template_app = app
                                    break
                                if "service_share_uuid" not in app and "service_key" in app and app[
                                    "service_key"] == extend_info["source_service_share_uuid"]:
                                    template_app = app
                                    break
                            if template_app:
                                share_image = template_app.get("share_image", None)
                                share_slug_path = template_app.get("share_slug_path", None)
                                new_extend_info = {}
                                if share_image and template_app.get("service_image", None):
                                    source_image = dict()
                                    service_dict["image_info"] = source_image
                                    source_image["image_url"] = share_image
                                    source_image["user"] = template_app.get("service_image").get("hub_user")
                                    source_image["password"] = template_app.get("service_image").get("hub_password")
                                    source_image["cmd"] = service.cmd
                                    new_extend_info = template_app["service_image"]
                                if share_slug_path:
                                    slug_info = template_app.get("service_slug")
                                    slug_info["slug_path"] = share_slug_path
                                    new_extend_info = slug_info
                                    service_dict["slug_info"] = new_extend_info
                                # This should not be an upgrade, code should be analyzed and improved.
                                if upgrade:
                                    new_extend_info["source_deploy_version"] = template_app.get("deploy_version")
                                    new_extend_info["source_service_share_uuid"] \
                                        = template_app.get("service_share_uuid") \
                                        if template_app.get("service_share_uuid", None) \
                                        else template_app.get("service_key", "")
                                    if app_version:
                                        new_extend_info["update_time"] = app_version.update_time.strftime(
                                            '%Y-%m-%d %H:%M:%S')
                                    if install_from_cloud:
                                        new_extend_info["install_from_cloud"] = True
                                        new_extend_info["market"] = "default"
                                        new_extend_info["market_name"] = old_extent_info.get("market_name")
                                    service_source.extend_info = json.dumps(new_extend_info)
                                    code, msg = self.__save_env(session=session, tenant_env=tenant_env, service=service,
                                                                inner_envs=app["service_env_map_list"],
                                                                outer_envs=app["service_connect_info_map_list"])
                                    if code != 200:
                                        raise Exception(msg)
                                    self.__save_volume(session=session, tenant_env=tenant_env, service=service,
                                                       volumes=app["service_volume_map_list"])
                                    code, msg = self.__save_port(session=session, tenant_env=tenant_env,
                                                                 service=service,
                                                                 ports=app["port_map_list"])
                                    if code != 200:
                                        raise Exception(msg)
                                    self.__save_extend_info(session=session, service=service,
                                                            extend_info=app["extend_method_map"])
                except ServiceHandleException as e:
                    if e.msg != "no found app market":
                        logger.exception(e)
                        raise e
                except Exception as e:
                    logger.exception(e)
                    if service_source:
                        extend_info = json.loads(service_source.extend_info)
                        if service.is_slug():
                            service_dict["slug_info"] = extend_info
            deploy_infos_list.append(service_dict)
        return 200, body

    def __save_env(self, session: SessionClass, tenant_env, service, inner_envs, outer_envs):
        if not inner_envs and not outer_envs:
            return 200, "success"
        for env in inner_envs:
            exist = (
                session.execute(
                    select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant_env.env_id,
                                                  ComponentEnvVar.service_id == service.service_id,
                                                  ComponentEnvVar.attr_name == env["attr_name"],
                                                  ComponentEnvVar.scope == "inner"))
            ).scalars().first()

            if exist:
                continue
            code, msg, env_data = env_var_service.add_service_env_var(session=session, tenant_env=tenant_env,
                                                                      service=service,
                                                                      container_port=0, name=env["name"],
                                                                      attr_name=env["attr_name"],
                                                                      attr_value=env.get("attr_value"),
                                                                      is_change=env["is_change"],
                                                                      scope="inner")
            if code != 200:
                logger.error("save market app env error {0}".format(msg))
                return code, msg
        for env in outer_envs:
            exist = (
                session.execute(
                    select(ComponentEnvVar).where(ComponentEnvVar.tenant_env_id == tenant.tenant_env_id,
                                                  ComponentEnvVar.service_id == service.service_id,
                                                  ComponentEnvVar.attr_name == env["attr_name"],
                                                  ComponentEnvVar.scope == "outer"))
            ).scalars().first()
            if exist:
                continue
            container_port = env.get("container_port", 0)
            if container_port == 0:
                if env.get("attr_value") == "**None**":
                    env["attr_value"] = service.service_id[:8]
                code, msg, env_data = env_var_service.add_service_env_var(session=session, tenant_env=tenant_env,
                                                                          service=service,
                                                                          container_port=container_port,
                                                                          name=env["name"], attr_name=env["attr_name"],
                                                                          attr_value=env.get("attr_value"),
                                                                          is_change=env["is_change"],
                                                                          scope="outer")
                if code != 200:
                    logger.error("save market app env error {0}".format(msg))
                    return code, msg
        return 200, "success"

    def __save_port(self, session: SessionClass, tenant_env, service, ports):
        if not ports:
            return 200, "success"
        for port in ports:
            mapping_port = int(port["container_port"])
            env_prefix = port["port_alias"].upper() if bool(port["port_alias"]) else service.service_key.upper()
            service_port = (
                session.execute(
                    select(TeamComponentPort).where(TeamComponentPort.tenant_env_id == tenant_env.env_id,
                                                    TeamComponentPort.service_id == service.service_id,
                                                    TeamComponentPort.container_port == int(port["container_port"])))
            ).scalars().first()

            if service_port:
                if port["is_inner_service"]:
                    code, msg, data = env_var_service.add_service_env_var(
                        session=session,
                        tenant_env=tenant_env,
                        service=service,
                        container_port=int(port["container_port"]),
                        name="连接地址",
                        attr_name=env_prefix + "_HOST",
                        attr_value="127.0.0.1",
                        is_change=False,
                        scope="outer")
                    if code != 200 and code != 412:
                        return code, msg
                    code, msg, data = env_var_service.add_service_env_var(
                        session=session,
                        tenant_env=tenant_env,
                        service=service,
                        container_port=int(port["container_port"]),
                        name="端口",
                        attr_name=env_prefix + "_PORT",
                        attr_value=mapping_port,
                        is_change=False,
                        scope="outer")
                    if code != 200 and code != 412:
                        return code, msg
                continue

            code, msg, port_data = port_service.add_service_port(session=session, tenant_env=tenant_env,
                                                                 service=service,
                                                                 container_port=int(port["container_port"]),
                                                                 protocol=port["protocol"],
                                                                 port_alias=port["port_alias"],
                                                                 is_inner_service=port["is_inner_service"],
                                                                 is_outer_service=port["is_outer_service"])
            if code != 200:
                logger.error("save market app port error: {}".format(msg))
                return code, msg
        return 200, "success"

    def __save_extend_info(self, session: SessionClass, service, extend_info):
        if not extend_info:
            return 200, "success"
        params = {
            "service_key": service.service_key,
            "app_version": service.version,
            "min_node": extend_info["min_node"],
            "max_node": extend_info["max_node"],
            "step_node": extend_info["step_node"],
            "min_memory": extend_info["min_memory"],
            "max_memory": extend_info["max_memory"],
            "step_memory": extend_info["step_memory"],
            "is_restart": extend_info["is_restart"]
        }
        add_model: ComponentExtendMethod = ComponentExtendMethod(**params)
        session.add(add_model)

    def __save_volume(self, session: SessionClass, tenant_env, service, volumes):
        if volumes:
            for volume in volumes:
                service_volume = (
                    session.execute(
                        select(TeamComponentVolume).where(TeamComponentVolume.service_id == service.service_id,
                                                          TeamComponentVolume.volume_name == volume["volume_name"]))
                ).scalars().first()

                if service_volume:
                    continue
                service_volume = (
                    session.execute(
                        select(TeamComponentVolume).where(TeamComponentVolume.service_id == service.service_id,
                                                          TeamComponentVolume.volume_path == volume["volume_path"]))
                ).scalars().first()
                if service_volume:
                    continue
                file_content = volume.get("file_content", None)
                settings = {}
                settings["volume_capacity"] = volume["volume_capacity"]
                volume_service.add_service_volume(
                    session=session,
                    tenant_env=tenant_env,
                    service=service,
                    volume_path=volume["volume_path"],
                    volume_type=volume["volume_type"],
                    volume_name=volume["volume_name"],
                    file_content=file_content,
                    settings=settings)

    def restart(self, session: SessionClass, tenant_env, service, user):
        if service.create_status == "complete":
            status_info_map = application_service.get_service_status(session=session, tenant_env=tenant_env,
                                                                     service=service)
            if status_info_map.get("status", "Unknown") in [
                "undeploy", "closed "
            ] and not True:
                raise ServiceHandleException(error_code=20002, msg="not enough quota")
            body = dict()
            body["operator"] = str(user.nick_name)
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.restart_service(session,
                                                        service.service_region, tenant_env,
                                                        service.service_alias, body)
                logger.debug("user {0} retart app !".format(user.nick_name))
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                return 507, "组件异常"
            except remote_component_client.CallApiFrequentError as e:
                logger.exception(e)
                return 409, "操作过于频繁，请稍后再试"
        return 200, "操作成功"

    def stop(self, session: SessionClass, tenant_env, service, user):
        if service.create_status == "complete":
            body = dict()
            body["operator"] = str(user.nick_name)
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.stop_service(session,
                                                     service.service_region, tenant_env,
                                                     service.service_alias, body)
                logger.debug("user {0} stop app !".format(user.nick_name))
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                raise ServiceHandleException(msg_show="从集群关闭组件受阻，请稍后重试", msg="check console log", status_code=500)
            except remote_component_client.CallApiFrequentError:
                raise ServiceHandleException(msg_show="操作过于频繁，请稍后重试", msg="wait a moment please", status_code=409)

    def start(self, session: SessionClass, tenant_env, service, user):
        if service.service_source != "third_party" and not True:
            raise ServiceHandleException(error_code=20002, msg="not enough quota")
        if service.create_status == "complete":
            body = dict()
            body["operator"] = str(user.nick_name)
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.start_service(session,
                                                      service.service_region, tenant_env,
                                                      service.service_alias, body)
                logger.debug("user {0} start app !".format(user.nick_name))
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                return 507, "组件异常"
            except remote_component_client.CallApiFrequentError as e:
                logger.exception(e)
                return 409, "操作过于频繁，请稍后再试"
        return 200, "操作成功"

    def upgrade(self, session: SessionClass, tenant_env, service, user):
        status_info_map = application_service.get_service_status(session=session, tenant_env=tenant_env,
                                                                 service=service)
        if status_info_map.get("status", "Unknown") in [
            "undeploy", "closed "
        ] and not True:
            raise ServiceHandleException(error_code=20002, msg="not enough quota")
        body = dict()
        body["service_id"] = service.service_id
        body["operator"] = str(user.nick_name)
        try:
            body = remote_component_client.upgrade_service(session,
                                                           service.service_region, tenant_env,
                                                           service.service_alias, body)
            event_id = body["bean"].get("event_id", "")
            return 200, "操作成功", event_id
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            return 507, "更新异常", ""
        except remote_component_client.CallApiFrequentError as e:
            logger.exception(e)
            return 409, "操作过于频繁，请稍后再试", ""

    def __is_service_running(self, session: SessionClass, tenant_env, service):
        try:
            if service.create_status != "complete":
                return False
            status_info = remote_component_client.check_service_status(session,
                                                                       service.service_region, tenant_env,
                                                                       service.service_alias,
                                                                       tenant_env.enterprise_id)
            status = status_info["bean"]["cur_status"]
            if status in (
                    "running", "starting", "stopping", "failure", "unKnow", "unusual", "abnormal", "some_abnormal"):
                return True
        except remote_component_client.CallApiError as e:
            if int(e.status) == 404:
                return False
        return False

    def __is_service_related_by_other_app_service(self, session: SessionClass, tenant_env, service):
        tsrs = dep_relation_repo.get_dependency_by_dep_id(session, tenant_env.env_id, service.service_id)
        if tsrs:
            sids = list(set([tsr.service_id for tsr in tsrs]))
            service_group = application_repo.get_service_group(session, service.service_id, tenant_env.env_id)
            groups = application_repo.get_groups(session, sids, tenant_env.env_id)
            group_ids = set([group.group_id for group in groups])
            if group_ids and service_group.group_id in group_ids:
                group_ids.remove(service_group.group_id)
            if not group_ids:
                return False
            return True
        return False

    def __is_service_related(self, session: SessionClass, tenant_env, service):
        tsrs = dep_relation_repo.get_dependency_by_dep_id(session, tenant_env.env_id, service.service_id)
        if tsrs:
            sids = [tsr.service_id for tsr in tsrs]
            service_ids = service_info_repo.get_services_by_service_ids(session, sids)
            services = [service.service_cname for service in service_ids]
            if not services:
                return False, ""
            dep_service_names = ",".join(list(services))
            return True, dep_service_names
        return False, ""

    def __is_service_mnt_related(self, session: SessionClass, tenant, service):
        sms = mnt_repo.get_mount_current_service(session, tenant.tenant_env_id, service.service_id)
        if sms:
            sids = [sm.service_id for sm in sms]
            service_ids = service_info_repo.get_services_by_service_ids(session, sids)
            services = [service.service_cname for service in service_ids]
            mnt_service_names = ",".join(list(services))
            return True, mnt_service_names
        return False, ""

    def move_service_into_recycle_bin(self, session: SessionClass, service):
        """将组件移入回收站"""
        data = service.toJSON()
        data.pop("ID")
        trash_service = recycle_bin_repo.create_trash_service(**data)

        # 如果这个组件属于模型安装应用, 则删除最后一个组件后同时删除安装应用关系。
        if service.tenant_service_group_id > 0:
            count = service_info_repo.get_services_by_service_group_id(session=session,
                                                                       service_group_id=service.tenant_service_group_id).count()
            if count <= 1:
                tenant_service_group_repo.delete_tenant_service_group_by_pk(session=session,
                                                                            pk=service.tenant_service_group_id)

        service.delete()
        return trash_service

    def move_service_relation_info_recycle_bin(self, session: SessionClass, tenant_env, service):
        # 1.如果组件依赖其他组件，将组件对应的关系放入回收站
        relations = dep_relation_repo.get_service_dependencies(session, tenant_env.env_id, service.service_id)
        if relations:
            for r in relations:
                r_data = r.__dict__
                r_data.pop("ID")
                relation_recycle_bin_repo.create_trash_service_relation(**r_data)
                r.delete()
        # 如果组件被其他应用下的组件依赖，将组件对应的关系删除
        relations = dep_relation_repo.get_dependency_by_dep_id(tenant_env.env_id, service.service_id)
        if relations:
            relations.delete()
        # 如果组件关系回收站有被此组件依赖的组件，将信息及其对应的数据中心的依赖关系删除
        recycle_relations = relation_recycle_bin_repo.get_by_dep_service_id(service.service_id)
        if recycle_relations:
            for recycle_relation in recycle_relations:
                task = dict()
                task["dep_service_id"] = recycle_relation.dep_service_id
                task["tenant_env_id"] = tenant_env.env_id
                task["dep_service_type"] = "v"
                task["enterprise_id"] = tenant_env.enterprise_id
                try:
                    remote_component_client.delete_service_dependency(session,
                                                                      service.service_region, tenant_env,
                                                                      service.service_alias, task)
                except Exception as e:
                    logger.exception(e)
                recycle_relation.delete()

    def delete(self, session: SessionClass, user, tenant_env, service, is_force):
        # 判断组件是否是运行状态
        if self.__is_service_running(session=session, tenant_env=tenant_env,
                                     service=service) and service.service_source != "third_party":
            msg = "组件可能处于运行状态,请先关闭组件"
            return 409, msg
        # 判断组件是否被依赖
        is_related, msg = self.__is_service_related(session=session, tenant_env=tenant_env, service=service)
        if is_related:
            return 412, "组件被{0}依赖，不可删除".format(msg)
        # 判断组件是否被其他组件挂载
        is_mounted, msg = self.__is_service_mnt_related(session=session, tenant=tenant_env, service=service)
        if is_mounted:
            return 412, "当前组件有存储被{0}组件挂载, 不可删除".format(msg)
        if not is_force:
            # 如果不是真删除，将数据备份,删除tenant_service表中的数据
            self.move_service_into_recycle_bin(session=session, service=service)
            # 组件关系移除
            self.move_service_relation_info_recycle_bin(session=session, tenant=tenant_env, service=service)
            return 200, "success"
        else:
            try:
                code, msg = self.truncate_service(session=session, tenant_env=tenant_env, service=service, user=user)
                if code != 200:
                    return code, msg
                else:
                    return code, "success"
            except Exception as e:
                logger.exception(e)
                return 507, "删除异常"

    def change_service_type(self, session: SessionClass, tenant_env, service, extend_method, user_name=''):
        # 存储限制
        tenant_service_volumes = volume_service.get_service_volumes(session=session, tenant_env=tenant_env, service=service)
        if tenant_service_volumes:
            old_extend_method = service.extend_method
            for tenant_service_volume in tenant_service_volumes:
                if tenant_service_volume["volume_type"] == "share-file" or tenant_service_volume[
                    "volume_type"] == "memoryfs":
                    continue
                if tenant_service_volume["volume_type"] == "local":
                    if old_extend_method == ComponentType.state_singleton.value:
                        raise ServiceHandleException(
                            msg="local storage only support state_singleton", msg_show="本地存储仅支持有状态单实例组件")
                if tenant_service_volume.get("access_mode", "") == "RWO":
                    if not is_state(extend_method):
                        raise ServiceHandleException(msg="storage access mode do not support",
                                                     msg_show="存储读写属性限制,不可修改为无状态组件")
        # 实例个数限制
        if is_singleton(extend_method) and service.min_node > 1:
            raise ServiceHandleException(
                msg="singleton service limit", msg_show="组件实例数为{0}，不可修改为单实例组件类型".format(service.min_node))

        if service.create_status != "complete":
            service.extend_method = extend_method
            return

        data = dict()
        data["extend_method"] = extend_method
        data["operator"] = user_name
        try:
            remote_component_client.update_service(session,
                                                   service.service_region, tenant_env,
                                                   service.service_alias, data)
            service.extend_method = extend_method
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            raise ErrChangeServiceType

    def deploy(self, session: SessionClass, tenant_env, service, user):
        status_info_map = application_service.get_service_status(session=session, tenant_env=tenant_env,
                                                                 service=service)
        # if status_info_map.get("status", "Unknown") in ["undeploy", "closed "] and not True:
        #     raise ServiceHandleException(msg="not enough quota", error_code=20002)
        body = dict()
        # 默认更新升级
        body["action"] = "deploy"
        if service.build_upgrade:
            body["action"] = "upgrade"
        body["envs"] = self.get_build_envs(session=session, tenant_env_id=tenant_env.env_id,
                                           service_id=service.service_id)
        kind = self.__get_service_kind(session=session, service=service)
        body["kind"] = kind
        body["operator"] = str(user.nick_name)
        body["configs"] = {}
        body["service_id"] = service.service_id
        # source type parameter
        if kind == "build_from_source_code" or kind == "source":
            body["code_info"] = {
                "repo_url": service.git_url,
                "branch": service.code_version,
                "server_type": service.server_type,
                "lang": service.language,
                "cmd": service.cmd,
            }
        if kind == "build_from_image" or kind == "build_from_market_image":
            body["image_info"] = {
                "image_url": service.image,
                "cmd": service.cmd,
            }
        service_source = (
            session.execute(
                select(ComponentSourceInfo).where(ComponentSourceInfo.tenant_env_id == service.tenant_env_id,
                                                  ComponentSourceInfo.service_id == service.service_id))
        ).scalars().first()

        if service_source and (service_source.user_name or service_source.password):
            if body.get("code_info", None):
                body["code_info"]["user"] = service_source.user_name
                body["code_info"]["password"] = service_source.password
            if body.get("image_info", None):
                body["image_info"]["user"] = service_source.user_name
                body["image_info"]["password"] = service_source.password
        if service_source and service_source.extend_info:
            extend_info = json.loads(service_source.extend_info)
            if service.is_slug():  # abandoned
                body["slug_info"] = extend_info
            else:
                hub_user = extend_info.get("hub_user", None)
                hub_password = extend_info.get("hub_password", None)
                if hub_user or hub_password:
                    if body.get("image_info", None):
                        body["image_info"]["user"] = hub_user
                        body["image_info"]["password"] = hub_password
        else:
            logger.warning("service_source is not exist for service {0}".format(service.service_id))
        try:
            re = remote_component_client.build_service(session,
                                                       service.service_region, tenant_env,
                                                       service.service_alias, body)
            if re and re.get("bean") and re.get("bean").get("status") != "success":
                logger.error("deploy component failure {}".format(re))
                return 507, "构建异常", ""
            event_id = re["bean"].get("event_id", "")
        except remote_component_client.CallApiError as e:
            if e.status == 400:
                logger.warning("failed to deploy service: {}".format(e))
                raise ErrVersionAlreadyExists()
            logger.exception(e)
            return 507, "构建异常", ""
        except remote_component_client.CallApiFrequentError as e:
            logger.exception(e)
            return 409, "操作过于频繁，请稍后再试", ""
        return 200, "操作成功", event_id

    def delete_region_service(self, session: SessionClass, tenant_env, service):
        try:
            data = {}
            logger.debug("delete service {0} for team {1}".format(service.service_cname, tenant_env.tenant_name))
            data["etcd_keys"] = self.get_etcd_keys(session=session, tenant=tenant_env, service=service)
            remote_component_client.delete_service(session, service.service_region, tenant_env,
                                                   service.service_alias, tenant_env.enterprise_id,
                                                   data)
            return 200, "success"
        except remote_component_client.CallApiError as e:
            if e.status != 404:
                logger.exception(e)
                return 500, "数据中心删除失败"
            return 200, "success"

    # 变更应用分组
    # todo 事务
    def move(self, session: SessionClass, service, move_group_id, tenant_env):
        # 先删除分组应用关系表中该组件数据
        session.execute(
            delete(ComponentApplicationRelation).where(ComponentApplicationRelation.service_id == service.service_id)
        )
        # 再新建该组件新的关联数据
        add_model: ComponentApplicationRelation = ComponentApplicationRelation(service_id=service.service_id,
                                                                               group_id=move_group_id,
                                                                               tenant_env_id=service.tenant_env_id,
                                                                               region_name=service.service_region)
        session.add(add_model)

        team = (
            session.execute(select(TeamEnvInfo).where(TeamEnvInfo.env_id == service.tenant_env_id))
        ).scalars().first()
        if not team:
            raise TenantNotExistError

        tenant_name = team.tenant_name
        region_app_id = (
            session.execute(
                select(RegionApp.region_app_id).where(RegionApp.region_name == service.service_region,
                                                      RegionApp.app_id == move_group_id))
        ).scalars().first()

        update_body = {"service_name": service.service_name, "app_id": region_app_id}
        remote_app_client.update_service_app_id(session,
                                                service.service_region, tenant_env, service.service_alias,
                                                update_body)

    def __is_service_bind_domain(self, session: SessionClass, service):
        domains = domain_repo.get_service_domains(session, service.service_id)
        if not domains:
            return False

        for domain in domains:
            if domain.type == 1:
                return True
        return False

    def __is_service_has_plugins(self, session: SessionClass, service):
        service_plugin_relations = app_plugin_relation_repo.get_service_plugin_relation_by_service_id(
            session, service.service_id)
        if service_plugin_relations:
            return True
        return False

    # 批量删除组件
    def batch_delete(self, session: SessionClass, user, tenant_env, service, is_force):
        # 判断组件是否是运行状态
        if self.__is_service_running(session=session, tenant_env=tenant_env,
                                     service=service) and service.service_source != "third_party":
            msg = "当前组件处于运行状态,请先关闭组件"
            code = 409
            return code, msg
        # 判断组件是否被其他组件挂载
        is_mounted, msg = self.__is_service_mnt_related(session=session, tenant=tenant_env, service=service)
        if is_mounted:
            code = 412
            msg = "当前组件被其他组件挂载, 您确定要删除吗？"
            return code, msg
        # 判断组件是否绑定了域名
        is_bind_domain = self.__is_service_bind_domain(session=session, service=service)
        if is_bind_domain:
            code = 412
            msg = "当前组件绑定了域名， 您确定要删除吗？"
            return code, msg
        # 判断是否有插件
        if self.__is_service_has_plugins(session=session, service=service):
            code = 412
            msg = "当前组件安装了插件， 您确定要删除吗？"
            return code, msg
        # 判断是否被其他应用下的组件依赖
        if self.__is_service_related_by_other_app_service(session=session, tenant_env=tenant_env, service=service):
            code = 412
            msg = "当前组件被其他应用下的组件依赖了，您确定要删除吗？"
            return code, msg

        if not is_force:
            # 如果不是真删除，将数据备份,删除tenant_service表中的数据
            self.move_service_into_recycle_bin(session=session, service=service)
            # 组件关系移除
            self.move_service_relation_info_recycle_bin(session=session, tenant=tenant_env, service=service)
            code = 200
            msg = "success"
            return code, msg
        else:
            try:
                code, msg = self.truncate_service(session=session, tenant_env=tenant_env, service=service, user=user)
                if code != 200:
                    return code, msg
                else:
                    msg = "success"
                    return code, msg
            except Exception as e:
                logger.exception(e)
                code = 507
                msg = "删除异常"
                return code, msg

    def batch_action(self, session: SessionClass, region_name, tenant_env, user, action, service_ids, move_group_id):
        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        code = 500
        msg = "系统异常"
        fail_service_name = []
        for service in services:
            try:
                # 第三方组件不具备启动，停止，重启操作
                if action == "start" and service.service_source != "third_party":
                    self.start(session=session, tenant_env=tenant_env, service=service, user=user)
                elif action == "stop" and service.service_source != "third_party":
                    self.stop(session=session, tenant_env=tenant_env, service=service, user=user)
                elif action == "restart" and service.service_source != "third_party":
                    self.restart(session=session, tenant_env=tenant_env, service=service, user=user)
                elif action == "move":
                    application_service.sync_app_services(session=session, tenant_env=tenant_env,
                                                          region_name=region_name,
                                                          app_id=move_group_id)
                    self.move(session=session, service=service, move_group_id=move_group_id, tenant_env=tenant_env)
                elif action == "deploy" and service.service_source != "third_party":
                    self.deploy(session=session, tenant_env=tenant_env, service=service, user=user)
                elif action == "upgrade" and service.service_source != "third_party":
                    self.upgrade(session=session, tenant_env=tenant_env, service=service, user=user)
                code = 200
                msg = "success"
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                fail_service_name.append(service.service_cname)
                logger.exception(e)
        logger.debug("fail service names {0}".format(fail_service_name))
        return code, msg

    def close_all_component_in_tenant(self, session: SessionClass, tenant_env, region_name, user):
        try:
            # list components
            components = service_info_repo.get_services_by_team_and_region(session, tenant_env.env_id, region_name)
            component_ids = [cpt.service_id for cpt in components]
            self.batch_operations(session=session, tenant_env=tenant_env, region_name=region_name, user=user,
                                  action="stop",
                                  service_ids=component_ids)
        except Exception as e:
            logger.exception(e)

    def close_all_component_in_team(self, session: SessionClass, tenant_env, user):
        # close all component in define team
        tenant_regions = self.list_by_tenant_env_id(session=session, tenant_env_id=tenant_env.env_id)
        tenant_regions = tenant_regions if tenant_regions else []
        for region in tenant_regions:
            self.close_all_component_in_tenant(session=session, tenant_env=tenant_env, region_name=region.region_name,
                                               user=user)

    def list_by_tenant_env_id(self, session: SessionClass, tenant_env_id):
        where = """
        WHERE
            ti.tenant_env_id = tr.tenant_env_id
            AND ri.region_name = tr.region_name
            AND ti.tenant_env_id = "{tenant_env_id}"
        """.format(tenant_env_id=tenant_env_id)
        sql = """
        SELECT
            ri.*, ti.tenant_name
        FROM
            region_info ri,
            tenant_info ti,
            tenant_region tr
        {where}
        """.format(where=where)
        result = session.execute(sql)
        data = result.fetchall()
        return data

    def check_service_cname(self, service_cname):
        if not service_cname:
            return False, "组件名称不能为空"
        if len(service_cname) > 100:
            return False, "组件名称最多支持100个字符"
        return True, "success"

    def create_service_alias(self, session, service_id):
        service_alias = "wt" + service_id[-6:]
        svc = (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.service_alias == service_alias))
        ).scalars().first()

        if svc is None:
            return service_alias
        service_alias = self.create_service_alias(session, make_uuid(service_id))
        return service_alias

    def _create_third_component(self, session, tenant_env, region_name, user, service_cname,
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
        tenant_service = TeamComponentInfo()
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
        tenant_service.create_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenant_service.deploy_version = ""
        tenant_service.git_project_id = 0
        tenant_service.service_type = "application"
        tenant_service.total_memory = 0
        tenant_service.volume_mount_path = ""
        tenant_service.host_path = ""
        tenant_service.service_source = AppConstants.THIRD_PARTY
        tenant_service.create_status = "creating"
        return tenant_service

    @staticmethod
    def _create_third_component_body(component, endpoint, ports, envs):
        component_base = jsonable_encoder(component)
        component_base["component_id"] = component_base["service_id"]
        component_base["component_name"] = component_base["service_cname"]
        component_base["component_alias"] = component_base["service_alias"]
        component_base["container_cpu"] = component.min_cpu
        component_base["container_memory"] = component.min_memory
        component_base["replicas"] = component.min_node
        component_base["kind"] = "third_party"

        return {
            "component_base": component_base,
            "envs": [jsonable_encoder(env) for env in envs],
            "ports": [jsonable_encoder(port) for port in ports],
            "endpoint": endpoint,
        }

    @staticmethod
    def _sync_third_components(session, tenant_name, region_name, region_app_id, component_bodies):
        body = {
            "components": component_bodies,
        }
        remote_app_client.sync_components(session, tenant_name, region_name, region_app_id, body)

    @staticmethod
    def _rollback_third_components(session, tenant_name, region_name, region_app_id, components: [TeamComponentInfo]):
        body = {
            "delete_component_ids": [component.component_id for component in components],
        }
        remote_app_client.sync_components(session, tenant_name, region_name, region_app_id, body)

    @staticmethod
    def _save_third_components(session, components, relations, third_endpoints, ports, envs):
        session.add_all(components)
        service_group_relation_repo.bulk_create(session, relations)
        session.add_all(third_endpoints)
        session.add_all(ports)
        session.add_all(envs)

    def create_third_components_kubernetes(self, session, tenant_env, region_name, user, app: Application, services):
        components = []
        relations = []
        endpoints = []
        new_ports = []
        envs = []
        component_bodies = []
        for service in services:
            # components
            component_cname = service["service_name"]
            component = self._create_third_component(session, tenant_env, region_name, user, component_cname)
            component.create_status = "complete"
            components.append(component)

            relation = ComponentApplicationRelation(
                group_id=app.app_id,
                tenant_env_id=component.tenant_env_id,
                service_id=component.component_id,
                region_name=region_name,
            )
            relations.append(relation)

            # endpoints
            endpoints.append(
                ThirdPartyComponentEndpoints(
                    tenant_env_id=component.tenant_env_id,
                    service_id=component.service_id,
                    service_cname=component_cname,
                    endpoints_type="kubernetes",
                    endpoints_info=json.dumps({
                        'serviceName': service["service_name"],
                        'namespace': service["namespace"],
                    }),
                ))
            endpoint = {
                "kubernetes": {
                    'serviceName': service["service_name"],
                    'namespace': service["namespace"],
                }
            }

            # ports
            ports = service.get("ports")
            if not ports:
                continue
            for port in ports:
                new_port = TeamComponentPort(
                    tenant_env_id=component.tenant_env_id,
                    service_id=component.service_id,
                    container_port=port["port"],
                    mapping_port=port["port"],
                    protocol="udp" if port["protocol"].lower() == "udp" else "tcp",
                    port_alias=component.service_alias.upper() + str(port["port"]),
                    is_inner_service=True,
                    is_outer_service=False,
                    k8s_service_name=component.service_alias + "-" + str(port["port"]),
                )
                new_ports.append(new_port)

                # port envs
                port_envs = port_service.create_envs_4_ports(component, new_port, app.governance_mode)
                envs.extend(port_envs)

            component_body = self._create_third_component_body(component, endpoint, new_ports, envs)
            component_bodies.append(component_body)

        region_app_id = region_app_repo.get_region_app_id(session, region_name, app.app_id)

        self._sync_third_components(session, tenant_env.tenant_name, region_name, region_app_id, component_bodies)

        try:
            self._save_third_components(session, components, relations, endpoints, new_ports, envs)
        except Exception as e:
            self._rollback_third_components(session, tenant_env.tenant_name, region_name, region_app_id, components)
            raise e

        return components

    def create_third_components(self, session, tenant_env, region_name, user, app: Application, component_type,
                                services):
        if component_type != "kubernetes":
            raise AbortRequest("unsupported third component type: {}".format(component_type))
        components = self.create_third_components_kubernetes(session, tenant_env, region_name, user, app, services)

        # start the third components
        component_ids = [cpt.component_id for cpt in components]
        try:
            app_manage_service.batch_operations(session, tenant_env, region_name, user, "start", component_ids)
        except Exception as e:
            logger.exception(e)
            raise ErrThirdComponentStartFailed()

    def vertical_upgrade(self, session, tenant_env, service, user, new_memory, new_gpu_type=None, new_gpu=None,
                         new_cpu=None):
        """组件垂直升级"""
        new_memory = int(new_memory)
        if new_memory > 65536 or new_memory < 0:
            return 400, "内存范围在0M到64G之间"
        if new_memory % 32 != 0:
            return 400, "内存必须为32的倍数"
        if new_memory > service.min_memory and not True:
            raise ServiceHandleException(error_code=20002, msg="not enough quota")
        if service.create_status == "complete":
            body = dict()
            body["container_memory"] = new_memory
            if new_cpu is None or type(new_cpu) != int:
                new_cpu = baseService.calculate_service_cpu(service.service_region, new_memory)
            body["container_cpu"] = new_cpu
            if new_gpu is not None and type(new_gpu) == int:
                body["container_gpu"] = new_gpu
            if new_gpu_type is not None and new_gpu_type != '':
                body["container_gpu_type"] = new_gpu_type
            body["operator"] = str(user.nick_name)
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.vertical_upgrade(session,
                                                         service.service_region, tenant_env,
                                                         service.service_alias, body)
                service.min_cpu = new_cpu
                service.min_memory = new_memory
                service.gpu_type = new_gpu_type
                service.container_gpu = new_gpu
                service.update_time = datetime.datetime.now()
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                return 507, "组件异常"
            except remote_component_client.CallApiFrequentError as e:
                logger.exception(e)
                return 409, "操作过于频繁，请稍后再试"
        return 200, "操作成功"

    def horizontal_upgrade(self, session, tenant_env, service, user, new_node, oauth_instance):
        """组件水平升级"""
        new_node = int(new_node)
        if new_node > 100 or new_node < 0:
            raise ServiceHandleException(status_code=409, msg="node replicas must between 1 and 100",
                                         msg_show="节点数量需在1到100之间")

        if new_node > 1 and is_singleton(service.extend_method):
            raise ServiceHandleException(status_code=409, msg="singleton component, do not allow",
                                         msg_show="组件为单实例组件，不可使用多节点")

        if service.create_status == "complete":
            body = dict()
            body["node_num"] = new_node
            body["operator"] = str(user.nick_name)
            body["enterprise_id"] = tenant_env.enterprise_id
            try:
                remote_component_client.horizontal_upgrade(session,
                                                           service.service_region, tenant_env,
                                                           service.service_alias, body)
                service.min_node = new_node
                # service.save()
            except ServiceHandleException as e:
                logger.exception(e)
                if e.error_code == 10104:
                    e.msg_show = "节点没有变化，无需升级"
                raise e
            except remote_component_client.CallApiError as e:
                logger.exception(e)
                raise ServiceHandleException(status_code=507, msg="component error", msg_show="组件异常")
            except remote_component_client.CallApiFrequentError as e:
                logger.exception(e)
                raise ServiceHandleException(status_code=409, msg="just wait a moment", msg_show="操作过于频繁，请稍后再试")


app_manage_service = AppManageService()
