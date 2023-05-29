from datetime import datetime

from loguru import logger
from sqlalchemy import select, update, not_, delete, bindparam
from models.application.models import Application, ComponentApplicationRelation
from repository.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):

    def get_groups_by_project_id(self, session, project_id):
        return session.execute(select(Application).where(
            Application.project_id == project_id)).scalars().all()

    def get_groups_by_tenant_env_ids(self, session, tenant_env_ids):
        return session.execute(select(Application).where(
            Application.tenant_env_id.in_(tenant_env_ids)).order_by(
            Application.update_time.desc(), Application.order_index.desc())).scalars().all()

    def get_tenant_region_groups(self, session, env_id, region, query="", app_type="", project_ids=None):
        params = {
            "region_name": region,
            "env_id": env_id,
            "group_name": query,
            "app_type": app_type,
            "project_ids": project_ids,
        }
        sql = "select * from service_group where tenant_env_id = :env_id and is_delete=0 and " \
              "region_name = :region_name and group_name like '%' :group_name '%'"
        if app_type:
            sql += " and app_type = :app_type"
        if project_ids:
            sql += " and project_id in ({0})".format(",".join("'{0}'".format(project_id) for project_id in project_ids))
        return session.execute(sql, params).fetchall()

    def get_groups_by_team_name(self, session, team_name, env_id, app_name):
        params = {
            "team_code": team_name,
            "env_id": env_id,
            "app_name": app_name
        }
        sql = "select * from service_group where team_code = :team_code and is_delete=0"
        if env_id:
            sql += " and tenant_env_id = :env_id order by update_time desc"
        if app_name:
            sql += " and group_name like '%' :app_name '%'"
        sql += ""
        return session.execute(sql, params).fetchall()

    def get_hn_tenant_region_groups(self, session, env_id, query="", app_type=""):
        sql = select(Application).where(Application.tenant_env_id == env_id,
                                        Application.group_name.contains(query)).order_by(
            Application.update_time.desc(), Application.order_index.desc())
        if app_type:
            sql = select(Application).where(Application.tenant_env_id == env_id,
                                            Application.app_type == app_type,
                                            Application.group_name.contains(query)).order_by(
                Application.update_time.desc(), Application.order_index.desc())
        return session.execute(sql).scalars().all()

    def get_tenant_region_groups_count(self, session, env_id, region):
        sql = select(Application).where(Application.tenant_env_id == env_id,
                                        Application.region_name == region,
                                        Application.is_delete == 0)
        count = len((session.execute(sql)).scalars().all())
        return count

    def get_apps_in_multi_team(self, session, env_ids, region_names):
        return (
            session.execute(
                select(Application).where(Application.tenant_env_id.in_(env_ids),
                                          Application.region_name.in_(region_names)
                                          ).order_by(Application.update_time.desc(),
                                                     Application.order_index.desc())
            )
        ).scalars().all()

    def get_multi_app_info(self, session, app_ids):
        return session.execute(
            select(Application).where(Application.ID.in_(app_ids)).order_by(
                Application.update_time.desc(),
                Application.order_index.desc())).scalars().all()

    def get_group_by_id(self, session, group_id):
        return (
            session.execute(
                select(Application).where(Application.ID == group_id)
            )
        ).scalars().first()

    def delete_group_by_id(self, session, group_id):
        session.execute(delete(Application).where(Application.ID == group_id))

    def get_group_count_by_team_id_and_group_id(self, session, env_id, group_id):
        service_group_info = session.execute(
            select(Application).where(Application.tenant_env_id == env_id,
                                      Application.ID == group_id,
                                      Application.is_delete == 0)
        ).scalars().all()
        group_count = len(service_group_info)
        return group_count

    def list_tenant_group_on_region(self, session, tenant_env, region_name):
        return session.query(Application).filter(
            Application.tenant_env_id == tenant_env.env_id,
            Application.region_name == region_name)

    def get_group_by_unique_key(self, session, tenant_env_id, region_name, group_name):
        """

        :param tenant_env_id:
        :param region_name:
        :param group_name:
        :return:
        """
        group = (
            session.execute(
                select(Application).where(Application.tenant_env_id == tenant_env_id,
                                          Application.region_name == region_name,
                                          Application.group_name == group_name))
        ).scalars().first()
        return group

    def create(self, session, model: Application):
        """
        创建应用
        :param model:
        """
        session.add(model)
        session.flush()

    def is_app_code_duplicate(self, session, env_id, region_name, app_code, app_id=None):
        if not app_code:
            return False
        params = {
            "env_id": env_id,
            "region_name": region_name,
            "app_id": app_id,
            "app_code": app_code
        }
        sql = "select * from service_group where tenant_env_id = :env_id and region_name = :region_name " \
              "and binary app_code = :app_code"
        if app_id:
            sql = sql + " and not ID = :app_id"
            service_groups = session.execute(sql, params).fetchall()
            return len(service_groups) > 0
        service_groups = session.execute(sql, params).fetchall()
        return len(service_groups) > 0

    def is_k8s_app_duplicate(self, session, env_id, region_name, k8s_app, app_id=None):
        if not k8s_app:
            return False
        if app_id:
            service_groups = session.execute(select(Application).where(
                Application.tenant_env_id == env_id,
                Application.region_name == region_name,
                Application.k8s_app == k8s_app,
                not_(Application.ID == app_id)
            )).scalars().all()
            return len(service_groups) > 0
        service_groups = session.execute(select(Application).where(
            Application.tenant_env_id == env_id,
            Application.region_name == region_name,
            Application.k8s_app == k8s_app
        )).scalars().all()
        return len(service_groups) > 0

    def get_app_by_k8s_app(self, session, tenant_env_id, region_name, k8s_app):
        return session.execute(select(Application).where(
            Application.tenant_env_id == tenant_env_id,
            Application.region_name == region_name,
            Application.k8s_app == k8s_app
        )).scalars().first()

    def get_by_service_id(self, session, env_id, service_id):
        rel = (session.execute(
            select(ComponentApplicationRelation).where(ComponentApplicationRelation.tenant_env_id == env_id,
                                                       ComponentApplicationRelation.service_id == service_id))).scalars().first()
        return (session.execute(
            select(Application).where(Application.ID == rel.group_id))).scalars().first()

    def get_service_group(self, session, service_id, tenant_env_id):
        return (session.execute(
            select(ComponentApplicationRelation).where(ComponentApplicationRelation.tenant_env_id == tenant_env_id,
                                                       ComponentApplicationRelation.service_id == service_id))).scalars().first()

    def get_groups(self, session, sids, tenant_env_id):
        return (session.execute(
            select(ComponentApplicationRelation).where(ComponentApplicationRelation.tenant_env_id == tenant_env_id,
                                                       ComponentApplicationRelation.service_id.in_(
                                                           sids)))).scalars().all()

    def update_governance_mode(self, session, tenant_env_id, region_name, app_id, governance_mode):
        sg = session.execute(select(Application).where(
            Application.ID == app_id
        )).scalars().first()
        sg.tenant_env_id = tenant_env_id
        sg.region_name = region_name
        sg.governance_mode = governance_mode
        sg.update_time = datetime.now()

    def update(self, session, app_id, **data):
        session.execute(update(Application).where(
            Application.ID == app_id
        ).values(**data))
        session.flush()

    def get_logic_delete_records(self, session, delete_date):
        return session.execute(
            select(Application).where(Application.is_delete == True, Application.delete_time < delete_date)
        ).scalars().all()


application_repo = ApplicationRepository(Application)
