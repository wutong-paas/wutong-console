from models.teams import EnvInfo
from repository.teams.team_enterprise_repo import tenant_enterprise_repo
from repository.teams.team_enterprise_token_repo import tenant_enterprise_token_repo
from repository.teams.env_repo import env_repo


# from service.team_service import env_services


def get_enterprise_access_token(session, enterprise_id, access_target):
    """

    :param enterprise_id:
    :param access_target:
    :return:
    """
    enter = tenant_enterprise_repo.get_tenant_enterprise_by_enterprise_id(session, enterprise_id)
    try:
        data = tenant_enterprise_token_repo.get_tenant_enterprise_token(session, enter.ID, access_target)
        return data
    except Exception:
        return None


cached_enter_token = dict()


class ClientAuthService(object):
    """
    ClientAuthService
    """

    def get_region_access_token_by_tenant(self, session, tenant_name, region_name):
        """

        :param tenant_name:
        :param region_name:
        :return:
        """
        tenant = env_repo.get_tenant_by_tenant_name(session, tenant_name)
        if not tenant:
            return None, None
        # todo token cache
        token = self.reflush_access_token(session, tenant.enterprise_id, region_name)

        if not token:
            return None, None

        return token.access_url, token.access_token

    def reflush_access_token(self, session, enterprise_id, access_target):
        """

        :param enterprise_id:
        :param access_target:
        :return:
        """
        enter_token = get_enterprise_access_token(session, enterprise_id, access_target)
        return enter_token

    def get_region_access_token_by_enterprise_id(self, session, enterprise_id, region_name):
        """

        :param enterprise_id:
        :param region_name:
        :return:
        """
        token = self.reflush_access_token(session, enterprise_id, region_name)
        if not token:
            return None, None
        return token.access_url, token.access_token

    def __get_cached_access_token(self, enterprise_id, access_target):
        key = '-'.join([enterprise_id, access_target])
        return cached_enter_token.get(key)

    def get_region_access_enterprise_id_by_tenant(self, session, tenant_name, region_name):
        team = env_repo.get_one_by_model(session=session, query_model=EnvInfo(tenant_name=tenant_name))
        if not team:
            return None

        token = self.__get_cached_access_token(team.enterprise_id, region_name)
        if not token:
            token = self.reflush_access_token(session, team.enterprise_id, region_name)

        if not token:
            return None

        return token.access_id


client_auth_service = ClientAuthService()
