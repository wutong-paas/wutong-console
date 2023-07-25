from typing import Optional
from loguru import logger
from sqlalchemy import select, func, delete, not_, text
from sqlalchemy.orm import defer
import yaml
import os
from database.session import SessionClass
from models.application.models import ApplicationExportRecord
from models.market import models
from models.market.models import AppImportRecord
from models.market.models import CenterApp, CenterAppVersion
from repository.base import BaseRepository
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

    def get_user_not_finished_import_record_in_enterprise(self, session, user_name):
        return session.execute(select(AppImportRecord).where(
            AppImportRecord.user_name == user_name,
            not_(AppImportRecord.status.in_(["success", "failed"]))
        )).scalars().all()


class CenterRepository(BaseRepository[CenterApp]):
    def get_wutong_app_version_by_app_ids(self, session, app_ids, is_complete=None, rm_template_field=False):
        sql = session.query(CenterAppVersion).where(
            CenterAppVersion.app_id.in_(app_ids)
        ).order_by(CenterAppVersion.create_time.asc())
        if is_complete:
            sql = session.query(CenterAppVersion).where(
                CenterAppVersion.app_id.in_(app_ids),
                CenterAppVersion.is_complete == is_complete
            ).order_by(CenterAppVersion.create_time.asc())
        if rm_template_field:
            return sql.options(defer("app_template")).all()
        return sql.all()

    def get_wutong_app_in_enterprise_by_query(self,
                                              session,
                                              scope,
                                              app_name,
                                              teams=None,
                                              tag_names=None,
                                              page=1,
                                              page_size=10,
                                              need_install="false"):
        return self._prepare_get_wutong_app_by_query_sql(session, scope, app_name, teams, tag_names, page,
                                                         page_size,
                                                         need_install)

    def get_wutong_app_total_count(self, session, scope, teams, app_name, tag_names, need_install="false"):
        extend_where = ""
        join_version = ""
        if tag_names:
            extend_where += " and tag.name in ({0})".format(
                ",".join("'{0}'".format(tag_name) for tag_name in tag_names))
        if app_name:
            extend_where += " and app.app_name like '%{0}%'".format(app_name)
        if need_install == "true":
            join_version += " left join center_app_version apv on app.app_id = apv.app_id"
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
        if extend_where[:5] == " and ":
            extend_where = extend_where[5:]
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
                {extend_where}
            """.format(
            extend_where=extend_where, join_version=join_version)
        count = session.execute(sql).fetchall()
        return count[0][0]

    def _prepare_get_wutong_app_by_query_sql(self,
                                             session,
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
            extend_where += " and tag.name in :tag_param"
        if app_name:
            extend_where += " and app.app_name like :app_name"
        if need_install == "true":
            join_version += " left join center_app_version apv on app.app_id = apv.app_id"
            extend_where += " and apv.`version` <> '' and apv.is_complete"
        if scope == "team":
            team_sql = ""
            if teams:
                team_sql = " and app.create_team in (:team_param)"
            team_sql += " and app.scope='team'"
            extend_where += team_sql
        if scope == "enterprise":
            extend_where += " and app.scope='enterprise'"
        if extend_where[:5] == " and ":
            extend_where = extend_where[5:]
        # sql
        sql = """
            select
                distinct app.*
            from
                center_app app
            left join center_app_tag_relation apr on
                app.app_id = apr.app_id
            left join center_app_tag tag on
                apr.tag_id = tag.ID
            {join_version}
            where
                {extend_where}
            order by app.update_time desc
            limit :offset, :rows
            """.format(extend_where=extend_where, join_version=join_version)
        # 参数
        sql = text(sql)
        if tag_names:
            sql = sql.bindparams(tag_param=tuple(tag_names))
        if app_name:
            sql = sql.bindparams(app_name="%" + app_name + "%")
        if scope == "team" and teams:
            team_param = ",".join("{0}".format(team) for team in teams)
            sql = sql.bindparams(team_param=team_param)
        sql = sql.bindparams(offset=(page - 1) * page_size, rows=page_size)

        apps = session.execute(sql).fetchall()
        return apps

    def get_wutong_app_in_teams_by_querey(self,
                                          session,
                                          scope,
                                          teams,
                                          app_name,
                                          tag_names=None,
                                          page=1,
                                          page_size=10,
                                          need_install="false"):
        return self._prepare_get_wutong_app_by_query_sql(session, scope, app_name, teams, tag_names, page,
                                                         page_size,
                                                         need_install)

    def get_center_app_list(self,
                            session: SessionClass,
                            app_name: str,
                            scope: Optional[str] = None,
                            page: Optional[int] = 1,
                            page_size: Optional[int] = 10, ):
        """
        获取本地市场应用列表
        :param app_name:
        :param scope:
        :param page:
        :param page_size:
        :return:
        """
        logger.info("获取本地市场应用列表,scope:{},app_name:{},page:{},page_size:{}:{}", scope, app_name, page,
                    page_size)
        sql = select(CenterApp).where(CenterApp.app_name.like("%" + app_name + "%")).limit(page_size).offset(
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

    def get_wutong_app_versions(self, session: SessionClass, app_id):

        return (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.app_id == app_id))
        ).scalars().all()

    def get_wutong_app_and_version(self, session: SessionClass, app_id, app_version):
        app = (
            session.execute(select(CenterApp).where(CenterApp.app_id == app_id))
        ).scalars().first()

        if not app_version:
            return app, None
        app_version = (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.app_id == app_id,
                                               CenterAppVersion.version == app_version,
                                               CenterAppVersion.scope.in_(
                                                   ["gooodrain", "team", "enterprise"])).order_by(
                    CenterAppVersion.upgrade_time.desc())).scalars().first()
        )

        if app_version and app:
            return app, app_version
        app_version = (
            session.execute(
                select(CenterAppVersion).where(CenterAppVersion.app_id == app_id,
                                               CenterAppVersion.version == app_version,
                                               CenterAppVersion.scope.in_(
                                                   ["gooodrain", "team", "enterprise"])).order_by(
                    CenterAppVersion.upgrade_time.desc())).scalars().first()
        )
        return app, app_version

    def get_all_helm_info(self, dir):
        values = []
        for root, _, files in os.walk(dir):
            for file_name in files:
                stream = open(root + "\\" + file_name, mode='r', encoding='utf-8')
                value = yaml.safe_load(stream)
                values.append(value)
        return values

    def get_wutong_app_by_app_id(self, session: SessionClass, app_id):
        return session.execute(select(CenterApp).where(
            CenterApp.app_id == app_id)).scalars().first()

    @staticmethod
    def get_wutong_app_version_by_record_id(session: SessionClass, record_id):
        return session.execute(select(CenterAppVersion).where(
            CenterAppVersion.record_id == record_id)).scalars().first()


class AppExportRepository(BaseRepository[ApplicationExportRecord]):

    def get_export_record(self, session, app_id, app_version, export_format):
        return session.execute(select(ApplicationExportRecord).where(
            ApplicationExportRecord.group_key == app_id,
            ApplicationExportRecord.version == app_version,
            ApplicationExportRecord.format == export_format,
            ApplicationExportRecord.status == "exporting"
        )).scalars().first()

    def create_app_export_record(self, session, **params):
        app_export_record = ApplicationExportRecord(**params)
        session.add(app_export_record)
        session.flush()
        return app_export_record

    def get_enter_export_record_by_key_and_version(self, session, group_key, version):
        return session.execute(select(ApplicationExportRecord).where(
            ApplicationExportRecord.group_key == group_key,
            ApplicationExportRecord.version == version
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
