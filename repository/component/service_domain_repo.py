import datetime
import os

from sqlalchemy import select, delete, func, text

from models.teams import ServiceDomain, ServiceDomainCertificate
from repository.base import BaseRepository


class ServiceDomainRepository(BaseRepository[ServiceDomain]):

    def delete_http_domains(self, session, http_rule_id):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.http_rule_id == http_rule_id
        ))
        session.flush()

    def list_service_domains_by_cert_id(self, session, certificate_id):
        return session.execute(select(ServiceDomain).where(
            ServiceDomain.certificate_id == certificate_id)).scalars().all()

    def add_certificate(self, session, tenant_env_id, alias, certificate_id, certificate, private_key, certificate_type):
        service_domain_certificate = dict()
        service_domain_certificate["tenant_env_id"] = tenant_env_id
        service_domain_certificate["certificate_id"] = certificate_id
        service_domain_certificate["certificate"] = certificate
        service_domain_certificate["private_key"] = private_key
        service_domain_certificate["alias"] = alias
        service_domain_certificate["certificate_type"] = certificate_type
        service_domain_certificate["create_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        certificate_info = ServiceDomainCertificate(**service_domain_certificate)
        session.add(certificate_info)
        return certificate_info

    def get_certificate_by_alias(self, session, tenant_env_id, alias):
        return session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.tenant_env_id == tenant_env_id,
            ServiceDomainCertificate.alias == alias)).scalars().first()

    def delete_service_domain(self, session, service_id):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.service_id == service_id))

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id.in_(component_ids)))).scalars().all()

    def save_service_domain(self, session, service_domain):
        session.merge(service_domain)

    def get_service_domains(self, session, service_id, is_delete=False):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id == service_id,
            ServiceDomain.is_delete == is_delete))).scalars().all()

    def get_certificate_by_pk(self, session, pk):
        return (session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.ID == pk))).scalars().first()

    def delete_certificate_by_pk(self, session, pk):
        session.execute(delete(ServiceDomainCertificate).where(
            ServiceDomainCertificate.ID == pk))

    def get_tenant_certificate_page(self, session, tenant_env_id, start, end):
        """提供指定位置和数量的数据"""
        cert = (session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.tenant_env_id == tenant_env_id))).scalars().all()
        nums = len(cert)  # 证书数量
        # if end > nums - 1:
        #     end =nums - 1
        # if start <= nums - 1:

        part_cert = cert[start:end + 1]
        return part_cert, nums

    def count_by_service_ids(self, session, region_id, service_ids):
        return (session.execute(
            select(func.count(ServiceDomain.ID)).where(ServiceDomain.region_id == region_id,
                                                       ServiceDomain.service_id.in_(service_ids))
        )).first()[0]

    def get_service_domain_by_container_port(self, session, service_id, container_port):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id == service_id,
            ServiceDomain.container_port == container_port))).scalars().all()

    def get_domain_by_name_and_port_and_protocol(self, session, service_id, container_port, domain_name, protocol,
                                                 domain_path=None):
        if domain_path:
            return (session.execute(select(ServiceDomain).where(
                ServiceDomain.service_id == service_id,
                ServiceDomain.container_port == container_port,
                ServiceDomain.domain_name == domain_name,
                ServiceDomain.protocol == protocol,
                ServiceDomain.domain_path == domain_path))).scalars().first()
        else:
            return (session.execute(select(ServiceDomain).where(
                ServiceDomain.service_id == service_id,
                ServiceDomain.container_port == container_port,
                ServiceDomain.domain_name == domain_name,
                ServiceDomain.protocol == protocol))).scalars().first()

    def get_domain_by_domain_name(self, session, domain_name):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.domain_name == domain_name))).scalars().first()

    def add_service_domain(self, session, **domain_info):
        service_domain = ServiceDomain(**domain_info)
        session.add(service_domain)
        session.flush()
        return service_domain

    def create_service_domains(self, session, service_id, service_name, domain_name, create_time, container_port,
                               protocol,
                               http_rule_id,
                               tenant_env_id, service_alias, region_id):
        service_domain = ServiceDomain(
            service_id=service_id,
            service_name=service_name,
            domain_name=domain_name,
            create_time=create_time,
            container_port=container_port,
            protocol=protocol,
            http_rule_id=http_rule_id,
            tenant_env_id=tenant_env_id,
            service_alias=service_alias,
            region_id=region_id,
            domain_path="",
            domain_cookie="",
            domain_heander="",
            rule_extensions="")
        session.add(service_domain)

    def get_domain_by_name_and_port(self, session, service_id, container_port, domain_name):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.domain_name == domain_name,
            ServiceDomain.service_id == service_id,
            ServiceDomain.container_port == container_port))).scalars().all()

    def delete_domain_by_name_and_port(self, session, service_id, container_port, domain_name):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.domain_name == domain_name,
            ServiceDomain.service_id == service_id,
            ServiceDomain.container_port == container_port))

    def list_service_domain_by_port(self, session, service_id, container_port):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id == service_id,
            ServiceDomain.container_port == container_port))).scalars().all()

    def delete_service_domain_by_port(self, session, service_id, container_port):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.service_id == service_id,
            ServiceDomain.container_port == container_port))

    def get_domain_count_search_conditions(self, session, tenant_env_id, region_id, search_conditions, app_id):

        sql = """
        select count(sd.domain_name) 
        from service_domain sd 
            left join service_group_relation sgr on sd.service_id = sgr.service_id 
            left join service_group sg on sgr.group_id = sg.id  
        where sd.tenant_env_id=:tenant_env_id and sd.region_id=:region_id and  sgr.group_id=:group_id
            and (sd.domain_name like :search_conditions 
                or sd.service_alias like :search_conditions 
                or sg.group_name like :search_conditions)
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id,
                                   search_conditions="%" + search_conditions + "%")
        result = session.execute(sql).fetchall()
        return result

    def get_tenant_tuples_search_conditions(self, session, tenant_env_id, region_id, search_conditions, start, end, app_id):

        sql = """
        select sd.domain_name, sd.type, sd.is_senior, sd.certificate_id, sd.service_alias, 
                sd.protocol, sd.service_name, sd.container_port, sd.http_rule_id, sd.service_id, 
                sd.domain_path, sd.domain_cookie, sd.domain_heander, sd.the_weight, 
                sd.is_outer_service, sd.path_rewrite, sd.rewrites 
        from service_domain sd 
            left join service_group_relation sgr 
                on sd.service_id = sgr.service_id 
            left join service_group sg 
                on sgr.group_id = sg.id 
        where sd.tenant_env_id=:tenant_env_id 
            and sd.is_delete = 0 
            and sd.region_id=:region_id 
            and sgr.group_id=:group_id 
            and (sd.domain_name like :search_conditions 
                or sd.service_alias like :search_conditions 
                or sg.group_name like :search_conditions) 
        order by type desc LIMIT :start,:end
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id,
                                   search_conditions="%" + search_conditions + "%", start=start, end=end)
        result = session.execute(sql).fetchall()
        return result

    def get_tenant_tuples(self, session, tenant_env_id, region_id, app_id):

        sql = """
        select sd.domain_name, sd.type, sd.is_senior, sd.certificate_id, sd.service_alias, 
                    sd.protocol, sd.service_name, sd.container_port, sd.http_rule_id, sd.service_id, 
                    sd.domain_path, sd.domain_cookie, sd.domain_heander, sd.the_weight, 
                    sd.is_outer_service, sd.path_rewrite, sd.rewrites 
        from service_domain sd 
            left join service_group_relation sgr 
                on sd.service_id = sgr.service_id 
            left join service_group sg 
                on sgr.group_id = sg.id 
        where sd.tenant_env_id=:tenant_env_id 
            and sd.is_delete = 0 
            and sd.region_id=:region_id 
            and sgr.group_id=:group_id 
        order by type desc
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id)
        result = session.execute(sql).fetchall()
        return result

    def get_domain_count(self, session, tenant_env_id, region_id, app_id):

        sql = """
        select count(sd.domain_name) 
        from service_domain sd 
            left join service_group_relation sgr 
                on sd.service_id = sgr.service_id 
            left join service_group sg 
                on sgr.group_id = sg.id  
        where sd.tenant_env_id=:tenant_env_id 
            and sd.region_id=:region_id 
            and sgr.group_id=:group_id
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id)
        result = session.execute(sql).fetchall()
        return result

    def get_domain_by_name_and_path(self, session, domain_name, domain_path):
        if domain_path:
            return (session.execute(select(ServiceDomain).where(
                ServiceDomain.domain_name == domain_name,
                ServiceDomain.domain_path == domain_path))).scalars().all()
        else:
            return None

    def get_service_domain_by_http_rule_id(self, session, http_rule_id):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.http_rule_id == http_rule_id))).scalars().first()

    def get_domain_by_name_and_path_and_protocol(self, session, domain_name, domain_path, protocol):
        if domain_path:
            return (session.execute(select(ServiceDomain).where(
                ServiceDomain.domain_name == domain_name,
                ServiceDomain.domain_path == domain_path,
                ServiceDomain.protocol == protocol))).scalars().all()
        else:
            return None

    def delete_domain_by_rule_id(self, session, http_rule_id):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.http_rule_id == http_rule_id))


domain_repo = ServiceDomainRepository(ServiceDomain)
