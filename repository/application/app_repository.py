import time

from loguru import logger
from sqlalchemy import select, delete, text

from models.component.models import Component, ComponentWebhooks, ComponentRecycleBin, \
    ComponentRelationRecycleBin, TeamComponentInfoDelete, TeamComponentConfigurationFile
from models.market.models import CenterApp, CenterAppVersion, CenterAppTag, CenterAppTagsRelation


class TenantServiceDeleteRepository(object):
    def create_delete_service(self, session, **params):
        tsi = TeamComponentInfoDelete(**params)
        session.add(tsi)
        session.flush()


class AppRepo(object):

    def add_wutong_install_num(self, session, app_id, app_version):
        app = session.execute(select(CenterApp).where(
            CenterApp.app_id == app_id
        )).scalars().first()
        app.install_number += 1

        app_version = session.execute(select(CenterAppVersion).where(
            CenterAppVersion.app_id == app_id,
            CenterAppVersion.version == app_version
        ).order_by(CenterAppVersion.update_time.desc())).scalars().first()
        app_version.install_number += 1

    def get_wutong_app_qs_by_key(self, session, app_id):
        """使用group_key获取一个云市应用的所有版本查询集合"""
        return session.execute(select(CenterApp).where(
            CenterApp.app_id == app_id)).scalars().first()

    def delete_app_version_by_version(self, session, app_id, version):
        session.execute(delete(CenterAppVersion).where(
            CenterAppVersion.app_id == app_id,
            CenterAppVersion.version == version
        ))

    def update_app_version(self, session, app_id, version, **data):
        version = session.execute(select(CenterAppVersion).where(
            CenterAppVersion.app_id == app_id,
            CenterAppVersion.version == version
        ).order_by(CenterAppVersion.create_time.desc())).scalars().first()
        if version is not None:
            if data["version_alias"] is not None:
                version.version_alias = data["version_alias"]
            if data["app_version_info"] is not None:
                version.app_version_info = data["app_version_info"]
            if data["dev_status"] == "release":
                version.release_user_id = data["release_user_id"]
            version.dev_status = data["dev_status"]
            version.update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            return version
        return None

    def get_wutong_app_version_by_app_id_and_version(self, session, app_id, version):
        return (
            session.execute(select(CenterAppVersion).where(
                CenterAppVersion.app_id == app_id,
                CenterAppVersion.version == version))
        ).scalars().first()

    def get_app_by_app_id(self, session, app_id):
        return (
            session.execute(select(CenterApp).where(
                CenterApp.ID == app_id))
        ).scalars().first()

    def get_enterpirse_app_by_key_and_version(self, session, group_key, group_version):
        app = (session.execute(select(CenterApp).where(
            CenterApp.app_id == group_key))
        ).scalars().first()
        rcapps = (session.execute(select(CenterAppVersion).where(
            CenterAppVersion.version == group_version,
            CenterAppVersion.app_id == group_key).order_by(
            CenterAppVersion.update_time.desc()
        ))
        ).scalars().all()
        if rcapps and app:
            rcapp = (session.execute(select(CenterAppVersion).where(
                CenterAppVersion.version == group_version,
                CenterAppVersion.app_id == group_key).order_by(
                CenterAppVersion.update_time.desc()
            ))
            ).scalars().all()
            # 优先获取企业下的应用
            if rcapp:
                rcapp[0].pic = app.pic
                rcapp[0].group_name = app.app_name
                rcapp[0].describe = app.describe

                return rcapp[0]
            else:
                rcapps[0].pic = app.pic
                rcapps[0].describe = app.describe
                rcapps[0].group_name = app.app_name
            return rcapps[0]
        logger.warning(
            "Group Key: {0}; Version: {1}".format(group_key, group_version))
        return None

    def get_app_list(self, session, tenant_env_id, region, query=""):
        if query:
            sql = select(Component).where(Component.tenant_env_id == tenant_env_id,
                                          Component.service_region == region,
                                          Component.service_cname.contains(query))
        else:
            sql = select(Component).where(Component.tenant_env_id == tenant_env_id,
                                          Component.service_region == region)
        return session.execute(sql).scalars().all()


class TenantServiceWebhooks(object):

    def create_service_webhooks(self, session, service_id, webhooks_type):
        service_webhooks = ComponentWebhooks(service_id=service_id, webhooks_type=webhooks_type)
        session.add(service_webhooks)

        return service_webhooks

    def save(self, session, webhook):
        session.merge(webhook)

    def get_service_webhooks_by_service_id_and_type(self, session, service_id, webhooks_type):
        return (
            session.execute(select(ComponentWebhooks).where(ComponentWebhooks.service_id == service_id,
                                                            ComponentWebhooks.webhooks_type == webhooks_type))
        ).scalars().first()

    def get_or_create_service_webhook(self, session, service_id, deployment_way):
        """获取或创建service_webhook"""
        return self.get_service_webhooks_by_service_id_and_type(session=session, service_id=service_id,
                                                                webhooks_type=deployment_way) or self.create_service_webhooks(
            session=session, service_id=service_id,
            webhooks_type=deployment_way)


class ServiceRecycleBinRepository(object):

    def get_team_trash_services(self, session, tenant_env_id):
        return (
            session.execute(select(ComponentRecycleBin).where(ComponentRecycleBin.tenant_env_id == tenant_env_id))
        ).scalars().all()

    def create_trash_service(self, session, **params):
        srb = ComponentRecycleBin(**params)
        session.add(srb)

        return srb

    def delete_trash_service_by_service_id(self, session, service_id):
        session.execute(delete(ComponentRecycleBin).where(ComponentRecycleBin.service_id == service_id))

    def delete_transh_service_by_service_ids(self, session, service_ids):
        session.execute(delete(ComponentRecycleBin).where(ComponentRecycleBin.service_id.in_(service_ids)))


class ServiceRelationRecycleBinRepository(object):

    def create_trash_service_relation(self, session, **params):
        srr = ComponentRelationRecycleBin(**params)
        session.add(srr)

    def get_by_dep_service_id(self, session, dep_service_id):
        return (
            session.execute(select(ComponentRelationRecycleBin).where(
                ComponentRelationRecycleBin.dep_service_id == dep_service_id))
        ).scalars().all()

    def get_by_service_id(self, session, service_id):
        return (
            session.execute(select(ComponentRelationRecycleBin).where(
                ComponentRelationRecycleBin.service_id == service_id))
        ).scalars().all()


class AppTagRepository(object):
    def get_multi_apps_tags(self, session, app_ids):
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
            and atr.app_id in :app_ids;
        """
        sql = text(sql).bindparams(app_ids=tuple(app_ids.split(",")))
        apps = session.execute(sql).fetchall()
        return apps

    def create_app_tags_relation(self, session, app, tag_ids):
        relation_list = []
        session.execute(delete(CenterAppTagsRelation).where(
            CenterAppTagsRelation.app_id == app.app_id
        ))
        for tag_id in tag_ids:
            relation_list.append(
                CenterAppTagsRelation(app_id=app.app_id, tag_id=tag_id))

        return session.add_all(relation_list)

    def create_tag(self, session, name):
        old_tag = session.execute(select(CenterAppTag).where(
            CenterAppTag.name == name
        )).scalars().all()
        if old_tag:
            return False
        wcat = CenterAppTag(name=name, is_deleted=False)
        session.add(wcat)
        return wcat


class ComponentConfigurationFileRepository(object):
    @staticmethod
    def bulk_create(session, config_files):
        session.add_all(config_files)

    @staticmethod
    def overwrite_by_component_ids(session, component_ids, config_files):
        session.execute(delete(TeamComponentConfigurationFile).where(
            TeamComponentConfigurationFile.service_id.in_(component_ids)))
        for config_file in config_files:
            session.merge(config_file)
        session.flush()


app_repo = AppRepo()
service_webhooks_repo = TenantServiceWebhooks()
recycle_bin_repo = ServiceRecycleBinRepository()
relation_recycle_bin_repo = ServiceRelationRecycleBinRepository()
delete_service_repo = TenantServiceDeleteRepository()
app_tag_repo = AppTagRepository()
config_file_repo = ComponentConfigurationFileRepository()
