import os
import random
import re
import string

from loguru import logger
from sqlalchemy import select

from core.utils.crypt import make_uuid
from database.session import SessionClass
from models.teams.enterprise import TeamEnterprise
from repository.base import BaseRepository
from repository.region.region_config_repo import region_config_repo


class TeamEnterpriseRepository(BaseRepository[TeamEnterprise]):
    """
    TenantEnterpriseRepository
    """

    def random_enterprise_name(self, session: SessionClass, length=8):
        """
        生成随机的云帮企业名，副需要符合k8s的规范(小写字母,_)
        :param length:
        :return:
        """

        enter_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        results = session.execute(
            select(TeamEnterprise).where(TeamEnterprise.enterprise_name == enter_name)).scalars().all()
        while len(results) > 0:
            enter_name = ''.join(random.sample(string.ascii_lowercase + string.digits, length))
        return enter_name

    def get_tenant_enterprise_by_enterprise_id(self, session: SessionClass, enterprise_id):
        """

        :param enterprise_id:
        :return:
        """
        logger.info("get_tenant_enterprise_by_enterprise_id,param:{}", enterprise_id)
        sql = select(TeamEnterprise).where(TeamEnterprise.enterprise_id == enterprise_id)
        results = session.execute(sql)
        data = results.scalars().first()
        return data

    def create_enterprise(self, session: SessionClass, enterprise_name='', enterprise_alias=''):
        """
        创建一个本地的企业信息, 并生成本地的企业ID

        :param enterprise_name: 企业的英文名, 如果没有则自动生成一个, 如果存在则需要保证传递的名字在数据库中唯一
        :param enterprise_alias: 企业的别名, 可以中文, 用于展示用, 如果为空则自动生成一个
        :return:
        """
        enterprise = TeamEnterprise()

        # Deal with enterprise English name, discard logic.
        if enterprise_name:
            enterprise_name_regx = re.compile(r'^[a-z0-9-]*$')
            if enterprise_name and not enterprise_name_regx.match(enterprise_name):
                logger.error('bad enterprise_name: {}'.format(enterprise_name))
                raise Exception('enterprise_name  must consist of lower case alphanumeric characters or -')

            if TeamEnterprise.objects.filter(enterprise_name=enterprise_name).count() > 0:
                raise Exception('enterprise_name [{}] already existed!'.format(enterprise_name))
            else:
                enter_name = enterprise_name
        else:
            enter_name = self.random_enterprise_name(session=session)
        enterprise.enterprise_name = enter_name

        # 根据企业英文名确认UUID
        results = session.execute(select(TeamEnterprise))
        results = results.scalars().all()
        is_first_ent = len(results) == 0
        eid = os.environ.get('ENTERPRISE_ID')
        if not eid or not is_first_ent:
            eid = make_uuid(str(enter_name))
        res = region_config_repo.get_all_regions(session=session)
        if len(res) > 0 and res[0]:
            res[0].enterprise_id = eid
            # region.save()
        enterprise.enterprise_id = eid

        # 处理企业别名
        if not enterprise_alias:
            enterprise.enterprise_alias = '企业{0}'.format(enter_name)
        else:
            enterprise.enterprise_alias = enterprise_alias

        # enterprise.save()
        session.add(enterprise)
        return enterprise


tenant_enterprise_repo = TeamEnterpriseRepository(TeamEnterprise)
