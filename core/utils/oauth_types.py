# -*- coding: utf8 -*-
# todo
support_oauth_type = {
    "github": None

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
