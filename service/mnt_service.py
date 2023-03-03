from fastapi_pagination import Params, paginate
from loguru import logger

from clients.remote_component_client import remote_component_client
from core.enum.component_enum import is_state
from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import mnt_repo, volume_repo
from service.app_config.volume_service import volume_service


class AppMntService(object):
    SHARE = 'share-file'
    CONFIG = 'config-file'

    def delete_service_mnt_relation(self, session, tenant_env, service, dep_vol_id, user_name=''):
        dep_volume = volume_repo.get_service_volume_by_pk(session, dep_vol_id)

        try:
            if service.create_status == "complete":
                data = {
                    "depend_service_id": dep_volume.service_id,
                    "volume_name": dep_volume.volume_name,
                    "operator": user_name
                }
                res, body = remote_component_client.delete_service_dep_volumes(session,
                                                                               service.service_region,
                                                                               tenant_env,
                                                                               service.service_alias, data)
                logger.debug("delete service mnt info res:{0}, body {1}".format(res, body))
            mnt_repo.delete_mnt_relation(session, service.service_id, dep_volume.service_id, dep_volume.volume_name)

        except remote_component_client.CallApiError as e:
            logger.exception(e)
            if e.status == 404:
                logger.debug('service mnt relation not in region then delete rel directly in console')
                mnt_repo.delete_mnt_relation(service.service_id, dep_volume.service_id, dep_volume.volume_name)
        return 200, "success"

    def get_service_mnt_details(self, session: SessionClass, tenant_env, service, volume_types, page=1, page_size=20):
        all_mnt_relations = mnt_repo.get_service_mnts_filter_volume_type(session, tenant_env.tenant_id, service.service_id,
                                                                         volume_types)
        total = len(all_mnt_relations)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(all_mnt_relations, params)
        mnt_relations = event_paginator.items
        mounted_dependencies = []
        if mnt_relations:
            for mount in mnt_relations:
                dep_service = service_info_repo.get_service_by_service_id(session, mount.dep_service_id)
                if dep_service:
                    gs_rel = app_component_relation_repo.get_group_by_service_id(session, dep_service.service_id)
                    group = None
                    if gs_rel:
                        group = application_repo.get_by_primary_key(session=session, primary_key=gs_rel.group_id)
                    dep_volume = volume_repo.get_service_volume_by_name(session, dep_service.service_id, mount.mnt_name)
                    if dep_volume:
                        mounted_dependencies.append({
                            "local_vol_path": mount.mnt_dir,
                            "dep_vol_name": dep_volume.volume_name,
                            "dep_vol_path": dep_volume.volume_path,
                            "dep_vol_type": dep_volume.volume_type,
                            "dep_app_name": dep_service.service_cname,
                            "dep_app_group": group.group_name if group else '未分组',
                            "dep_vol_id": dep_volume.ID,
                            "dep_group_id": group.ID if group else -1,
                            "dep_app_alias": dep_service.service_alias
                        })
        return mounted_dependencies, total

    def get_service_unmount_volume_list(self, session: SessionClass, tenant_env, service, service_ids, page, page_size,
                                        is_config=False):
        """
        1. 获取租户下其他所有组件列表，方便后续进行名称的冗余
        2. 获取其他组件的所有可共享的存储
        3. 获取已经使用的存储，方便后续过滤
        4. 遍历存储，组装信息
        """

        for serviceID in service_ids:
            if serviceID == service.service_id:
                service_ids.remove(serviceID)
        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        state_services = []  # 有状态组件
        for svc in services:
            if is_state(svc.extend_method):
                state_services.append(svc)
        state_service_ids = [svc.service_id for svc in state_services]

        current_tenant_services_id = service_ids
        # 已挂载的组件路径
        mounted = mnt_repo.get_service_mnts(session, tenant_env.tenant_id, service.service_id)
        mounted_ids = [mnt.volume_id for mnt in mounted]
        # 当前未被挂载的共享路径
        service_volumes = []
        # 配置文件无论组件是否是共享存储都可以共享，只需过滤掉已经挂载的存储；其他存储类型则需要考虑排除有状态组件的存储
        if is_config:
            service_volumes = volume_repo.get_services_volumes_by_config(session, current_tenant_services_id,
                                                                         self.CONFIG, mounted_ids)
        else:
            service_volumes = volume_repo.get_services_volumes_by_share(session, current_tenant_services_id,
                                                                        self.SHARE, mounted_ids,
                                                                        state_service_ids)

        total = len(service_volumes)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(service_volumes, params)
        page_volumes = event_paginator.items
        un_mount_dependencies = []
        for volume in page_volumes:
            gs_rel = app_component_relation_repo.get_group_by_service_id(session, volume.service_id)
            group = None
            if gs_rel:
                group = application_repo.get_by_primary_key(session=session, primary_key=gs_rel.group_id)
            dep_app_name = ""
            dep_app_alias = ""
            for ser in services:
                if ser.service_id == volume.service_id:
                    dep_app_name = ser.service_cname
                    dep_app_alias = ser.service_alias
            un_mount_dependencies.append({
                "dep_app_name": dep_app_name,
                "dep_app_group": group.group_name if group else '未分组',
                "dep_vol_name": volume.volume_name,
                "dep_vol_path": volume.volume_path,
                "dep_vol_type": volume.volume_type,
                "dep_vol_id": volume.ID,
                "dep_group_id": group.ID if group else -1,
                "dep_app_alias": dep_app_alias
            })
        return un_mount_dependencies, total

    def get_volume_dependent(self, session: SessionClass, tenant, service):
        mnts = mnt_repo.get_by_dep_service_id(session, tenant.tenant_id, service.service_id)
        if not mnts:
            return None

        service_ids = [mnt.service_id for mnt in mnts]
        services = service_info_repo.get_services_by_service_ids(session, service_ids)
        # to dict
        id_to_services = {}
        for svc in services:
            if not id_to_services.get(svc.service_id, None):
                id_to_services[svc.service_id] = [svc]
                continue
            id_to_services[svc.service_id].append(svc)

        result = []
        for mnt in mnts:
            # get volume
            vol = volume_repo.get_service_volume_by_name(session, service.service_id, mnt.mnt_name)
            if not vol:
                continue
            # services that depend on this volume
            services_dep_vol = id_to_services[mnt.service_id]
            for svc in services_dep_vol:
                result.append({
                    "volume_name": vol.volume_name,
                    "service_name": svc.service_cname,
                    "service_alias": svc.service_alias,
                })

        return result

    def add_service_mnt_relation(self, session: SessionClass, tenant_env, service, source_path, dep_volume, user_name=''):
        if not dep_volume:
            return
        if service.create_status == "complete":
            if dep_volume.volume_type != "config-file":
                data = {
                    "depend_service_id": dep_volume.service_id,
                    "volume_name": dep_volume.volume_name,
                    "volume_path": source_path,
                    "volume_type": dep_volume.volume_type
                }
            else:
                config_file = volume_repo.get_service_config_file(session, dep_volume)
                data = {
                    "depend_service_id": dep_volume.service_id,
                    "volume_name": dep_volume.volume_name,
                    "volume_path": source_path,
                    "volume_type": dep_volume.volume_type,
                    "file_content": config_file.file_content
                }
            data["operator"] = user_name
            res, body = remote_component_client.add_service_dep_volumes(session,
                                                                        service.service_region,
                                                                        tenant_env, service.service_alias,
                                                                        data)
            logger.debug("add service mnt info res: {0}, body:{1}".format(res, body))

        mnt_relation = mnt_repo.add_service_mnt_relation(session, tenant_env, service.service_id,
                                                         dep_volume.service_id,
                                                         dep_volume.volume_name, source_path)
        logger.debug(
            "mnt service {0} to service {1} on dir {2}".format(mnt_relation.service_id, mnt_relation.dep_service_id,
                                                               mnt_relation.mnt_dir))

    def batch_mnt_serivce_volume(self, session: SessionClass, tenant_env, service, dep_vol_data, user_name=''):
        local_path = []
        tenant_service_volumes = volume_service.get_service_volumes(session=session, tenant_env=tenant_env, service=service)
        local_path = [l_path["volume_path"] for l_path in tenant_service_volumes]
        for dep_vol in dep_vol_data:
            volume_service.check_volume_path(session=session, service=service, volume_path=dep_vol["path"],
                                             local_path=local_path)
        for dep_vol in dep_vol_data:
            dep_vol_id = dep_vol['id']
            source_path = dep_vol['path'].strip()
            dep_volume = volume_repo.get_service_volume_by_pk(session, dep_vol_id)
            try:
                self.add_service_mnt_relation(session=session, tenant_env=tenant_env, service=service, source_path=source_path,
                                              dep_volume=dep_volume, user_name=user_name)
            except Exception as e:
                logger.exception(e)


mnt_service = AppMntService()
