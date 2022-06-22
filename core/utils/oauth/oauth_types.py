# -*- coding: utf8 -*-
from core.utils.oauth.aliyun_api import AliYunApiV1
from core.utils.oauth.dbox_api import DboxApiV1
from core.utils.oauth.dingtalk_api import DingtalkApiV1
from core.utils.oauth.gitee_api import GiteeApiV5
from core.utils.oauth.github_api import GithubApiV3
from core.utils.oauth.gitlab_api import GitlabApiV4
from core.utils.oauth.idaas_api import IDaaSApiV1

support_oauth_type = {
    "github": GithubApiV3,
    "gitlab": GitlabApiV4,
    "gitee": GiteeApiV5,
    "aliyun": AliYunApiV1,
    "dingtalk": DingtalkApiV1,
    "dbox": DboxApiV1,
    "idaas": IDaaSApiV1
}


class NoSupportOAuthType(Exception):
    """
    type not support
    """


def get_support_oauth_servers():
    '''
    get the supported oauth server type
    '''
    return list(support_oauth_type.keys())


def get_oauth_instance(type_str=None, oauth_service=None, oauth_user=None):
    if type_str in support_oauth_type:
        instance = support_oauth_type[type_str]()
        instance.set_oauth_service(oauth_service)
        instance.set_oauth_user(oauth_user)
        return instance
    raise NoSupportOAuthType()
