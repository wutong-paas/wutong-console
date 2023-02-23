import json

from fastapi.encoders import jsonable_encoder
from loguru import logger

from clients.remote_component_client import remote_component_client
from clients.remote_migrate_client import remote_migrate_client_api
from core.enum.component_enum import is_state
from core.utils.crypt import make_uuid, AuthCode
from core.utils.timeutil import current_time_str
from database.session import SessionClass
from exceptions.exceptions import ErrObjectStorageInfoNotFound, ErrBackupRecordNotFound, ErrBackupInProgress
from exceptions.main import ServiceHandleException
from repository.application.app_backup_repo import backup_record_repo
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.component_repo import service_source_repo
from repository.component.compose_repo import compose_repo, compose_relation_repo
from repository.component.env_var_repo import env_var_repo
from repository.component.graph_repo import component_graph_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import volume_repo, configuration_repo, \
    extend_repo, \
    mnt_repo, port_repo, dep_relation_repo, service_endpoints_repo, auth_repo, compile_env_repo, app_config_group_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_label_repo import service_label_repo
from repository.component.service_probe_repo import probe_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.plugin.plugin_config_repo import config_group_repo, config_item_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo, service_plugin_config_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.app_config.service_monitor_service import service_monitor_service
from service.app_config_group import app_config_group_service
from service.application_service import application_service
from service.region_service import EnterpriseConfigService


class GroupAppBackupService(object):

    def export_group_backup(self, session, tenant, backup_id):
        backup_record = backup_record_repo.get_record_by_backup_id(session, tenant.tenant_id, backup_id)
        if not backup_record:
            return 404, "不存在该备份记录", None
        # if backup_record.mode == "full-offline":
        #     return 409, "本地备份数据暂不支持导出", None
        if backup_record.status == "starting":
            return 409, "正在备份中，请稍后重试", None

        data_str = AuthCode.encode(json.dumps(jsonable_encoder(backup_record)), "GOODRAINLOVE")
        return 200, "success", data_str

    def get_group_back_up_info(self, session: SessionClass, tenant, region, group_id):
        return backup_record_repo.get_group_backup_records(session=session, team_id=tenant.tenant_id,
                                                           region_name=region, group_id=group_id)

    def check_backup_condition(self, session: SessionClass, tenant, region, group_id):
        """
        检测备份条件，有状态组件备份应该
        """
        services = application_service.get_group_services(session=session, group_id=group_id)
        service_ids = [s.service_id for s in services]
        body = remote_component_client.service_status(session, region, tenant.tenant_name, {
            "service_ids": service_ids,
            "enterprise_id": tenant.enterprise_id
        })
        status_list = body["list"]
        service_status_map = {status_map["service_id"]: status_map["status"] for status_map in status_list}
        # 处于运行中的有状态
        running_state_services = []
        for service in services:
            if is_state(service.extend_method):
                if service_status_map.get(service.service_id) not in ("closed", "undeploy"):
                    running_state_services.append(service.service_cname)

        return 200, running_state_services

    def check_backup_app_used_custom_volume(self, session: SessionClass, group_id):
        services = application_service.get_group_services(session=session, group_id=group_id)
        service_list = dict()
        for service in services:
            service_list[service.service_id] = service.service_cname

        service_ids = [service.service_id for service in services]
        volumes = volume_repo.list_custom_volumes(session, service_ids)

        use_custom_svc = []
        for volume in volumes:
            if service_list[volume.service_id] not in use_custom_svc:
                use_custom_svc.append(service_list[volume.service_id])

        return use_custom_svc

    def get_backup_group_uuid(self, session: SessionClass, group_id):
        backup_record = backup_record_repo.get_record_by_group_id(session=session, group_id=group_id)
        if backup_record:
            return backup_record[0].group_uuid
        return make_uuid()

    def get_service_details(self, session: SessionClass, tenant, service):
        service_base = jsonable_encoder(service)
        service_labels = service_label_repo.get_service_labels(session, service.service_id)
        service_domains = domain_repo.get_service_domains(session, service.service_id)
        http_rule_configs = configuration_repo.list_by_rule_ids(session, [sd.http_rule_id for sd in service_domains])
        service_tcpdomains = tcp_domain_repo.get_service_tcpdomains(session, service.service_id)
        service_probes = probe_repo.get_all_service_probe(session, service.service_id)
        service_source = service_source_repo.get_service_source(session,
                                                                tenant.tenant_id,
                                                                service.service_id)
        service_auths = auth_repo.get_service_auth(session, service.service_id)
        service_env_vars = env_var_repo.get_service_env_by_tenant_id_and_service_id(session=session,
                                                                                    tenant_id=tenant.tenant_id,
                                                                                    service_id=service.service_id)
        service_compile_env = compile_env_repo.get_service_compile_env(session, service.service_id)
        service_extend_method = extend_repo.get_extend_method_by_service(session, service)
        service_mnts = mnt_repo.get_service_mnts(session=session,
                                                 tenant_id=tenant.tenant_id,
                                                 service_id=service.service_id)
        service_volumes = volume_repo.get_service_volumes_with_config_file(session, service.service_id)
        service_config_file = volume_repo.get_service_config_files(session, service.service_id)
        service_ports = port_repo.get_service_ports(session=session, tenant_id=tenant.tenant_id,
                                                    service_id=service.service_id)
        service_relation = dep_relation_repo.get_service_dependencies(session=session, tenant_id=tenant.tenant_id,
                                                                      service_id=service.service_id)
        service_monitors = service_monitor_service.get_component_service_monitors(session=session,
                                                                                  tenant_id=tenant.tenant_id,
                                                                                  service_id=service.service_id)
        component_graphs = component_graph_repo.list(session, service.service_id)
        # plugin
        service_plugin_relation = app_plugin_relation_repo.get_service_plugin_relation_by_service_id(session,
                                                                                                     service.service_id)
        service_plugin_config = service_plugin_config_repo.get_service_plugin_all_config(session=session,
                                                                                         service_id=service.service_id)
        # third_party_service
        third_party_service_endpoints = service_endpoints_repo.get_all_service_endpoints_by_service_id(
            session, service.service_id)
        if service.service_source == "third_party":
            if not third_party_service_endpoints:
                raise ServiceHandleException(msg="third party service endpoints can't be null", msg_show="第三方组件实例不可为空")
        app_info = {
            "component_id": service.component_id,
            "service_base": service_base,
            "service_labels": [jsonable_encoder(label) for label in service_labels],
            "service_domains": [jsonable_encoder(domain) for domain in service_domains],
            "http_rule_configs": [jsonable_encoder(config) for config in http_rule_configs],
            "service_tcpdomains": [jsonable_encoder(tcpdomain) for tcpdomain in service_tcpdomains],
            "service_probes": [jsonable_encoder(probe) for probe in service_probes],
            "service_source": jsonable_encoder(service_source) if service_source else None,
            "service_auths": [jsonable_encoder(auth) for auth in service_auths],
            "service_env_vars": [jsonable_encoder(env_var) for env_var in service_env_vars],
            "service_compile_env": jsonable_encoder(service_compile_env) if service_compile_env else None,
            "service_extend_method": jsonable_encoder(service_extend_method) if service_extend_method else None,
            "service_mnts": [jsonable_encoder(mnt) for mnt in service_mnts],
            "service_plugin_relation": [jsonable_encoder(plugin_relation) for plugin_relation in
                                        service_plugin_relation],
            "service_plugin_config": [jsonable_encoder(config) for config in service_plugin_config],
            "service_relation": [jsonable_encoder(relation) for relation in service_relation],
            "service_volumes": [jsonable_encoder(volume) for volume in service_volumes],
            "service_config_file": [jsonable_encoder(config_file) for config_file in service_config_file],
            "service_ports": [jsonable_encoder(port) for port in service_ports],
            "third_party_service_endpoints": [jsonable_encoder(endpoint) for endpoint in third_party_service_endpoints],
            "service_monitors": [jsonable_encoder(monitor) for monitor in service_monitors],
            "component_graphs": [jsonable_encoder(graph) for graph in component_graphs]
        }
        plugin_ids = [pr.plugin_id for pr in service_plugin_relation]

        return app_info, plugin_ids

    def get_group_app_metadata(self, session: SessionClass, group_id, tenant, region_name):
        all_data = dict()
        compose_group_info = compose_repo.get_group_compose_by_group_id(session, group_id)
        compose_service_relation = None
        if compose_group_info:
            compose_service_relation = compose_relation_repo.get_compose_service_relation_by_compose_id(
                session, compose_group_info.compose_id)
        group_info = application_repo.get_group_by_id(session, group_id)

        service_group_relations = app_component_relation_repo.get_services_by_group(session, group_id)
        service_ids = [sgr.service_id for sgr in service_group_relations]
        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        all_data["compose_group_info"] = jsonable_encoder(compose_group_info) if compose_group_info else None
        all_data["compose_service_relation"] = [jsonable_encoder(relation)
                                                for relation in
                                                compose_service_relation] if compose_service_relation else None
        all_data["group_info"] = jsonable_encoder(group_info)
        all_data["service_group_relation"] = [jsonable_encoder(sgr) for sgr in service_group_relations]
        apps = []
        total_memory = 0
        plugin_ids = []
        for service in services:
            if service.create_status != "complete":
                continue
            if service.service_source != "third_party":
                total_memory += service.min_memory * service.min_node
            app_info, pids = self.get_service_details(session=session, tenant=tenant, service=service)
            plugin_ids.extend(pids)
            apps.append(app_info)
        all_data["apps"] = apps

        # plugin
        plugins = []
        plugin_build_versions = []
        plugin_config_groups = []
        plugin_config_items = []
        for plugin_id in plugin_ids:
            plugin = plugin_repo.get_plugin_by_plugin_id(session, tenant.tenant_id, plugin_id)
            if plugin is None:
                continue
            plugins.append(jsonable_encoder(plugin))
            bv = plugin_version_repo.get_last_ok_one(session=session, plugin_id=plugin_id, tenant_id=tenant.tenant_id)
            if bv is None:
                continue
            plugin_build_versions.append(jsonable_encoder(bv))
            pcgs = config_group_repo.list_by_plugin_id(session=session, plugin_id=plugin_id)
            if pcgs:
                plugin_config_groups.extend([jsonable_encoder(p) for p in pcgs])
            pcis = config_item_repo.list_by_plugin_id(session=session, plugin_id=plugin_id)
            if pcis:
                plugin_config_items.extend([jsonable_encoder(p) for p in pcis])
        all_data["plugin_info"] = {}
        all_data["plugin_info"]["plugins"] = jsonable_encoder(plugins)
        all_data["plugin_info"]["plugin_build_versions"] = jsonable_encoder(plugin_build_versions)
        all_data["plugin_info"]["plugin_config_groups"] = jsonable_encoder(plugin_config_groups)
        all_data["plugin_info"]["plugin_config_items"] = jsonable_encoder(plugin_config_items)

        # application config group
        config_group_infos = app_config_group_repo.get_config_group_in_use(session, region_name, group_id)
        app_config_groups = []
        for cgroup_info in config_group_infos:
            config_group = app_config_group_service.get_config_group(session=session, region_name=region_name,
                                                                     app_id=group_id,
                                                                     config_group_name=cgroup_info["config_group_name"])
            app_config_groups.append(config_group)
        all_data["app_config_group_info"] = app_config_groups
        return total_memory, all_data

    def backup_group_apps(self, session: SessionClass, tenant, user, region_name, group_id, mode, note, force=False):
        s3_config = EnterpriseConfigService(tenant.enterprise_id).get_cloud_obj_storage_info(session=session)
        if mode == "full-online" and not s3_config:
            raise ErrObjectStorageInfoNotFound
        services = application_service.get_group_services(session=session, group_id=group_id)
        event_id = make_uuid()
        group_uuid = self.get_backup_group_uuid(session=session, group_id=group_id)
        total_memory, metadata = self.get_group_app_metadata(session=session, group_id=group_id, tenant=tenant,
                                                             region_name=region_name)
        version = current_time_str("%Y%m%d%H%M%S")

        data = {
            "event_id": event_id,
            "group_id": group_uuid,
            "metadata": json.dumps(metadata),
            "service_ids": [s.service_id for s in services if s.create_status == "complete"],
            "mode": mode,
            "version": version,
            "s3_config": s3_config,
            "force": force,
        }
        # 向数据中心发起备份任务
        try:
            body = remote_migrate_client_api.backup_group_apps(session, region_name, tenant.tenant_name, data)
            bean = body["bean"]
            record_data = {
                "group_id": group_id,
                "event_id": event_id,
                "group_uuid": group_uuid,
                "version": version,
                "team_id": tenant.tenant_id,
                "region": region_name,
                "status": bean["status"],
                "note": note,
                "mode": mode,
                "backup_id": bean.get("backup_id", ""),
                "source_dir": bean.get("source_dir", ""),
                "source_type": bean.get("source_type", ""),
                "backup_size": bean.get("backup_size", 0),
                "user": user.nick_name,
                "total_memory": total_memory,
            }
            return backup_record_repo.create_backup_records(session, **record_data)
        except remote_migrate_client_api.CallApiError as e:
            logger.exception(e)
            if e.message["body"].get("msg",
                                     "") == "last backup task do not complete or have restore backup or version is exist":
                raise ServiceHandleException(msg="backup failed", msg_show="上次备份任务未完成或有正在恢复的备份或该版本已存在", status_code=409)
            if e.status == 401:
                raise ServiceHandleException(msg="backup failed", msg_show="有状态组件必须停止方可进行备份")
            raise ServiceHandleException(msg=e.message["body"].get("msg", "backup failed"), msg_show="备份失败")

    def get_groupapp_backup_status_by_backup_id(self, session: SessionClass, tenant, region, backup_id):
        backup_record = backup_record_repo.get_record_by_backup_id(session=session, team_id=tenant.tenant_id,
                                                                   backup_id=backup_id)
        if not backup_record:
            return 404, "不存在该备份记录", None
        if backup_record.status == "starting":
            body = remote_migrate_client_api.get_backup_status_by_backup_id(session,
                                                                            region, tenant.tenant_name, backup_id)
            bean = body["bean"]
            backup_record.status = bean["status"]
            backup_record.source_dir = bean["source_dir"]
            backup_record.source_type = bean["source_type"]
            backup_record.backup_size = bean["backup_size"]
        return 200, "success", backup_record

    def delete_group_backup_by_backup_id(self, session: SessionClass, tenant, region, backup_id):
        backup_record = backup_record_repo.get_record_by_backup_id(session=session, team_id=tenant.tenant_id,
                                                                   backup_id=backup_id)
        if not backup_record:
            raise ErrBackupRecordNotFound
        if backup_record.status == "starting":
            return ErrBackupInProgress

        try:
            remote_migrate_client_api.delete_backup_by_backup_id(session, region, tenant.tenant_name, backup_id)
        except remote_migrate_client_api.CallApiError as e:
            if e.status != 404:
                raise e

        backup_record_repo.delete_record_by_backup_id(session=session, team_id=tenant.tenant_id, backup_id=backup_id)

    def import_group_backup(self, session, tenant, region, group_id, upload_file):
        group = application_repo.get_group_by_id(session, group_id)
        if not group:
            return 404, "需要导入的组不存在", None
        services = application_service.get_group_services(session, group_id)
        if services:
            return 409, "请确保需要导入的组中不存在组件", None
        content = upload_file
        try:
            data = json.loads(AuthCode.decode(content, "WUTONGPAAS"))
        except:
            return 400, "文件错误", None
        current_backup = backup_record_repo.get_record_by_group_id_and_backup_id(session, group_id, data["backup_id"])
        if current_backup:
            return 412, "当前团队已导入过该备份", None
        event_id = make_uuid()
        group_uuid = make_uuid()
        params = {
            "event_id": event_id,
            "group_id": group_uuid,
            "status": data["status"],
            "version": data["version"],
            "source_dir": data["source_dir"],
            "source_type": data["source_type"],
            "backup_mode": data["mode"],
            "backup_size": data["backup_size"]
        }
        body = remote_migrate_client_api.copy_backup_data(session, region, tenant.tenant_name, params)

        bean = body["bean"]
        record_data = {
            "group_id": group.ID,
            "event_id": event_id,
            "group_uuid": group_uuid,
            "version": data["version"],
            "team_id": tenant.tenant_id,
            "region": region,
            "status": bean["status"],
            "note": data["note"],
            "mode": data["mode"],
            "backup_id": bean["backup_id"],
            "source_dir": data["source_dir"],
            "source_type": data["source_type"],
            "backup_size": data["backup_size"],
            "user": data["user"],
            "total_memory": data["total_memory"],
            "backup_server_info": data["backup_server_info"]
        }

        new_backup_record = backup_record_repo.create_backup_records(session, **record_data)
        return 200, "success", new_backup_record

    def get_all_group_back_up_info(self, session, tenant, region):
        return backup_record_repo.get_group_backup_records_by_team_id(session, tenant.tenant_id, region)


groupapp_backup_service = GroupAppBackupService()
