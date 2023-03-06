import json
import os
from sqlalchemy import select, delete, text

from core.setting import settings
from core.utils.crypt import make_uuid
from models.application.plugin import TeamComponentPluginRelation, ComponentPluginConfigVar, \
    PluginConfigGroup, PluginConfigItems
from repository.base import BaseRepository
from repository.plugin.plugin_config_repo import config_group_repo, config_item_repo
from repository.teams.team_plugin_repo import plugin_repo
from service.plugin.plugin_version_service import plugin_version_service


class AppPluginRelationRepository(BaseRepository[TeamComponentPluginRelation]):
    def overwrite_by_component_ids(self, session, component_ids, plugin_deps):
        plugin_deps = [plugin_dep for plugin_dep in plugin_deps if plugin_dep.service_id in component_ids]
        session.execute(delete(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id.in_(component_ids)
        ))
        for plugin_dep in plugin_deps:
            session.merge(plugin_dep)
        session.flush()

    def list_by_component_ids(self, session, service_ids):
        rels = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id.in_(service_ids)
        )).scalars().all()
        return [rel for rel in rels]

    def check_plugins_by_eid(self, session):
        """
        check if an app has been shared
        """
        sql = """
            SELECT
                a.plugin_id
            FROM
                tenant_service_plugin_relation a,
                tenant_service c,
                tenant_info b
            WHERE
                c.tenant_env_id = b.tenant_env_id
                AND a.service_id = c.service_id
                AND c.service_source <> 'market'
                LIMIT 1"""
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def get_used_plugin_services(self, session, plugin_id):
        """获取使用了某个插件的组件"""
        results = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.plugin_id == plugin_id))
        return results.scalars().all()

    def delete_service_plugin_relation_by_plugin_id(self, session, plugin_id):
        session.execute(delete(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.plugin_id == plugin_id))

    def get_service_plugin_relation_by_service_id(self, session, service_id):
        results = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_status == 1))
        return results.scalars().all()

    def delete_service_plugin_relation_by_service_id(self, session, service_id, build_error_plugin_ids):
        session.execute(delete(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_status == 1,
            TeamComponentPluginRelation.plugin_id.in_(build_error_plugin_ids)
        ))

    def get_service_plugin_relation(self, session, service_id):
        results = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id))
        return results.scalars().all()

    def get_relation_by_service_and_plugin(self, session, service_id, plugin_id):
        results = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_id == plugin_id))
        return results.scalars().all()

    def get_relation_by_service_and_plugin_version(self, session, service_id, plugin_id, build_version):
        results = session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.build_version == build_version,
            TeamComponentPluginRelation.plugin_id == plugin_id))
        return results.scalars().first()

    def create_service_plugin_relation(self, session, **params):
        """创建组件插件关系"""
        tsp = TeamComponentPluginRelation(**params)
        session.add(tsp)

        return tsp

    def delete_service_plugin(self, session, service_id, plugin_id):
        session.execute(delete(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_id == plugin_id))

    def update_service_plugin_status(self, session, service_id, plugin_id, is_active, cpu, memory):
        tspr = (session.execute(select(TeamComponentPluginRelation).where(
            TeamComponentPluginRelation.service_id == service_id,
            TeamComponentPluginRelation.plugin_id == plugin_id))).scalars().first()
        tspr.plugin_status = is_active
        if cpu is not None and type(cpu) == int and cpu >= 0:
            tspr.min_cpu = cpu
        if memory is not None and type(memory) == int and memory >= 0:
            tspr.min_memory = memory


class ServicePluginConfigVarRepository(BaseRepository[ComponentPluginConfigVar]):

    def overwrite_by_component_ids(self, session, component_ids, plugin_configs):
        plugin_configs = [config for config in plugin_configs if config.service_id in component_ids]
        session.execute(delete(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.service_id.in_(component_ids)
        ))
        for plugin_config in plugin_configs:
            session.merge(plugin_config)
        session.flush()

    def list_by_component_ids(self, session, component_ids):
        configs = session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.service_id.in_(component_ids)
        )).scalars().all()
        return [config for config in configs]

    def get_service_plugin_config_var(self, session, service_id, plugin_id, build_version):
        return session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id,
            ComponentPluginConfigVar.service_id == service_id,
            ComponentPluginConfigVar.build_version == build_version)).scalars().all()

    def get_service_plugin_downstream_envs(self, session, service_id, plugin_id, build_version,
                                           service_meta_type, dest_service_id, container_port):
        return session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id,
            ComponentPluginConfigVar.service_id == service_id,
            ComponentPluginConfigVar.build_version == build_version,
            ComponentPluginConfigVar.service_meta_type == service_meta_type,
            ComponentPluginConfigVar.dest_service_id == dest_service_id,
            ComponentPluginConfigVar.container_port == container_port)).scalars().all()

    def get_service_plugin_config(self, session, service_id, plugin_id):
        return session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id,
            ComponentPluginConfigVar.service_id == service_id)).scalars().first()

    def get_sys_service_plugin_config(self, session, plugin_id):
        return session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id)).scalars().first()

    file_path = os.path.join('service/plugin/default_config.json')
    with open(file_path, encoding='utf-8') as f:
        all_default_config = json.load(f)

    def update_sys_plugin(self, session, plugin, tenant_env, plugin_type, user, region, needed_plugin_config,
                          build_version):
        build_cmd = ""
        if plugin_type == "mysql_dbgate_plugin" or plugin_type == "redis_dbgate_plugin":
            min_memory = 512
        elif plugin_type == "filebrowser_plugin":
            min_memory = 256
        else:
            min_memory = 64

        if plugin_type == "java_agent_plugin":
            build_cmd = "cp agent.jar /agent/agent.jar"

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

        plugin_build_version = plugin_version_service.create_build_version(session=session,
                                                                           region=region,
                                                                           plugin_id=plugin.plugin_id,
                                                                           tenant_env_id=tenant_env.env_id,
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
        return plugin_build_version

    def get_plugins_by_origin(self, session, region, tenant_env, service_id, origin, user):
        """获取组件已开通和未开通的插件"""

        QUERY_INSTALLED_SQL = """
        SELECT
            tp.plugin_id AS plugin_id,
            tp.DESC AS "desc",
            tp.plugin_alias AS plugin_alias,
            tp.category AS category,
            tp.origin_share_id AS origin_share_id,
            pbv.build_version AS build_version,
            tsp.min_memory AS min_memory,
            tsp.plugin_status AS plugin_status,
            tsp.min_cpu As min_cpu
        FROM
            tenant_service_plugin_relation tsp
            LEFT JOIN plugin_build_version pbv ON tsp.plugin_id = pbv.plugin_id
            AND tsp.build_version = pbv.build_version
            JOIN tenant_plugin tp ON tp.plugin_id = tsp.plugin_id
            AND tp.tenant_env_id = pbv.tenant_env_id
        WHERE
            tsp.service_id = "{0}"
            AND tp.region = "{1}"
            AND tp.tenant_env_id = "{2}" """.format(service_id, region, tenant_env.env_id)

        QUERI_UNINSTALLED_SQL = """
            SELECT
                tp.plugin_id AS plugin_id,
                tp.DESC AS "desc",
                tp.plugin_alias AS plugin_alias,
                tp.category AS category,
                pbv.build_version AS build_version
            FROM
                tenant_plugin AS tp
                JOIN plugin_build_version AS pbv ON tp.plugin_id = pbv.plugin_id
                AND tp.tenant_env_id = pbv.tenant_env_id
            WHERE
                pbv.plugin_id NOT IN ( SELECT plugin_id FROM tenant_service_plugin_relation WHERE service_id = "{0}" )
                AND tp.tenant_env_id = "{1}"
                AND tp.region = "{2}"
                AND pbv.build_status = "{3}"
        """.format(service_id, tenant_env.env_id, region, "build_success")

        SHARED_QUERI_UNINSTALLED_SQL = """
            SELECT
                tp.plugin_id AS plugin_id,
                tp.DESC AS "desc",
                tp.plugin_alias AS plugin_alias,
                tp.category AS category,
                pbv.build_version AS build_version
            FROM
                tenant_plugin AS tp
                JOIN plugin_build_version AS pbv ON tp.plugin_id = pbv.plugin_id
                AND tp.tenant_env_id = pbv.tenant_env_id
            WHERE
                pbv.plugin_id NOT IN ( SELECT plugin_id FROM tenant_service_plugin_relation WHERE service_id = "{0}")
                AND tp.region = "{1}"
        """.format(service_id, region)

        SHARED_QUERY_INSTALLED_SQL = """
        SELECT
            tp.plugin_id AS plugin_id,
            tp.DESC AS "desc",
            tp.plugin_alias AS plugin_alias,
            tp.category AS category,
            tp.origin_share_id AS origin_share_id,
            pbv.build_version AS build_version,
            tsp.min_memory AS min_memory,
            tsp.plugin_status AS plugin_status,
            tsp.min_cpu As min_cpu
        FROM
            tenant_service_plugin_relation tsp
            LEFT JOIN plugin_build_version pbv ON tsp.plugin_id = pbv.plugin_id
            AND tsp.build_version = pbv.build_version
            JOIN tenant_plugin tp ON tp.plugin_id = tsp.plugin_id
            AND tp.tenant_env_id = pbv.tenant_env_id
        WHERE
            tsp.service_id = "{0}"
            AND tp.region = "{1}" """.format(service_id, region)
        uninstalled_plugins = []
        installed_plugins = []
        if origin == "sys":
            all_default_config = self.all_default_config
            if not all_default_config:
                raise Exception("no config was found")

            plugins_type = all_default_config.keys()
            for plugin_type in plugins_type:
                needed_plugin_config = all_default_config[plugin_type]
                plugin_id = needed_plugin_config.get("plugin_id", "")
                desc = needed_plugin_config.get("desc", "")
                plugin_alias = needed_plugin_config.get("plugin_alias", "")
                category = needed_plugin_config.get("category", "")
                build_version = needed_plugin_config.get("build_version", "")
                origin_share_id = needed_plugin_config.get("origin_share_id", "")

                plugin_dict = {
                    "plugin_type": plugin_type,
                    "plugin_id": plugin_id,
                    "desc": desc,
                    "plugin_alias": plugin_alias,
                    "category": category,
                    "build_version": build_version
                }

                install_plugins_rel = app_plugin_relation_repo.get_service_plugin_relation(session, service_id)
                if install_plugins_rel:
                    is_open = False
                    for plugin_rel in install_plugins_rel:
                        plugin_id = plugin_rel.plugin_id
                        plugin = plugin_repo.get_by_plugin_id(session, plugin_id)

                        if plugin.origin == origin and plugin.origin_share_id == plugin_type:
                            plugin_dict.update({"origin_share_id": origin_share_id})
                            plugin_dict.update({"min_memory": plugin_rel.min_memory})
                            plugin_dict.update({"plugin_status": plugin_rel.plugin_status})
                            plugin_dict.update({"min_cpu": plugin_rel.min_cpu})
                            plugin_dict.update({"build_version": plugin_rel.build_version})
                            plugin_dict.update({"new_build_version": build_version})
                            plugin_dict.update({"plugin_id": plugin_id})
                            installed_plugins.append(plugin_dict.copy())
                            is_open = True
                    if not is_open:
                        uninstalled_plugins.append(plugin_dict)
                else:
                    uninstalled_plugins.append(plugin_dict)
        elif origin == "shared":
            query_installed_plugin = """{0} AND tp.origin="{1}" """.format(SHARED_QUERY_INSTALLED_SQL, origin)

            query_uninstalled_plugin = """{0} AND tp.origin="{1}" """.format(SHARED_QUERI_UNINSTALLED_SQL, origin)

            installed_plugins = (session.execute(query_installed_plugin)).fetchall()
            uninstalled_plugins = (session.execute(query_uninstalled_plugin)).fetchall()

        else:
            query_installed_plugin = """{0} AND tp.origin="{1}" """.format(QUERY_INSTALLED_SQL, origin)

            query_uninstalled_plugin = """{0} AND tp.origin="{1}" """.format(QUERI_UNINSTALLED_SQL, origin)

            installed_plugins = (session.execute(query_installed_plugin)).fetchall()
            uninstalled_plugins = (session.execute(query_uninstalled_plugin)).fetchall()
        return installed_plugins, uninstalled_plugins

    def delete_service_plugin_config_var(self, session, service_id, plugin_id):
        session.execute(delete(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.plugin_id == plugin_id,
            ComponentPluginConfigVar.service_id == service_id))

    def create_bulk_service_plugin_config_var(self, session, service_plugin_var):
        session.add_all(service_plugin_var)
        session.flush()

    def get_service_plugin_all_config(self, session, service_id):
        return (session.execute(select(ComponentPluginConfigVar).where(
            ComponentPluginConfigVar.service_id == service_id))).scalars().all()


app_plugin_relation_repo = AppPluginRelationRepository(TeamComponentPluginRelation)
service_plugin_config_repo = ServicePluginConfigVarRepository(ComponentPluginConfigVar)
