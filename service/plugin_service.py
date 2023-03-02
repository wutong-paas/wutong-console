import json
import os
from loguru import logger
from clients.remote_plugin_client import remote_plugin_client
from core.setting import settings
from core.utils.constants import PluginCategoryConstants, DefaultPluginConstants, PluginImage
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.bcode import ErrPluginIsUsed
from exceptions.main import ServiceHandleException
from models.application.plugin import PluginConfigGroup, PluginConfigItems
from repository.plugin.plugin_config_repo import config_item_repo, config_group_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.plugin.plugin_version_service import plugin_version_service

allow_plugins = [
    PluginCategoryConstants.OUTPUT_INPUT_NET, PluginCategoryConstants.OUTPUT_NET, PluginCategoryConstants.INPUT_NET,
    PluginCategoryConstants.PERFORMANCE_ANALYSIS, PluginCategoryConstants.INIT_TYPE,
    PluginCategoryConstants.COMMON_TYPE, PluginCategoryConstants.EXPORTER_TYPE,
    PluginCategoryConstants.DBGATE_TYPE
]

default_plugins = [
    DefaultPluginConstants.DOWNSTREAM_NET_PLUGIN, DefaultPluginConstants.PERF_ANALYZE_PLUGIN,
    DefaultPluginConstants.INANDOUT_NET_PLUGIN, DefaultPluginConstants.FILEBEAT_LOG_PLUGIN,
    DefaultPluginConstants.LOGTAIL_LOG_PLUGIN, DefaultPluginConstants.MYSQLD_EXPORTER_PLUGIN,
    DefaultPluginConstants.FILEBROWSER_PLUGIN, DefaultPluginConstants.MYSQL_DBGATE_PLUGIN,
    DefaultPluginConstants.REDIS_DBGATE_PLUGIN, DefaultPluginConstants.JAVA_AGENT_PLUGIN
]


class PluginService(object):

    def get_tenant_plugins(self, session: SessionClass, region, tenant_env):
        return plugin_repo.get_tenant_plugins(session, tenant_env.tenant_id, region)

    def create_tenant_plugin(self, session: SessionClass, plugin_params):
        plugin_id = make_uuid()
        plugin_params["plugin_id"] = plugin_id
        plugin_params["plugin_name"] = "wt" + plugin_id[:6]
        if plugin_params["build_source"] == "dockerfile" and not plugin_params["code_repo"]:
            return 400, "代码仓库不能为空", None
        if plugin_params["build_source"] == "image" and not plugin_params["image"]:
            return 400, "镜像地址不能为空", None
        if plugin_params["category"] not in allow_plugins:
            return 400, "插件类别参数不支持", None
        tenant_plugin = plugin_repo.create_plugin(session, **plugin_params)
        return 200, "success", tenant_plugin

    def create_region_plugin(self, session: SessionClass, region, tenant_env, tenant_plugin, image_tag="latest"):
        """创建region端插件信息"""
        plugin_data = dict()
        plugin_data["build_model"] = tenant_plugin.build_source
        plugin_data["git_url"] = tenant_plugin.code_repo
        plugin_data["image_url"] = "{0}:{1}".format(tenant_plugin.image, image_tag)
        plugin_data["plugin_id"] = tenant_plugin.plugin_id
        plugin_data["plugin_info"] = tenant_plugin.desc
        plugin_data["plugin_model"] = tenant_plugin.category
        plugin_data["plugin_name"] = tenant_plugin.plugin_name
        plugin_data["tenant_id"] = tenant_env.tenant_id
        plugin_data["origin"] = tenant_plugin.origin
        remote_plugin_client.create_plugin(session, region, tenant_env, plugin_data)
        return 200, "success"

    def build_plugin(self, session: SessionClass, region, plugin, plugin_version, user, tenant_env, event_id,
                     image_info=None):

        build_data = dict()

        build_data["build_version"] = plugin_version.build_version
        build_data["event_id"] = event_id
        build_data["info"] = plugin_version.update_info

        build_data["operator"] = user.nick_name
        build_data["plugin_cmd"] = plugin_version.build_cmd
        build_data["plugin_memory"] = int(plugin_version.min_memory)
        build_data["plugin_cpu"] = int(plugin_version.min_cpu)
        build_data["repo_url"] = plugin_version.code_version
        build_data["username"] = plugin.username  # git username
        build_data["password"] = plugin.password  # git password
        build_data["tenant_id"] = tenant_env.tenant_id
        build_data["ImageInfo"] = image_info
        build_data["build_image"] = "{0}:{1}".format(plugin.image, plugin_version.image_tag)
        origin = plugin.origin
        if origin == "sys":
            plugin_from = "yb"
        elif origin == "market":
            plugin_from = "ys"
        else:
            plugin_from = None
        build_data["plugin_from"] = plugin_from

        body = remote_plugin_client.build_plugin(session, region, tenant_env, plugin.plugin_id, build_data)
        return body

    def delete_plugin(self, session: SessionClass, region, tenant_env, plugin_id, ignore_cluster_resource=False,
                      is_force=False):
        services = app_plugin_relation_repo.get_used_plugin_services(session=session, plugin_id=plugin_id)
        if services and not is_force:
            raise ErrPluginIsUsed
        if not ignore_cluster_resource:
            try:
                remote_plugin_client.delete_plugin(session, region, tenant_env, plugin_id)
            except remote_plugin_client.CallApiError as e:
                if e.status != 404:
                    raise ServiceHandleException(msg="delete plugin form cluster failure", msg_show="从集群删除插件失败")
        app_plugin_relation_repo.delete_service_plugin_relation_by_plugin_id(session=session, plugin_id=plugin_id)
        plugin_version_repo.delete_build_version_by_plugin_id(session=session, tenant_id=tenant_env.tenant_id,
                                                              plugin_id=plugin_id)
        plugin_repo.delete_by_plugin_id(session=session, tenant_id=tenant_env.tenant_id, plugin_id=plugin_id)
        config_item_repo.delete_config_items_by_plugin_id(session=session, plugin_id=plugin_id)
        config_group_repo.delete_config_group_by_plugin_id(session=session, plugin_id=plugin_id)

    # all_default_config = None
    module_dir = os.path.dirname(__file__)
    file_path = os.path.join(module_dir, 'plugin/default_config.json')
    with open(file_path, encoding='utf-8') as f:
        all_default_config = json.load(f)

    def add_default_plugin(self, session: SessionClass, user, tenant_env, region, plugin_type="perf_analyze_plugin",
                           build_version=None):
        plugin_base_info = None
        try:
            if not self.all_default_config:
                raise Exception("no config was found")
            needed_plugin_config = self.all_default_config[plugin_type]
            image = needed_plugin_config.get("image", "")
            build_source = needed_plugin_config.get("build_source", "")
            image_tag = "latest"
            if image and build_source and build_source == "image":
                ref = image.split(":")
                if len(ref) > 1:
                    image_tag = ":".join(ref[1:])
                if "goodrain.me" in image:
                    _, name = ref.split_hostname()
                    image = settings.IMAGE_REPO + "/" + name
                else:
                    image = ref[0]
            plugin_params = {
                "tenant_id": "-",
                "region": region,
                "create_user": user.user_id,
                "desc": needed_plugin_config["desc"],
                "plugin_alias": needed_plugin_config["plugin_alias"],
                "category": needed_plugin_config["category"],
                "build_source": build_source,
                "image": image,
                "code_repo": needed_plugin_config["code_repo"],
                "username": "",
                "password": ""
            }
            code, msg, plugin_base_info = self.create_tenant_plugin(session=session, plugin_params=plugin_params)
            plugin_base_info.origin = "sys"
            plugin_base_info.origin_share_id = plugin_type
            # plugin_base_info.save()

            build_cmd = ""
            if plugin_type == "mysql_dbgate_plugin" or plugin_type == "redis_dbgate_plugin":
                min_memory = 512
            elif plugin_type == "filebrowser_plugin":
                min_memory = 256
            elif plugin_type == "java_agent_plugin":
                min_memory = 0
                build_cmd = "cp agent.jar /agent/agent.jar"
            else:
                min_memory = 64

            plugin_build_version = plugin_version_service.create_build_version(session=session,
                                                                               region=region,
                                                                               plugin_id=plugin_base_info.plugin_id,
                                                                               tenant_id=tenant_env.tenant_id,
                                                                               user_id=user.user_id, update_info="",
                                                                               build_status="unbuild",
                                                                               min_memory=min_memory,
                                                                               image_tag=image_tag,
                                                                               build_version=build_version,
                                                                               build_cmd=build_cmd)

            plugin_config_meta_list = []
            config_items_list = []
            config_group = needed_plugin_config.get("config_group")
            if config_group:
                for config in config_group:
                    options = config["options"]
                    plugin_config_meta = PluginConfigGroup(
                        plugin_id=plugin_build_version.plugin_id,
                        build_version=plugin_build_version.build_version,
                        config_name=config["config_name"],
                        service_meta_type=config["service_meta_type"],
                        injection=config["injection"])
                    plugin_config_meta_list.append(plugin_config_meta)

                    for option in options:
                        config_item = PluginConfigItems(
                            plugin_id=plugin_build_version.plugin_id,
                            build_version=plugin_build_version.build_version,
                            service_meta_type=config["service_meta_type"],
                            attr_name=option["attr_name"],
                            attr_alt_value=option["attr_alt_value"],
                            attr_type=option.get("attr_type", "string"),
                            attr_default_value=option.get("attr_default_value", None),
                            is_change=option.get("is_change", False),
                            attr_info=option.get("attr_info", ""),
                            protocol=option.get("protocol", ""))
                        config_items_list.append(config_item)

                config_group_repo.bulk_create_plugin_config_group(session, plugin_config_meta_list)
                config_item_repo.bulk_create_items(session, config_items_list)

            event_id = make_uuid()
            plugin_build_version.event_id = event_id
            plugin_build_version.plugin_version_status = "fixed"

            self.create_region_plugin(session=session, region=region, tenant_env=tenant_env, tenant_plugin=plugin_base_info,
                                      image_tag=image_tag)

            self.build_plugin(session=session, region=region, plugin=plugin_base_info,
                              plugin_version=plugin_build_version, user=user, tenant_env=tenant_env, event_id=event_id)
            plugin_build_version.build_status = "build_success"

            return plugin_base_info.plugin_id

        except Exception as e:
            logger.exception(e)
            if plugin_base_info:
                self.delete_plugin(session=session, region=region, tenant_env=tenant_env, plugin_id=plugin_base_info.plugin_id,
                                   is_force=True)
            raise e

    def get_default_plugin(self, session: SessionClass, region, tenant_env):
        # 兼容3.5版本升级
        plugins = plugin_repo.get_def_tenant_plugins(session, tenant_env.tenant_id,
                                                     region, [plugin for plugin in default_plugins])
        if plugins:
            return plugins
        else:
            DEF_IMAGE_REPO = "goodrain.me"
            IMAGE_REPO = os.getenv("IMAGE_REPO", DEF_IMAGE_REPO)
            return plugin_repo.get_default_tenant_plugins(session, tenant_env.tenant_id, region, PluginImage, IMAGE_REPO)

    def get_default_plugin_from_cache(self, session: SessionClass, region, tenant_env):
        if not self.all_default_config:
            raise Exception("no config was found")

        default_plugin_list = []
        for plugin in self.all_default_config:
            default_plugin_list.append({
                "category": plugin,
                "plugin_alias": self.all_default_config[plugin].get("plugin_alias"),
                "desc": self.all_default_config[plugin].get("desc"),
                "plugin_type": self.all_default_config[plugin].get("category"),
            })

        installed_default_plugin_alias_list = None
        installed_default_plugins = self.get_default_plugin(session=session, region=region, tenant_env=tenant_env)
        if installed_default_plugins:
            installed_default_plugin_alias_list = [plugin.plugin_alias for plugin in installed_default_plugins]

        for plugin in default_plugin_list:
            plugin["has_install"] = False
            if installed_default_plugin_alias_list is not None and plugin[
                "plugin_alias"] in installed_default_plugin_alias_list:
                plugin["has_install"] = True

        return default_plugin_list

    def delete_console_tenant_plugin(self, session, tenant_id, plugin_id):
        plugin_repo.delete_by_plugin_id(session, tenant_id, plugin_id)

    def update_region_plugin_info(self, session, region, tenant_env, tenant_plugin, plugin_build_version):
        data = dict()
        data["build_model"] = tenant_plugin.build_source
        data["git_url"] = tenant_plugin.code_repo
        image = tenant_plugin.image
        version = image.split(':')[-1]
        if not version:
            data["image_url"] = "{0}:{1}".format(tenant_plugin.image, plugin_build_version.image_tag)
        else:
            data["image_url"] = tenant_plugin.image
        data["plugin_info"] = tenant_plugin.desc
        data["plugin_model"] = tenant_plugin.category
        data["plugin_name"] = tenant_plugin.plugin_name
        remote_plugin_client.update_plugin_info(session,
                                                region, tenant_env, tenant_plugin.plugin_id, data)

    def get_plugin_event_log(self, session, region, tenant_env, event_id, level):
        data = {"event_id": event_id, "level": level}
        body = remote_plugin_client.get_plugin_event_log(session, region, tenant_env, data)
        return body["list"]

    def get_by_plugin_id(self, session: SessionClass, tenant_id, plugin_id):
        plugin = plugin_repo.get_by_plugin_id(session, plugin_id)
        return plugin

    def get_by_share_plugins(self, session: SessionClass, tenant_id, origin):
        plugins = plugin_repo.get_by_share_plugins(session, tenant_id, origin)
        return plugins

    def get_by_type_plugins(self, session: SessionClass, plugin_type, origin, service_region):
        plugins = plugin_repo.get_by_type_plugins(session, plugin_type, origin, service_region)
        return plugins


plugin_service = PluginService()
