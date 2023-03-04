"""
tenant repository
"""
import datetime
import random
import string
from loguru import logger
from sqlalchemy import select, delete, not_
from core.idaasapi import idaas_api
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.region.models import EnvRegionInfo
from models.teams import TeamEnvInfo, PermRelTenant, RegionConfig
from models.component.models import TeamComponentInfo
from repository.base import BaseRepository


class EnvRepository(BaseRepository[TeamEnvInfo]):
    """
    TenantRepository
    """

    def get_enterprise_team_by_name(self, session, enterprise_id, team_name):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.enterprise_id == enterprise_id,
            TeamEnvInfo.tenant_name == team_name
        )).scalars().first()

    def get_team_by_enterprise_id(self, session, enterprise_id):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.enterprise_id == enterprise_id
        )).scalars().all()

    # 返回该团队下的所有管理员
    def get_tenant_admin_by_tenant_env_id(self, tenant):
        return idaas_api.get_user_info(tenant.creater)

    def get_tenant_by_tenant_name(self, session: SessionClass, env_name, exception=True):
        """
        get_tenant_by_tenant_name

        :param team_name:
        :return:
        """
        logger.info("get_tenant_by_tenant_name,param:{}", env_name)
        tenant = session.execute(select(TeamEnvInfo).where(TeamEnvInfo.env_name == env_name)).scalars().first()
        if not tenant and exception:
            return None
        return tenant

    def get_tenant_by_tenant_env_id(self, session: SessionClass, tenant_env_id):
        """
        get_tenant_by_tenant_env_id

        :param tenant_env_id:
        :return:
        """
        logger.info("get_tenant_by_tenant_env_id,param:{}", tenant_env_id)
        sql = select(TeamEnvInfo).where(TeamEnvInfo.env_id == tenant_env_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_team_by_team_names(self, session, team_names):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.tenant_name.in_(team_names))).scalars().all()

    def get_team_by_team_id(self, session, env_id):
        tenant = session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id))
        return tenant.scalars().first()

    def get_env_by_env_id(self, session, env_id):
        return session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id)).scalars().first()

    def get_env_by_env_name(self, session, env_name):
        return session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.env_name == env_name)).scalars().first()

    def get_team_by_team_name_and_eid(self, session, team_name):
        tenant = session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == team_name)).scalars().first()
        if not tenant:
            raise ServiceHandleException(msg_show="团队不存在", msg="team not found")
        return tenant

    def delete_by_env_id(self, session, env_id):
        row = session.execute(
            delete(TeamEnvInfo).where(TeamEnvInfo.env_id == env_id))
        return row.rowcount > 0

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_ids))).scalars().all()

    def save_tenant_service_info(self, session, ts):
        session.add(ts)
        session.flush()

    def get_team_region_by_name(self, session, env_id, region_name):
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.region_name == region_name,
            EnvRegionInfo.region_env_id == env_id)).scalars().all()

    def get_user_tenant_by_name(self, session, user_id, name):
        res = session.execute(select(PermRelTenant).where(
            PermRelTenant.user_id == user_id)).scalars().all()
        tenant_env_ids = [r.tenant_env_id for r in res]
        tenant = session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.ID.in_(tenant_env_ids),
            TeamEnvInfo.tenant_name == name)).scalars().first()
        return tenant

    def get_teams_by_enterprise_id(self, session, enterprise_id, user_id=None, query=None):
        """
        查询企业团队列表
        :param enterprise_id:
        :param user_id:
        :param query:
        :return:
        """
        sql = select(TeamEnvInfo).where(
            TeamEnvInfo.enterprise_id == enterprise_id).order_by(TeamEnvInfo.create_time.desc())
        if user_id:
            sql = select(TeamEnvInfo).where(
                TeamEnvInfo.enterprise_id == enterprise_id,
                TeamEnvInfo.creater == user_id).order_by(TeamEnvInfo.create_time.desc())
        if query:
            sql = select(TeamEnvInfo).where(
                TeamEnvInfo.enterprise_id == enterprise_id,
                TeamEnvInfo.tenant_alias.like('%' + query + '%')).order_by(TeamEnvInfo.create_time.desc())

        data = session.execute(sql).scalars().all()
        return data

    def random_env_name(self, session, enterprise=None, length=8):
        """
        生成随机的云帮租户（云帮的团队名），副需要符合k8s的规范(小写字母,_)
        :param enterprise 企业信息
        :param length:
        :return:
        """
        tenant_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        sql = select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == tenant_name)
        q = session.execute(sql)
        session.flush()
        data = q.scalars().all()
        while len(data) > 0:
            tenant_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        return tenant_name

    def env_is_exists_by_env_name(self, session, env_id, env_alias):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.env_alias == env_alias,
            TeamEnvInfo.env_id == env_id)).scalars().first()

    def env_is_exists_by_namespace(self, session, tenant_env_id, env_name):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.env_name == env_name,
            TeamEnvInfo.env_id == tenant_env_id)).scalars().first()

    def create_env(self, session, user, region_name, env_name, env_alias, team_id, team_name, namespace="",
                   desc=""):
        if not env_alias:
            env_alias = "{0}的环境".format(user.nick_name)
        params = {
            "env_name": env_name,
            "region_name": region_name,
            "creater": user.user_id,
            "env_alias": env_alias,
            "limit_memory": 0,
            "namespace": namespace,
            "tenant_env_id": team_id,
            "tenant_name": team_name,
            "desc": desc
        }
        add_team = TeamEnvInfo(**params)
        session.add(add_team)
        session.flush()
        return add_team

    def get_team_region_names(self, session, env_id):
        result_region_names = session.execute(
            select(EnvRegionInfo.region_name).where(EnvRegionInfo.region_env_id == env_id))
        region_names = result_region_names.scalars().all()
        result_regions = session.execute(
            select(RegionConfig.region_name).where(RegionConfig.region_name.in_(region_names)))
        regions = result_regions.scalars().all()
        return regions

    def get_team_by_team_name(self, session, team_name):
        return session.execute(select(TeamEnvInfo).where(
            TeamEnvInfo.tenant_name == team_name)).scalars().first()

    def get_region_alias(self, session, region_name):
        try:
            results = session.execute(select(RegionConfig).where(
                RegionConfig.region_name == region_name))
            region = results.scalars().all()
            if region:
                region = region[0]
                region_alias = region.region_alias
                return region_alias
            else:
                return None
        except Exception as e:
            logger.exception(e)
            return "测试Region"

    def get_tenant(self, session, tenant_name):
        tenant = session.execute(
            select(TeamEnvInfo).where(TeamEnvInfo.tenant_name == tenant_name))
        return tenant.scalars().first()


env_repo = EnvRepository(TeamEnvInfo)
