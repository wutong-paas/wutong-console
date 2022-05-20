"""
tenant repository
"""
import datetime
import random
import string

from loguru import logger
from sqlalchemy import select, delete, or_, not_

from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.teams.enterprise import TeamEnterprise
from models.region.models import TeamRegionInfo
from core.setting import settings
from models.teams import TeamInfo, PermRelTenant, UserMessage, RegionConfig, TeamGitlabInfo
from models.users.users import Users
from models.component.models import TeamComponentInfo
from repository.base import BaseRepository
from repository.teams.team_roles_repo import team_roles_repo
from repository.users.user_role_repo import user_role_repo


class TeamRepository(BaseRepository[TeamInfo]):
    """
    TenantRepository
    """

    def get_enterprise_team_by_name(self, session, enterprise_id, team_name):
        return session.execute(select(TeamInfo).where(
            TeamInfo.enterprise_id == enterprise_id,
            TeamInfo.tenant_name == team_name
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
        sql = select(TeamInfo).where(not_(TeamInfo.ID.in_(tenant_ids)))
        if name:
            sql = select(TeamInfo).where(not_(TeamInfo.ID.in_(tenant_ids)),
                                         TeamInfo.tenant_alias.contains(name))
        return session.execute(sql).scalars().all()

    def get_team_by_enterprise_id(self, session, enterprise_id):
        return session.execute(select(TeamInfo).where(
            TeamInfo.enterprise_id == enterprise_id
        )).scalars().all()

    # 返回该团队下的所有管理员
    def get_tenant_admin_by_tenant_id(self, session, tenant):
        return session.execute(select(Users).where(
            Users.user_id == tenant.creater)).scalars().all()

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
        tenant = session.execute(select(TeamInfo).where(TeamInfo.tenant_name == team_name)).scalars().first()
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
        sql = select(TeamInfo).where(TeamInfo.tenant_id == tenant_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def get_team_by_team_names(self, session, team_names):
        return session.execute(select(TeamInfo).where(
            TeamInfo.tenant_name.in_(team_names))).scalars().all()

    def get_tenants_by_user_id(self, session, user_id, name=None):
        tenants = session.execute(select(PermRelTenant).where(
            PermRelTenant.user_id == user_id)).scalars().all()
        tenant_ids = [tenant.tenant_id for tenant in tenants]
        if name:
            tenants = session.execute(select(TeamInfo).where(
                TeamInfo.ID.in_(tenant_ids),
                TeamInfo.tenant_alias.contains(name)).order_by(
                TeamInfo.create_time.desc()
            )).scalars().all()
        else:
            tenants = session.execute(select(TeamInfo).where(
                TeamInfo.ID.in_(tenant_ids)).order_by(
                TeamInfo.create_time.desc()
            )).scalars().all()
        return tenants

    def get_tenant_users_by_tenant_name(self, session, team_name, name=None):
        """
        返回一个团队中所有用户对象
        :param team_name:
        :return:
        """
        logger.info("获取团队信息")
        tenant = (session.execute(select(TeamInfo).where(
            TeamInfo.tenant_name == team_name))).scalars().first()
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
        users = (session.execute(select(Users).where(
            Users.user_id.in_(user_id_list)))).scalars().all()
        if users and name:
            users = (session.execute(select(Users).where(or_(Users.nick_name.contains_(name),
                                                             Users.real_name.contains_(name))))).scalars().all()
        return users

    def get_team_by_team_id(self, session, team_id):
        tenant = session.execute(
            select(TeamInfo).where(TeamInfo.tenant_id == team_id))
        return tenant.scalars().first()

    def get_team_by_team_name_and_eid(self, session, eid, team_name):
        tenant = session.execute(
            select(TeamInfo).where(TeamInfo.tenant_name == team_name,
                                   TeamInfo.enterprise_id == eid)).scalars().first()
        if not tenant:
            raise ServiceHandleException(msg_show="团队不存在", msg="team not found")
        return tenant

    def delete_by_tenant_id(self, session, tenant_id):
        tenant = session.execute(
            select(TeamInfo).where(TeamInfo.tenant_id == tenant_id)).scalars().first()
        session.execute(
            delete(PermRelTenant).where(PermRelTenant.tenant_id == tenant.ID))
        row = session.execute(
            delete(TeamInfo).where(TeamInfo.ID == tenant.ID))
        return row.rowcount > 0

    def list_by_component_ids(self, session, service_ids: []):
        return session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_ids))).scalars().all()

    def save_tenant_service_info(self, session, ts):
        session.merge(ts)

    def get_team_region_by_name(self, session, team_id, region_name):
        return session.execute(select(TeamRegionInfo).where(
            TeamRegionInfo.region_name == region_name,
            TeamRegionInfo.tenant_id == team_id)).scalars().all()

    def get_user_tenant_by_name(self, session, user_id, name):
        res = session.execute(select(PermRelTenant).where(
            PermRelTenant.user_id == user_id)).scalars().all()
        tenant_ids = [r.tenant_id for r in res]
        tenant = session.execute(select(TeamInfo).where(
            TeamInfo.ID.in_(tenant_ids),
            TeamInfo.tenant_name == name)).scalars().first()
        return tenant

    def get_teams_by_enterprise_id(self, session, enterprise_id, user_id=None, query=None):
        """
        查询企业团队列表
        :param enterprise_id:
        :param user_id:
        :param query:
        :return:
        """
        sql = select(TeamInfo).where(
            TeamInfo.enterprise_id == enterprise_id).order_by(TeamInfo.create_time.desc())
        if user_id:
            sql = select(TeamInfo).where(
                TeamInfo.enterprise_id == enterprise_id,
                TeamInfo.creater == user_id).order_by(TeamInfo.create_time.desc())
        if query:
            sql = select(TeamInfo).where(
                TeamInfo.enterprise_id == enterprise_id,
                TeamInfo.tenant_alias.like('%' + query + '%')).order_by(TeamInfo.create_time.desc())

        data = session.execute(sql).scalars().all()
        return data

    def random_tenant_name(self, session, enterprise=None, length=8):
        """
        生成随机的云帮租户（云帮的团队名），副需要符合k8s的规范(小写字母,_)
        :param enterprise 企业信息
        :param length:
        :return:
        """
        tenant_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        sql = select(TeamInfo).where(TeamInfo.tenant_name == tenant_name)
        q = session.execute(sql)
        session.flush()
        data = q.scalars().all()
        while len(data) > 0:
            tenant_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        return tenant_name

    def team_is_exists_by_team_name(self, session, team_alias, enterprise_id):
        return session.execute(select(TeamInfo).where(
            TeamInfo.tenant_alias == team_alias,
            TeamInfo.enterprise_id == enterprise_id)).scalars().first()

    def team_is_exists_by_namespace(self, session, namespace, enterprise_id):
        return session.execute(select(TeamInfo).where(
            TeamInfo.namespace == namespace,
            TeamInfo.enterprise_id == enterprise_id)).scalars().first()

    def create_team(self, session, user, enterprise, regions, team_alias, namespace=""):
        team_name = self.random_tenant_name(session, enterprise=user.enterprise_id, length=8)

        is_public = settings.SSO_LOGIN
        if not is_public:
            pay_type = 'payed'
            pay_level = 'company'
        else:
            pay_type = 'free'
            pay_level = 'company'
        expired_day = int(settings.TENANT_VALID_TIME)
        expire_time = datetime.datetime.now() + datetime.timedelta(days=expired_day)
        if not team_alias:
            team_alias = "{0}的团队".format(user.nick_name)
        params = {
            "tenant_name": team_name,
            "pay_type": pay_type,
            "pay_level": pay_level,
            "creater": user.user_id,
            "expired_time": expire_time,
            "tenant_alias": team_alias,
            "enterprise_id": enterprise.enterprise_id,
            "limit_memory": 0,
            "namespace": namespace
        }
        add_team = TeamInfo(**params)
        session.add(add_team)
        session.flush()

        create_perm_param = {
            "user_id": user.user_id,
            "tenant_id": add_team.ID,
            "identity": "owner",
            "enterprise_id": enterprise.ID,
        }
        add = PermRelTenant(**create_perm_param)
        session.add(add)
        session.flush()

        # # init default roles
        team_roles_repo.init_default_roles(session=session, kind="team", kind_id=add_team.tenant_id)
        admin_role = team_roles_repo.get_role_by_name(session=session, kind="team", kind_id=add_team.tenant_id,
                                                      name="管理员")
        user_role_repo.delete_user_roles(session=session, kind="team", kind_id=add_team.tenant_id, user=user)
        user_role_repo.update_user_roles(session=session,
                                         kind="team", kind_id=add_team.tenant_id, user=user,
                                         role_ids=[admin_role.ID])
        return add_team

    def get_team_region_names(self, session, team_id):
        result_region_names = session.execute(
            select(TeamRegionInfo.region_name).where(TeamRegionInfo.tenant_id == team_id))
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
        user_list = session.execute(select(Users).where(
            Users.user_id.in_(user_id_list))).scalars().all()
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
        user_list = session.execute(select(Users).where(
            Users.user_id.in_(user_id_list),
            or_(Users.real_name.contains(name),
                Users.nick_name.contains(name)))).scalars().all()
        return user_list

    def get_team_by_team_name(self, session, team_name):
        return session.execute(select(TeamInfo).where(
            TeamInfo.tenant_name == team_name)).scalars().first()

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
            select(TeamInfo).where(TeamInfo.tenant_name == tenant_name))
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


class TeamGitlabRepo(object):
    def get_team_gitlab_by_team_id(self, session, team_id):
        return session.execute(select(TeamGitlabInfo).where(
            TeamGitlabInfo.team_id == team_id
        )).scalars().all()

    def create_team_gitlab_info(self, session, **params):
        gitlab_info = TeamGitlabInfo(**params)
        session.add(gitlab_info)
        session.flush()
        return gitlab_info

    def get_team_repo_by_code_name(self, session, team_id, repo_name):
        return session.execute(select(TeamGitlabInfo).where(
            TeamGitlabInfo.team_id == team_id,
            TeamGitlabInfo.repo_name == repo_name
        )).scalars().first()


team_repo = TeamRepository(TeamInfo)
team_gitlab_repo = TeamGitlabRepo()
