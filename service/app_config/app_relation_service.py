from loguru import logger

from clients.remote_component_client import remote_component_client
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from repository.component.env_var_repo import env_var_repo
from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import dep_relation_repo, port_repo
from service.app_config.port_service import port_service
from service.plugin.app_plugin_service import app_plugin_service


class AppServiceRelationService(object):
    def __get_dep_service_ids(self, session: SessionClass, tenant, service):
        service_dependencies = dep_relation_repo.get_service_dependencies(session, tenant.tenant_id, service.service_id)
        return [service_dep.dep_service_id for service_dep in service_dependencies]

    def get_service_dependencies(self, session: SessionClass, tenant, service):
        dep_ids = self.__get_dep_service_ids(session=session, tenant=tenant, service=service)
        services = service_repo.get_services_by_service_ids(session, dep_ids)
        return services

    def delete_region_dependency(self, session: SessionClass, tenant, service):
        deps = self.__get_dep_service_ids(session=session, tenant=tenant, service=service)
        for dep_id in deps:
            task = {}
            task["dep_service_id"] = dep_id
            task["tenant_id"] = tenant.tenant_id
            task["dep_service_type"] = "v"
            task["enterprise_id"] = tenant.enterprise_id
            try:
                remote_component_client.delete_service_dependency(session,
                                                                  service.service_region, tenant.tenant_name,
                                                                  service.service_alias, task)
            except Exception as e:
                logger.exception(e)

    def get_undependencies(self, session: SessionClass, tenant, service):

        # 打开对内端口才能被依赖
        services = service_repo.get_tenant_region_services_by_service_id(session=session, region=service.service_region,
                                                                         tenant_id=tenant.tenant_id,
                                                                         service_id=service.service_id)
        not_dependencies = []
        dep_services = dep_relation_repo.get_service_dependencies(session, tenant.tenant_id, service.service_id)
        dep_service_ids = [dep.dep_service_id for dep in dep_services]
        for s in services:
            # 查找打开内部访问的组件
            open_inner_services = port_repo.get_service_ports_by_is_inner_service(session, tenant.tenant_id,
                                                                                  s.service_id)
            if open_inner_services:
                if s.service_id not in dep_service_ids:
                    not_dependencies.append(s)
        return not_dependencies

    def get_dependencies(self, session: SessionClass, tenant):

        # 打开对内端口才能被依赖
        services = service_repo.devops_get_tenant_region_services_by_service_id(session=session,
                                                                                tenant_id=tenant.tenant_id)
        dependencies = []
        for s in services:
            # 查找打开内部访问的组件
            open_inner_services = port_repo.get_service_ports_by_is_inner_service(session, tenant.tenant_id,
                                                                                  s.service_id)
            if open_inner_services:
                dependencies.append(s)
        return dependencies

    def __open_port(self, session: SessionClass, tenant, dep_service, container_port, user_name=''):
        open_service_ports = []
        if container_port:
            tenant_service_port = port_service.get_service_port_by_port(session=session, service=dep_service,
                                                                        port=int(container_port))
            open_service_ports.append(tenant_service_port)
        else:
            # dep component not have inner port, will open all port
            ports = port_service.get_service_ports(session=session, service=dep_service)
            if ports:
                have_inner_port = False
                for port in ports:
                    if port.is_inner_service:
                        have_inner_port = True
                        break
                if not have_inner_port:
                    open_service_ports.extend(ports)

        for tenant_service_port in open_service_ports:
            try:
                code, msg, data = port_service.manage_port(session=session, tenant=tenant, service=dep_service,
                                                           region_name=dep_service.service_region,
                                                           container_port=int(tenant_service_port.container_port),
                                                           action="open_inner",
                                                           protocol=tenant_service_port.protocol,
                                                           port_alias=tenant_service_port.port_alias,
                                                           user_name=user_name)
                if code != 200:
                    logger.warning("auto open depend service inner port faliure {}".format(msg))
                else:
                    logger.debug("auto open depend service inner port success ")
            except ServiceHandleException as e:
                logger.exception(e)
                if e.status_code != 404:
                    raise e

    def __is_env_duplicate(self, session: SessionClass, tenant, service, dep_service):
        dep_ids = self.__get_dep_service_ids(session=session, tenant=tenant, service=service)
        service_envs = env_var_repo.get_service_env_by_scope(session, tenant.tenant_id, dep_service.service_id)
        attr_names = [service_env.attr_name for service_env in service_envs]
        envs = env_var_repo.get_env_by_ids_and_attr_names(session, dep_service.tenant_id, dep_ids, attr_names)
        if envs:
            return True
        return False

    def add_service_dependency(self, session: SessionClass, tenant, service, dep_service_id, open_inner=None,
                               container_port=None,
                               user_name=''):
        dep_service_relation = dep_relation_repo.get_depency_by_serivce_id_and_dep_service_id(
            session, tenant.tenant_id, service.service_id, dep_service_id)
        if dep_service_relation:
            return 212, "当前组件已被关联", None

        dep_service = service_repo.get_service_by_tenant_and_id(session=session, tenant_id=tenant.tenant_id,
                                                                service_id=dep_service_id)
        # 开启对内端口
        if open_inner:
            self.__open_port(session, tenant, dep_service, container_port, user_name)
        else:
            # 校验要依赖的组件是否开启了对内端口
            open_inner_services = port_repo.get_service_ports_by_is_inner_service(session,
                                                                                  tenant.tenant_id,
                                                                                  dep_service.service_id)
            if not open_inner_services:
                service_ports = port_repo.get_service_ports(session, tenant.tenant_id, dep_service.service_id)
                port_list = [service_port.container_port for service_port in service_ports]
                return 201, "要关联的组件暂未开启对内端口，是否打开", port_list

        is_duplicate = self.__is_env_duplicate(session=session, tenant=tenant, service=service, dep_service=dep_service)
        if is_duplicate:
            return 412, "要关联的组件的变量与已关联的组件变量重复，请修改后再试", None
        if service.create_status == "complete":
            task = dict()
            task["dep_service_id"] = dep_service_id
            task["tenant_id"] = tenant.tenant_id
            task["dep_service_type"] = dep_service.service_type
            task["enterprise_id"] = tenant.enterprise_id
            task["operator"] = user_name
            remote_component_client.add_service_dependency(session,
                                                           service.service_region, tenant.tenant_name,
                                                           service.service_alias, task)
        tenant_service_relation = {
            "tenant_id": tenant.tenant_id,
            "service_id": service.service_id,
            "dep_service_id": dep_service_id,
            "dep_service_type": dep_service.service_type,
            "dep_order": 0,
        }
        dep_relation = dep_relation_repo.add_service_dependency(session, **tenant_service_relation)
        # component dependency change, will change export network governance plugin configuration
        if service.create_status == "complete":
            app_plugin_service.update_config_if_have_export_plugin(session=session, tenant=tenant, service=service)
        return 200, "success", dep_relation

    def patch_add_dependency(self, session: SessionClass, tenant, service, dep_service_ids, user_name=''):
        dep_service_relations = dep_relation_repo.get_dependency_by_dep_service_ids(session,
                                                                                    tenant.tenant_id,
                                                                                    service.service_id,
                                                                                    dep_service_ids)
        dep_ids = [dep.dep_service_id for dep in dep_service_relations]
        services = service_repo.get_services_by_service_ids(session, dep_ids)
        if dep_service_relations:
            service_cnames = [s.service_cname for s in services]
            return 412, "组件{0}已被关联".format(service_cnames)
        for dep_id in dep_service_ids:
            code, msg, relation = self.add_service_dependency(session=session, tenant=tenant, service=service,
                                                              dep_service_id=dep_id, user_name=user_name)
            if code != 200:
                return code, msg
        return 200, "success"

    def delete_service_dependency(self, session: SessionClass, tenant, service, dep_service_id, user_name=''):
        dependency = dep_relation_repo.get_depency_by_serivce_id_and_dep_service_id(session,
                                                                                    tenant.tenant_id,
                                                                                    service.service_id,
                                                                                    dep_service_id)
        if not dependency:
            return 404, "需要删除的依赖不存在", None
        if service.create_status == "complete":
            task = dict()
            task["dep_service_id"] = dep_service_id
            task["tenant_id"] = tenant.tenant_id
            task["dep_service_type"] = "v"
            task["enterprise_id"] = tenant.enterprise_id
            task["operator"] = user_name

            remote_component_client.delete_service_dependency(session,
                                                              service.service_region, tenant.tenant_name,
                                                              service.service_alias,
                                                              task)

        dep_relation_repo.delete(session, dependency)
        # component dependency change, will change export network governance plugin configuration
        if service.create_status == "complete":
            app_plugin_service.update_config_if_have_export_plugin(session=session, tenant=tenant, service=service)
        return 200, "success", dependency


dependency_service = AppServiceRelationService()
