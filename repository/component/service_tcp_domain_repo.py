from sqlalchemy import select, delete, and_, or_, func, text

from models.teams import ServiceTcpDomain
from repository.base import BaseRepository


class ServiceTcpDomainRepository(BaseRepository[ServiceTcpDomain]):

    def list_by_component_ids(self, session, component_ids):
        return session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id.in_(component_ids)
        )).scalars().all()

    def delete_service_tcp_domain(self, session, service_id):
        session.execute(delete(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == service_id))

    def get_service_tcpdomain(self, session, tenant_env_id, region_id, service_id, container_port):
        return (
            session.execute(select(ServiceTcpDomain).where(ServiceTcpDomain.tenant_env_id == tenant_env_id,
                                                           ServiceTcpDomain.region_id == region_id,
                                                           ServiceTcpDomain.service_id == service_id,
                                                           ServiceTcpDomain.container_port == container_port))
        ).scalars().first()

    def get_service_tcpdomains(self, session, service_id, is_delete=False):
        return session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == service_id,
            ServiceTcpDomain.is_delete == is_delete
        )).scalars().all()

    def get_service_tcpdomain_by_tcp_rule_id(self, session, tcp_rule_id):
        return (session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.tcp_rule_id == tcp_rule_id))).scalars().first()

    def delete_service_tcpdomain_by_tcp_rule_id(self, session, tcp_rule_id):
        session.execute(delete(ServiceTcpDomain).where(
            ServiceTcpDomain.tcp_rule_id == tcp_rule_id))

    def get_tcpdomain_by_end_point(self, session, region_id, end_point):
        try:
            hostport = end_point.split(":")
            if len(hostport) > 1:
                if hostport[0] == "0.0.0.0":
                    return (session.execute(select(ServiceTcpDomain).where(
                        ServiceTcpDomain.region_id == region_id,
                        ServiceTcpDomain.end_point.contains(":{}".format(hostport[1]))))).scalars().all()
                query_default_endpoint = "0.0.0.0:{0}".format(hostport[1])
                return (session.execute(select(ServiceTcpDomain).where(and_(
                    ServiceTcpDomain.region_id == region_id,
                    ServiceTcpDomain.end_point == end_point)), or_(
                    ServiceTcpDomain.region_id == region_id,
                    ServiceTcpDomain.end_point == query_default_endpoint
                ))).scalars().all()
            return None
        except:
            return None

    def add_service_tcpdomain(self, session, **domain_info):
        service_domain = ServiceTcpDomain(**domain_info)
        session.add(service_domain)
        return service_domain

    def count_by_service_ids(self, session, region_id, service_ids):
        return (session.execute(
            select(func.count(ServiceTcpDomain.ID)).where(ServiceTcpDomain.region_id == region_id,
                                                          ServiceTcpDomain.service_id.in_(service_ids))
        )).first()[0]

    def get_service_tcp_domains_by_service_id_and_port(self, session, service_id, container_port):
        return (session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == service_id,
            ServiceTcpDomain.container_port == container_port))).scalars().all()

    def create_service_tcp_domains(self, session, service_id, service_name, end_point, create_time, container_port,
                                   protocol,
                                   service_alias, tcp_rule_id, tenant_env_id, region_id):
        service_tcp_domain = ServiceTcpDomain(
            service_id=service_id,
            service_name=service_name,
            end_point=end_point,
            create_time=create_time,
            service_alias=service_alias,
            container_port=container_port,
            protocol=protocol,
            tcp_rule_id=tcp_rule_id,
            tenant_env_id=tenant_env_id,
            region_id=region_id)
        session.add(service_tcp_domain)
        session.flush()

    def delete_tcp_domain(self, session, tcp_rule_id):
        session.execute(delete(ServiceTcpDomain).where(
            ServiceTcpDomain.tcp_rule_id == tcp_rule_id))

    def delete_by_component_port(self, session, component_id, port):
        session.execute(delete(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == component_id,
            ServiceTcpDomain.container_port == port))

    def get_domain_count_search_conditions(self, session, tenant_env_id, region_id, search_conditions, app_id):

        sql = """
        select count(1) 
            from service_tcp_domain std 
        left join service_group_relation sgr 
            on std.service_id = sgr.service_id 
        left join service_group sg 
            on sgr.group_id = sg.id 
        where std.tenant_env_id=:tenant_env_id 
            and std.region_id=:region_id 
            and sgr.group_id=:group_id 
            and (std.end_point like :search_conditions 
                or std.service_alias like :search_conditions 
                or sg.group_name like :search_conditions)
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id,
                                   search_conditions="%" + search_conditions + "%")
        result = session.execute(sql).fetchall()
        return result

    def get_tenant_tuples_search_conditions(self, session, tenant_env_id, region_id, search_conditions, start, end, app_id):

        sql = """
        select  std.end_point, 
                std.type, 
                std.protocol, 
                std.service_name, 
                std.service_alias, 
                std.container_port, 
                std.tcp_rule_id, 
                std.service_id, 
                std.is_outer_service 
        from service_tcp_domain std 
        left join service_group_relation sgr 
            on std.service_id = sgr.service_id 
        left join service_group sg 
            on sgr.group_id = sg.id  
        where std.tenant_env_id=:tenant_env_id 
            and std.is_delete = 0 
            and std.region_id=:region_id 
            and sgr.group_id=:group_id 
            and (std.end_point like :search_conditions 
                or std.service_alias like :search_conditions 
                or sg.group_name like :search_conditions) 
        order by type desc limit :start,:end
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id,
                                   search_conditions=search_conditions, start=start, end=end)
        result = session.execute(sql).fetchall()
        return result

    def get_tenant_tuples(self, session, tenant_env_id, region_id, start, end, app_id):

        sql = """
        select  std.end_point, 
                std.type, 
                std.protocol, 
                std.service_name, 
                std.service_alias, 
                std.container_port, 
                std.tcp_rule_id, 
                std.service_id, 
                std.is_outer_service 
        from service_tcp_domain std 
        left join service_group_relation sgr 
            on std.service_id = sgr.service_id 
        left join service_group sg 
            on sgr.group_id = sg.id  
        where std.tenant_env_id=:tenant_env_id 
            and std.is_delete = 0 
            and std.region_id=:region_id 
            and sgr.group_id=:group_id 
        order by type desc limit :start,:end
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id, start=start, end=end)
        result = session.execute(sql).fetchall()
        return result

    def get_domain_count(self, session, tenant_env_id, region_id, app_id):

        sql = """
        select count(1) 
        from service_tcp_domain std 
        left join service_group_relation sgr 
            on std.service_id = sgr.service_id 
        left join service_group sg 
            on sgr.group_id = sg.id  
        where std.tenant_env_id=:tenant_env_id 
            and std.region_id=:region_id 
            and sgr.group_id=:group_id
        """
        sql = text(sql).bindparams(tenant_env_id=tenant_env_id, region_id=region_id, group_id=app_id)
        result = session.execute(sql).fetchall()
        return result


tcp_domain_repo = ServiceTcpDomainRepository(ServiceTcpDomain)
