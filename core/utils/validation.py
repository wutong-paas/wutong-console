# -*- coding: utf8 -*-
import re
import ipaddress
import validators
from exceptions.main import ServiceHandleException


def validate_endpoint_address(address):
    def parse_ip():
        domain_ip = False
        format_address = address
        try:
            for item in address:
                if item == ".":
                    format_address = ipaddress.IPv4Address(address)
                    break
                elif item == ":":
                    format_address = ipaddress.IPv6Address(address)
                    break
        except ipaddress.AddressValueError:
            if validators.domain(address):
                domain_ip = True
        return format_address, domain_ip

    errs = []
    ip, domain_ip = parse_ip()
    if not domain_ip:
        if ip is None:
            errs.append("{} must be a valid IP address".format(address))
            return errs
        if ip.is_unspecified:
            errs.append("{} may not be unspecified (0.0.0.0)".format(address))
        if ip.is_loopback:
            errs.append("{} may not be in the loopback range (127.0.0.0/8)".format(address))
        # if ip.is_link_local:
        #     errs.append("{} may not be in the link-local range (169.254.0.0/16)".format(address))
        # if ip.is_link_local:
        #     errs.append("{} may not be in the link-local multicast range (224.0.0.0/24)".format(address))
    return errs, domain_ip


def validate_endpoints_info(endpoints_info):
    total_domain = 0
    exist_address = dict()
    for address in endpoints_info:
        if exist_address.get(address):
            raise ServiceHandleException(msg="Multiple instances of the same address are not allowed",
                                         msg_show="不允许多实例地址相同")
        exist_address[address] = address
        if "https://" in address:
            address = address.partition("https://")[2]
        if "http://" in address:
            address = address.partition("http://")[2]
        if ":" in address:
            address = address.rpartition(":")[0]
        errs, domain_ip = validate_endpoint_address(address)
        if domain_ip:
            total_domain += 1
        if errs:
            if len(errs) > 0:
                raise ServiceHandleException(msg=errs, msg_show="ip地址不合法")
    if total_domain > 1:
        raise ServiceHandleException(msg="do not support multi domain endpoint", msg_show="不允许多实例域名地址")
    elif total_domain > 0 and len(endpoints_info) > 1:
        raise ServiceHandleException(msg="do not support multi domain endpoint", msg_show="不允许多实例域名、ip混合地址")


def validate_name(name):
    # 只支持中文、字母、数字和-_组合,并且必须以中文、字母、数字开始和结束
    if re.match(r'^[a-z0-9A-Z\u4e00-\u9fa5]([a-zA-Z0-9_\-\u4e00-\u9fa5]*[a-z0-9A-Z\u4e00-\u9fa5])?$', name):
        return True
    return False


def node_validate_name(name):
    # 只支持英文、数字、中横线、下划线组合，只能以英文开头且中横线、下划线不能位于首尾。
    if re.match(r'^[a-zA-Z]([a-zA-Z0-9_\-]*[a-z0-9A-Z])?$', name):
        return True
    return False


# 验证名称
def is_qualified_name(name):
    # 只支持英文、数字、中横线、下划线、空格组合
    if re.match(r'^[\u4E00-\u9FA5\sA-Za-z0-9_-]+$', name):
        return True
    return False


# 验证标识
def is_qualified_code(code):
    # 只支持小写字母、数字或“-”，并且必须以字母开始、以数字或字母结尾
    if re.match(r'^[a-z]([-a-z0-9]*[a-z0-9])?$', code):
        return True
    return False


def name_rule_verification(name, code):

    if not name:
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error", msg_show="名称不能为空")

    if not code:
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error", msg_show="标识不能为空")

    if len(name) > 32:
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error", msg_show="名称不能超过32个字符")

    if len(code) > 32:
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error", msg_show="标识不能超过32个字符")

    if not is_qualified_name(name):
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error",
                                     msg_show="名称只支持中英文、数字、空格、中横线、下划线组合")

    if not is_qualified_code(code):
        raise ServiceHandleException(status_code=400, error_code=400, msg="param error",
                                     msg_show="标识只支持小写字母、数字、以及短横杠“-”组成，标识只能以小写字母开头，不能以数字开头且短横杠不能位于首尾")
