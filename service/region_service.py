import json
import os
import yaml
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select, not_

from clients.remote_build_client import remote_build_client
from clients.remote_tenant_client import remote_tenant_client
from core.utils.crypt import make_uuid
from core.utils.oauth.oauth_types import NoSupportOAuthType, get_oauth_instance
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.market.models import CenterAppVersion
from models.teams.enterprise import TeamEnterprise
from models.users.oauth import OAuthServices
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_repo
from repository.config.config_repo import sys_config_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_plugin_repo import plugin_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.team_repo import team_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.base_services import base_service
from service.market_app_service import market_app_service

from service.platform_config_service import ConfigService
from service.plugin_service import plugin_service


def get_region_list_by_team_name(session: SessionClass, team_name):
    """

    :param team_name:
    :return:
    """
    regions = team_region_repo.get_active_region_by_tenant_name(session=session, tenant_name=team_name)
    if regions:
        region_name_list = []
        for region in regions:
            region_config = team_region_repo.get_region_by_region_name(session, region.region_name)
            if region_config and region_config.status in ("1", "3"):
                region_info = {
                    "service_status": region.service_status,
                    "is_active": region.is_active,
                    "region_status": region_config.status,
                    "team_region_alias": region_config.region_alias,
                    "region_tenant_id": region.region_tenant_id,
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


class RegionService(object):

    def get_region_wsurl(self, session, region_name):
        region = region_repo.get_region_by_region_name(session, region_name)
        if region:
            return region.wsurl
        return ""

    def _create_sample_application(self, session, ent, region, user):
        try:
            # create default team
            team = team_repo.create_team(session, user, ent, None, None)
            region_services.create_tenant_on_region(session, ent.enterprise_id, team.tenant_name, region.region_name,
                                                    team.namespace)
            # Do not create sample applications in offline environment
            if os.getenv("IS_OFFLINE", False):
                return region
            # create sample applications
            tenant = team_repo.get_team_by_team_name_and_eid(session, ent.enterprise_id, team.tenant_name)
            group = application_repo.get_group_by_unique_key(session, tenant.tenant_id, region.region_name, "默认应用")

            module_dir = os.path.dirname(__file__) + '/plugin/'
            file_path = os.path.join(module_dir, 'init_app_default.json')
            with open(file_path) as f:
                default_app_config = json.load(f)
                version_template = default_app_config["version_template"]
                app_version = json.dumps(version_template)

            # Create component dependencies for application model installation
            scope = default_app_config["scope"]
            init_app_info = {
                "app_name": default_app_config["app_name"],
                "scope": scope,
                "pic": default_app_config["pic"],
                "describe": default_app_config["describe"],
            }
            app_uuid = make_uuid()
            market_app_service.create_wutong_app(session, ent.enterprise_id, init_app_info, app_uuid)

            wutong_app_version = CenterAppVersion(
                app_template=app_version,
                enterprise_id=ent.enterprise_id,
                app_id=app_uuid,
                version="1.0",
                template_version="v1",
                record_id=0,
                share_team=team.tenant_name,
                share_user=1,
                scope=scope)
            session.add(wutong_app_version)
            # Create default components
            app_model_key = app_uuid
            version = "1.0"
            app_id = group.ID
            install_from_cloud = False
            is_deploy = True
            market_name = ""
            market_app_service.install_app(session, tenant, region, user, app_id, app_model_key, version, market_name,
                                           install_from_cloud, is_deploy)
            return region
        except Exception as e:
            logger.exception(e)
            return region

    def add_region(self, session, region_data, user):
        ent = enterprise_repo.get_enterprise_by_enterprise_id(session, region_data.get("enterprise_id"))
        if not ent:
            raise ServiceHandleException(status_code=404, msg="enterprise not found", msg_show="企业不存在")

        region = region_repo.get_region_by_region_name(session, region_data["region_name"])
        if region:
            raise ServiceHandleException(status_code=400, msg="",
                                         msg_show="集群ID{0}已存在".format(region_data["region_name"]))
        try:

            remote_build_client.test_region_api(region_data)
        except ServiceHandleException:
            raise ServiceHandleException(status_code=400, msg="test link region field", msg_show="连接集群测试失败，请确认网络和集群状态")

        # 根据当前企业查询是否有region
        exist_region = region_repo.get_region_by_enterprise_id(session, ent.enterprise_id)
        region = region_repo.create_region(session, region_data)

        if exist_region:
            return region
        return self._create_sample_application(session, ent, region, user)

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

    def update_enterprise_region(self, session, enterprise_id, region_id, data):
        return self.__init_region_resource_data(session,
                                                region_repo.update_enterprise_region(session,
                                                                                     enterprise_id,
                                                                                     region_id,
                                                                                     data))

    def get_enterprise_region(self, session, enterprise_id, region_id, check_status=True):
        region = region_repo.get_region_by_id(session, enterprise_id, region_id)
        if not region:
            return None
        return self.conver_region_info(session, region, check_status)

    def get_region_license_features(self, session: SessionClass, tenant, region_name):
        try:
            body = remote_build_client.get_region_license_feature(session, tenant, region_name)
            if body and "list" in body:
                return body["list"]
            return []
        except Exception as e:
            logger.exception(e)
            return []

    def get_enterprise_regions(self, session: SessionClass, enterprise_id, level="open", status="", check_status="yes"):
        regions = team_region_repo.get_regions_by_enterprise_id(session, enterprise_id, status)
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
                    session=session, enterprise_id=region.enterprise_id, region=region.region_name)
                res, body = remote_build_client.get_region_resources(session,
                                                                     region.enterprise_id,
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
                    region_resource["total_disk"] = body["bean"]["cap_disk"] / 1024 / 1024 / 1024
                    region_resource["used_disk"] = body["bean"]["req_disk"] / 1024 / 1024 / 1024
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
        region_resource["enterprise_id"] = region.enterprise_id
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
        region_resource["enterprise_id"] = region.enterprise_id
        enterprise_info = enterprise_repo.get_enterprise_by_enterprise_id(session, region.enterprise_id)
        if enterprise_info:
            region_resource["enterprise_alias"] = enterprise_info.enterprise_alias
        return region_resource

    def get_region_all_list_by_team_name(self, session: SessionClass, team_name):
        regions = region_repo.get_region_by_tenant_name(session=session, tenant_name=team_name)
        region_name_list = list()
        if regions:
            for region in regions:
                region_desc = region_repo.get_region_desc_by_region_name(session=session,
                                                                         region_name=region.region_name)
                region_name_list.append({
                    "region_id": region.ID,
                    "region_name": region.region_name,
                    "service_status": region.service_status,
                    "is_active": region.is_active,
                    "is_init": region.is_init,
                    "region_scope": region.region_scope,
                    "region_alisa": team_repo.get_region_alias(session, region.region_name),
                    "region.region_tenant_id": region.region_tenant_id,
                    "create_time": region.create_time,
                    "desc": region_desc
                })
            return region_name_list
        else:
            return []

    def create_tenant_on_region(self, session: SessionClass, enterprise_id, team_name, region_name, namespace):
        tenant = team_repo.get_team_by_team_name_and_eid(session, enterprise_id, team_name)
        region_config = region_repo.get_enterprise_region_by_region_name(session, enterprise_id, region_name)
        if not region_config:
            raise ServiceHandleException(msg="cluster not found", msg_show="需要开通的集群不存在")
        tenant_region = region_repo.get_team_region_by_tenant_and_region(session, tenant.tenant_id, region_name)
        if not tenant_region:
            tenant_region_info = {"tenant_id": tenant.tenant_id, "region_name": region_name, "is_active": False}
            tenant_region = region_repo.create_tenant_region(session, **tenant_region_info)
        if not tenant_region.is_init:
            res, body = remote_tenant_client.create_tenant(session, region_name, tenant.tenant_name, tenant.tenant_id,
                                                           tenant.enterprise_id, namespace)
            if res["status"] != 200 and body['msg'] != 'tenant name {} is exist'.format(tenant.tenant_name):
                logger.error(res)
                raise ServiceHandleException(msg="cluster init failure ", msg_show="集群初始化租户失败")
            tenant_region.is_active = True
            tenant_region.is_init = True
            tenant_region.region_tenant_id = tenant.tenant_id
            tenant_region.region_tenant_name = tenant.tenant_name
            tenant_region.region_scope = region_config.scope
            tenant_region.enterprise_id = tenant.enterprise_id
        else:
            if (not tenant_region.region_tenant_id) or \
                    (not tenant_region.region_tenant_name) or \
                    (not tenant_region.enterprise_id):
                tenant_region.region_tenant_id = tenant.tenant_id
                tenant_region.region_tenant_name = tenant.tenant_name
                tenant_region.region_scope = region_config.scope
                tenant_region.enterprise_id = tenant.enterprise_id
        _ = application_service.create_default_app(session=session, tenant=tenant, region_name=region_name)
        return tenant_region

    def delete_tenant_on_region(self, session: SessionClass, enterprise_id, team_name, region_name, user):
        tenant = team_repo.get_team_by_team_name_and_eid(session, enterprise_id, team_name)
        tenant_region = region_repo.get_team_region_by_tenant_and_region(session, tenant.tenant_id, region_name)
        if not tenant_region:
            raise ServiceHandleException(msg="team not open cluster, not need close", msg_show="该团队未开通此集群，无需关闭")
        # start delete
        region_config = region_repo.get_enterprise_region_by_region_name(session, enterprise_id, region_name)
        ignore_cluster_resource = False
        if not region_config:
            # cluster spec info not found, cluster side resources are no longer operated on
            ignore_cluster_resource = True
        else:
            info = remote_build_client.check_region_api(session, enterprise_id, region_name)
            # check cluster api health
            if not info or info["rbd_version"] == "":
                ignore_cluster_resource = True
        services = service_repo.get_services_by_team_and_region(session, tenant.tenant_id, region_name)
        if not ignore_cluster_resource and services and len(services) > 0:
            # check component status
            service_ids = [service.service_id for service in services]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name, tenant_name=tenant.tenant_name,
                                                            service_ids=service_ids,
                                                            enterprise_id=tenant.enterprise_id)
            status_list = [x for x in [x["status"] for x in status_list] if x not in ["closed", "undeploy"]]
            if len(status_list) > 0:
                raise ServiceHandleException(
                    msg="There are running components under the current application",
                    msg_show="团队在集群{0}下有运行态的组件,请关闭组件后再卸载当前集群".format(region_config.region_alias))
        # Components are the key to resource utilization,
        # and removing the cluster only ensures that the component's resources are freed up.
        not_delete_from_cluster = False
        for service in services:
            not_delete_from_cluster = app_manage_service.really_delete_service(session=session, tenant=tenant,
                                                                               service=service, user=user,
                                                                               ignore_cluster_result=ignore_cluster_resource,
                                                                               not_delete_from_cluster=not_delete_from_cluster)
        plugins = plugin_repo.get_tenant_plugins(session, tenant.tenant_id, region_name)
        if plugins:
            for plugin in plugins:
                plugin_service.delete_plugin(session=session, region=region_name, team=tenant,
                                             plugin_id=plugin.plugin_id,
                                             ignore_cluster_resource=ignore_cluster_resource,
                                             is_force=True)

        application_repo.list_tenant_group_on_region(session, tenant, region_name).delete()
        # delete tenant
        if not ignore_cluster_resource:
            try:
                remote_tenant_client.delete_tenant(session, region_name, team_name)
            except remote_tenant_client.CallApiError as e:
                if e.status != 404:
                    logger.error("delete tenant failure {}".format(e.body))
                    raise ServiceHandleException(msg="delete tenant from cluster failure", msg_show="从集群删除租户失败")
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(msg="delete tenant from cluster failure", msg_show="从集群删除租户失败")
        region_repo.delete_team_region_by_tenant_and_region(session, tenant.tenant_id, region_name)

    def get_team_unopen_region(self, session: SessionClass, team_name, enterprise_id):
        team_opened_regions = region_repo.get_team_opened_region(session, team_name, is_init=True)
        opened_regions_name = [team_region.region_name for team_region in team_opened_regions]
        unopen_regions = region_repo.get_usable_regions(session, enterprise_id, opened_regions_name)
        return [jsonable_encoder(unopen_region) for unopen_region in unopen_regions]

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

    def get_team_usable_regions(self, session: SessionClass, team_name, enterprise_id):
        usable_regions = region_repo.get_usable_regions_by_enterprise_id(session=session, enterprise_id=enterprise_id)
        region_names = [r.region_name for r in usable_regions]
        team_opened_regions = region_repo.get_team_opened_region_name(session, team_name, region_names)
        return team_opened_regions


class EnterpriseConfigService(ConfigService):
    def __init__(self, eid):
        super(EnterpriseConfigService, self).__init__()
        self.enterprise_id = eid
        self.base_cfg_keys = ["OAUTH_SERVICES"]
        self.cfg_keys = [
            "APPSTORE_IMAGE_HUB",
            "NEWBIE_GUIDE",
            "EXPORT_APP",
            "CLOUD_MARKET",
            "OBJECT_STORAGE",
            "AUTO_SSL",
            "VISUAL_MONITOR",
        ]
        self.cfg_keys_value = {
            "APPSTORE_IMAGE_HUB": {
                # "value": {
                #     "hub_user": None,
                #     "hub_url": None,
                #     "namespace": None,
                #     "hub_password": None
                # },
                "value": None,
                "desc": "AppStore镜像仓库配置",
                "enable": False
            },
            "NEWBIE_GUIDE": {
                "value": None,
                "desc": "开启/关闭新手引导",
                "enable": True
            },
            "EXPORT_APP": {
                "value": None,
                "desc": "开启/关闭导出应用",
                "enable": False
            },
            "CLOUD_MARKET": {
                "value": None,
                "desc": "开启/关闭云应用市场",
                "enable": True
            },
            "OBJECT_STORAGE": {
                # "value": {
                #     "provider": "",
                #     "endpoint": "",
                #     "access_key": "",
                #     "secret_key": "",
                #     "bucket_name": "",
                # },
                "value": None,
                "desc": "云端备份使用的对象存储信息",
                "enable": False
            },
            "AUTO_SSL": {
                "value": None,
                "desc": "证书自动签发",
                "enable": False
            },
            "VISUAL_MONITOR": {
                # "value": {
                #     "home_url": "",
                #     "cluster_monitor_suffix": "/d/cluster/ji-qun-jian-kong-ke-shi-hua",
                #     "node_monitor_suffix": "/d/node/jie-dian-jian-kong-ke-shi-hua",
                #     "component_monitor_suffix": "/d/component/zu-jian-jian-kong-ke-shi-hua",
                #     "slo_monitor_suffix": "/d/service/fu-wu-jian-kong-ke-shi-hua",
                # },
                "value": None,
                "desc": "可视化监控配置(链接外部监控)",
                "enable": False
            },
        }

    def init_base_config_value(self, session):
        self.base_cfg_keys_value = {
            "OAUTH_SERVICES": {
                "value": self.get_oauth_services(session),
                "desc": "开启/关闭OAuthServices功能",
                "enable": False
            },
        }

    def get_oauth_services(self, session):
        rst = []
        enterprise = session.execute(select(TeamEnterprise).where(
            TeamEnterprise.enterprise_id == self.enterprise_id)).scalars().first()
        if enterprise.ID != 1:
            oauth_services = session.execute(select(OAuthServices).where(
                not_(OAuthServices.oauth_type == "enterprisecenter"),
                OAuthServices.eid == enterprise.enterprise_id,
                OAuthServices.is_deleted == 0,
                OAuthServices.enable == 1
            )).scalars().all()
        else:
            oauth_services = session.execute(select(OAuthServices).where(
                OAuthServices.eid == enterprise.enterprise_id,
                OAuthServices.is_deleted == 0,
                OAuthServices.enable == 1
            )).scalars().all()
        if oauth_services:
            for oauth_service in oauth_services:
                try:
                    api = get_oauth_instance(oauth_service.oauth_type, oauth_service, None)
                    authorize_url = api.get_authorize_url()
                    rst.append({
                        "service_id": oauth_service.ID,
                        "enable": oauth_service.enable,
                        "name": oauth_service.name,
                        "oauth_type": oauth_service.oauth_type,
                        "is_console": oauth_service.is_console,
                        "home_url": oauth_service.home_url,
                        "eid": oauth_service.eid,
                        "is_auto_login": oauth_service.is_auto_login,
                        "is_git": oauth_service.is_git,
                        "authorize_url": authorize_url,
                    })
                except NoSupportOAuthType:
                    continue
        return rst

    def get_config_by_key(self, session: SessionClass, key):
        return sys_config_repo.get_config_by_key_and_enterprise_id(session=session, key=key,
                                                                   enterprise_id=self.enterprise_id)

    def get_cloud_obj_storage_info(self, session: SessionClass):
        cloud_obj_storage_info = self.get_config_by_key(session=session, key="OBJECT_STORAGE")
        if not cloud_obj_storage_info or not cloud_obj_storage_info.enable:
            return None
        return eval(cloud_obj_storage_info.value)

    def get_auto_ssl_info(self, session: SessionClass):
        auto_ssl_config = self.get_config_by_key(session=session, key="AUTO_SSL")
        if not auto_ssl_config or not auto_ssl_config.enable:
            return None
        return eval(auto_ssl_config.value)


region_services = RegionService()
