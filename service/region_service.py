import json
import yaml
from fastapi.encoders import jsonable_encoder
from loguru import logger
from clients.remote_build_client import remote_build_client
from clients.remote_tenant_client import remote_tenant_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException, AbortRequest
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_plugin_repo import plugin_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.env_repo import env_repo
from service.app_actions.app_manage import app_manage_service
from service.base_services import base_service
from service.plugin_service import plugin_service


def get_region_list_by_team_name(session: SessionClass, envs):
    """

    :param team_name:
    :return:
    """
    region_name_list = []
    team_region_name_list = []
    if envs:
        for env in envs:
            region = team_region_repo.get_active_region_by_env(session=session, tenant_env=env)
            region_name = region.region_name
            if region_name in team_region_name_list:
                continue
            team_region_name_list.append(region.region_name)
            region_config = team_region_repo.get_region_by_region_name(session, region.region_name)
            if region_config and region_config.status in ("1", "3"):
                region_info = {
                    "service_status": region.service_status,
                    "is_active": region.is_active,
                    "region_status": region_config.status,
                    "team_region_alias": region_config.region_alias,
                    "region_env_id": region.region_env_id,
                    "region_tenant_id": env.tenant_id,
                    "team_region_name": region.region_name,
                    "region_scope": region_config.scope,
                    "region_create_time": region_config.create_time,
                    "websocket_uri": region_config.wsurl,
                    "tcpdomain": region_config.tcpdomain
                }
                region_name_list.append(region_info)
        return region_name_list
    else:
        return []


def get_team_env_list(envs):
    """
    :param session:
    :param envs:
    :return:
    """
    team_env_list = []
    if envs:
        for env in envs:
            env_info = {
                "env_id": env.env_id,
                "env_code": env.env_name,
                "env_namespace": env.namespace,
                "env_name": env.env_alias,
                "region_name": env.region_name,
                "region_code": env.region_code
            }
            team_env_list.append(env_info)
        return team_env_list
    else:
        return []


class RegionService(object):

    async def get_region_by_request(self, session, request):
        try:
            data = await request.json()
        except:
            data = {}
        response_region = data.get("region_name", None)
        if not response_region:
            response_region = request.query_params.get("region_name", None)
        if not response_region:
            response_region = request.query_params.get("region", None)
        if not response_region:
            response_region = request.headers.get('X_REGION_NAME', None)
        if not response_region:
            response_region = request.cookies.get('region_name', None)
        region_name = response_region
        if not response_region:
            raise AbortRequest("region not found", "数据中心不存在", status_code=404, error_code=404)
        region = region_repo.get_region_by_region_name(session, region_name)
        if not region:
            raise AbortRequest("region not found", "数据中心不存在", status_code=404, error_code=404)
        region = region
        return region

    def get_public_key(self, session, tenant_env, region):
        try:
            res, body = remote_build_client.get_region_publickey(session, tenant_env, region,
                                                                 tenant_env.env_id)
            if body and "bean" in body:
                return body["bean"]
            return {}
        except Exception as e:
            logger.exception(e)
            return {}

    def get_region_wsurl(self, session, region_name):
        region = region_repo.get_region_by_region_name(session, region_name)
        if region:
            return region.wsurl
        return ""

    def add_region(self, session, region_data, user):
        region = region_repo.get_region_by_region_name(session, region_data["region_name"])
        if region:
            raise ServiceHandleException(status_code=400, msg="",
                                         msg_show="集群ID{0}已存在".format(region_data["region_name"]))
        try:

            remote_build_client.test_region_api(session, region_data)
        except ServiceHandleException:
            raise ServiceHandleException(status_code=400, msg="test link region field", msg_show="连接集群测试失败，请确认网络和集群状态")

        # 根据当前企业查询是否有region
        exist_region = region_repo.get_region(session)
        region = region_repo.create_region(session, region_data)

        if exist_region:
            return region
        return region

    def parse_token(self, token, region_name, region_alias, region_type):
        try:
            info = yaml.load(token, Loader=yaml.BaseLoader)
        except Exception as e:
            logger.exception(e)
            raise ServiceHandleException("parse yaml error", "Region Config 内容不是有效YAML格式", 400, 400)
        if not isinstance(info, dict):
            raise ServiceHandleException("parse yaml error", "Region Config 内容不是有效YAML格式", 400, 400)
        if not info.get("ca.pem"):
            raise ServiceHandleException("ca.pem not found", "CA证书不存在", 400, 400)
        if not info.get("client.key.pem"):
            raise ServiceHandleException("client.key.pem not found", "客户端密钥不存在", 400, 400)
        if not info.get("client.pem"):
            raise ServiceHandleException("client.pem not found", "客户端证书不存在", 400, 400)
        if not info.get("apiAddress"):
            raise ServiceHandleException("apiAddress not found", "API地址不存在", 400, 400)
        if not info.get("websocketAddress"):
            raise ServiceHandleException("websocketAddress not found", "Websocket地址不存在", 400, 400)
        if not info.get("defaultDomainSuffix"):
            raise ServiceHandleException("defaultDomainSuffix not found", "HTTP默认域名后缀不存在", 400, 400)
        if not info.get("defaultTCPHost"):
            raise ServiceHandleException("defaultTCPHost not found", "TCP默认IP地址不存在", 400, 400)
        region_info = {
            "region_alias": region_alias,
            "region_name": region_name,
            "region_type": region_type,
            "ssl_ca_cert": info.get("ca.pem"),
            "key_file": info.get("client.key.pem"),
            "cert_file": info.get("client.pem"),
            "url": info.get("apiAddress"),
            "wsurl": info.get("websocketAddress"),
            "httpdomain": info.get("defaultDomainSuffix"),
            "tcpdomain": info.get("defaultTCPHost"),
            "region_id": make_uuid()
        }
        return region_info

    def get_region_by_region_name(self, session, region_name):
        return region_repo.get_region_by_region_name(session=session, region_name=region_name)

    def get_region_by_region_id(self, session, region_id):
        return region_repo.get_region_by_region_id(session=session, region_id=region_id)

    def update_enterprise_region(self, session, region_id, data):
        return self.__init_region_resource_data(session,
                                                region_repo.update_enterprise_region(session,
                                                                                     region_id,
                                                                                     data))

    def get_enterprise_region(self, session, region_id, check_status=True):
        region = region_repo.get_region_by_id(session, region_id)
        if not region:
            return None
        return self.conver_region_info(session, region, check_status)

    def get_region_license_features(self, session: SessionClass, tenant_env, region_name):
        try:
            body = remote_build_client.get_region_license_feature(session, tenant_env, region_name)
            if body and "list" in body:
                return body["list"]
            return []
        except Exception as e:
            logger.exception(e)
            return []

    def get_enterprise_regions(self, session: SessionClass, level="open", status="", check_status="yes"):
        regions = team_region_repo.get_regions(session, status)
        if not regions:
            return []
        return self.conver_regions_info(session=session, regions=regions, check_status=check_status, level=level)

    def conver_regions_info(self, session: SessionClass, regions, check_status, level="open"):
        # 转换集群数据，若需要附加状态则从集群API获取
        region_info_list = []
        for region in regions:
            region_info_list.append(
                self.conver_region_info(session=session, region=region, check_status=check_status, level=level))
        return region_info_list

    def conver_region_info(self, session: SessionClass, region, check_status, level="open"):
        # 转换集群数据，若需要附加状态则从集群API获取
        region_resource = self.__init_region_resource_data(session=session, region=region, level=level)
        if check_status == "yes":
            try:
                _, rbd_version = remote_build_client.get_enterprise_api_version_v2(
                    session=session, region=region.region_name)
                res, body = remote_build_client.get_region_resources(session,
                                                                     region=region.region_name)
                if not rbd_version:
                    rbd_version = "v1.0.0"
                else:
                    rbd_version = rbd_version["raw"]
                if res.get("status") == 200:
                    region_resource["total_memory"] = body["bean"]["cap_mem"]
                    region_resource["used_memory"] = body["bean"]["req_mem"]
                    region_resource["total_cpu"] = body["bean"]["cap_cpu"]
                    region_resource["used_cpu"] = body["bean"]["req_cpu"]
                    region_resource["total_disk"] = body["bean"]["total_capacity_storage"]
                    region_resource["used_disk"] = body["bean"]["total_used_storage"]
                    region_resource["rbd_version"] = rbd_version
            except (remote_build_client.CallApiError, ServiceHandleException) as e:
                logger.exception(e)
                region_resource["rbd_version"] = ""
                region_resource["health_status"] = "failure"
        return region_resource

    def __init_region_resource_data(self, session: SessionClass, region, level="open"):
        region_resource = {}
        region_resource["region_id"] = region.region_id
        region_resource["region_alias"] = region.region_alias
        region_resource["region_name"] = region.region_name
        region_resource["status"] = region.status
        region_resource["region_type"] = (json.loads(region.region_type) if region.region_type else [])
        region_resource["url"] = region.url
        region_resource["scope"] = region.scope
        region_resource["provider"] = region.provider
        region_resource["provider_cluster_id"] = region.provider_cluster_id
        if level == "open":
            region_resource["wsurl"] = region.wsurl
            region_resource["httpdomain"] = region.httpdomain
            region_resource["tcpdomain"] = region.tcpdomain
            region_resource["ssl_ca_cert"] = region.ssl_ca_cert
            region_resource["cert_file"] = region.cert_file
            region_resource["key_file"] = region.key_file
        region_resource["desc"] = region.desc
        region_resource["total_memory"] = 0
        region_resource["used_memory"] = 0
        region_resource["total_cpu"] = 0
        region_resource["used_cpu"] = 0
        region_resource["total_disk"] = 0
        region_resource["used_disk"] = 0
        region_resource["rbd_version"] = "unknown"
        region_resource["health_status"] = "ok"
        return region_resource

    def create_env_on_region(self, session: SessionClass, team_id, team_name, env, region_name,
                             namespace):
        region_config = region_repo.get_enterprise_region_by_region_name(session, region_name)
        if not region_config:
            raise ServiceHandleException(msg="cluster not found", msg_show="需要开通的集群不存在")
        env_region = region_repo.get_env_region_by_env_and_region(session, env.env_id, region_name)
        if not env_region:
            env_region_info = {"region_name": region_name, "is_active": False}
            env_region = region_repo.create_tenant_region(session, **env_region_info)
        if not env_region.is_init:
            res, body = remote_tenant_client.create_env(session, region_name, team_id, team_name, env.env_name,
                                                        env.env_id,
                                                        namespace)
            if res["status"] != 200 and body['msg'] != 'env name {} is exist'.format(env.env_name):
                logger.error(res)
                logger.error(body)
                raise ServiceHandleException(msg="cluster init failure ", msg_show="集群初始化环境失败")
            env_region.is_active = True
            env_region.is_init = True
            env_region.region_env_id = env.env_id
            env_region.region_env_name = env.env_name
            env_region.region_scope = region_config.scope
        else:
            if (not env_region.region_env_id) or \
                    (not env_region.region_env_name):
                env_region.region_env_id = env.env_id
                env_region.region_env_name = env.env_name
                env_region.region_scope = region_config.scope
        return env_region

    def delete_env_on_region(self, session: SessionClass, env, region_name, user_nickname):
        env_region = region_repo.get_env_region_by_env_and_region(session, env.env_id, region_name)
        if not env_region:
            raise ServiceHandleException(msg="env not open cluster, not need close", msg_show="该环境未开通此集群，无需关闭")
        # start delete
        region_config = region_repo.get_enterprise_region_by_region_name(session, region_name)
        ignore_cluster_resource = False
        if not region_config:
            # cluster spec info not found, cluster side resources are no longer operated on
            ignore_cluster_resource = True
        else:
            info = remote_build_client.check_region_api(session, region_name)
            # check cluster api health
            if not info or info["rbd_version"] == "":
                ignore_cluster_resource = True
        services = service_info_repo.get_services_by_env_and_region(session, env.env_id, region_name)
        if not ignore_cluster_resource and services and len(services) > 0:
            # check component status
            service_ids = [service.service_id for service in services]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name, tenant_env=env,
                                                            service_ids=service_ids)
            status_list = [x for x in [x["status"] for x in status_list] if x not in ["closed", "undeploy"]]
            if len(status_list) > 0:
                raise ServiceHandleException(
                    msg="There are running components under the current application",
                    msg_show="环境在集群{0}下有运行态的组件,请关闭组件后再卸载当前集群".format(region_config.region_alias))
        # Components are the key to resource utilization,
        # and removing the cluster only ensures that the component's resources are freed up.
        not_delete_from_cluster = False
        for service in services:
            not_delete_from_cluster = app_manage_service.really_delete_service(session=session, tenant_env=env,
                                                                               service=service, user_nickname=user_nickname,
                                                                               ignore_cluster_result=ignore_cluster_resource,
                                                                               not_delete_from_cluster=not_delete_from_cluster)
        plugins = plugin_repo.get_tenant_plugins(session, env.env_id, region_name)
        if plugins:
            for plugin in plugins:
                plugin_service.delete_plugin(session=session, region=region_name, tenant_env=env,
                                             plugin_id=plugin.plugin_id,
                                             ignore_cluster_resource=ignore_cluster_resource,
                                             is_force=True)

        application_repo.list_tenant_group_on_region(session, env, region_name).delete()
        # delete env
        if not ignore_cluster_resource:
            try:
                remote_tenant_client.delete_env(session, region_name, env)
            except remote_tenant_client.CallApiError as e:
                if e.status != 404:
                    logger.error("delete tenant failure {}".format(e.body))
                    raise ServiceHandleException(msg="delete tenant from cluster failure", msg_show="从集群删除租户失败")
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(msg="delete tenant from cluster failure", msg_show="从集群删除租户失败")
        region_repo.delete_team_region_by_tenant_and_region(session, env.env_id, region_name)

    def get_region_tcpdomain(self, session: SessionClass, region_name):
        region = region_repo.get_region_by_region_name(session, region_name)
        if region:
            return region.tcpdomain
        return ""

    def get_region_httpdomain(self, session: SessionClass, region_name):
        region = region_repo.get_region_by_region_name(session, region_name)
        if region:
            return region.httpdomain
        return ""


region_services = RegionService()
