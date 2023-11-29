import json
import time
from addict import Dict
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select, delete
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException, MarketAppLost, RbdAppNotFound, AbortRequest
from models.application.models import Application, ApplicationUpgradeRecord
from models.component.models import TeamApplication
from models.market.models import CenterApp, CenterAppTagsRelation, CenterAppVersion, CenterAppTag
from models.teams import TeamEnvInfo
from repository.application.app_repository import app_tag_repo, app_repo
from repository.application.app_upgrade_repo import upgrade_repo
from repository.component.component_repo import tenant_service_group_repo, service_source_repo
from repository.component.group_service_repo import service_info_repo
from repository.market.center_repo import center_app_repo
from service.application_service import application_service
from service.component_group import ComponentGroup
from service.market_app.app_upgrade import AppUpgrade


class MarketAppService(object):

    def list_app_upgradeable_versions(self, session, record: ApplicationUpgradeRecord):
        component_group = tenant_service_group_repo.get_component_group(session, record.upgrade_group_id)
        component_group = ComponentGroup(component_group, record.old_version)
        app_template_source = component_group.app_template_source(session)
        return self.__get_upgradeable_versions(session,
                                               component_group.app_model_key, component_group.version,
                                               app_template_source.get_template_update_time())

    def update_wutong_app_install_num(self, session, app_id, app_version):
        app_repo.add_wutong_install_num(session, app_id, app_version)

    def get_wutong_app(self, session, app_id):
        return app_repo.get_wutong_app_qs_by_key(session, app_id)

    def check_market_service_info(self, session, tenant_env, service):
        app_not_found = MarketAppLost("当前云市应用已删除")
        service_source = service_source_repo.get_service_source(session, tenant_env.env_id, service.service_id)
        if not service_source:
            logger.info("app has been delete on market:{0}".format(service.service_cname))
            raise app_not_found
        wutong_app, wutong_app_version = market_app_service.get_wutong_app_and_version(
            session, service_source.group_key, service_source.version)
        if not wutong_app or not wutong_app_version:
            logger.info("app has been delete on market:{0}".format(service.service_cname))
            raise app_not_found

    def delete_wutong_app_version(self, session, app_id, version):
        try:
            app_repo.delete_app_version_by_version(session, app_id, version)
        except Exception as e:
            logger.exception(e)
            raise e

    def update_wutong_app_version_info(self, session, app_id, version, **body):
        version = app_repo.update_app_version(session, app_id, version, **body)
        if not version:
            raise ServiceHandleException(msg="can't get version", msg_show="应用下无该版本", status_code=404)
        return version

    def _get_wutong_app_min_memory(self, apps_model_versions):
        apps_min_memory = dict()
        for app_model_version in apps_model_versions:
            min_memory = 0
            try:
                app_temp = json.loads(app_model_version.app_template)
                for app in app_temp.get("apps"):
                    if app.get("extend_method_map"):
                        try:
                            if app.get("extend_method_map").get("init_memory"):
                                min_memory += int(app.get("extend_method_map").get("init_memory"))
                            else:
                                min_memory += int(app.get("extend_method_map").get("min_memory"))
                        except Exception:
                            pass
                apps_min_memory[app_model_version.app_id] = min_memory
            except ValueError:
                pass
            if min_memory <= apps_min_memory.get(app_model_version.app_id, 0):
                apps_min_memory[app_model_version.app_id] = min_memory
        return apps_min_memory

    def _patch_wutong_app_versions_tag(self, session, apps, is_complete):
        app_ids = [app.app_id for app in apps]
        versions = center_app_repo.get_wutong_app_version_by_app_ids(session, app_ids, is_complete,
                                                                     rm_template_field=True)
        tags = app_tag_repo.get_multi_apps_tags(session, app_ids)
        app_with_tags = dict()
        app_with_versions = dict()
        app_release_ver_nums = dict()
        app_not_release_ver_nums = dict()

        for tag in tags:
            if not app_with_tags.get(tag.app_id):
                app_with_tags[tag.app_id] = []
            app_with_tags[tag.app_id].append({"tag_id": tag.ID, "name": tag.name})

        # versions = versions[:200]
        for version in versions:
            if not app_with_versions.get(version.app_id):
                app_with_versions[version.app_id] = dict()
                app_release_ver_nums[version.app_id] = []
                app_not_release_ver_nums[version.app_id] = []

            version_info = {
                "is_complete": version.is_complete,
                "version": version.version,
                "version_alias": version.version_alias,
                "dev_status": version.dev_status,
            }
            # If the versions are the same, take the last version information
            app_with_versions[version.app_id][version_info["version"]] = version_info
            if version_info["version"] in app_release_ver_nums[version.app_id]:
                app_release_ver_nums[version.app_id].remove(version_info["version"])
            if version_info["version"] in app_not_release_ver_nums[version.app_id]:
                app_not_release_ver_nums[version.app_id].remove(version_info["version"])
            if version_info["dev_status"] == "release":
                app_release_ver_nums[version.app_id].append(version_info["version"])
                continue
            app_not_release_ver_nums[version.app_id].append(version_info["version"])

        apps_min_memory = self._get_wutong_app_min_memory(versions)
        apps_list = []
        for app in apps:
            app_dict = jsonable_encoder(app)
            dev_status = ""
            app_dict.update({"dev_status": ""})
            app_dict.update({"versions_info": []})
            app_dict["tags"] = app_with_tags.get(app.app_id)
            min_memory = apps_min_memory.get(app.app_id, 0)
            if len(app_with_versions.get(app.app_id, {})) == 0:
                apps_list.append(app_dict)
                continue
            versions = []
            # sort rainbond app versions by version
            release_ver_nums = app_release_ver_nums.get(app.app_id, [])
            not_release_ver_nums = app_not_release_ver_nums.get(app.app_id, [])
            # If there is a version to release, set the application to release state
            if len(release_ver_nums) > 0:
                app_dict["dev_status"] = "release"
                release_ver_nums = sorted_versions(release_ver_nums)
            if len(not_release_ver_nums) > 0:
                not_release_ver_nums = sorted_versions(not_release_ver_nums)
            # Obtain version information according to the sorted version number and construct the returned data
            release_ver_nums.extend(not_release_ver_nums)
            for ver_num in release_ver_nums:
                versions.append(app_with_versions[app.app_id][ver_num])
            versions_info = list(reversed(versions))
            app_dict.update({"versions_info": versions_info})
            app_dict.update({"min_memory": min_memory})
            app_dict.update({"dev_status": dev_status})
            apps_list.append(app_dict)
        return apps_list

    def get_visiable_apps(self,
                          session,
                          user,
                          scope,
                          app_name,
                          sort_type,
                          teams=None,
                          tag_names=None,
                          is_complete=True,
                          page=1,
                          page_size=10,
                          need_install="false"):
        apps = center_app_repo.get_wutong_app_in_enterprise_by_query(session, scope, app_name, sort_type, teams,
                                                                     tag_names,
                                                                     page,
                                                                     page_size,
                                                                     need_install)
        count = center_app_repo.get_wutong_app_total_count(session, scope, teams, app_name, tag_names,
                                                           need_install)
        if not apps:
            return [], count

        apps_list = self._patch_wutong_app_versions_tag(session, apps, is_complete)
        return apps_list, count

    def list_app_versions(self, session, component_source):
        versions = center_app_repo.get_wutong_app_versions(session, component_source.group_key)
        return versions

    def __upgradable_versions(self, component_source, versions):
        current_version = component_source.version
        current_version_time = component_source.get_template_update_time()
        result = []
        for version in versions:
            new_version_time = time.mktime(version.update_time.timetuple())
            compare = compare_version(version.version, current_version)
            if compare == 1:
                result.append(version.version)
            elif current_version_time:
                version_time = time.mktime(current_version_time.timetuple())
                if compare == 0 and new_version_time > version_time:
                    result.append(version.version)
        result = list(set(result))
        result.sort(reverse=True)
        return result

    def list_wutong_app_components(self, session, tenant_env, app_id, model_app_key, upgrade_group_id):
        """
        return the list of the rainbond app.
        """
        # list components by app_id
        component_sources_list = []
        _, component_sources = application_service.get_component_and_resource_by_group_ids(session, app_id,
                                                                                           [upgrade_group_id])
        for component_source in component_sources:
            if component_source.group_key == model_app_key:
                component_sources_list.append(component_source)
        if not component_sources_list:
            return []
        component_ids = [cs.service_id for cs in component_sources_list]
        components = service_info_repo.list_by_component_ids(session, component_ids)

        versions = self.list_app_versions(session, component_sources_list[0])

        # make a map of component_sources
        component_sources = {cs.service_id: cs for cs in component_sources_list}

        result = []
        for component in components:
            component_source = component_sources[component.service_id]
            cpt = jsonable_encoder(component)
            cpt["upgradable_versions"] = self.__upgradable_versions(component_source, versions)
            cpt["current_version"] = component_source.version
            result.append(cpt)

        return result

    def create_wutong_app(self, session, app_info, app_id):
        app = CenterApp(
            app_id=app_id,
            app_name=app_info.get("app_name"),
            create_user=app_info.get("create_user"),
            create_user_name=app_info.get("create_user_name"),
            create_team=app_info.get("create_team"),
            pic=app_info.get("pic"),
            source=app_info.get("source"),
            dev_status=app_info.get("dev_status"),
            scope=app_info.get("scope"),
            describe=app_info.get("describe"),
            details=app_info.get("details"),
        )
        session.add(app)
        session.flush()
        # save app and tag relation
        if app_info.get("tag_ids"):
            app_tag_repo.create_app_tags_relation(session, app, app_info.get("tag_ids"))

    # todo 事务
    def update_wutong_app(self, session: SessionClass, app_id, app_info):
        app = (
            session.execute(select(CenterApp).where(CenterApp.app_id == app_id))
        ).scalars().first()

        if not app:
            raise RbdAppNotFound(msg="app not found")
        app.app_name = app_info.get("name")
        app.describe = app_info.get("describe")
        app.pic = app_info.get("pic")
        app.details = app_info.get("details")
        app.dev_status = app_info.get("dev_status")
        session.execute(
            delete(CenterAppTagsRelation).where(CenterAppTagsRelation.app_id == app_id)
        )
        session.flush()
        for tag_id in app_info.get("tag_ids"):
            add_model: CenterAppTagsRelation = CenterAppTagsRelation(app_id=app.app_id, tag_id=tag_id)
            session.add(add_model)

        app.scope = app_info.get("scope")
        if app.scope == "team":
            # update create team
            create_team = app_info.get("create_team")
            if create_team:
                team = (
                    session.execute(select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == create_team))
                ).scalars().first()

                if team:
                    app.create_team = create_team

    def delete_wutong_app_all_info_by_id(self, session: SessionClass, app_id):
        # todo 事务
        session.execute(delete(CenterAppTagsRelation).where(CenterAppTagsRelation.app_id == app_id))
        session.execute(delete(CenterAppVersion).where(CenterAppVersion.app_id == app_id))
        session.execute(delete(CenterApp).where(CenterApp.app_id == app_id))

    def get_wutong_app_and_versions(self, session: SessionClass, app_id, page, page_size):
        app = (
            session.execute(select(CenterApp).where(CenterApp.app_id == app_id))
        ).scalars().first()

        if not app:
            raise RbdAppNotFound("未找到该应用")

        app_versions = (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.app_id == app_id))
        ).scalars().all()

        apv_ver_nums = []
        app_release = False
        app_with_versions = dict()
        for version in app_versions:
            if version.dev_status == "release":
                app_release = True

            version.release_user = ""
            version.create_time = str(version.create_time)
            version.update_time = str(version.update_time)

            app_with_versions[version.version] = version
            if version.version not in apv_ver_nums:
                apv_ver_nums.append(version.version)

        # Obtain version information according to the sorted version number and construct the returned data
        sort_versions = []
        apv_ver_nums = sorted_versions(apv_ver_nums)
        for ver_num in apv_ver_nums:
            sort_versions.append(app_with_versions.get(ver_num, {}))

        tag_list = []
        tags = (
            session.execute(
                select(CenterAppTagsRelation).where(CenterAppTagsRelation.app_id == app_id))
        ).scalars().all()

        for t in tags:
            tag = (
                session.execute(select(CenterAppTag).where(CenterAppTag.ID == t.tag_id))
            ).scalars().first()

            tag_list.append({"tag_id": t.tag_id, "name": tag.name})

        app = jsonable_encoder(app)
        app["tags"] = tag_list
        if app_release:
            app["dev_status"] = 'release'
        else:
            app["dev_status"] = ''
        #     todo 分页查询
        # p = Paginator(sort_versions, page_size)
        # total = p.count
        if len(sort_versions) > 0:
            return app, sort_versions, len(sort_versions)
        return app, None, 0

    def install_app(self,
                    session,
                    tenant_env,
                    region,
                    user,
                    app_id,
                    app_model_key,
                    version,
                    market_name,
                    install_from_cloud,
                    is_deploy=False):
        app = (
            session.execute(select(Application).where(Application.ID == app_id,
                                                      Application.is_delete == 0))
        ).scalars().first()

        if not app:
            raise AbortRequest("app not found", "应用不存在", status_code=404, error_code=404)

        market_app, app_version = self.get_wutong_app_and_version(session, app_model_key, version)
        if app_version and app_version.region_name and app_version.region_name != region.region_name:
            raise AbortRequest(
                msg="app version can not install to this region",
                msg_show="该应用版本属于{}集群，无法跨集群安装，若需要跨集群，请在企业设置中配置跨集群访问的镜像仓库后重新发布。".format(app_version.region_name))
        if not market_app:
            raise AbortRequest("market app not found", "应用市场应用不存在", status_code=404, error_code=404)
        if not app_version:
            raise AbortRequest("app version not found", "应用市场应用版本不存在", status_code=404, error_code=404)

        app_template = json.loads(app_version.app_template)
        app_template["update_time"] = app_version.update_time

        component_group = self._create_tenant_service_group(session, region.region_name, tenant_env.env_id,
                                                            app.app_id,
                                                            market_app.app_id, version, market_app.app_name)
        app_upgrade = AppUpgrade(
            session,
            tenant_env,
            region,
            user,
            app,
            version,
            component_group,
            app_template,
            install_from_cloud,
            market_name,
            is_deploy=is_deploy)
        app_upgrade.install(session)
        return market_app.app_name

    def _create_tenant_service_group(self, session: SessionClass, region_name, tenant_env_id, group_id, app_key,
                                     app_version, app_name):
        group_name = '_'.join(["wt", make_uuid()[-4:]])
        params = {
            "tenant_env_id": tenant_env_id,
            "group_name": group_name,
            "group_alias": app_name,
            "group_key": app_key,
            "group_version": app_version,
            "region_name": region_name,
            "service_group_id": 0 if group_id == -1 else group_id
        }
        add_model: TeamApplication = TeamApplication(**params)
        session.add(add_model)
        session.flush()

        return add_model

    def app_models_serializers(self, session: SessionClass, market, data):
        app_models = []

        if data:
            for dt in data:
                versions = []
                for version in dt.versions:
                    versions.append({
                        "app_key_id": version.app_key_id,
                        "app_version": version.app_version,
                        "app_version_alias": version.app_version_alias,
                        "create_time": version.create_time,
                        "desc": version.desc,
                        "rainbond_version": version.desc,
                        "update_time": version.update_time,
                        "update_version": version.update_version,
                    })

                market_info = {
                    "app_id": dt.app_key_id,
                    "app_name": dt.name,
                    "update_time": dt.update_time,
                    "local_market_id": market.ID,
                    "local_market_name": market.name,
                    "source": "market",
                    "versions": versions,
                    "tags": [t for t in dt.tags],
                    "logo": dt.logo,
                    "market_id": dt.market_id,
                    "market_name": dt.market_name,
                    "market_url": dt.market_url,
                    "install_number": dt.install_count,
                    "describe": dt.desc,
                    "dev_status": dt.dev_status,
                    "app_detail_url": dt.app_detail_url,
                    "create_time": dt.create_time,
                    "download_number": dt.download_count,
                    "details": dt.introduction,
                    "details_html": dt.introduction_html,
                    "is_official": dt.is_official,
                    "publish_type": dt.publish_type,
                    "start_count": dt.start_count,
                }
                app_models.append(Dict(market_info))
        return app_models

    def count_upgradeable_market_apps(self, session: SessionClass, tenant_env, region_name, app_id):
        market_apps = self.get_market_apps_in_app(session, region_name, tenant_env, app_id)
        apps = [app for app in market_apps if app["can_upgrade"]]
        return len(apps)

    def get_market_apps_in_app(self, session: SessionClass, region_name, tenant_env, app_id):
        component_groups = tenant_service_group_repo.get_group_by_app_id(session, app_id)
        group_ids = [component.ID for component in component_groups]
        components, service_sources = application_service.get_component_and_resource_by_group_ids(session=session,
                                                                                                  app_id=app_id,
                                                                                                  group_ids=group_ids)
        upgrade_app_models = dict()
        component_groups_cache = {}
        for component in components:
            if component.tenant_service_group_id:
                component_groups_cache[component.service_id] = component.tenant_service_group_id

        component_groups = {cg.ID: cg for cg in component_groups}

        for ss in service_sources:
            if ss.service_id in component_groups_cache:
                upgrade_group_id = component_groups_cache[ss.service_id]
                component_group = component_groups[upgrade_group_id]
                upgrade_app_key = "{0}-{1}".format(ss.group_key, upgrade_group_id)
                if (upgrade_app_key not in upgrade_app_models) or compare_version(
                        upgrade_app_models[upgrade_app_key]['version'], ss.version) == -1:
                    # The version of the component group is the version of the application
                    upgrade_app_models[upgrade_app_key] = {'version': component_group.group_version,
                                                           'component_source': ss}
        iterator = self.yield_app_info(session=session, app_models=upgrade_app_models, tenant_env=tenant_env,
                                       app_id=app_id)
        # todo
        if iterator:
            app_info_list = [app_info for app_info in iterator]
            return app_info_list
        return []

    def get_app_not_upgrade_record(self, session: SessionClass, tenant_env_id, group_id, group_key):
        """获取未完成升级记录"""
        result = upgrade_repo.get_app_not_upgrade_record(session=session,
                                                         tenant_env_id=tenant_env_id,
                                                         group_id=int(group_id),
                                                         group_key=group_key)
        if not result:
            return ApplicationUpgradeRecord()
        return result

    def yield_app_info(self, session: SessionClass, app_models, tenant_env, app_id):
        for upgrade_key in app_models:
            app_model_key = upgrade_key.split("-")[0]
            upgrade_group_id = upgrade_key.split("-")[1]
            version = app_models[upgrade_key]['version']
            component_source = app_models[upgrade_key]['component_source']
            market_name = component_source.get_market_name()
            app_model, _ = center_app_repo.get_wutong_app_and_version(session,
                                                                      app_model_key,
                                                                      version)
            if not app_model:
                continue
            dat = {
                'group_key': app_model_key,
                'upgrade_group_id': upgrade_group_id,
                'group_name': app_model.app_name,
                'app_model_name': app_model.app_name,
                'app_model_id': app_model_key,
                'share_user': app_model.create_user,
                'share_env': app_model.create_team,
                'tenant_service_group_id': app_model.app_id,
                'pic': app_model.pic,
                'source': app_model.source,
                'market_name': market_name,
                'describe': app_model.describe,
                'is_official': app_model.is_official,
                'details': app_model.details
            }
            not_upgrade_record = self.get_app_not_upgrade_record(session=session, tenant_env_id=tenant_env.env_id,
                                                                 group_id=app_id,
                                                                 group_key=app_model_key)
            versions = self.__get_upgradeable_versions(session,
                                                       app_model_key, version,
                                                       component_source.get_template_update_time())
            dat.update({
                'current_version': version,
                'can_upgrade': bool(versions),
                'upgrade_versions': (set(versions) if versions else []),
                'not_upgrade_record_id': not_upgrade_record.ID,
                'not_upgrade_record_status': not_upgrade_record.status,
            })
            yield dat

    def __get_upgradeable_versions(self, session: SessionClass,
                                   app_model_key,
                                   current_version,
                                   current_version_time):
        # Simply determine if there is a version that can be upgraded, not attribute changes.
        versions = []
        app_version_list = center_app_repo.get_wutong_app_versions(session=session,
                                                                   app_id=app_model_key)
        if not app_version_list:
            return None
        for version in app_version_list:
            new_version_time = time.mktime(version.update_time.timetuple())
            # If the current version cannot be found, all versions are upgradable by default.
            if current_version:
                compare = compare_version(version.version, current_version)
                if compare == 1:
                    versions.append(version.version)
                elif current_version_time:
                    version_time = time.mktime(current_version_time.timetuple())
                    logger.debug("current version time: {}; new version time: {}; need update: {}".format(
                        new_version_time, version_time, new_version_time > version_time))
                    if compare == 0 and new_version_time > version_time:
                        versions.append(version.version)
            else:
                versions.append(version.version)
        versions = sorted_versions(list(set(versions)))
        return versions

    def app_model_versions_serializers(self, market, data, extend=False):
        app_models = []
        if data:
            for dt in data:
                version = {
                    "app_id": dt.app_key_id,
                    "version": dt.app_version,
                    "version_alias": dt.app_version_alias,
                    "update_version": dt.update_version,
                    "app_version_info": dt.desc,
                    "rainbond_version": dt.rainbond_version,
                    "create_time": dt.create_time,
                    "update_time": dt.update_time,
                    "local_market_id": market.ID,
                }
                app_models.append(Dict(version))
        return app_models

    def get_wutong_app_and_version(self, session: SessionClass, app_id, app_version):
        app, app_version = center_app_repo.get_wutong_app_and_version(session, app_id, app_version)
        if not app:
            raise RbdAppNotFound("未找到该应用")
        return app, app_version

    def get_wutong_detail_app_and_version(self, session: SessionClass, app_id, app_version):
        app, app_version = center_app_repo.get_wutong_app_and_version(session, app_id, app_version)
        return app, app_version

    def app_model_serializers(self, market, data, extend=False):
        app_model = {}
        if data:
            app_model = {
                "app_id": data.app_key_id,
                "app_name": data.name,
                "update_time": data.update_time,
                "local_market_id": market.ID,
                "source": "market",
            }
            if extend:
                app_model.update({
                    "market_id": data.market_id,
                    "logo": data.logo,
                    "market_name": data.market_name,
                    "market_url": data.market_url,
                    "install_number": data.install_count,
                    "describe": data.desc,
                    "dev_status": data.dev_status,
                    "app_detail_url": data.app_detail_url,
                    "create_time": data.create_time,
                    "download_number": data.download_count,
                    "details": data.introduction,
                    "details_html": data.introduction_html,
                    "is_official": data.is_official,
                    "publish_type": data.publish_type,
                    "start_count": data.start_count,
                    "versions": data.versions,
                    "tags": data.tags,
                })
        return Dict(app_model)

    def list_upgradeable_versions(self, session, tenant_env, service):
        component_source = service_source_repo.get_service_source(session, service.tenant_env_id, service.service_id)
        if component_source:
            return self.__get_upgradeable_versions(session,
                                                   component_source.group_key,
                                                   component_source.version,
                                                   component_source.get_template_update_time())
        return []


def compare_version(currentversion, expectedversion):
    if currentversion == expectedversion:
        return 0
    versions = [currentversion, expectedversion]
    sort_versions = sorted(versions, key=lambda x: [int(str(y)) if str.isdigit(str(y)) else -1 for y in x.split(".")])
    max_version = sort_versions.pop()
    if max_version == currentversion:
        return 1
    return -1


def sorted_versions(versions):
    sort_versions = sorted(versions, key=lambda x: [int(str(y)) if str.isdigit(str(y)) else -1 for y in x.split(".")])
    sort_versions.reverse()
    return sort_versions


market_app_service = MarketAppService()
