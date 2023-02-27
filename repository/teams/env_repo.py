"""
tenant repository
"""
import datetime
import random
import string
from loguru import logger
from sqlalchemy import select, delete, not_
from core.idaasapi import idaas_api
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams.enterprise import TeamEnterprise
from models.region.models import EnvRegionInfo
from core.setting import settings
from models.teams import EnvInfo, PermRelTenant, UserMessage, RegionConfig
from models.component.models import TeamComponentInfo
from repository.base import BaseRepository


class EnvRepository(BaseRepository[EnvInfo]):
    """
    TenantRepository
    """

    def get_enterprise_team_by_name(self, session, enterprise_id, team_name):
        return session.execute(select(EnvInfo).where(
            EnvInfo.enterprise_id == enterprise_id,
            EnvInfo.tenant_name == team_name
        )).scalars().first()

    @staticmethod
    def get_user_notjoin_teams(session, eid, user_id, name=None):
        enterprise = session.execute(select(TeamEnterprise).where(
            TeamEnterprise.enterprise_id == eid
        )).scalars().first()
        if not enterprise:
            return []
        perm_tenants = session.execute(select(PermRelTenant).where(
            PermRelTenant.enterprise_id == enterprise.ID,
            PermRelTenant.user_id == user_id
        ).order_by(PermRelTenant.ID.desc())).scalars().all()
        tenant_ids = [perm_tenant.tenant_id for perm_tenant in perm_tenants]
        sql = select(EnvInfo).where(not_(EnvInfo.ID.in_(tenant_ids)))
        if name:
            sql = select(EnvInfo).where(not_(EnvInfo.ID.in_(tenant_ids)),
                                        EnvInfo.tenant_alias.contains(name))
        return session.execute(sql).scalars().all()

    def get_team_by_enterprise_id(self, session, enterprise_id):
        return session.execute(select(EnvInfo).where(
            EnvInfo.enterprise_id == enterprise_id
        )).scalars().all()

    # 返回该团队下的所有管理员
    def get_tenant_admin_by_tenant_id(self, tenant):
        return idaas_api.get_user_info(tenant.creater)

    def delete_user_perms_in_permtenant(self, session, user_id, tenant_id):
        session.execute(delete(PermRelTenant).where(
            PermRelTenant.user_id == user_id,
            PermRelTenant.tenant_id == tenant_id))

    def get_tenant_by_tenant_name(self, session: SessionClass, team_name, exception=True):
        """
        get_tenant_by_tenant_name

        :param team_name:
        :return:
        """
        logger.info("get_tenant_by_tenant_name,param:{}", team_name)
        tenant = session.execute(select(EnvInfo).where(EnvInfo.tenant_name == team_name)).scalars().first()
        if not tenant and exception:
            return None
        return tenant

    def get_tenant_by_tenant_id(self, session: SessionClass, tenant_id):
        """
        get_tenant_by_tenant_id

        :param tenant_id:
        :return:
        """
        logger.info("get_tenant_by_tenant_id,param:{}", tenant_id)
        sql = select(EnvInfo).where(EnvInfo.tenant_id == tenant_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_team_by_team_names(self, session, team_names):
        return session.execute(select(EnvInfo).where(
            EnvInfo.tenant_name.in_(team_names))).scalars().all()

    def get_tenants_by_user_id(self, session, user_id, name=None):
        tenants = session.execute(select(PermRelTenant).where(
            PermRelTenant.user_id == user_id)).scalars().all()
        tenant_ids = [tenant.tenant_id for tenant in tenants]
        if name:
            tenants = session.execute(select(EnvInfo).where(
                EnvInfo.ID.in_(tenant_ids),
                EnvInfo.tenant_alias.contains(name)).order_by(
                EnvInfo.create_time.desc()
            )).scalars().all()
        else:
            tenants = session.execute(select(EnvInfo).where(
                EnvInfo.ID.in_(tenant_ids)).order_by(
                EnvInfo.create_time.desc()
            )).scalars().all()
        return tenants

    def get_tenant_users_by_tenant_name(self, session, team_name, name=None):
        """
        返回一个团队中所有用户对象
        :param team_name:
        :return:
        """
        logger.info("获取团队信息")
        tenant = (session.execute(select(EnvInfo).where(
            EnvInfo.tenant_name == team_name))).scalars().first()
        if not tenant:
            raise ServiceHandleException(msg="tenant not exist",
                                         msg_show="{}团队不存在".format(team_name))

        result = (session.execute(select(PermRelTenant).where(
            PermRelTenant.tenant_id == tenant.ID))).scalars().all()
        user_id_list = []
        for row in result:
            user_id_list.append(row.user_id)
        if not user_id_list:
            return []
        users = idaas_api.get_user_infos("/user/find-list-by-user-id-list", params={"userIdList": user_id_list})
        # todo
        # if users and name:
        #     users = (session.execute(select(Users).where(or_(Users.nick_name.contains_(name),
        #                                                      Users.real_name.contains_(name))))).scalars().all()
        return users

    def get_team_by_team_id(self, session, team_id):
        tenant = session.execute(
            select(EnvInfo).where(EnvInfo.tenant_id == team_id))
        return tenant.scalars().first()

    def get_env_by_env_id(self, session, env_id):
        return session.execute(
            select(EnvInfo).where(EnvInfo.env_id == env_id)).scalars().first()

    def get_team_by_team_name_and_eid(self, session, eid, team_name):
        tenant = session.execute(
            select(EnvInfo).where(EnvInfo.tenant_name == team_name,
                                  EnvInfo.enterprise_id == eid)).scalars().first()
        if not tenant:
            raise ServiceHandleException(msg_show="团队不存在", msg="team not found")
        return tenant

    def delete_by_env_id(self, session, env_id):
        row = session.execute(
            delete(EnvInfo).where(EnvInfo.env_id == env_id))
        return row.rowcount > 0

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_ids))).scalars().all()

    def save_tenant_service_info(self, session, ts):
        session.add(ts)
        session.flush()

    def get_team_region_by_name(self, session, team_id, region_name):
        return session.execute(select(EnvRegionInfo).where(
            EnvRegionInfo.region_name == region_name,
            EnvRegionInfo.tenant_id == team_id)).scalars().all()

    def get_user_tenant_by_name(self, session, user_id, name):
        res = session.execute(select(PermRelTenant).where(
            PermRelTenant.user_id == user_id)).scalars().all()
        tenant_ids = [r.tenant_id for r in res]
        tenant = session.execute(select(EnvInfo).where(
            EnvInfo.ID.in_(tenant_ids),
            EnvInfo.tenant_name == name)).scalars().first()
        return tenant

    def get_teams_by_enterprise_id(self, session, enterprise_id, user_id=None, query=None):
        """
        查询企业团队列表
        :param enterprise_id:
        :param user_id:
        :param query:
        :return:
        """
        sql = select(EnvInfo).where(
            EnvInfo.enterprise_id == enterprise_id).order_by(EnvInfo.create_time.desc())
        if user_id:
            sql = select(EnvInfo).where(
                EnvInfo.enterprise_id == enterprise_id,
                EnvInfo.creater == user_id).order_by(EnvInfo.create_time.desc())
        if query:
            sql = select(EnvInfo).where(
                EnvInfo.enterprise_id == enterprise_id,
                EnvInfo.tenant_alias.like('%' + query + '%')).order_by(EnvInfo.create_time.desc())

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
        sql = select(EnvInfo).where(EnvInfo.tenant_name == tenant_name)
        q = session.execute(sql)
        session.flush()
        data = q.scalars().all()
        while len(data) > 0:
            tenant_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        return tenant_name

    def env_is_exists_by_env_name(self, session, env_alias, enterprise_id):
        return session.execute(select(EnvInfo).where(
            EnvInfo.env_alias == env_alias,
            EnvInfo.enterprise_id == enterprise_id)).scalars().first()

    def env_is_exists_by_namespace(self, session, namespace, enterprise_id):
        return session.execute(select(EnvInfo).where(
            EnvInfo.namespace == namespace,
            EnvInfo.enterprise_id == enterprise_id)).scalars().first()

    def create_env(self, session, user, enterprise, env_alias, team_name, namespace=""):
        env_name = self.random_env_name(session, enterprise=user.enterprise_id, length=8)
        if not env_alias:
            env_alias = "{0}的环境".format(user.nick_name)
        params = {
            "env_name": env_name,
            "creater": user.user_id,
            "env_alias": env_alias,
            "enterprise_id": enterprise.enterprise_id,
            "limit_memory": 0,
            "namespace": namespace,
            "team_name": team_name
        }
        add_team = EnvInfo(**params)
        session.add(add_team)
        session.flush()
        return add_team

    def get_team_region_names(self, session, env_id):
        result_region_names = session.execute(
            select(EnvRegionInfo.region_name).where(EnvRegionInfo.env_id == env_id))
        region_names = result_region_names.scalars().all()
        result_regions = session.execute(
            select(RegionConfig.region_name).where(RegionConfig.region_name.in_(region_names)))
        regions = result_regions.scalars().all()
        return regions

    def get_tenant_users_by_tenant_ID(self, session, tenant_ID):
        """
        返回一个团队中所有用户对象
        :param tenant_ID:
        :return:
        """
        user_id_list = []
        res = session.execute(select(PermRelTenant).where(
            PermRelTenant.tenant_id == tenant_ID)).scalars().all()
        for rw in res:
            user_id_list.append(rw.user_id)

        if not user_id_list:
            return []
        user_list = idaas_api.get_user_infos("/user/find-list-by-user-id-list", params={"userIdList": user_id_list})
        return user_list

    def get_tenant_users_by_tenant_ID_name(self, session, tenant_ID, name):
        """
        返回一个团队中所有用户对象
        :param tenant_ID:
        :return:
        """
        user_id_list = []
        res = session.execute(select(PermRelTenant).where(
            PermRelTenant.tenant_id == tenant_ID)).scalars().all()
        for rw in res:
            user_id_list.append(rw.user_id)

        if not user_id_list:
            return []
        # todo
        user_list = idaas_api.get_user_infos("/user/find-list-by-user-id-list", params={"userIdList": user_id_list})
        # user_list = session.execute(select(Users).where(
        #     Users.user_id.in_(user_id_list),
        #     or_(Users.real_name.contains(name),
        #         Users.nick_name.contains(name)))).scalars().all()
        return user_list

    def get_team_by_team_name(self, session, team_name):
        return session.execute(select(EnvInfo).where(
            EnvInfo.tenant_name == team_name)).scalars().first()

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

    # 用户加入团队，发送站内信给用户
    def send_user_message_for_apply_info(self, session, user_id, team_name, info):
        tenant = self.get_tenant_by_tenant_name(session=session, team_name=team_name)
        message_id = make_uuid()
        content = '{0}团队{1}您加入该团队'.format(tenant.tenant_alias, info)
        session.add(UserMessage(message_id=message_id, receiver_id=user_id, content=content,
                                msg_type="warn", title="用户加入团队信息"))

    def get_tenant(self, session, tenant_name):
        tenant = session.execute(
            select(EnvInfo).where(EnvInfo.tenant_name == tenant_name))
        return tenant.scalars().first()

    def get_not_join_users(self, session, enterprise, tenant, query):
        where = """(SELECT DISTINCT user_id FROM tenant_perms WHERE tenant_id="{}" AND enterprise_id={})""".format(
            tenant.ID, enterprise.ID)

        sql = """
            SELECT user_id, nick_name, enterprise_id, email
            FROM user_info
            WHERE user_id NOT IN {where}
            AND enterprise_id="{enterprise_id}"
        """.format(
            where=where, enterprise_id=enterprise.enterprise_id)
        if query:
            sql += """
            AND nick_name like "%{query}%"
            """.format(query=query)
        result = session.execute(sql).fetchall()

        return result


env_repo = EnvRepository(EnvInfo)
