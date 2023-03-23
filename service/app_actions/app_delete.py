import datetime

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from clients.remote_component_client import remote_component_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.application.models import ServiceShareRecordEvent
from models.component.models import ComponentEvent
from repository.application.app_repository import delete_service_repo
from repository.application.config_group_repo import app_config_group_service_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.component_repo import service_source_repo, tenant_service_group_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import dep_relation_repo, mnt_repo, auth_repo, port_repo, volume_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_label_repo import service_label_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_share_repo import component_share_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from service.app_actions.app_log import event_service
from service.app_config.component_graph import component_graph_service
from service.app_config.service_monitor_service import service_monitor_service


def _delete_check(session: SessionClass, tenant_env, service):
    # 判断组件是否是运行状态
    try:
        if service.create_status != "complete":
            return False
        status_info = remote_component_client.check_service_status(session,
                                                                   service.service_region, tenant_env,
                                                                   service.service_alias)
        status = status_info["bean"]["cur_status"]
        if status in (
                "running", "starting", "stopping", "failure", "unKnow", "unusual", "abnormal", "some_abnormal"):
            return False, "当前组件正在运行中,请先关闭组件"
    except remote_component_client.CallApiError as e:
        if int(e.status) != 404:
            return False, "集群通信异常,请稍后重试"

    # 判断组件是否被依赖
    tsrs = dep_relation_repo.get_dependency_by_dep_id(session, tenant_env.env_id, service.service_id)
    if tsrs:
        sids = [tsr.service_id for tsr in tsrs]
        service_ids = service_info_repo.get_services_by_service_ids(session, sids)
        services = [service.service_cname for service in service_ids]
        if services:
            dep_service_names = ",".join(list(services))
            return False, "当前组件被{0}依赖,请先解除依赖关系".format(dep_service_names)
    # 判断组件是否被其他组件挂载
    sms = mnt_repo.get_mount_current_service(session, tenant_env.env_id, service.service_id)
    if sms:
        sids = [sm.service_id for sm in sms]
        service_ids = service_info_repo.get_services_by_service_ids(session, sids)
        services = [service.service_cname for service in service_ids]
        mnt_service_names = ",".join(list(services))
        return False, "当前组件有存储被{0}组件挂载, 不可删除".format(mnt_service_names)
    return True, ""


def _stop_component(session: SessionClass, tenant_env, user, service):
    # 状态检验
    if service.create_status == "complete":
        body = dict()
        body["operator"] = str(user.nick_name)
        try:
            remote_component_client.stop_service(session,
                                                 service.service_region, tenant_env,
                                                 service.service_alias, body)
            logger.info("user {0} stop app !".format(user.nick_name))
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            raise ServiceHandleException(msg_show="从集群关闭组件受阻，请稍后重试", msg="check console log", status_code=500)
        except remote_component_client.CallApiFrequentError:
            raise ServiceHandleException(msg_show="操作过于频繁，请稍后重试", msg="wait a moment please", status_code=409)


class ComponentDeleteService(object):

    def delete(self, session: SessionClass, tenant_env, service, user_nickname):
        logger.info("删除组件")
        try:
            self.__really_delete_service(session, tenant_env, service, user_nickname)
        except ServiceHandleException as e:
            raise e
        except Exception as e:
            logger.exception(e)
            raise ServiceHandleException(msg="delete component {} failure".format(service.service_alias),
                                         msg_show="组件删除失败")

    @staticmethod
    def logic_delete(session: SessionClass, tenant_env, service, user, is_force):
        logger.info("逻辑删除组件")
        # 前置条件判断
        if is_force:
            # 不进行校验 强制删除 todo
            logger.info("强制删除组件")

        check_result, msg = _delete_check(session=session, tenant_env=tenant_env, service=service)
        if check_result:
            # 停用集群资源
            _stop_component(session=session, tenant_env=tenant_env, user=user, service=service)
            # 组件主表标记删除
            service.is_delete = True
            service.delete_time = datetime.datetime.now()
            service.delete_operator = user.nick_name
            tcp_domains = tcp_domain_repo.get_service_tcpdomains(session, service.service_id)
            for tcp_domain in tcp_domains:
                tcp_domain.is_delete = True
                tcp_domain.delete_time = datetime.datetime.now()
                tcp_domain.delete_operator = user.nick_name
            service_domains = domain_repo.get_service_domains(session, service.service_id)
            for service_domain in service_domains:
                service_domain.is_delete = True
                service_domain.delete_time = datetime.datetime.now()
                service_domain.delete_operator = user.nick_name
            service_info_repo.update_by_primary_key(session=session, update_model=service)
            # 组件从表标记删除 todo
            return 200, "删除成功"
        # 不满足删除前提
        return 500, msg

    def __really_delete_service(self, session: SessionClass, tenant_env, service, user_nickname=None,
                                ignore_cluster_result=False,
                                not_delete_from_cluster=False):
        ignore_delete_from_cluster = not_delete_from_cluster
        if not not_delete_from_cluster:
            try:
                data = {}
                data["etcd_keys"] = self.__get_etcd_keys(session, tenant_env, service)
                remote_component_client.delete_service(session, service.service_region, tenant_env,
                                                       service.service_alias,
                                                       data)
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
            data.pop("is_delete")
            data.pop("delete_time")
            data.pop("delete_operator")
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
        event_service.delete_service_events(session, service)
        probe_repo.delete_service_probe(session, service.service_id)
        service_source_repo.delete_service_source(session=session, env_id=tenant_env.env_id,
                                                  service_id=service.service_id)
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
        self.__create_service_delete_event(session=session, tenant_env=tenant_env, service=service,
                                           user_nickname=user_nickname)
        return ignore_delete_from_cluster

    @staticmethod
    def __get_etcd_keys(session: SessionClass, tenant_env, service):
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

    @staticmethod
    def __create_service_delete_event(session: SessionClass, tenant_env, service, user_nickname):
        if not user_nickname:
            return None
        try:
            event_info = {
                "event_id": make_uuid(),
                "service_id": service.service_id,
                "tenant_env_id": tenant_env.env_id,
                "type": "truncate",
                "old_deploy_version": "",
                "user_name": user_nickname,
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


component_delete_service = ComponentDeleteService()
