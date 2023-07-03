import datetime
import json
import os
import time

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select, or_, text, delete, and_

from appstore.app_store import app_store
from clients.remote_build_client import remote_build_client
from clients.remote_plugin_client import remote_plugin_client
from common.api_base_http_client import ApiBaseHttpClient
from core.enum.component_enum import is_singleton
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import AbortRequest, ServiceHandleException, RbdAppNotFound
from models.application.models import ServiceShareRecord, ServiceShareRecordEvent
from models.application.plugin import TeamComponentPluginRelation, TeamPlugin, ComponentPluginConfigVar, \
    PluginShareRecordEvent, PluginBuildVersion
from models.component.models import TeamComponentConfigurationFile, TeamComponentPort, Component, \
    ComponentEnvVar, TeamComponentVolume, TeamComponentMountRelation, ComponentProbe, ComponentMonitor, ComponentGraph, \
    ComponentLabels, ComponentEvent
from models.market.models import CenterApp, CenterAppVersion
from models.region.label import Labels
from models.relate.models import TeamComponentRelation
from repository.application.config_group_repo import app_config_group_item_repo, app_config_group_service_repo
from repository.component.service_config_repo import app_config_group_repo, configuration_repo, port_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_share_repo import component_share_repo
from repository.market.center_repo import center_app_repo, app_export_record_repo
from service.application_service import application_service
from service.base_services import base_service
from service.market_app_service import market_app_service
from service.plugin.plugin_config_service import plugin_config_service


class ShareService(object):

    def get_sync_plugin_events(self, session, region_name, tenant_env, record_event):
        res, body = remote_plugin_client.share_plugin_result(session, region_name, tenant_env, record_event.plugin_id,
                                                             record_event.region_share_id)
        ret = body.get('bean')
        if ret and ret.get('status'):
            record_event.event_status = ret.get("status")
            # record_event.save()
        return record_event

    def sync_service_plugin_event(self, session, user, region_name, tenant_env, record_id, record_event):
        apps_version = center_app_repo.get_wutong_app_version_by_record_id(session, record_event.record_id)
        if not apps_version:
            raise RbdAppNotFound("分享的应用不存在")
        app_template = json.loads(apps_version.app_template)
        if "plugins" not in app_template:
            return
        plugins_info = app_template["plugins"]
        plugin_list = []
        for plugin in plugins_info:
            if record_event.plugin_id == plugin["plugin_id"]:
                event_id = make_uuid()
                body = {
                    "plugin_id": plugin["plugin_id"],
                    "plugin_version": plugin["build_version"],
                    "plugin_key": plugin["plugin_key"],
                    "event_id": event_id,
                    "share_user": user.nick_name,
                    "share_scope": apps_version.scope,
                    "image_info": plugin.get("plugin_image") if plugin.get("plugin_image") else {},
                }
                try:
                    res, body = remote_plugin_client.share_plugin(session, region_name, tenant_env,
                                                                  plugin["plugin_id"], body)
                    data = body.get("bean")
                    if not data:
                        raise ServiceHandleException(msg="share failed", msg_show="数据中心分享错误")

                    record_event.region_share_id = data.get("share_id", None)
                    record_event.event_id = data.get("event_id", None)
                    record_event.event_status = "start"
                    record_event.update_time = datetime.datetime.now()
                    # record_event.save()
                    image_name = data.get("image_name", None)
                    if image_name:
                        plugin["share_image"] = image_name
                except Exception as e:
                    logger.exception(e)
                    raise ServiceHandleException(msg="share failed", msg_show="插件分享事件同步发生错误", status_code=500)

            plugin_list.append(plugin)
        app_template["plugins"] = plugin_list
        apps_version.app_template = json.dumps(app_template)
        # apps_version.save()
        return record_event

    def wrapper_service_plugin_config(self, service_related_plugin_config, shared_plugin_info):
        """添加plugin key信息"""
        id_key_map = {}
        if shared_plugin_info:
            id_key_map = {i["plugin_id"]: i["plugin_key"] for i in shared_plugin_info}

        service_plugin_config_list = []
        for config in service_related_plugin_config:
            config["plugin_key"] = id_key_map.get(config["plugin_id"])
            service_plugin_config_list.append(config)
        return service_plugin_config_list

    def _handle_dependencies(self, service, dev_service_set, use_force):
        """检查组件依赖信息，如果依赖不完整则中断请求， 如果强制执行则删除依赖"""

        def filter_dep(dev_service):
            """过滤依赖关系"""
            dep_service_key = dev_service['dep_service_key']
            if dep_service_key not in dev_service_set:
                return False
            elif dep_service_key not in dev_service_set and not use_force:
                raise AbortRequest(
                    error_code=10501,
                    msg="{} service is missing dependencies".format(service['service_cname']),
                    msg_show="{}组件缺少依赖组件，请添加依赖组件，或强制执行".format(service['service_cname']))
            else:
                return True

        if service.get('dep_service_map_list'):
            service['dep_service_map_list'] = list(filter(filter_dep, service['dep_service_map_list']))

    def _parse_cookie_or_header(self, cookies: str):
        # example: foo=bar;apple=pie
        cookies = cookies.replace(" ", "")
        result = {}
        for cookie in cookies.split(";"):
            kvs = cookie.split("=")
            if len(kvs) != 2 or kvs[0] == "" or kvs[1] == "":
                continue
            result[kvs[0]] = kvs[1]
        return result

    def _list_http_ingresses(self, session, tenant_env, component_keys):
        service_domains = domain_repo.list_by_component_ids(session, component_keys.keys())
        if not service_domains:
            return []
        configs = configuration_repo.list_by_rule_ids(session, [sd.http_rule_id for sd in service_domains])
        configs = {cfg.rule_id: json.loads(cfg.value) for cfg in configs}

        ports = port_repo.list_by_service_ids(session, tenant_env.env_id, component_keys.keys())
        ports = {port.container_port: port for port in ports}

        ingress_http_routes = []
        for sd in service_domains:
            # only work for outer port
            port = ports.get(sd.container_port)
            if not port or not port.is_outer_service:
                continue

            config = configs.get(sd.http_rule_id, {})
            header_list = config.get("set_headers")
            header = {}
            if header_list is not None:
                for head in header_list:
                    header.update({head["item_key"]: head["item_value"]})
                config.update({"set_headers": header})
            else:
                config.update({"set_headers": header_list})

            ingress_http_route = {
                "default_domain": sd.type == 0,
                "location": sd.domain_path,
                "cookies": self._parse_cookie_or_header(sd.domain_cookie),
                "headers": self._parse_cookie_or_header(sd.domain_heander),
                "path_rewrite": sd.path_rewrite,
                "rewrites": sd.rewrites,
                "ssl": sd.auto_ssl,
                "load_balancing": sd.load_balancing,
                "connection_timeout": config.get("proxy_connect_timeout"),
                "request_timeout": config.get("proxy_send_timeout"),
                "response_timeout": config.get("proxy_read_timeout"),
                "request_body_size_limit": config.get("proxy_body_size"),
                "proxy_buffer_numbers": config.get("proxy_buffer_numbers"),
                "proxy_buffer_size": config.get("proxy_buffer_size"),
                "websocket": config.get("WebSocket"),
                "component_key": component_keys.get(sd.service_id),
                "port": sd.container_port,
                "proxy_header": config.get("set_headers"),
            }
            ingress_http_routes.append(ingress_http_route)
        return ingress_http_routes

    def config_groups(self, session: SessionClass, region_name, service_ids_keys_map):
        groups = app_config_group_repo.list_by_service_ids(session, region_name, service_ids_keys_map.keys())
        cgs = []
        for group in groups:
            # list related items
            cg = {
                "name":
                    group.config_group_name,
                "injection_type":
                    group.deploy_type,
                "enable":
                    group.enable,
                "config_items":
                    {item.item_key: item.item_value
                     for item in
                     app_config_group_item_repo.list(session=session, config_group_id=group.config_group_id)},
                "component_keys": [
                    service_ids_keys_map.get(service.service_id)
                    for service in
                    app_config_group_service_repo.list(session=session, config_group_id=group.config_group_id)
                ]
            }
            cgs.append(cg)

        return cgs

    def get_plugins_group_items(self, session, plugins):
        rt_list = []
        for p in plugins:
            config_group_list = plugin_config_service.get_config_details(session=session, plugin_id=p["plugin_id"],
                                                                         build_version=p["build_version"])
            p["config_groups"] = config_group_list
            if p["origin_share_id"] == "new_create":
                p["plugin_key"] = make_uuid()
            else:
                p["plugin_key"] = p["origin_share_id"]
            rt_list.append(p)
        return rt_list

    def create_share_info(self, session, tenant_env, region_name, share_record,
                          share_env, share_user, share_info, use_force):
        try:
            share_version_info = share_info.app_version_info
            app_model_id = share_version_info.app_model_id
            version = share_version_info.version
            target = share_version_info.scope_target
            version_alias = share_version_info.version_alias
            template_type = share_version_info.template_type
            version_describe = share_version_info.describe
            market_id = None
            market = None
            share_store_name = ''
            if target:
                market_id = target.get("store_id")
            if not market_id:
                market_id = share_record.share_app_market_name
            local_app_version = session.execute(select(CenterApp).where(
                CenterApp.app_id == app_model_id)).scalars().first()
            local_app_version.store_id = share_info.store_id
            if not local_app_version:
                return 400, "本地应用模型不存在", None
            scope = local_app_version.scope
            app_model_name = local_app_version.app_name
            if scope is None or app_model_name is None:
                return 400, "参数错误", None

            # 删除历史数据
            session.execute(delete(ServiceShareRecordEvent).where(
                ServiceShareRecordEvent.record_id == share_record.ID))

            app_templete = {}
            # 处理基本信息
            try:
                app_templete["template_version"] = "v2"
                app_templete["group_key"] = app_model_id
                app_templete["group_name"] = app_model_name
                app_templete["group_version"] = version
                app_templete["group_dev_status"] = ""
            except Exception as e:
                logger.exception(e)
                raise ServiceHandleException(msg="Basic information processing error", msg_show="基本信息处理错误")

            # group config
            service_ids_keys_map = {svc["service_id"]: svc['service_key'] for svc in share_info.share_service_list}
            app_templete["app_config_groups"] = self.config_groups(session, region_name, service_ids_keys_map)

            # ingress
            ingress_http_routes = self._list_http_ingresses(session, tenant_env, service_ids_keys_map)
            app_templete["ingress_http_routes"] = ingress_http_routes

            # plugins
            try:
                # 确定分享的插件ID
                plugins = share_info.share_plugin_list
                shared_plugin_info = None
                if plugins:
                    for plugin_info in plugins:
                        # one account for one plugin
                        share_image_info = app_store.get_app_hub_info(session, market, app_model_id)
                        plugin_info["plugin_image"] = share_image_info
                        event = PluginShareRecordEvent(
                            record_id=share_record.ID,
                            env_name=share_env.env_name,
                            tenant_env_id=share_env.env_id,
                            plugin_id=plugin_info['plugin_id'],
                            plugin_name=plugin_info['plugin_alias'],
                            event_status='not_start',
                            region_share_id="")
                        session.add(event)
                        session.flush()

                    shared_plugin_info = self.get_plugins_group_items(session=session, plugins=plugins)
                    app_templete["plugins"] = shared_plugin_info
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                return 500, "插件处理发生错误", None

            # 处理组件相关
            try:
                services = share_info.share_service_list
                if services:
                    new_services = list()
                    service_ids = [s["service_id"] for s in services]
                    version_list = base_service.get_apps_deploy_versions(session,
                                                                         services[0]["service_region"],
                                                                         tenant_env,
                                                                         service_ids)
                    delivered_type_map = {v["service_id"]: v["delivered_type"] for v in version_list}

                    dep_service_keys = {service['service_share_uuid'] for service in services}

                    for service in services:
                        delivered_type = delivered_type_map.get(service['service_id'], None)
                        if not delivered_type:
                            continue
                        if delivered_type == "slug":
                            # service['service_slug'] = app_store.get_slug_hub_info(session, market, app_model_id)
                            service["share_type"] = "slug"
                            if not service['service_slug']:
                                return 400, "获取源码包上传地址错误", None
                        else:
                            service["service_image"] = app_store.get_app_hub_info(session, market, app_model_id)
                            service["share_type"] = "image"
                            if not service["service_image"]:
                                return 400, "获取镜像上传地址错误", None

                        # 处理依赖关系
                        self._handle_dependencies(service, dep_service_keys, use_force)

                        service["service_related_plugin_config"] = self.wrapper_service_plugin_config(
                            service["service_related_plugin_config"], shared_plugin_info)

                        if service.get("need_share", None):
                            ssre = ServiceShareRecordEvent(
                                tenant_env_id=share_env.env_id,
                                service_key=service["service_key"],
                                service_id=service["service_id"],
                                service_name=service["service_cname"],
                                service_alias=service["service_alias"],
                                record_id=share_record.ID,
                                env_name=share_env.env_name,
                                event_status="not_start",
                                region_share_id="")
                            session.merge(ssre)
                            session.flush()
                        new_services.append(service)
                    app_templete["apps"] = new_services
                else:
                    return 400, "分享的组件信息不能为空", None
            except ServiceHandleException as e:
                raise e
            except Exception as e:
                logger.exception(e)
                return 500, "组件信息处理发生错误", None
            share_record.scope = scope
            if not version_describe:
                version_describe = ""
            app_version = CenterAppVersion(
                app_id=app_model_id,
                version=version,
                app_version_info=version_describe,
                version_alias=version_alias,
                template_type=template_type,
                record_id=share_record.ID,
                share_user=share_user.nick_name,
                share_env=share_env.env_name,
                group_id=share_record.group_id,
                source="local",
                scope=scope,
                app_template=json.dumps(app_templete),
                template_version="v2",
                upgrade_time=time.time(),
            )
            session.add(app_version)
            session.flush()
            share_record.step = 2
            share_record.scope = scope
            share_record.app_id = app_model_id
            share_record.share_version = version
            share_record.share_version_alias = version_alias
            share_record.share_app_market_name = market_id
            share_record.share_app_model_name = app_model_name
            share_record.share_store_name = share_store_name
            share_record.update_time = datetime.datetime.now()
            share_record.share_app_version_info = version_describe
            session.flush()
            return 200, "分享信息处理成功", share_record.__dict__
        except ServiceHandleException as e:
            raise e
        except Exception as e:
            logger.exception(e)
            return 500, "应用分享处理发生错误", None

    def get_last_shared_app_and_app_list(self, tenant_env, group_id, scope, market_name,
                                         session: SessionClass):
        if scope == "market":
            last_shared = (
                session.execute(select(ServiceShareRecord).where(ServiceShareRecord.group_id == group_id,
                                                                 ServiceShareRecord.scope == scope,
                                                                 ServiceShareRecord.is_success == True).order_by(
                    ServiceShareRecord.create_time.desc()))
            ).scalars().first()
        else:
            last_shared = (
                session.execute(select(ServiceShareRecord).where(ServiceShareRecord.group_id == group_id,
                                                                 ServiceShareRecord.scope.in_(["team", "enterprise"]),
                                                                 ServiceShareRecord.env_name == tenant_env.env_name,
                                                                 ServiceShareRecord.is_success == True).order_by(
                    ServiceShareRecord.create_time.desc()))
            ).scalars().first()

        dt = {"app_model_list": [], "last_shared_app": {}, "scope": scope}
        if scope == "market":
            logger.info("")
        else:
            logger.info("")

        if last_shared:
            last_shared_app_info = (
                session.execute(select(CenterApp).where(and_(CenterApp.app_id == last_shared.app_id,
                                                             or_(
                                                                 CenterApp.create_team == tenant_env.tenant_name,
                                                                 CenterApp.scope == "enterprise"))))
            ).scalars().first()

            if last_shared_app_info:
                self._patch_rainbond_app_tag(app=last_shared_app_info, session=session)
                dt["last_shared_app"] = {
                    "app_name": last_shared_app_info.app_name,
                    "app_id": last_shared.app_id,
                    "version": last_shared.share_version,
                    "pic": last_shared_app_info.pic,
                    "app_describe": last_shared_app_info.describe,
                    "dev_status": last_shared_app_info.dev_status,
                    "scope": last_shared_app_info.scope,
                    "tags": last_shared_app_info.tags
                }
        app_list = self.get_team_local_apps_versions(tenant_env.tenant_name, session,
                                                     market=scope == "market")
        self._patch_rainbond_apps_tag(app_list, session)
        dt["app_model_list"] = app_list
        return dt

    def get_team_local_apps_versions(self, team_name, session: SessionClass, market: bool = False):
        app_list = []
        if market:
            apps = (
                session.execute(select(CenterApp).where(
                    # CenterApp.source == "local",
                    or_(CenterApp.create_team == team_name,
                        CenterApp.scope == "market")).order_by(
                    CenterApp.create_time.desc()))
            ).scalars().all()
        else:
            apps = (
                session.execute(select(CenterApp).where(
                    or_(
                        and_(CenterApp.create_team == team_name,
                             CenterApp.scope == "team"),
                        (CenterApp.scope == "enterprise"))).order_by(
                    CenterApp.create_time.desc()))
            ).scalars().all()

        if apps:
            for app in apps:
                app_versions = list(self.get_last_app_versions_by_app_id(app.app_id, session))
                app_list.append({
                    "app_name":
                        app.app_name,
                    "app_id":
                        app.app_id,
                    "pic":
                        app.pic,
                    "app_describe":
                        app.describe,
                    "dev_status":
                        app.dev_status,
                    "versions":
                    # sorted(
                        app_versions,
                    # todo
                    # key=lambda x: [int(str(y)) if str.isdigit(str(y)) else -1 for y in x["version"].split(".")],
                    # reverse=True),
                    "scope":
                        app.scope,
                })
        return app_list

    def _patch_rainbond_apps_tag(self, apps, session: SessionClass):
        app_ids = [app["app_id"] for app in apps]
        tags = self.get_multi_apps_tags(app_ids, session)
        if not tags:
            return
        app_with_tags = dict()
        for tag in tags:
            if not app_with_tags.get(tag.app_id):
                app_with_tags[tag.app_id] = []
            app_with_tags[tag.app_id].append({"tag_id": tag.ID, "name": tag.name})

        for app in apps:
            app["tags"] = app_with_tags.get(app["app_id"])

    def get_multi_apps_tags(self, app_ids, session: SessionClass):
        if not app_ids:
            return None
        app_ids = ",".join("'{0}'".format(app_id) for app_id in app_ids)

        sql = """
        select
            atr.app_id, tag.*
        from
            center_app_tag_relation atr
        left join center_app_tag tag on
            atr.tag_id = tag.ID
        where
            atr.app_id in ({app_ids});
        """.format(app_ids=app_ids)
        result = (session.execute(text(sql))).fetchall()
        return result

    def get_last_app_versions_by_app_id(self, app_id, session: SessionClass):
        sql = """
            SELECT B.version, B.version_alias, B.dev_status, B.app_version_info as `describe`
            FROM (SELECT app_id, version, max(upgrade_time) as upgrade_time
                FROM center_app_version
                WHERE is_complete=1
                GROUP BY app_id, version) A
            LEFT JOIN center_app_version B
            ON A.app_id=B.app_id AND A.version=B.version AND A.upgrade_time=B.upgrade_time
            WHERE A.app_id = "{app_id}"
            """.format(app_id=app_id)
        result = (session.execute(text(sql))).fetchall()
        return result

    def _patch_rainbond_app_tag(self, app, session: SessionClass):
        sql = """
            select
                 tag.*
            from
                center_app_tag_relation atr
            left join center_app_tag tag on
                atr.tag_id = tag.ID
            where
                atr.app_id = '{app_id}';
            """.format(app_id=app.app_id)
        tags = (session.execute(text(sql))).fetchall()

        app.tags = []
        if not tags:
            return
        for tag in tags:
            app.tags.append({"tag_id": tag.ID, "name": tag.name})

    def get_group_services_used_plugins(self, group_id, session: SessionClass):
        service_list = application_service.get_group_services(session=session, group_id=group_id)
        if not service_list:
            return []
        service_ids = [x.service_id for x in service_list]
        sprs = (
            session.execute(
                select(TeamComponentPluginRelation).where(TeamComponentPluginRelation.service_id.in_(service_ids)))
        ).scalars().all()

        plugin_list = []
        temp_plugin_ids = []
        for spr in sprs:
            if spr.plugin_id in temp_plugin_ids:
                continue
            tenant_plugin = (
                session.execute(select(TeamPlugin).where(TeamPlugin.plugin_id == spr.plugin_id))
            ).scalars().first()
            plugin_build_version = (
                session.execute(select(PluginBuildVersion).where(PluginBuildVersion.plugin_id == spr.plugin_id))
            ).scalars().first()

            plugin_dict = tenant_plugin.__dict__

            plugin_dict["build_version"] = spr.build_version
            plugin_dict["build_cmd"] = plugin_build_version.build_cmd
            plugin_list.append(plugin_dict)
            temp_plugin_ids.append(spr.plugin_id)
        return plugin_list

    def check_service_source(self, session: SessionClass, tenant_env, group_id, region_name):
        service_list = component_share_repo.get_service_list_by_group_id(session=session, tenant_env=tenant_env,
                                                                         group_id=group_id)
        if service_list:
            # 批量查询组件状态
            service_ids = [service.service_id for service in service_list]
            status_list = base_service.status_multi_service(session=session,
                                                            region=region_name, tenant_env=tenant_env,
                                                            service_ids=service_ids)
            for status in status_list:
                if status["status"] == "running":
                    data = {"code": 200, "success": True, "msg": "应用的组件有在运行中可以发布。", "list": list(), "bean": dict()}
                    return data
            data = {"code": 400, "success": False, "msg": "应用下所有组件都在未运行状态，不能发布。", "list": list(), "bean": dict()}
            return data
        else:
            data = {"code": 400, "success": False, "msg": "当前应用内无组件", "list": list(), "bean": dict()}
            return data

    def create_service_share_record(self, session: SessionClass, **kwargs):
        return component_share_repo.create_service_share_record(session, **kwargs)

    def query_share_service_info(self, tenant_env, group_id, session: SessionClass, scope=None):
        service_list = component_share_repo.get_service_list_by_group_id(session=session, tenant_env=tenant_env,
                                                                         group_id=group_id)
        if service_list:
            array_ids = [x.service_id for x in service_list]
            deploy_versions = self.get_team_service_deploy_version(session, service_list[0].service_region, tenant_env,
                                                                   array_ids)
            array_keys = []
            for x in service_list:
                if x.service_key == "application" or x.service_key == "0000" or x.service_key == "":
                    array_keys.append(x.service_key)
            # 查询组件端口信息
            service_port_map = self.get_service_ports_by_ids(array_ids, session)
            # 查询组件依赖
            dep_service_map = self.get_service_dependencys_by_ids(array_ids, session)
            service_env_map = self.get_service_env_by_ids(array_ids, session)
            # 查询组件持久化信息
            service_volume_map = self.get_service_volume_by_ids(array_ids, session)
            # dependent volume
            dep_mnt_map = self.get_dep_mnts_by_ids(tenant_env.env_id, array_ids, session)
            # 获取组件的健康检测设置
            probe_map = self.get_service_probes(array_ids, session)

            # service monitor
            sid_2_monitors = self.list_service_monitors(tenant_env.env_id, array_ids, session)
            # component graphs
            sid_2_graphs = self.list_component_graphs(array_ids, session)
            all_data_map = dict()

            labels = self.list_component_labels(array_ids, session)

            for service in service_list:
                if not deploy_versions or not deploy_versions.get(service.service_id):
                    continue
                data = dict()
                data['service_id'] = service.service_id
                data['tenant_env_id'] = service.tenant_env_id
                data['service_cname'] = service.service_cname
                # The component is redistributed without the key from the installation source, which would cause duplication.
                # service_id  can be thought of as following a component lifecycle.
                data['service_key'] = service.service_id
                # service_share_uuid The build policy cannot be changed
                data["service_share_uuid"] = "{0}+{1}".format(data['service_key'], data['service_id'])
                data['need_share'] = True
                data['category'] = service.category
                data['language'] = service.language
                data['extend_method'] = service.extend_method
                data['version'] = service.version
                data['memory'] = service.min_memory - service.min_memory % 32
                data['service_type'] = service.service_type
                data['service_source'] = service.service_source
                data['deploy_version'] = deploy_versions[
                    data['service_id']] if deploy_versions else service.deploy_version
                data['image'] = service.image
                data['service_alias'] = service.service_alias
                data['service_name'] = service.service_name
                data['service_region'] = service.service_region
                data['creater'] = service.creater
                data["cmd"] = service.cmd
                data['probes'] = [jsonable_encoder(probe) for probe in probe_map.get(service.service_id, [])]
                e_m = dict()
                e_m['step_node'] = 1
                e_m['min_memory'] = 64
                e_m['init_memory'] = service.min_memory
                e_m['max_memory'] = 65536
                e_m['step_memory'] = 64
                e_m['is_restart'] = 0
                e_m['min_node'] = service.min_node
                e_m['container_cpu'] = service.min_cpu
                if is_singleton(service.extend_method):
                    e_m['max_node'] = 1
                else:
                    e_m['max_node'] = 64
                data['extend_method_map'] = e_m
                data['port_map_list'] = list()
                if service_port_map.get(service.service_id):
                    for port in service_port_map.get(service.service_id):
                        p = dict()
                        # 写需要返回的port数据
                        p['protocol'] = port.protocol
                        p['tenant_env_id'] = port.tenant_env_id
                        p['port_alias'] = port.port_alias
                        p['container_port'] = port.container_port
                        p['is_inner_service'] = port.is_inner_service
                        p['is_outer_service'] = port.is_outer_service
                        p['k8s_service_name'] = port.k8s_service_name
                        data['port_map_list'].append(p)

                data['service_volume_map_list'] = list()
                if service_volume_map.get(service.service_id):
                    for volume in service_volume_map.get(service.service_id):
                        s_v = dict()
                        s_v['file_content'] = ''
                        if volume.volume_type == "config-file":
                            config_file = (
                                session.execute(select(TeamComponentConfigurationFile).where(
                                    TeamComponentConfigurationFile.service_id == volume.service_id,
                                    or_(TeamComponentConfigurationFile.volume_id == volume.ID,
                                        TeamComponentConfigurationFile.volume_name == volume.volume_name)))
                            ).scalars().first()

                            if config_file:
                                s_v['file_content'] = config_file.file_content
                        s_v['category'] = volume.category
                        s_v['volume_capacity'] = volume.volume_capacity
                        s_v['volume_provider_name'] = volume.volume_provider_name
                        s_v['volume_type'] = volume.volume_type
                        s_v['volume_path'] = volume.volume_path
                        s_v['volume_name'] = volume.volume_name
                        s_v['access_mode'] = volume.access_mode
                        s_v['share_policy'] = volume.share_policy
                        s_v['backup_policy'] = volume.backup_policy
                        s_v['mode'] = volume.mode
                        data['service_volume_map_list'].append(s_v)

                data['service_env_map_list'] = list()
                data['service_connect_info_map_list'] = list()
                if service_env_map.get(service.service_id):
                    for env_change in service_env_map.get(service.service_id):
                        e_c = dict()
                        e_c['name'] = env_change.name
                        e_c['attr_name'] = env_change.attr_name
                        e_c['attr_value'] = env_change.attr_value
                        e_c['is_change'] = env_change.is_change
                        if env_change.scope == "outer":
                            data['service_connect_info_map_list'].append(e_c)
                            e_c['container_port'] = env_change.container_port
                        else:
                            data['service_env_map_list'].append(e_c)

                data['service_related_plugin_config'] = list()
                plugins_relation_list = (
                    session.execute(select(TeamComponentPluginRelation).where(
                        TeamComponentPluginRelation.service_id == service.service_id))
                ).scalars().all()

                for spr in plugins_relation_list:
                    service_plugin_config_var = (
                        session.execute(
                            select(ComponentPluginConfigVar).where(
                                ComponentPluginConfigVar.service_id == spr.service_id,
                                ComponentPluginConfigVar.plugin_id == spr.plugin_id,
                                ComponentPluginConfigVar.build_version == spr.build_version))
                    ).scalars().all()

                    plugin_data = spr.__dict__
                    plugin_data["attr"] = [jsonable_encoder(var) for var in service_plugin_config_var]
                    data['service_related_plugin_config'].append(plugin_data)
                # component monitor
                data["component_monitors"] = sid_2_monitors.get(service.service_id, None)
                data["component_graphs"] = sid_2_graphs.get(service.service_id, None)
                data["labels"] = labels.get(service.service_id, {})

                all_data_map[service.service_id] = data

            all_data = list()
            for service_id in all_data_map:
                service = all_data_map[service_id]
                service['dep_service_map_list'] = list()
                if dep_service_map.get(service['service_id']):
                    for dep in dep_service_map[service['service_id']]:
                        d = dict()
                        if all_data_map.get(dep.service_id):
                            # 通过service_key和service_id来判断依赖关系
                            d['dep_service_key'] = all_data_map[dep.service_id]["service_share_uuid"]
                            service['dep_service_map_list'].append(d)

                service["mnt_relation_list"] = list()

                if dep_mnt_map.get(service_id):
                    for dep_mnt in dep_mnt_map.get(service_id):
                        if not all_data_map.get(dep_mnt.dep_service_id):
                            continue
                        service["mnt_relation_list"].append({
                            "service_share_uuid":
                                all_data_map[dep_mnt.dep_service_id]["service_share_uuid"],
                            "mnt_name":
                                dep_mnt.mnt_name,
                            "mnt_dir":
                                dep_mnt.mnt_dir
                        })
                all_data.append(service)
            return all_data
        else:
            return []

    def get_team_service_deploy_version(self, session, region, tenant_env, service_ids):
        try:
            res, body = remote_build_client.get_env_services_deploy_version(session,
                                                                            region, tenant_env,
                                                                            {"service_ids": service_ids})
            if res.status == 200:
                service_versions = {}
                for version in body["list"]:
                    if version and "service_id" in version and "build_version" in version:
                        service_versions[version["service_id"]] = version["build_version"]
                return service_versions
        except Exception as e:
            logger.exception(e)
        logger.debug("======>get services deploy version failure")
        return None

    def get_service_ports_by_ids(self, service_ids, session: SessionClass):
        """
        根据多个组件ID查询组件的端口信息
        :param session: session
        :param service_ids: 组件ID列表
        :return: {"service_id":TenantServicesPort[object]}
        """
        port_list = session.execute(
            select(TeamComponentPort).where(TeamComponentPort.service_id.in_(service_ids))
        ).scalars().all()
        if port_list:
            service_port_map = {}
            for port in port_list:
                service_id = port.service_id
                tmp_list = []
                if service_id in list(service_port_map.keys()):
                    tmp_list = service_port_map.get(service_id)
                tmp_list.append(port)
                service_port_map[service_id] = tmp_list
            return service_port_map
        else:
            return {}

    def get_service_dependencys_by_ids(self, service_ids, session: SessionClass):
        """
        根据多个组件ID查询组件的依赖组件信息
        :param session:
        :param service_ids:组件ID列表
        :return: {"service_id":TenantServiceInfo[object]}
        """
        relation_list = (
            session.execute(select(TeamComponentRelation).where(TeamComponentRelation.service_id.in_(service_ids)))
        ).scalars().all()

        if relation_list:
            relation_list_service_ids = [relation.service_id for relation in relation_list]
            dep_service_map = {service_id: [] for service_id in relation_list_service_ids}
            for dep_service in relation_list:
                dep_service_info = (
                    session.execute(
                        select(Component).where(Component.service_id == dep_service.dep_service_id,
                                                Component.tenant_env_id == dep_service.tenant_env_id))
                ).scalars().first()

                if dep_service_info is None:
                    continue
                dep_service_map[dep_service.service_id].append(dep_service_info)
            return dep_service_map
        else:
            return {}

    def get_service_env_by_ids(self, service_ids, session: SessionClass):
        """
        获取组件env
        :param session:
        :param service_ids: 组件ID列表
        # :return: 可修改的环境变量service_env_change_map，不可修改的环境变量service_env_nochange_map
        :return: 环境变量service_env_map
        """
        env_list = (
            session.execute(select(ComponentEnvVar).where(ComponentEnvVar.service_id.in_(service_ids)))
        ).scalars().all()

        if env_list:
            service_env_map = {}
            for env in env_list:
                if env.scope == "build":
                    continue
                service_id = env.service_id
                tmp_list = []
                if service_id in list(service_env_map.keys()):
                    tmp_list = service_env_map.get(service_id)
                tmp_list.append(env)
                service_env_map[service_id] = tmp_list
            return service_env_map
        else:
            return {}

    def get_service_volume_by_ids(self, service_ids, session: SessionClass):
        """
        获取组件持久化目录
        """
        volume_list = (
            session.execute(select(TeamComponentVolume).where(TeamComponentVolume.service_id.in_(service_ids)))
        ).scalars().all()

        if volume_list:
            service_volume_map = {}
            for volume in volume_list:
                service_id = volume.service_id
                tmp_list = []
                if service_id in list(service_volume_map.keys()):
                    tmp_list = service_volume_map.get(service_id)
                tmp_list.append(volume)
                service_volume_map[service_id] = tmp_list
            return service_volume_map
        else:
            return {}

    def get_dep_mnts_by_ids(self, tenant_env_id, service_ids, session: SessionClass):
        mnt_relations = (
            session.execute(
                select(TeamComponentMountRelation).where(TeamComponentMountRelation.tenant_env_id == tenant_env_id,
                                                         TeamComponentMountRelation.service_id.in_(
                                                             service_ids)))
        ).scalars().all()

        if not mnt_relations:
            return {}
        result = {}
        for mnt_relation in mnt_relations:
            service_id = mnt_relation.service_id
            if service_id in list(result.keys()):
                values = result.get(service_id)
            else:
                values = []
                result[service_id] = values
            values.append(mnt_relation)

        return result

    def get_service_probes(self, service_ids, session: SessionClass):
        """
        获取组件健康检测探针
        """
        probe_list = (
            session.execute(select(ComponentProbe).where(ComponentProbe.service_id.in_(service_ids)))
        ).scalars().all()

        if probe_list:
            service_probe_map = {}
            for probe in probe_list:
                service_id = probe.service_id
                tmp_list = []
                if service_id in list(service_probe_map.keys()):
                    tmp_list = service_probe_map.get(service_id)
                tmp_list.append(probe)
                service_probe_map[service_id] = tmp_list
            return service_probe_map
        else:
            return {}

    @staticmethod
    def list_service_monitors(tenant_env_id, service_ids, session: SessionClass):
        monitors = (
            session.execute(select(ComponentMonitor).where(ComponentMonitor.tenant_env_id == tenant_env_id,
                                                           ComponentMonitor.service_id.in_(service_ids)))
        ).scalars().all()

        result = {}
        for monitor in monitors:
            if not result.get(monitor.service_id):
                result[monitor.service_id] = []
            m = jsonable_encoder(monitor)
            del m["ID"]
            result[monitor.service_id].append(m)
        return result

    @staticmethod
    def list_component_graphs(component_ids, session: SessionClass):
        graphs = (
            session.execute(select(ComponentGraph).where(ComponentGraph.component_id.in_(component_ids)))
        ).scalars().all()

        result = {}
        for graph in graphs:
            if not result.get(graph.component_id):
                result[graph.component_id] = []
            g = jsonable_encoder(graph)
            del g["ID"]
            result[graph.component_id].append(g)
        return result

    @staticmethod
    def list_component_labels(component_ids, session: SessionClass):
        component_labels = (
            session.execute(select(ComponentLabels).where(ComponentLabels.service_id.in_(component_ids)))
        ).scalars().all()

        labels = (
            session.execute(select(Labels).where(Labels.label_id.in_([label.label_id for label in component_labels])))
        ).scalars().all()

        labels = {label.label_id: label for label in labels}

        res = {}
        for component_label in component_labels:
            clabels = res.get(component_label.service_id, {})
            label = labels.get(component_label.label_id)
            if not label:
                logger.warning("component id: {}; label id: {}; label not found".format(component_label.service_id,
                                                                                        component_label.label_id))
                continue
            clabels[label.label_name] = label.label_alias
            res[component_label.service_id] = clabels
        return res

    def get_service_share_record_by_ID(self, session, ID, env_name):
        return component_share_repo.get_service_share_record_by_ID(session, ID=ID, env_name=env_name)

    def delete_record(self, session, ID, env_name):
        return component_share_repo.delete_record(session=session, ID=ID, env_name=env_name)

    def create_publish_event(self, session, record_event, user_name, event_type):
        import datetime
        event = ComponentEvent(
            event_id=make_uuid(),
            service_id=record_event.service_id,
            tenant_env_id=record_event.tenant_env_id,
            type=event_type,
            user_name=user_name,
            start_time=datetime.datetime.now(),
            status="",
            message="",
            deploy_version="",
            old_deploy_version="",
            code_version="",
            old_code_version="")
        session.merge(event)
        session.flush()
        return event

    def sync_event(self, session, user, region_name, tenant_env, record_event):
        app_version = center_app_repo.get_wutong_app_version_by_record_id(session=session,
                                                                          record_id=record_event.record_id)
        if not app_version:
            raise RbdAppNotFound("分享的应用不存在")
        event_type = "share-yb"
        if app_version.scope.startswith("goodrain"):
            event_type = "share-ys"
        event = self.create_publish_event(session, record_event, user.nick_name, event_type)
        record_event.event_id = event.event_id
        app_templetes = json.loads(app_version.app_template)
        apps = app_templetes.get("apps", None)
        if not apps:
            raise ServiceHandleException(msg="get share app info failed", msg_show="分享的应用信息获取失败", status_code=500)
        new_apps = list()
        try:
            for app in apps:
                # 处理事件的应用
                if app["service_key"] == record_event.service_key:
                    body = {
                        "service_key": app["service_key"],
                        "app_version": app_version.version,
                        "event_id": event.event_id,
                        "share_user": user.nick_name,
                        "share_scope": app_version.scope,
                        "image_info": app.get("service_image", None),
                        "slug_info": app.get("service_slug", None)
                    }
                    re_body = None
                    try:
                        res, re_body = remote_build_client.share_service(session,
                                                                         region_name, tenant_env,
                                                                         record_event.service_alias, body)
                        bean = re_body.get("bean")
                        if bean:
                            record_event.region_share_id = bean.get("share_id", None)
                            record_event.event_id = bean.get("event_id", None)
                            record_event.event_status = "start"
                            record_event.update_time = datetime.datetime.now()
                            session.flush()
                            image_name = bean.get("image_name", None)
                            if image_name:
                                app["share_image"] = image_name
                            slug_path = bean.get("slug_path", None)
                            if slug_path:
                                app["share_slug_path"] = slug_path
                            new_apps.append(app)
                        else:
                            raise ServiceHandleException(msg="share failed", msg_show="数据中心分享错误")
                    except remote_build_client.CallApiFrequentError as e:
                        logger.exception(e)
                        raise ServiceHandleException(msg="wait a moment please", msg_show="操作过于频繁，请稍后再试",
                                                     status_code=409)
                    except Exception as e:
                        logger.exception(e)
                        if re_body:
                            logger.error(re_body)
                        raise ServiceHandleException(msg="share failed", msg_show="数据中心分享错误", status_code=500)
                else:
                    new_apps.append(app)
            app_templetes["apps"] = new_apps
            app_version.app_template = json.dumps(app_templetes)
            app_version.update_time = datetime.datetime.now()
            session.flush()
            return record_event
        except ServiceHandleException as e:
            logger.exception(e)
            raise e
        except Exception as e:
            logger.exception(e)
            raise ServiceHandleException(msg="share failed", msg_show="应用分享介质同步发生错误", status_code=500)

    def get_sync_event_result(self, session, region_name, tenant_env, record_event):
        res, re_body = remote_build_client.share_service_result(session,
                                                                region_name, tenant_env, record_event.service_alias,
                                                                record_event.region_share_id)
        bean = re_body.get("bean")
        if bean and bean.get("status", None):
            record_event.event_status = bean.get("status", None)
            session.flush()
        return record_event

    def get_app_by_key(self, session, key):
        app = component_share_repo.get_app_by_key(session, key)
        if app:
            return app[0]
        else:
            return None

    def delete_app(self, session, key):
        component_share_repo.delete_app(session, key)

    def complete(self, session, tenant_env, user, share_record):
        app = component_share_repo.get_app_version_by_record_id(session, share_record.ID)
        app_market_url = None
        if app:
            app.is_complete = True
            app.update_time = datetime.datetime.now()
            session.flush()
            session.execute(delete(CenterAppVersion).where(
                CenterAppVersion.app_id == app.app_id,
                CenterAppVersion.source == "local",
                CenterAppVersion.scope == "wutong",
                CenterAppVersion.is_complete == 1
            ))
            session.flush()
            share_record.is_success = True
            share_record.step = 3
            share_record.status = 1
            share_record.update_time = datetime.datetime.now()
            session.flush()
        # 应用有更新，删除导出记录
        app_export_record_repo.delete_by_key_and_version(session, app.app_id, app.version)
        return app_market_url


share_service = ShareService()
