import os
from datetime import datetime

from sqlalchemy import select, update, not_, delete

from exceptions.main import ServiceHandleException
from models.application.models import Application, ComponentApplicationRelation
from models.market.models import AppMarket
from repository.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):

    def get_groups_by_tenant_env_ids(self, session, tenant_env_ids):
        return session.execute(select(Application).where(
            Application.tenant_env_id.in_(tenant_env_ids)).order_by(
            Application.update_time.desc(), Application.order_index.desc())).scalars().all()

    def get_tenant_region_groups(self, session, env_id, region, query="", app_type=""):
        sql = select(Application).where(Application.tenant_env_id == env_id,
                                        Application.region_name == region,
                                        Application.group_name.contains(query)).order_by(
            Application.update_time.desc(), Application.order_index.desc())
        if app_type:
            sql = select(Application).where(Application.tenant_env_id == env_id,
                                            Application.region_name == region,
                                            Application.app_type == app_type,
                                            Application.group_name.contains(query)).order_by(
                Application.update_time.desc(), Application.order_index.desc())
        return session.execute(sql).scalars().all()

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
                                        Application.region_name == region)
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
                                      Application.ID == group_id)
        ).scalars().all()
        group_count = len(service_group_info)
        return group_count

    def get_or_create_default_group(self, session, tenant_env_id, region_name):
        # 查询是否有团队在当前数据中心是否有默认应用，没有创建
        group = session.execute(
            select(Application).where(Application.tenant_env_id == tenant_env_id,
                                      Application.region_name == region_name,
                                      Application.is_default == 1)).scalars().first()
        if not group:
            group = Application(
                tenant_env_id=tenant_env_id,
                region_name=region_name,
                group_name="默认应用",
                note="",
                is_default=True,
                username="",
                update_time=datetime.now(),
                create_time=datetime.now())
            session.add(group)
            session.flush()

        return group

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


class AppMarketRepository(object):

    def create_default_app_market_if_not_exists(self, session):
        access_key = os.getenv("DEFAULT_APP_MARKET_ACCESS_KEY", "")
        domain = os.getenv("DEFAULT_APP_MARKET_DOMAIN", "rainbond")
        url = os.getenv("DEFAULT_APP_MARKET_URL", "https://store.goodrain.com")
        name = os.getenv("DEFAULT_APP_MARKET_NAME", "RainbondMarket")

        markets = session.execute(select(AppMarket).where(
            AppMarket.domain == domain,
            AppMarket.url == url
        )).scalars().all()
        if markets or os.getenv("DISABLE_DEFAULT_APP_MARKET", False):
            return
        app_market = AppMarket(
            name=name,
            url=url,
            domain=domain,
            type="rainstore",
            access_key=access_key
        )
        session.add(app_market)
        session.flush()

    def get_app_market_by_name(self, session, name, raise_exception=False):
        market = session.execute(select(AppMarket).where(
            AppMarket.name == name
        )).scalars().first()
        if raise_exception:
            if not market:
                raise ServiceHandleException(status_code=404, msg="no found app market", msg_show="应用商店不存在")
        return market


application_repo = ApplicationRepository(Application)
app_market_repo = AppMarketRepository()
