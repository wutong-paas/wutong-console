import base64
import datetime
import json
import re

from fastapi.encoders import jsonable_encoder
from loguru import logger

from clients.remote_build_client import remote_build_client
from clients.remote_domain_client import remote_domain_client_api
from core.utils.certutil import analyze_cert, cert_is_effective
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import ServiceHandleException, AbortRequest
from models.teams import ServiceDomain
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import configuration_repo, port_repo
from repository.component.service_domain_repo import domain_repo
from repository.component.service_tcp_domain_repo import tcp_domain_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo
from service.cert_service import cert_service


class DomainService(object):
    HTTP = "http"

    def delete_certificate_by_pk(self, session, pk):
        cert = domain_repo.get_certificate_by_pk(session, pk)
        if not cert:
            raise ServiceHandleException("certificate not found", "证书不存在", 404, 404)

        # can't delete the cerificate that till has http rules
        http_rules = domain_repo.list_service_domains_by_cert_id(session, pk)
        if http_rules:
            raise ServiceHandleException("the certificate still has http rules", "仍有网关策略在使用该证书", 400, 400)

        domain_repo.delete_certificate_by_pk(session, pk)

    def update_certificate(self, session, tenant_env, certificate_id, alias, certificate, private_key, certificate_type):
        cert_is_effective(certificate, private_key)
        cert = domain_repo.get_certificate_by_pk(session, certificate_id)
        if cert is None:
            raise ServiceHandleException("certificate not found", "证书不存在", 404, 404)
        if cert.alias != alias:
            self.__check_certificate_alias(session, tenant_env, alias)
            cert.alias = alias
        if certificate:
            cert.certificate = base64.b64encode(bytes(certificate, 'utf-8'))
        if certificate_type:
            cert.certificate_type = certificate_type
        if private_key:
            cert.private_key = private_key
        # cert.save()

        # update all ingress related to the certificate
        body = {
            "certificate_id": cert.certificate_id,
            "certificate_name": "foobar",
            "certificate": base64.b64decode(cert.certificate).decode(),
            "private_key": cert.private_key,
        }
        team_regions = cert_service.get_team_usable_regions(session, tenant_env.tenant_name)
        for team_region in team_regions:
            try:
                remote_build_client.update_ingresses_by_certificate(session, team_region.region_name,
                                                                    tenant_env, body)
            except Exception as e:
                logger.debug(e)
                continue
        return cert

    def get_certificate_by_pk(self, session, pk):
        certificate = domain_repo.get_certificate_by_pk(session, pk)
        if not certificate:
            return 404, "证书不存在", None
        data = dict()
        data["alias"] = certificate.alias
        data["certificate_type"] = certificate.certificate_type
        data["id"] = certificate.ID
        data["tenant_env_id"] = certificate.tenant_env_id
        data["certificate"] = base64.b64decode(certificate.certificate).decode()
        data["private_key"] = certificate.private_key
        return 200, "success", data

    def __check_certificate_alias(self, session, tenant_env, alias):
        if domain_repo.get_certificate_by_alias(session, tenant_env.env_id, alias):
            raise ServiceHandleException("certificate name already exists", "证书别名已存在", 412, 412)

    def add_certificate(self, session, tenant_env, alias, certificate_id, certificate, private_key, certificate_type):
        self.__check_certificate_alias(session, tenant_env, alias)
        cert_is_effective(certificate, private_key)
        certificate = base64.b64encode(bytes(certificate, 'utf-8'))
        certificate = domain_repo.add_certificate(session, tenant_env.env_id, alias, certificate_id, certificate,
                                                  private_key,
                                                  certificate_type)
        return certificate

    def get_time_now(self):
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def __check_domain_name(self, session: SessionClass, env_id, region_id, domain_name, certificate_id=None):
        if not domain_name:
            raise ServiceHandleException(status_code=400, error_code=400, msg="domain can not be empty",
                                         msg_show="域名不能为空")
        zh_pattern = re.compile('[\\u4e00-\\u9fa5]+')
        match = zh_pattern.search(domain_name)
        if match:
            raise ServiceHandleException(
                status_code=400, error_code=400, msg="domain can not be include chinese", msg_show="域名不能包含中文")
        # a租户绑定了域名manage.com,b租户就不可以在绑定该域名，只有a租户下可以绑定
        # s_domain = domain_repo.get_domain_by_domain_name(session, domain_name)
        # if s_domain and s_domain.tenant_env_id != team_id and s_domain.region_id == region_id:
        #     raise ServiceHandleException(
        #         status_code=400, error_code=400, msg="domain be used other team", msg_show="域名已经被其他团队使用")
        if len(domain_name) > 256:
            raise ServiceHandleException(
                status_code=400, error_code=400, msg="domain more than 256 bytes", msg_show="域名超过256个字符")
        if certificate_id:
            certificate_info = domain_repo.get_certificate_by_pk(session, int(certificate_id))
            cert = base64.b64decode(certificate_info.certificate).decode()
            data = analyze_cert(cert)
            sans = data["issued_to"]
            for certificat_domain_name in sans:
                if certificat_domain_name.startswith('*'):
                    domain_suffix = certificat_domain_name[2:]
                else:
                    domain_suffix = certificat_domain_name
                if domain_name.endswith(domain_suffix):
                    return
            raise ServiceHandleException(status_code=400, error_code=400, msg="domain", msg_show="域名与选择的证书不匹配")

    def update_tcpdomain(self, session: SessionClass, tenant_env, user, service, end_point, container_port, tcp_rule_id,
                         protocol, type,
                         rule_extensions,
                         default_ip):

        ip = end_point.split(":")[0]
        ip.replace(' ', '')
        port = end_point.split(":")[1]
        data = dict()
        data["service_id"] = service.service_id
        data["container_port"] = int(container_port)
        data["ip"] = ip
        data["port"] = int(port)
        data["tcp_rule_id"] = tcp_rule_id
        if rule_extensions:
            data["rule_extensions"] = rule_extensions

        try:
            # 给数据中心传送数据修改策略
            remote_domain_client_api.update_tcp_domain(session, service.service_region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        region = team_region_repo.get_region_by_region_name(session, service.service_region)
        # 先删除再添加
        tcp_domain_repo.delete_service_tcpdomain_by_tcp_rule_id(session, tcp_rule_id)
        domain_info = dict()
        domain_info["tcp_rule_id"] = tcp_rule_id
        domain_info["service_id"] = service.service_id
        domain_info["service_name"] = service.service_alias
        domain_info["service_alias"] = service.service_cname
        domain_info["create_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        domain_info["container_port"] = int(container_port)
        domain_info["tenant_env_id"] = tenant_env.env_id
        domain_info["protocol"] = protocol
        domain_info["end_point"] = end_point
        domain_info["type"] = type
        rule_extensions_str = ""
        if rule_extensions:
            # 拼接字符串，存入数据库
            for rule in rule_extensions:
                last_index = len(rule_extensions) - 1
                if last_index == rule_extensions.index(rule):
                    rule_extensions_str += rule["key"] + ":" + rule["value"]
                    continue
                rule_extensions_str += rule["key"] + ":" + rule["value"] + ","
        domain_info["rule_extensions"] = rule_extensions_str
        domain_info["region_id"] = region.region_id
        tcp_domain_repo.add_service_tcpdomain(session, **domain_info)
        return 200, "success"

    def get_certificate(self, session: SessionClass, tenant_env, page, page_size):
        end = page_size * page - 1  # 一页数据的开始索引
        start = end - page_size + 1  # 一页数据的结束索引
        certificate, nums = domain_repo.get_tenant_certificate_page(session, tenant_env.env_id, start, end)
        c_list = []
        for c in certificate:
            cert = base64.b64decode(c.certificate)
            data = dict()
            data["alias"] = c.alias
            data["certificate_type"] = c.certificate_type
            data["id"] = c.ID
            data.update(analyze_cert(cert))
            c_list.append(data)
        return c_list, nums

    def get_port_bind_domains(self, session: SessionClass, service, container_port):
        return domain_repo.get_service_domain_by_container_port(session, service.service_id, container_port)

    def get_tcp_port_bind_domains(self, session: SessionClass, service, container_port):
        return tcp_domain_repo.get_service_tcp_domains_by_service_id_and_port(session, service.service_id,
                                                                              container_port)

    def bind_domain(self, session: SessionClass, tenant_env, user, service, domain_name, container_port, protocol,
                    certificate_id,
                    domain_type,
                    rule_extensions):
        region = region_repo.get_region_by_region_name(session, service.service_region)
        self.__check_domain_name(session, tenant_env.env_id, region.region_id, domain_name, certificate_id)
        certificate_info = None
        http_rule_id = make_uuid(domain_name)
        if certificate_id:
            certificate_info = domain_repo.get_certificate_by_pk(session, int(certificate_id))
        data = dict()
        data["domain"] = domain_name
        data["service_id"] = service.service_id
        data["tenant_env_id"] = tenant_env.env_id
        data["container_port"] = int(container_port)
        data["protocol"] = protocol
        data["http_rule_id"] = http_rule_id
        # 证书信息
        data["certificate"] = ""
        data["private_key"] = ""
        data["certificate_name"] = ""
        if rule_extensions:
            data["rule_extensions"] = rule_extensions
        if certificate_info:
            data["certificate"] = base64.b64decode(certificate_info.certificate).decode()
            data["private_key"] = certificate_info.private_key
            data["certificate_name"] = certificate_info.alias
            data["certificate_id"] = certificate_info.certificate_id
        remote_domain_client_api.bind_http_domain(session, service.service_region, tenant_env, data)
        domain_info = dict()
        domain_info["service_id"] = service.service_id
        domain_info["service_name"] = service.service_alias
        domain_info["domain_name"] = domain_name
        domain_info["domain_type"] = domain_type
        domain_info["service_alias"] = service.service_cname
        domain_info["create_time"] = self.get_time_now()
        domain_info["container_port"] = int(container_port)
        domain_info["protocol"] = "http"
        if certificate_id:
            domain_info["protocol"] = "https"
        if rule_extensions:
            domain_info["rule_extensions"] = rule_extensions
        domain_info["certificate_id"] = certificate_info.ID if certificate_info else 0
        domain_info["http_rule_id"] = http_rule_id
        domain_info["type"] = 1
        domain_info["service_alias"] = service.service_cname
        domain_info["tenant_env_id"] = tenant_env.env_id
        domain_info["region_id"] = region.region_id
        domain_info["domain_path"] = ""
        domain_info["domain_cookie"] = ""
        domain_info["domain_heander"] = ""
        domain_info["rule_extensions"] = ""
        return domain_repo.add_service_domain(session, **domain_info)

    def unbind_domain(self, session: SessionClass, tenant_env, service, container_port, domain_name, is_tcp=False):
        if not is_tcp:
            service_domains = domain_repo.get_domain_by_name_and_port(session,
                                                                      service.service_id,
                                                                      container_port, domain_name)
            if not service_domains:
                raise ServiceHandleException(status_code=404, error_code=1404, msg="domain not found", msg_show="域名不存在")
            domain_repo.delete_domain_by_name_and_port(session, service.service_id, container_port, domain_name)
            for servicer_domain in service_domains:
                data = dict()
                data["service_id"] = servicer_domain.service_id
                data["domain"] = servicer_domain.domain_name
                data["container_port"] = int(container_port)
                data["http_rule_id"] = servicer_domain.http_rule_id
                try:
                    remote_domain_client_api.delete_http_domain(session,
                                                                service.service_region, tenant_env, data)
                except remote_domain_client_api.CallApiError as e:
                    if e.status != 404:
                        raise e
        else:
            servicer_tcp_domain = tcp_domain_repo.get_service_tcp_domain_by_service_id_and_port(
                service.service_id, container_port, domain_name)
            if not servicer_tcp_domain:
                raise ServiceHandleException(status_code=404, error_code=2404, msg="domain not found", msg_show="策略不存在")
            data = dict()
            data["tcp_rule_id"] = servicer_tcp_domain.tcp_rule_id
            try:
                remote_domain_client_api.unbind_tcp_domain(session, service.service_region, tenant_env, data)
                servicer_tcp_domain.delete()
            except remote_domain_client_api.CallApiError as e:
                if e.status != 404:
                    raise e

    def delete_by_port(self, session: SessionClass, component_id, port):
        http_rules = domain_repo.list_service_domain_by_port(session, component_id, port)
        http_rule_ids = [rule.http_rule_id for rule in http_rules]
        # delete rule extensions
        configuration_repo.delete_by_rule_ids(session, http_rule_ids)
        # delete http rules
        domain_repo.delete_service_domain_by_port(session, component_id, port)
        # delete tcp rules
        tcp_domain_repo.delete_by_component_port(session, component_id, port)

    def create_default_gateway_rule(self, session: SessionClass, tenant_env, region_info, service, port):
        if port.protocol == "http":
            service_id = service.service_id
            service_name = service.service_alias
            container_port = port.container_port
            domain_name = str(container_port) + "." + str(service_name) + "." + str(tenant_env.tenant_name) + "." + str(
                region_info.httpdomain)
            create_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            protocol = "http"
            http_rule_id = make_uuid(domain_name)
            tenant_env_id = tenant_env.env_id
            service_alias = service.service_cname
            region_id = region_info.region_id
            domain_repo.create_service_domains(session,
                                               service_id, service_name, domain_name, create_time, container_port,
                                               protocol,
                                               http_rule_id, tenant_env_id, service_alias, region_id)
            logger.debug("create default gateway http rule for component {0} port {1}".format(
                service.service_alias, port.container_port))
        else:
            res, data = remote_build_client.get_port(session, region_info.region_name, tenant_env, True)
            if int(res.status) != 200:
                logger.warning("can not get stream port from region, ignore {0} port {1}".format(
                    service.service_alias, port.container_port))
                return
            end_point = "0.0.0.0:{0}".format(data["bean"])
            service_id = service.service_id
            service_name = service.service_alias
            create_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            container_port = port.container_port
            protocol = port.protocol
            service_alias = service.service_cname
            tcp_rule_id = make_uuid(end_point)
            tenant_env_id = tenant_env.env_id
            region_id = region_info.region_id
            tcp_domain_repo.create_service_tcp_domains(session,
                                                       service_id, service_name, end_point, create_time,
                                                       container_port,
                                                       protocol,
                                                       service_alias, tcp_rule_id, tenant_env_id, region_id)
            logger.debug("create default gateway stream rule for component {0} port {1}, endpoint {2}".format(
                service.service_alias, port.container_port, end_point))

    # 获取应用下策略列表
    def get_app_service_domain_list(self, session: SessionClass, region, tenant_env, app_id, search_conditions, page,
                                    page_size):
        # 查询分页排序
        if search_conditions:
            if isinstance(search_conditions, bytes):
                search_conditions = search_conditions.decode('utf-8')
            # 获取总数
            domain_count = domain_repo.get_domain_count_search_conditions(session,
                                                                          tenant_env.env_id, region.region_id,
                                                                          search_conditions, app_id)
            total = domain_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num
            tenant_tuples = domain_repo.get_tenant_tuples_search_conditions(session,
                                                                            tenant_env.env_id, region.region_id,
                                                                            search_conditions, start, end, app_id)
        else:
            # 获取总数
            domain_count = domain_repo.get_domain_count(session, tenant_env.env_id, region.region_id, app_id)
            total = domain_count[0][0]
            tenant_tuples = domain_repo.get_tenant_tuples(session, tenant_env.env_id, region.region_id, app_id)

        return tenant_tuples, total

        # 获取应用下tcp&udp策略列表

    def get_app_service_tcp_domain_list(self, session: SessionClass, region, tenant_env, app_id, search_conditions, page,
                                        page_size):
        # 查询分页排序
        if search_conditions:
            if isinstance(search_conditions, bytes):
                search_conditions = search_conditions.decode('utf-8')
            # 获取总数
            domain_count = tcp_domain_repo.get_domain_count_search_conditions(session, tenant_env.env_id,
                                                                              region.region_id,
                                                                              search_conditions, app_id)

            total = domain_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            tenant_tuples = tcp_domain_repo.get_tenant_tuples_search_conditions(session, tenant_env.env_id,
                                                                                region.region_id,
                                                                                search_conditions, start,
                                                                                end,
                                                                                app_id)
        else:
            # 获取总数
            domain_count = tcp_domain_repo.get_domain_count(session, tenant_env.env_id, region.region_id, app_id)

            total = domain_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            tenant_tuples = tcp_domain_repo.get_tenant_tuples(session, tenant_env.env_id, region.region_id, start, end,
                                                              app_id)
        return tenant_tuples, total

    def bind_httpdomain(self, session: SessionClass, tenant_env, user, service, httpdomain, return_model=False):
        domain_name = httpdomain["domain_name"]
        certificate_id = httpdomain["certificate_id"]
        rule_extensions = httpdomain.get("rule_extensions", [])
        domain_path = httpdomain.get("domain_path", None)
        domain_cookie = httpdomain.get("domain_cookie", None)
        domain_heander = httpdomain.get("domain_heander", None)
        protocol = httpdomain.get("protocol", None)
        domain_type = httpdomain["domain_type"]
        auto_ssl = httpdomain["auto_ssl"]
        auto_ssl_config = httpdomain["auto_ssl_config"]
        path_rewrite = httpdomain["path_rewrite"]
        rewrites = httpdomain["rewrites"]
        region = region_repo.get_region_by_region_name(session, service.service_region)
        # 校验域名格式
        self.__check_domain_name(session, tenant_env.env_id, region.region_id, domain_name, certificate_id)
        http_rule_id = make_uuid(domain_name)
        domain_info = dict()
        certificate_info = None
        if certificate_id:
            certificate_info = domain_repo.get_certificate_by_pk(session=session, pk=int(certificate_id))
        data = dict()
        data["uuid"] = make_uuid(domain_name)
        data["domain"] = domain_name
        data["service_id"] = service.service_id
        data["tenant_env_id"] = tenant_env.env_id
        data["tenant_name"] = tenant_env.tenant_name
        data["protocol"] = protocol
        data["container_port"] = int(httpdomain["container_port"])
        data["add_time"] = self.get_time_now()
        data["add_user"] = user.nick_name if user else ""
        data["http_rule_id"] = http_rule_id
        data["path"] = domain_path
        data["cookie"] = domain_cookie
        data["header"] = domain_heander
        data["weight"] = int(httpdomain.get("the_weight", 100))
        if rule_extensions:
            data["rule_extensions"] = rule_extensions
        data["certificate"] = ""
        data["private_key"] = ""
        data["certificate_name"] = ""
        data["certificate_id"] = ""
        if certificate_info:
            data["certificate"] = base64.b64decode(certificate_info.certificate).decode()
            data["private_key"] = certificate_info.private_key
            data["certificate_name"] = certificate_info.alias
            data["certificate_id"] = certificate_info.certificate_id
        data["path_rewrite"] = path_rewrite
        if rewrites is None:
            data["rewrites"] = []
        else:
            data["rewrites"] = rewrites
        try:
            remote_domain_client_api.bind_http_domain(session, service.service_region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        if domain_path and domain_path != "/" or domain_cookie or domain_heander:
            domain_info["is_senior"] = True
        if protocol:
            domain_info["protocol"] = protocol
        else:
            domain_info["protocol"] = "http"
            if certificate_id:
                domain_info["protocol"] = "https"
        domain_info["http_rule_id"] = http_rule_id
        domain_info["service_id"] = service.service_id
        domain_info["service_name"] = service.service_alias
        domain_info["domain_name"] = domain_name
        domain_info["domain_type"] = domain_type
        domain_info["service_alias"] = service.service_cname
        domain_info["create_time"] = self.get_time_now()
        domain_info["container_port"] = int(httpdomain["container_port"])
        domain_info["certificate_id"] = certificate_info.ID if certificate_info else 0
        domain_info["domain_path"] = domain_path if domain_path else '/'
        domain_info["domain_cookie"] = domain_cookie if domain_cookie else ""
        domain_info["domain_heander"] = domain_heander if domain_heander else ""
        domain_info["the_weight"] = int(httpdomain.get("the_weight", 100))
        domain_info["tenant_env_id"] = tenant_env.env_id
        domain_info["auto_ssl"] = auto_ssl
        domain_info["auto_ssl_config"] = auto_ssl_config

        rule_extensions_str = ""
        if rule_extensions:
            # 拼接字符串，存入数据库
            for rule in rule_extensions:
                last_index = len(rule_extensions) - 1
                if last_index == rule_extensions.index(rule):
                    rule_extensions_str += rule["key"] + ":" + rule["value"]
                    continue
                rule_extensions_str += rule["key"] + ":" + rule["value"] + ","

        domain_info["rule_extensions"] = rule_extensions_str
        domain_info["region_id"] = region.region_id
        domain_info["path_rewrite"] = path_rewrite
        if rewrites is not None:
            domain_info["rewrites"] = json.dumps(rewrites)
        else:
            domain_info["rewrites"] = None
        region = region_repo.get_region_by_region_name(session, service.service_region)
        # 判断类型（默认or自定义）
        if domain_name != "{0}.{1}.{2}.{3}".format(httpdomain["container_port"], service.service_alias,
                                                   tenant_env.tenant_name,
                                                   region.httpdomain):
            domain_info["type"] = 1
        # 高级路由
        model = domain_repo.add_service_domain(session, **domain_info)
        if return_model:
            return model
        domain_info.update({"rule_extensions": rule_extensions})
        if certificate_info:
            domain_info.update({"certificate_name": certificate_info.alias})
        return domain_info

    def check_set_header(self, session: SessionClass, set_headers):
        r = re.compile('([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9]')
        for header in set_headers:
            if "item_key" in header and not r.match(header["item_key"]):
                raise ServiceHandleException(
                    msg="forbidden key: {0}".format(header["item_key"]),
                    msg_show="Header Key不合法",
                    status_code=400,
                    error_code=400)

    def update_rule_config(self, session: SessionClass, tenant_env, region_name, rule_id, configs, type, service_id=None):
        if type == "http":
            self.check_set_header(session=session, set_headers=configs["set_headers"])
            service_domain = domain_repo.get_service_domain_by_http_rule_id(session, rule_id)
            if not service_domain:
                raise AbortRequest("no domain", msg_show="策略不存在", status_code=404, error_code=None)
            service = service_info_repo.get_service_by_service_id(session, service_domain.service_id)
        else:
            service = service_info_repo.get_service_by_service_id(session, service_id)
        if not service:
            raise AbortRequest("no service", msg_show="组件不存在", status_code=404, error_code=None)
        cf = configuration_repo.get_configuration_by_rule_id(session, rule_id)
        gcc_dict = dict()
        gcc_dict["body"] = configs
        gcc_dict["rule_id"] = rule_id
        try:
            if type == "http":
                res, data = remote_build_client.upgrade_configuration(session, region_name, tenant_env,
                                                                      service.service_alias,
                                                                      gcc_dict)
            else:
                res, data = remote_build_client.upgrade_tcp_configuration(session, region_name, tenant_env,
                                                                          service.service_alias,
                                                                          gcc_dict)
            if res.status == 200:
                if cf:
                    cf.value = json.dumps(configs)
                else:
                    cf_dict = dict()
                    cf_dict["rule_id"] = rule_id
                    cf_dict["value"] = json.dumps(configs)
                    configuration_repo.add_configuration(session, **cf_dict)
        except remote_build_client.CallApiFrequentError as e:
            logger.exception(e)
            raise ServiceHandleException(
                msg="update http rule configuration failure", msg_show="更新HTTP策略的参数发生异常", status_code=500,
                error_code=500)

    def update_httpdomain(self, session: SessionClass, tenant_env, service, http_rule_id, update_data, re_model=False):
        service_domain = domain_repo.get_service_domain_by_http_rule_id(session, http_rule_id)
        if not service_domain:
            raise ServiceHandleException(msg="no found", status_code=404)
        domain_info = jsonable_encoder(service_domain)
        domain_info.update(update_data)

        self.__check_domain_name(session=session,
                                 env_id=tenant_env.env_id,
                                 region_id=service_domain.region_id,
                                 domain_name=domain_info["domain_name"],
                                 certificate_id=domain_info["certificate_id"])

        certificate_info = None
        if domain_info["certificate_id"]:
            certificate_info = domain_repo.get_certificate_by_pk(session, int(domain_info["certificate_id"]))

        data = dict()
        data["domain"] = domain_info["domain_name"]
        data["service_id"] = service.service_id
        data["tenant_env_id"] = tenant_env.env_id
        data["tenant_name"] = tenant_env.tenant_name
        data["container_port"] = int(domain_info["container_port"])
        data["http_rule_id"] = http_rule_id
        data["path"] = domain_info["domain_path"] if domain_info["domain_path"] else None
        data["cookie"] = domain_info["domain_cookie"] if domain_info["domain_cookie"] else None
        data["header"] = domain_info["domain_heander"] if domain_info["domain_heander"] else None
        data["weight"] = int(domain_info["the_weight"])
        if "rule_extensions" in list(update_data.keys()):
            if domain_info["rule_extensions"]:
                data["rule_extensions"] = domain_info["rule_extensions"]
        else:
            try:
                rule_extensions = eval(domain_info["rule_extensions"])
            except Exception:
                rule_extensions = []
            if rule_extensions:
                data["rule_extensions"] = rule_extensions

        # 证书信息
        data["certificate"] = ""
        data["private_key"] = ""
        data["certificate_name"] = ""
        data["certificate_id"] = ""
        if certificate_info:
            data["certificate"] = base64.b64decode(certificate_info.certificate).decode()
            data["private_key"] = certificate_info.private_key
            data["certificate_name"] = certificate_info.alias
            data["certificate_id"] = certificate_info.certificate_id
        data["path_rewrite"] = domain_info["path_rewrite"]
        data["rewrites"] = domain_info["rewrites"]
        try:
            # 给数据中心传送数据更新域名
            remote_domain_client_api.update_http_domain(session, service.service_region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        if "rule_extensions" in list(update_data.keys()):
            rule_extensions_str = ""
            # 拼接字符串，存入数据库
            for rule in update_data["rule_extensions"]:
                last_index = len(update_data["rule_extensions"]) - 1
                if last_index == update_data["rule_extensions"].index(rule):
                    rule_extensions_str += rule["key"] + ":" + rule["value"]
                    continue
                rule_extensions_str += rule["key"] + ":" + rule["value"] + ","
        else:
            rule_extensions_str = domain_info["rule_extensions"]
        domain_info["rule_extensions"] = rule_extensions_str
        if domain_info["domain_path"] and domain_info["domain_path"] != "/" or \
                domain_info["domain_cookie"] or domain_info["domain_heander"]:
            domain_info["is_senior"] = True
        domain_info["protocol"] = "http"
        if domain_info["certificate_id"]:
            domain_info["protocol"] = "https"
        domain_info["certificate_id"] = domain_info["certificate_id"] if domain_info["certificate_id"] else 0
        domain_info["domain_path"] = domain_info["domain_path"] if domain_info["domain_path"] else '/'
        domain_info["domain_cookie"] = domain_info["domain_cookie"] if domain_info["domain_cookie"] else ""
        domain_info["domain_heander"] = domain_info["domain_heander"] if domain_info["domain_heander"] else ""
        domain_info["container_port"] = int(domain_info["container_port"])
        domain_info["service_id"] = service.service_id
        domain_info["service_name"] = service.service_alias
        if not domain_info["rewrites"]:
            domain_info["rewrites"] = None
        model_data = ServiceDomain(**domain_info)
        domain_repo.save_service_domain(session, model_data)
        if re_model:
            return model_data
        return domain_info

    def unbind_httpdomain(self, session: SessionClass, tenant_env, region, http_rule_id):
        servicer_http_omain = domain_repo.get_service_domain_by_http_rule_id(session, http_rule_id)
        if not servicer_http_omain:
            raise ServiceHandleException(status_code=404, error_code=1404, msg="domain not found", msg_show="域名不存在")
        data = dict()
        data["service_id"] = servicer_http_omain.service_id
        data["domain"] = servicer_http_omain.domain_name
        data["http_rule_id"] = http_rule_id
        try:
            remote_domain_client_api.delete_http_domain(session, region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        domain_repo.delete_domain_by_rule_id(session, http_rule_id)

    def bind_tcpdomain(self, session: SessionClass, tenant_env, user, service, end_point, container_port, default_port,
                       rule_extensions, default_ip):
        tcp_rule_id = make_uuid(tenant_env.tenant_name)
        ip = str(end_point.split(":")[0])
        ip = ip.replace(' ', '')
        port = end_point.split(":")[1]
        data = dict()
        data["service_id"] = service.service_id
        data["container_port"] = int(container_port)
        data["ip"] = ip
        data["port"] = int(port)
        data["tcp_rule_id"] = tcp_rule_id
        if rule_extensions:
            data["rule_extensions"] = rule_extensions
        try:
            # 给数据中心传送数据添加策略
            remote_domain_client_api.bind_tcp_domain(session, service.service_region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        region = region_repo.get_region_by_region_name(session, service.service_region)
        domain_info = dict()
        domain_info["tcp_rule_id"] = tcp_rule_id
        domain_info["service_id"] = service.service_id
        domain_info["service_name"] = service.service_alias
        domain_info["service_alias"] = service.service_cname
        domain_info["create_time"] = self.get_time_now()
        domain_info["container_port"] = int(container_port)
        domain_info["tenant_env_id"] = tenant_env.env_id
        # 查询端口协议
        tenant_service_port = port_repo.get_service_port_by_port(session, service.tenant_env_id, service.service_id,
                                                                 container_port)
        if tenant_service_port:
            protocol = tenant_service_port.protocol
        else:
            protocol = ''
        if protocol:
            domain_info["protocol"] = protocol
        else:
            domain_info["protocol"] = 'tcp'
        domain_info["end_point"] = end_point
        domain_info["region_id"] = region.region_id
        rule_extensions_str = ""
        if rule_extensions:
            # 拼接字符串，存入数据库
            for rule in rule_extensions:
                last_index = len(rule_extensions) - 1
                if last_index == rule_extensions.index(rule):
                    rule_extensions_str += rule["key"] + ":" + rule["value"]
                    continue
                rule_extensions_str += rule["key"] + ":" + rule["value"] + ","

        domain_info["rule_extensions"] = rule_extensions_str

        if int(end_point.split(":")[1]) != default_port:
            domain_info["type"] = 1
        tcp_domain_repo.add_service_tcpdomain(session, **domain_info)
        domain_info.update({"rule_extensions": rule_extensions})
        return domain_info

    def unbind_tcpdomain(self, session: SessionClass, tenant_env, region, tcp_rule_id):
        service_tcp_domain = tcp_domain_repo.get_service_tcpdomain_by_tcp_rule_id(session, tcp_rule_id)
        if not service_tcp_domain:
            raise ServiceHandleException(status_code=404, error_code=2404, msg="domain not found", msg_show="策略不存在")
        data = dict()
        data["tcp_rule_id"] = tcp_rule_id
        try:
            # 给数据中心传送数据删除策略
            remote_domain_client_api.unbind_tcp_domain(session, region, tenant_env, data)
        except remote_domain_client_api.CallApiError as e:
            if e.status != 404:
                raise e
        tcp_domain_repo.delete_service_tcpdomain_by_tcp_rule_id(session, tcp_rule_id)


domain_service = DomainService()
