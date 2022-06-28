from typing import Optional

from loguru import logger
from sqlalchemy import select, or_, func, delete, not_, text
from sqlalchemy.orm import defer

from clients.remote_component_client import remote_component_client
from database.session import SessionClass
from models.application.models import ApplicationExportRecord
from models.market import models
from models.market.models import AppImportRecord
from models.market.models import CenterApp, CenterAppVersion, CenterPlugin
from models.teams import TeamInfo
from repository.base import BaseRepository
from repository.teams.team_repo import team_repo
from schemas import CenterAppCreate


class AppImportRepository(object):

    def delete_by_event_id(self, session, event_id):
        session.execute(delete(AppImportRecord).where(
            AppImportRecord.event_id == event_id
        ))
        session.flush()

    def get_import_record_by_event_id(self, session, event_id):
        return session.execute(select(AppImportRecord).where(
            AppImportRecord.event_id == event_id
        )).scalars().first()

    def create_app_import_record(self, session, **params):
        app_import_record = AppImportRecord(**params)
        session.add(app_import_record)
        return app_import_record

    def get_user_not_finished_import_record_in_enterprise(self, session, eid, user_name):
        return session.execute(select(AppImportRecord).where(
            AppImportRecord.user_name == user_name,
            AppImportRecord.enterprise_id == eid,
            not_(AppImportRecord.status.in_(["success", "failed"]))
        )).scalars().all()


class CenterRepository(BaseRepository[CenterApp]):
    def get_wutong_app_version_by_app_ids(self, session, eid, app_ids, is_complete=None, rm_template_field=False):
        sql = session.query(CenterAppVersion).where(
            CenterAppVersion.enterprise_id == eid,
            CenterAppVersion.app_id.in_(app_ids)
        ).order_by(CenterAppVersion.create_time.asc())
        if is_complete:
            sql = session.query(CenterAppVersion).where(
                CenterAppVersion.enterprise_id == eid,
                CenterAppVersion.app_id.in_(app_ids),
                CenterAppVersion.is_complete == is_complete
            ).order_by(CenterAppVersion.create_time.asc())
        if rm_template_field:
            return sql.options(defer("app_template")).all()
        return sql.all()

    def get_wutong_app_in_enterprise_by_query(self,
                                              session,
                                              eid,
                                              scope,
                                              app_name,
                                              tag_names=None,
                                              page=1,
                                              page_size=10,
                                              need_install="false"):
        return self._prepare_get_wutong_app_by_query_sql(session, eid, scope, app_name, None, tag_names, page,
                                                         page_size,
                                                         need_install)

    def get_wutong_app_total_count(self, session, eid, scope, teams, app_name, tag_names, need_install="false"):
        extend_where = ""
        join_version = ""
        if tag_names:
            extend_where += " and tag.name in ({0})".format(
                ",".join("'{0}'".format(tag_name) for tag_name in tag_names))
        if app_name:
            extend_where += " and app.app_name like '%{0}%'".format(app_name)
        if need_install == "true":
            join_version += " left join center_app_version apv on app.app_id = apv.app_id" \
                            " and app.enterprise_id = apv.enterprise_id"
            extend_where += " and apv.`version` <> '' and apv.is_complete"
        # if teams is None, create_team scope is ('')
        if scope == "team":
            team_sql = ""
            if teams:
                team_sql = " and app.create_team in({0})".format(",".join("'{0}'".format(team) for team in teams))
            team_sql += " and app.scope='" + scope + "'"
            extend_where += team_sql
        if scope == "enterprise":
            extend_where += " and app.scope='" + scope + "'"
        sql = """
            select
                count(distinct app.app_id) as total
            from
                center_app app
            left join (
                select
                    app_id,
                    tag.name
                from
                    center_app_tag_relation rcatr
                join center_app_tag tag on
                    rcatr.tag_id = tag.iD) tag on app.app_id = tag.app_id
            {join_version}
            where
                app.enterprise_id = '{eid}'
                {extend_where}
            """.format(
            eid=eid, extend_where=extend_where, join_version=join_version)
        count = session.execute(sql).fetchall()
        return count[0][0]

    def _prepare_get_wutong_app_by_query_sql(self,
                                             session,
                                             eid,
                                             scope,
                                             app_name,
                                             teams=None,
                                             tag_names=None,
                                             page=1,
                                             page_size=10,
                                             need_install="false"):
        extend_where = ""
        join_version = ""
        if tag_names:
            extend_where += " and tag.name in (:tag_param)"
        if app_name:
            extend_where += " and app.app_name like :app_name"
        if need_install == "true":
            join_version += " left join center_app_version apv on app.app_id = apv.app_id" \
                            " and app.enterprise_id = apv.enterprise_id"
            extend_where += " and apv.`version` <> '' and apv.is_complete"
        if scope == "team":
            team_sql = ""
            if teams:
                team_sql = " and app.create_team in(:team_param)"
            team_sql += " and app.scope='team'"
            extend_where += team_sql
        if scope == "enterprise":
            extend_where += " and app.scope='enterprise'"
        # sql
        sql = """
            select
                distinct app.*
            from
                center_app app
            left join center_app_tag_relation apr on
                app.app_id = apr.app_id
                and app.enterprise_id = apr.enterprise_id
            left join center_app_tag tag on
                apr.tag_id = tag.ID
                and tag.enterprise_id = app.enterprise_id
            {join_version}
            where
                app.enterprise_id = :eid
                {extend_where}
            order by app.update_time desc
            limit :offset, :rows
            """.format(extend_where=extend_where, join_version=join_version)
        # 参数
        sql = text(sql)
        if tag_names:
            sql = sql.bindparams(tag_param=",".join("'{0}'".format(tag_name) for tag_name in tag_names))
        if app_name:
            sql = sql.bindparams(app_name="%" + app_name + "%")
        if scope == "team" and teams:
            sql = sql.bindparams(team_param=",".join("'{0}'".format(team) for team in teams))
        sql = sql.bindparams(eid=eid, offset=(page - 1) * page_size, rows=page_size)

        apps = session.execute(sql).fetchall()
        return apps

    def get_wutong_app_in_teams_by_querey(self,
                                          session,
                                          eid,
                                          scope,
                                          teams,
                                          app_name,
                                          tag_names=None,
                                          page=1,
                                          page_size=10,
                                          need_install="false"):
        return self._prepare_get_wutong_app_by_query_sql(session, eid, scope, app_name, teams, tag_names, page,
                                                         page_size,
                                                         need_install)

    def get_center_app_list(self,
                            session: SessionClass,
                            enterprise_id: str,
                            app_name: str,
                            scope: Optional[str] = None,
                            page: Optional[int] = 1,
                            page_size: Optional[int] = 10, ):
        """
        获取本地市场应用列表
        :param enterprise_id:
        :param app_name:
        :param scope:
        :param page:
        :param page_size:
        :return:
        """
        logger.info("获取本地市场应用列表,scope:{},app_name:{},page:{},page_size:{},enterprise_id:{}", scope, app_name, page,
                    page_size, enterprise_id)
        sql = select(CenterApp).where(CenterApp.app_name.like("%" + app_name + "%"),
                                      (CenterApp.enterprise_id == enterprise_id)).limit(page_size).offset(
            (page - 1) * page_size)
        q = session.execute(sql)
        session.flush()
        result = q.all()
        return result

    def create_center_app(self, session: SessionClass, params: CenterAppCreate):
        logger.info("创建应用市场应用,params:{}", params)
        model = params.dict()
        add = models.CenterApp(**model)
        session.add(add)
        session.flush()

    def get_center_plugin_by_record_id(self, session: SessionClass, record_id):
        """

        :param record_id:
        :return:
        """
        sql = select(CenterPlugin).where(CenterPlugin.record_id == record_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def list_plugins_by_enterprise_ids(self, session: SessionClass, enterprise_ids):
        """
        查询企业插件列表

        :param enterprise_ids:
        :return:
        """
        data = session.query(CenterPlugin).filter(
            CenterPlugin.enterprise_id.in_(enterprise_ids)).all()
        return data

    def get_paged_plugins(self, session: SessionClass,
                          plugin_name="",
                          is_complete=None,
                          scope="",
                          source="",
                          tenant: TeamInfo = None,
                          page=1,
                          limit=10,
                          order_by="",
                          category=""):
        """
        分页查询插件列表
        :param plugin_name:
        :param is_complete:
        :param scope:
        :param source:
        :param tenant:
        :param page:
        :param limit:
        :param order_by:
        :param category:
        :return:
        """
        conditions = []
        if source:
            conditions.append(CenterPlugin.source == source)
        if is_complete:
            conditions.append(CenterPlugin.is_complete == is_complete)
        if plugin_name:
            conditions.append(CenterPlugin.plugin_name == plugin_name)
        if category:
            conditions.append(CenterPlugin.category == category)
        if scope == 'team':
            conditions.append(CenterPlugin.share_team == tenant.tenant_name)
        elif scope == 'goodrain':
            conditions.append(CenterPlugin.scope == scope)
        elif scope == 'enterprise':
            tenants = team_repo.get_teams_by_enterprise_id(session, tenant.enterprise_id)
            tenant_names = [t.tenant_name for t in tenants]
            conditions.append(or_(
                (CenterPlugin.share_team.in_(tenant_names), CenterPlugin.scope == "enterprise"),
                CenterPlugin.scope == "goodrain",
                (CenterPlugin.share_team == tenant.tenant_name, CenterPlugin.scope == "team")
            ))
        # 查询总数
        # todo
        count = session.query(func.count(CenterPlugin)).filter(*conditions).scalar()
        if order_by == 'is_complete':
            plugins = session.query(CenterPlugin).filter(*conditions).order_by(
                CenterPlugin.is_complete.desc()
            ).limit(limit).offset((page - 1) * limit).all()
        else:
            plugins = session.query(CenterPlugin).filter(*conditions).order_by(
                CenterPlugin.update_time.desc()
            ).limit(limit).offset((page - 1) * limit).all()
        data = [{
            'plugin_name': plugin.plugin_name,
            'plugin_key': plugin.plugin_key,
            'category': plugin.category,
            'pic': plugin.pic,
            'version': plugin.version,
            'desc': plugin.desc,
            'id': plugin.ID,
            'is_complete': plugin.is_complete,
            'source': plugin.source,
            'update_time': plugin.update_time,
            'details': plugin.details
        } for plugin in plugins]
        return count, data

    def get_wutong_app_versions(self, session: SessionClass, eid, app_id):

        return (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.enterprise_id == eid,
                                               CenterAppVersion.app_id == app_id))
        ).scalars().all()

    def get_wutong_app_and_version(self, session: SessionClass, enterprise_id, app_id, app_version):
        app = (
            session.execute(select(CenterApp).where(CenterApp.enterprise_id == enterprise_id,
                                                    CenterApp.app_id == app_id))
        ).scalars().first()

        if not app_version:
            return app, None
        app_version = (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.enterprise_id == enterprise_id,
                                               CenterAppVersion.app_id == app_id,
                                               CenterAppVersion.version == app_version,
                                               CenterAppVersion.scope.in_(
                                                   ["gooodrain", "team", "enterprise"])).order_by(
                    CenterAppVersion.upgrade_time.desc())).scalars().first()
        )

        if app_version and app:
            return app, app_version
        app_version = (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.enterprise_id == "public",
                                               CenterAppVersion.app_id == app_id,
                                               CenterAppVersion.version == app_version,
                                               CenterAppVersion.scope.in_(
                                                   ["gooodrain", "team", "enterprise"])).order_by(
                    CenterAppVersion.upgrade_time.desc())).scalars().first()
        )
        return app, app_version

    def get_all_helm_info(self, session: SessionClass, region_name, tenant_name, helm_name, helm_namespace):
        return remote_component_client.get_helm_chart_resources(session,
                                                                region_name,
                                                                tenant_name,
                                                                {"helm_name": helm_name,
                                                                 "helm_namespace": helm_namespace})

    def get_wutong_app_by_app_id(self, session: SessionClass, eid, app_id):
        return session.execute(select(CenterApp).where(
            CenterApp.app_id == app_id,
            CenterApp.enterprise_id == eid)).scalars().first()

    @staticmethod
    def get_wutong_app_version_by_record_id(session: SessionClass, record_id):
        return session.execute(select(CenterAppVersion).where(
            CenterAppVersion.record_id == record_id)).scalars().first()


class AppExportRepository(BaseRepository[ApplicationExportRecord]):

    def get_export_record(self, session, eid, app_id, app_version, export_format):
        return session.execute(select(ApplicationExportRecord).where(
            ApplicationExportRecord.group_key == app_id,
            ApplicationExportRecord.version == app_version,
            ApplicationExportRecord.format == export_format,
            ApplicationExportRecord.enterprise_id.in_([eid, "public"]),
            ApplicationExportRecord.status == "exporting"
        )).scalars().first()

    def create_app_export_record(self, session, **params):
        app_export_record = ApplicationExportRecord(**params)
        session.add(app_export_record)
        session.flush()
        return app_export_record

    def get_enter_export_record_by_key_and_version(self, session, enterprise_id, group_key, version):
        return session.execute(select(ApplicationExportRecord).where(
            ApplicationExportRecord.group_key == group_key,
            ApplicationExportRecord.version == version,
            ApplicationExportRecord.enterprise_id.in_(["public", enterprise_id])
        )).scalars().all()

    def delete_by_key_and_version(self, session: SessionClass, group_key, version):
        session.execute(delete(ApplicationExportRecord).where(
            ApplicationExportRecord.group_key == group_key,
            ApplicationExportRecord.version == version
        ))
        session.flush()


center_app_repo = CenterRepository(CenterApp)

app_import_record_repo = AppImportRepository()
app_export_record_repo = AppExportRepository(ApplicationExportRecord)
