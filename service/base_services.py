from re import split as re_split
from loguru import logger
from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.setting import settings
from database.session import SessionClass
from repository.application.app_repository import app_repo
from repository.component.component_repo import service_source_repo
from repository.teams.env_repo import env_repo


class BaseService:

    def get_group_services_list(self, session: SessionClass, env_id, region_name, group_id, query=""):
        parms = {
            "env_id": env_id,
            "region_name": region_name,
            "group_id": group_id,
            "service_cname": query
        }
        query_sql = '''
            SELECT
                t.service_id,
                t.k8s_component_name,
                t.service_alias,
                t.create_status,
                t.service_cname,
                t.service_type,
                t.deploy_version,
                t.version,
                t.update_time,
                t.min_memory * t.min_node AS min_memory,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_env_id = :env_id
                AND t.service_region = :region_name
                AND r.group_id = :group_id
                AND t.service_cname like '%' :service_cname '%'
            ORDER BY
                t.update_time DESC;
        '''
        services = session.execute(query_sql, parms).fetchall()
        return services

    def get_fuzzy_services_list(self, session: SessionClass, env_id, region_name, query_key, fields, order):
        if fields != "update_time" and fields != "ID":
            fields = "ID"
        if order != "desc" and order != "asc":
            order = "desc"
        query_sql = '''
            SELECT
                t.create_status,
                t.service_id,
                t.service_cname,
                t.min_memory * t.min_node AS min_memory,
                t.service_alias,
                t.service_type,
                t.deploy_version,
                t.version,
                t.update_time,
                r.group_id,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_env_id = "{env_id}"
                AND t.service_region = "{region_name}"
                AND t.service_cname LIKE "%{query_key}%"
            ORDER BY
                t.{fields} {order};
        '''.format(
            env_id=env_id, region_name=region_name, query_key=query_key, fields=fields, order=order)
        services = (session.execute(query_sql)).fetchall()
        session.remove()
        return services

    def status_multi_service(self, session: SessionClass, region, tenant_env, service_ids):
        try:
            body = remote_component_client.service_status(session, region, tenant_env, {"service_ids": service_ids})
            return body["list"]
        except Exception as e:
            return []

    def get_no_group_services_list(self, session: SessionClass, tenant_env_id, region_name):
        query_sql = '''
            SELECT
                t.service_id,
                t.service_alias,
                t.service_cname,
                t.service_type,
                t.create_status,
                t.deploy_version,
                t.version,
                t.update_time,
                t.min_memory * t.min_node AS min_memory,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_env_id = "{tenant_env_id}"
                AND t.service_region = "{region_name}"
                AND r.group_id IS NULL
            ORDER BY
                t.update_time DESC;
        '''.format(
            tenant_env_id=tenant_env_id, region_name=region_name)
        services = (session.execute(query_sql)).fetchall()
        return services

    def get_build_infos(self, session: SessionClass, tenant_env, service_ids):
        apps = dict()
        markets = dict()
        build_infos = dict()
        services = env_repo.list_by_component_ids(session=session, service_ids=service_ids)
        svc_sources = service_source_repo.get_service_sources(session=session, env_id=tenant_env.env_id,
                                                              service_ids=service_ids)
        service_sources = {svc_ss.service_id: svc_ss for svc_ss in svc_sources}

        for service in services:
            service_source = service_sources.get(service.service_id, None)
            code_from = service.code_from
            oauth_type = list(settings.source_code_type.keys())
            if code_from in oauth_type:
                result_url = re_split("[:,@]", service.git_url)
                service.git_url = result_url[0] + '//' + result_url[-1]
            bean = {
                "user_name": "",
                "password": "",
                "service_source": service.service_source,
                "image": service.image,
                "cmd": service.cmd,
                "code_from": service.code_from,
                "version": service.version,
                "docker_cmd": service.docker_cmd,
                "create_time": service.create_time,
                "git_url": service.git_url,
                "code_version": service.code_version,
                "server_type": service.server_type,
                "language": service.language,
                "oauth_service_id": service.oauth_service_id,
                "full_name": service.git_full_name
            }
            if service_source:
                bean["user"] = service_source.user_name
                bean["password"] = service_source.password
            if service.service_source == 'market':
                if not service_source:
                    build_infos[service.service_id] = bean
                    continue
                app = None
                if not app:
                    app = app_repo.get_wutong_app_qs_by_key(session, service_source.group_key)
                    if not app:
                        logger.warning("not found app {0} version {1} in local market".format(
                            service_source.group_key, service_source.version))

                if app:
                    bean["rain_app_name"] = app.app_name
                    bean["details"] = app.details
                    bean["group_key"] = app.app_id
                    bean["app_version"] = service_source.version
                    bean["version"] = service_source.version
            build_infos[service.service_id] = bean
        return build_infos

    def get_not_run_services_request_memory(self, session: SessionClass, tenant_env, services):
        if not services or len(services) == 0:
            return 0
        not_run_service_ids = []
        memory = 0
        service_ids = [service.service_id for service in services]
        service_status_list = self.status_multi_service(session=session, region=services[0].service_region,
                                                        tenant_env=tenant_env,
                                                        service_ids=service_ids)
        if service_status_list:
            for status_map in service_status_list:
                if status_map.get("status") in ["undeploy", "closed"]:
                    not_run_service_ids.append(status_map.get("service_id"))
            if not_run_service_ids:
                for service in services:
                    if service.service_id in not_run_service_ids:
                        memory += int(service.min_memory) * int(service.min_node)
        return memory

    def calculate_service_cpu(self, min_memory):
        # The algorithm is obsolete
        min_cpu = int(min_memory) / 128 * 20
        return int(min_cpu)

    def get_apps_deploy_versions(self, session, region, tenant_env, service_ids):
        data = {"service_ids": service_ids}
        try:
            res, body = remote_build_client.get_env_services_deploy_version(session, region, tenant_env, data)
            return body["list"]
        except Exception as e:
            logger.exception(e)
            return []


class BaseTenantService(object):
    def calculate_service_cpu(self, region, min_memory):
        # The algorithm is obsolete
        min_cpu = int(min_memory) / 128 * 20
        return int(min_cpu)


base_service = BaseService()
baseService = BaseTenantService()
