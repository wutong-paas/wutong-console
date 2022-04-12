import datetime
import os

from sqlalchemy import select, and_, or_, delete, func, not_

from models.application.models import ApplicationConfigGroup, ConfigGroupService
from models.relate.models import TeamComponentRelation
from models.teams import ServiceDomain, ServiceDomainCertificate, ServiceTcpDomain, GatewayCustomConfiguration
from models.component.models import TeamComponentPort, ComponentExtendMethod, TeamComponentMountRelation, \
    TeamComponentVolume, TeamComponentConfigurationFile, TeamComponentAuth, TeamComponentEnv, \
    ThirdPartyComponentEndpoints, ComponentCreateStep, ComponentPaymentNotify, ComponentAttachInfo
from repository.application.config_group_repo import app_config_group_service_repo
from repository.base import BaseRepository


class TenantServicePortRepository(BaseRepository[TeamComponentPort]):

    def get_service_port_by_alias(self, session, service_id, alias):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.port_alias == alias)).scalars().first()

    def overwrite_by_component_ids(self, session, component_ids, ports):
        session.execute(delete(TeamComponentPort).where(
            TeamComponentPort.service_id.in_(component_ids)))
        session.add_all(ports)

    def list_by_k8s_service_names(self, session, tenant_id, k8s_service_names):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.k8s_service_name.in_(k8s_service_names))).scalars().all()

    def list_inner_ports_by_service_ids(self, session, tenant_id, service_ids):
        if not service_ids:
            return []
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id.in_(service_ids),
            TeamComponentPort.is_inner_service == 1)).scalars().all()

    def delete_service_port(self, session, tenant_id, service_id):
        session.execute(
            delete(TeamComponentPort).where(
                TeamComponentPort.service_id == service_id,
                TeamComponentPort.tenant_id == tenant_id)
        )

    def bulk_all(self, session, port_list):
        session.add_all(port_list)
        session.flush()

    def get_by_k8s_service_name(self, session, tenant_id, k8s_service_name):
        if not k8s_service_name:
            return
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.k8s_service_name == k8s_service_name))).scalars().all()

    def list_by_service_ids(self, session, tenant_id, service_ids):
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id.in_(service_ids)))).scalars().all()

    def get_service_port_by_port(self, session, tenant_id, service_id, container_port):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.container_port == container_port)).scalars().first()

    def get_service_ports(self, session, tenant_id, service_id):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id == service_id)).scalars().all()

    def get_service_ports_is_outer_service(self, session, tenant_id, service_id):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.is_outer_service == 1)).scalars().all()

    def get_service_ports_by_is_inner_service(self, session, tenant_id, service_id):
        return (
            session.execute(select(TeamComponentPort).where(TeamComponentPort.tenant_id == tenant_id,
                                                            TeamComponentPort.service_id == service_id,
                                                            TeamComponentPort.is_inner_service == 1))
        ).scalars().all()

    def add_service_port(self, session, **tenant_service_port):
        service_port = TeamComponentPort(**tenant_service_port)
        session.add(service_port)
        session.flush()
        return service_port

    def delete_serivce_port_by_port(self, session, tenant_id, service_id, container_port):
        session.execute(delete(TeamComponentPort).where(TeamComponentPort.tenant_id == tenant_id,
                                                        TeamComponentPort.service_id == service_id,
                                                        TeamComponentPort.container_port == container_port))


class ServiceDomainRepository(BaseRepository[ServiceDomain]):

    def add_certificate(self, session, tenant_id, alias, certificate_id, certificate, private_key, certificate_type):
        service_domain_certificate = dict()
        service_domain_certificate["tenant_id"] = tenant_id
        service_domain_certificate["certificate_id"] = certificate_id
        service_domain_certificate["certificate"] = certificate
        service_domain_certificate["private_key"] = private_key
        service_domain_certificate["alias"] = alias
        service_domain_certificate["certificate_type"] = certificate_type
        service_domain_certificate["create_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        certificate_info = ServiceDomainCertificate(**service_domain_certificate)
        session.add(certificate_info)
        return certificate_info

    def get_certificate_by_alias(self, session, tenant_id, alias):
        return session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.tenant_id == tenant_id,
            ServiceDomainCertificate.alias == alias)).scalars().first()

    def check_custom_rule(self, session, eid):
        """
        check if there is a custom gateway rule
        """
        team_name_query = "'%' || b.tenant_name || '%'"
        if os.environ.get('DB_TYPE') == 'mysql':
            team_name_query = "concat('%',b.tenant_name,'%')"
        sql = """
            SELECT
                *
            FROM
                service_domain a,
                tenant_info b
            WHERE
                a.tenant_id = b.tenant_id
                AND b.enterprise_id = "{eid}"
                AND (
                    a.certificate_id <> 0
                    OR ( a.domain_path <> "/" AND a.domain_path <> "" )
                    OR a.domain_cookie <> ""
                    OR a.domain_heander <> ""
                    OR a.the_weight <> 100
                    OR a.domain_name NOT LIKE {team_name}
                )
                LIMIT 1""".format(
            eid=eid, team_name=team_name_query)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False

    def delete_service_domain(self, session, service_id):
        session.execute(delete(ServiceDomain).where(
            ServiceDomain.service_id == service_id))

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id.in_(component_ids)))).scalars().all()

    def save_service_domain(self, session, service_domain):
        session.merge(service_domain)

    def get_service_domains(self, session, service_id):
        return (session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id == service_id))).scalars().all()

    def get_certificate_by_pk(self, session, pk):
        return (session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.ID == pk))).scalars().first()

    def get_tenant_certificate_page(self, session, tenant_id, start, end):
        """提供指定位置和数量的数据"""
        cert = (session.execute(select(ServiceDomainCertificate).where(
            ServiceDomainCertificate.tenant_id == tenant_id))).scalars().all()
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

        return service_domain

    def create_service_domains(self, session, service_id, service_name, domain_name, create_time, container_port,
                               protocol,
                               http_rule_id,
                               tenant_id, service_alias, region_id):
        service_domain = ServiceDomain(
            service_id=service_id,
            service_name=service_name,
            domain_name=domain_name,
            create_time=create_time,
            container_port=container_port,
            protocol=protocol,
            http_rule_id=http_rule_id,
            tenant_id=tenant_id,
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

    def get_domain_count_search_conditions(self, session, tenant_id, region_id, search_conditions, app_id):
        return (session.execute("select count(sd.domain_name) \
            from service_domain sd \
                left join service_group_relation sgr on sd.service_id = sgr.service_id \
                left join service_group sg on sgr.group_id = sg.id  \
            where sd.tenant_id='{0}' and sd.region_id='{1}' and  sgr.group_id='{3}'\
                and (sd.domain_name like '%{2}%' \
                    or sd.service_alias like '%{2}%' \
                    or sg.group_name like '%{2}%');".format(tenant_id, region_id, search_conditions,
                                                            app_id))).fetchall()

    def get_tenant_tuples_search_conditions(self, session, tenant_id, region_id, search_conditions, start, end, app_id):
        return (session.execute("select sd.domain_name, sd.type, sd.is_senior, sd.certificate_id, sd.service_alias, \
                sd.protocol, sd.service_name, sd.container_port, sd.http_rule_id, sd.service_id, \
                sd.domain_path, sd.domain_cookie, sd.domain_heander, sd.the_weight, \
                sd.is_outer_service \
            from service_domain sd \
                left join service_group_relation sgr on sd.service_id = sgr.service_id \
                left join service_group sg on sgr.group_id = sg.id \
            where sd.tenant_id='{0}' \
                and sd.region_id='{1}' \
                and sgr.group_id='{5}' \
                and (sd.domain_name like '%{2}%' \
                    or sd.service_alias like '%{2}%' \
                    or sg.group_name like '%{2}%') \
            order by type desc LIMIT {3},{4};".format(tenant_id, region_id, search_conditions, start,
                                                      end,
                                                      app_id))).fetchall()

    def get_tenant_tuples(self, session, tenant_id, region_id, app_id):
        return (session.execute("select sd.domain_name, sd.type, sd.is_senior, sd.certificate_id, sd.service_alias, \
                    sd.protocol, sd.service_name, sd.container_port, sd.http_rule_id, sd.service_id, \
                    sd.domain_path, sd.domain_cookie, sd.domain_heander, sd.the_weight, \
                    sd.is_outer_service \
                from service_domain sd \
                    left join service_group_relation sgr on sd.service_id = sgr.service_id \
                    left join service_group sg on sgr.group_id = sg.id \
                where sd.tenant_id='{0}' \
                    and sd.region_id='{1}' \
                    and sgr.group_id='{2}' \
                order by type desc;".format(tenant_id, region_id, app_id))).fetchall()

    def get_domain_count(self, session, tenant_id, region_id, app_id):
        return (session.execute("select count(sd.domain_name) \
                                    from service_domain sd \
                                        left join service_group_relation sgr on sd.service_id = sgr.service_id \
                                        left join service_group sg on sgr.group_id = sg.id  \
                                    where sd.tenant_id='{0}' and \
                                    sd.region_id='{1}' and \
                                    sgr.group_id='{2}';".format(tenant_id, region_id, app_id))).fetchall()

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


class ServiceTcpDomainRepository(BaseRepository[ServiceTcpDomain]):

    def list_by_component_ids(self, session, component_ids):
        return session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id.in_(component_ids)
        )).scalars().all()

    def delete_service_tcp_domain(self, session, service_id):
        session.execute(delete(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == service_id))

    def get_service_tcpdomain(self, session, tenant_id, region_id, service_id, container_port):
        return (
            session.execute(select(ServiceTcpDomain).where(ServiceTcpDomain.tenant_id == tenant_id,
                                                           ServiceTcpDomain.region_id == region_id,
                                                           ServiceTcpDomain.service_id == service_id,
                                                           ServiceTcpDomain.container_port == container_port))
        ).scalars().first()

    def get_service_tcpdomains(self, session, service_id):
        return session.execute(select(ServiceTcpDomain).where(
            ServiceTcpDomain.service_id == service_id)).scalars().all()

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
                                   service_alias, tcp_rule_id, tenant_id, region_id):
        service_tcp_domain = ServiceTcpDomain(
            service_id=service_id,
            service_name=service_name,
            end_point=end_point,
            create_time=create_time,
            service_alias=service_alias,
            container_port=container_port,
            protocol=protocol,
            tcp_rule_id=tcp_rule_id,
            tenant_id=tenant_id,
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

    def get_domain_count_search_conditions(self, session, tenant_id, region_id, search_conditions, app_id):
        return (session.execute("select count(1) from service_tcp_domain std \
                     left join service_group_relation sgr on std.service_id = sgr.service_id \
                     left join service_group sg on sgr.group_id = sg.id  \
                 where std.tenant_id='{0}' and std.region_id='{1}' and sgr.group_id='{3}' \
                     and (std.end_point like '%{2}%' \
                         or std.service_alias like '%{2}%' \
                         or sg.group_name like '%{2}%');".format(tenant_id, region_id, search_conditions,
                                                                 app_id))).fetchall()

    def get_tenant_tuples_search_conditions(self, session, tenant_id, region_id, search_conditions, start, end, app_id):
        return (session.execute("select std.end_point, std.type, std.protocol, std.service_name, std.service_alias, \
                     std.container_port, std.tcp_rule_id, std.service_id, std.is_outer_service \
                 from service_tcp_domain std \
                     left join service_group_relation sgr on std.service_id = sgr.service_id \
                     left join service_group sg on sgr.group_id = sg.id  \
                 where std.tenant_id='{0}' and std.region_id='{1}' and sgr.group_id='{5}' \
                     and (std.end_point like '%{2}%' \
                         or std.service_alias like '%{2}%' \
                         or sg.group_name like '%{2}%') \
                 order by type desc LIMIT {3},{4};".format(tenant_id, region_id, search_conditions, start,
                                                           end,
                                                           app_id))).fetchall()

    def get_tenant_tuples(self, session, tenant_id, region_id, start, end, app_id):
        return (session.execute("select std.end_point, std.type, std.protocol, std.service_name, std.service_alias, \
                     std.container_port, std.tcp_rule_id, std.service_id, std.is_outer_service \
                 from service_tcp_domain std \
                     left join service_group_relation sgr on std.service_id = sgr.service_id \
                     left join service_group sg on sgr.group_id = sg.id  \
                 where std.tenant_id='{0}' and std.region_id='{1}' and sgr.group_id='{4}' \
                 order by type desc LIMIT {2},{3};".format(tenant_id, region_id, start, end, app_id))).fetchall()

    def get_domain_count(self, session, tenant_id, region_id, app_id):
        return (session.execute("select count(1) from service_tcp_domain std \
                     left join service_group_relation sgr on std.service_id = sgr.service_id \
                     left join service_group sg on sgr.group_id = sg.id  \
                 where std.tenant_id='{0}' and std.region_id='{1}' and sgr.group_id='{2}';".format(
            tenant_id, region_id, app_id))).fetchall()


class ApplicationConfigGroupRepository(BaseRepository[ConfigGroupService]):
    @staticmethod
    def bulk_create_or_update(session, config_groups):
        config_group_ids = [cg.config_group_id for cg in config_groups]
        session.execute(delete(ApplicationConfigGroup).where(
            ApplicationConfigGroup.config_group_id.in_(config_group_ids)
        ))
        session.add_all(config_groups)

    def list_by_service_ids(self, session, region_name, service_ids):
        config_groups = session.execute(
            select(ConfigGroupService).where(ConfigGroupService.service_id.in_(service_ids))
        ).scalars().all()
        config_group_ids = [config_group.config_group_id for config_group in config_groups]

        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.config_group_id.in_(config_group_ids),
                                                 ApplicationConfigGroup.region_name == region_name)
        ).scalars().all()

    def count_by_region_and_app_id(self, session, region_name, app_id):
        # return ApplicationConfigGroup.objects.filter(region_name=region_name, app_id=app_id).count()
        return (session.execute(
            select(func.count(ApplicationConfigGroup.ID)).where(ApplicationConfigGroup.region_name == region_name,
                                                                ApplicationConfigGroup.app_id == app_id)
        )).first()[0]

    def get_config_group_in_use(self, session, region_name, app_id):
        cgroups = session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id,
                                                 ApplicationConfigGroup.enable == 1)
        ).scalars().all()
        cgroup_infos = []
        if cgroups:
            for cgroup in cgroups:
                cgroup_services = app_config_group_service_repo.list(session=session,
                                                                     config_group_id=cgroup.config_group_id)
                if cgroup_services:
                    cgroup_info = {"config_group_id": cgroup.config_group_id,
                                   "config_group_name": cgroup.config_group_name}
                    cgroup_infos.append(cgroup_info)
        return cgroup_infos

    def get(self, session, region_name, app_id, config_group_name):
        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id,
                                                 ApplicationConfigGroup.config_group_name == config_group_name)
        ).scalars().all()

    def list(self, session, region_name, app_id):
        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id).order_by(
                ApplicationConfigGroup.create_time.desc())
        ).scalars().all()

    def create(self, session, **group_req):
        acg = ApplicationConfigGroup(**group_req)
        session.add(acg)
        session.flush()
        return acg

    def delete_by_region_name(self, session, region_name, app_id, config_group_name):
        session.execute(
            delete(ApplicationConfigGroup).where(
                ApplicationConfigGroup.region_name == region_name,
                ApplicationConfigGroup.app_id == app_id,
                ApplicationConfigGroup.config_group_name == config_group_name)
        )

    def update(self, session, **group_req):
        acg = session.execute(
            select(ApplicationConfigGroup).where(
                ApplicationConfigGroup.region_name == group_req["region_name"],
                ApplicationConfigGroup.app_id == group_req["app_id"],
                ApplicationConfigGroup.config_group_name == group_req["config_group_name"])
        ).scalars().first()
        acg.enable = group_req["enable"]
        acg.update_time = group_req["update_time"]


class TenantServiceEndpoints(BaseRepository[ThirdPartyComponentEndpoints]):

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id.in_(component_ids)))).scalars().all()

    def get_service_endpoints_by_service_id(self, session, service_id):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id == service_id))).scalars().first()

    def get_all_service_endpoints_by_service_id(self, session, service_id):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id == service_id))).scalars().all()

    def get_service_ports(self, session, tenant_id, service_id):
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_id == tenant_id,
            TeamComponentPort.service_id == service_id))).scalars().all()


class ServiceExtendRepository(BaseRepository[ComponentExtendMethod]):

    def get_extend_method_by_service(self, session, service):
        if service.service_source == "market":
            return (session.execute(select(ComponentExtendMethod).where(
                ComponentExtendMethod.service_key == service.service_key,
                ComponentExtendMethod.app_version == service.version))).scalars().first()
        return None


class TenantServiceMntRelationRepository(BaseRepository[TeamComponentMountRelation]):

    def overwrite_by_component_id(self, session, component_ids, volume_deps):
        volume_deps = [dep for dep in volume_deps if dep.service_id in component_ids]
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id.in_(component_ids)
        ))
        session.add_all(volume_deps)

    def list_mnt_relations_by_service_ids(self, session, tenant_id, service_ids):
        return session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_id == tenant_id,
            TeamComponentMountRelation.service_id.in_(service_ids)
        )).scalars().all()

    def delete_mnt_relation(self, session, service_id, dep_service_id, mnt_name):
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id == service_id,
            TeamComponentMountRelation.dep_service_id == dep_service_id,
            TeamComponentMountRelation.mnt_name == mnt_name))

    def delete_mnt(self, session, service_id):
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id == service_id))

    def get_service_mnts_filter_volume_type(self, session, tenant_id, service_id, volume_types=None):
        query = "mnt.tenant_id = '%s' and mnt.service_id = '%s'" % (tenant_id, service_id)
        # if volume_types:
        #     vol_type_sql = " and volume.volume_type in ({})".format(','.join(["'%s'"] * len(volume_types)))
        #     query += vol_type_sql % tuple(volume_types)

        sql = """
        select mnt.mnt_name,
            mnt.mnt_dir,
            mnt.dep_service_id,
            mnt.service_id,
            mnt.tenant_id,
            volume.volume_type,
            volume.ID as volume_id
        from tenant_service_mnt_relation as mnt
                 inner join tenant_service_volume as volume
                            on mnt.dep_service_id = volume.service_id and mnt.mnt_name = volume.volume_name
        where {};
        """.format(query)
        result = session.execute(sql).fetchall()
        dep_mnts = []
        for real_dep_mnt in result:
            mnt = TeamComponentMountRelation(
                tenant_id=real_dep_mnt.tenant_id,
                service_id=real_dep_mnt.service_id,
                dep_service_id=real_dep_mnt.dep_service_id,
                mnt_name=real_dep_mnt.mnt_name,
                mnt_dir=real_dep_mnt.mnt_dir)
            mnt.volume_type = real_dep_mnt.volume_type
            mnt.volume_id = real_dep_mnt.volume_id
            dep_mnts.append(mnt)
        return dep_mnts

    def get_by_dep_service_id(self, session, tenant_id, dep_service_id):
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_id == tenant_id,
            TeamComponentMountRelation.dep_service_id == dep_service_id))).scalars().all()

    def get_mount_current_service(self, session, tenant_id, service_id):
        """查询挂载当前组件的信息"""
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_id == tenant_id,
            TeamComponentMountRelation.dep_service_id == service_id))).scalars().all()

    def get_mnt_by_dep_id_and_mntname(self, session, dep_service_id, mnt_name):
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.dep_service_id == dep_service_id,
            TeamComponentMountRelation.mnt_name == mnt_name))).scalars().first()

    def get_service_mnts(self, session, tenant_id, service_id):
        return self.get_service_mnts_filter_volume_type(session=session, tenant_id=tenant_id, service_id=service_id)

    def add_service_mnt_relation(self, session, tenant_id, service_id, dep_service_id, mnt_name, mnt_dir):
        tsr = TeamComponentMountRelation(
            tenant_id=tenant_id,
            service_id=service_id,
            dep_service_id=dep_service_id,
            mnt_name=mnt_name,
            mnt_dir=mnt_dir  # this dir is source app's volume path
        )
        session.add(tsr)
        session.commit()
        return tsr


class TenantServiceVolumnRepository(BaseRepository[TeamComponentVolume]):

    def overwrite_by_component_ids(self, session, component_ids, volumes):
        session.execute(delete(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(component_ids)
        ))
        session.add_all(volumes)

    def delete_service_volumes(self, session, service_id):
        session.execute(
            delete(TeamComponentVolume).where(TeamComponentVolume.service_id == service_id)
        )

    def get_service_volume_by_name(self, session, service_id, volume_name):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_name == volume_name)).scalars().first()

    def get_service_volumes_about_config_file(self, session, service_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_type == "config-file")).scalars().all()

    def get_service_volume_by_pk(self, session, volume_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.ID == volume_id)).scalars().first()

    def get_service_config_file(self, session, volume: TeamComponentVolume):
        return session.execute(select(TeamComponentConfigurationFile).where(
            or_(and_(TeamComponentConfigurationFile.service_id == volume.service_id,
                     TeamComponentConfigurationFile.volume_id == volume.ID),
                TeamComponentConfigurationFile.volume_name == volume.volume_name))).scalars().first()

    def get_service_volumes(self, session, service_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            not_(TeamComponentVolume.volume_type == "config-file"))).scalars().all()

    def get_service_volume_by_path(self, session, service_id, volume_path):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_path == volume_path)).scalars().first()

    def save_service_volume(self, session, service_volume):
        session.add(service_volume)
        session.flush()

    def delete_volume_by_id(self, session, volume_id):
        session.execute(delete(TeamComponentVolume).where(
            TeamComponentVolume.ID == volume_id))

    def delete_file_by_volume(self, session, volume: TeamComponentVolume):
        session.execute(delete(TeamComponentConfigurationFile).where(
            or_(and_(TeamComponentConfigurationFile.service_id == volume.service_id,
                     TeamComponentConfigurationFile.volume_id == volume.ID),
                TeamComponentConfigurationFile.volume_name == volume.volume_name)))

    def get_services_volumes_by_config(self, session, service_ids, CONFIG, mounted_ids):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            TeamComponentVolume.volume_type == CONFIG,
            not_(TeamComponentVolume.ID.in_(mounted_ids)))).scalars().all()

    def get_services_volumes_by_share(self, session, service_ids, SHARE, mounted_ids, state_service_ids):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            TeamComponentVolume.volume_type == SHARE,
            not_(TeamComponentVolume.ID.in_(mounted_ids)),
            not_(TeamComponentVolume.service_id.in_(state_service_ids)))).scalars().all()

    def add_service_config_file(self, session, **service_config_file):
        tscf = TeamComponentConfigurationFile(**service_config_file)
        session.add(tscf)
        session.flush()
        return tscf

    def get_service_volumes_with_config_file(self, session, service_id):
        return (session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id))).scalars().all()

    def list_custom_volumes(self, session, service_ids):
        return (session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            not_(TeamComponentVolume.volume_type.in_(
                ["config-file", TeamComponentVolume.SHARE, TeamComponentVolume.LOCAL,
                 TeamComponentVolume.TMPFS]))))).scalars().all()

    def get_service_config_files(self, session, service_id):
        return (session.execute(select(TeamComponentConfigurationFile).where(
            TeamComponentConfigurationFile.service_id == service_id))).scalars().all()


class TenantServiceRelationRepository(BaseRepository[TeamComponentRelation]):

    @staticmethod
    def list_by_component_ids(session, tenant_id, component_ids):
        return session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == tenant_id,
            TeamComponentRelation.service_id.in_(component_ids)
        )).scalars().all()

    def overwrite_by_component_id(self, session, component_ids, component_deps):
        with session.no_autoflush:
            component_deps = [dep for dep in component_deps if dep.service_id in component_ids]
            session.execute(delete(TeamComponentRelation).where(
                TeamComponentRelation.service_id.in_(component_ids)
            ))
            session.add_all(component_deps)

    def check_db_dep_by_eid(self, session, eid):
        """
        check if there is a database installed from the market that is dependent on
        """
        sql = """
            SELECT
                a.service_id, a.dep_service_id
            FROM
                tenant_service_relation a,
                tenant_service b,
                tenant_info c,
                tenant_service d
            WHERE
                b.tenant_id = c.tenant_id
                AND c.enterprise_id = "{eid}"
                AND a.service_id = d.service_id
                AND a.dep_service_id = b.service_id
                AND ( b.image LIKE "%mysql%" OR b.image LIKE "%postgres%" OR b.image LIKE "%mariadb%" )
                AND (b.service_source <> "market" OR d.service_source <> "market")
                limit 1""".format(eid=eid)
        result = session.execute(sql).fetchall()
        if len(result) > 0:
            return True
        sql2 = """
            SELECT
                a.dep_service_id
            FROM
                tenant_service_relation a,
                tenant_service b,
                tenant_info c,
                tenant_service d,
                service_source e,
                service_source f
            WHERE
                b.tenant_id = c.tenant_id
                AND c.enterprise_id = "{eid}"
                AND a.service_id = d.service_id
                AND a.dep_service_id = b.service_id
                AND ( b.image LIKE "%mysql%" OR b.image LIKE "%postgres%" OR b.image LIKE "%mariadb%" )
                AND ( b.service_source = "market" AND d.service_source = "market" )
                AND e.service_id = b.service_id
                AND f.service_id = d.service_id
                AND e.group_key <> f.group_key
                LIMIT 1""".format(eid=eid)
        result2 = session.execute(sql2).fetchall()
        return True if len(result2) > 0 else False

    def delete_service_relation(self, session, tenant_id, service_id):
        session.execute(delete(TeamComponentRelation).where(
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.tenant_id == tenant_id))

    def get_service_dependencies(self, session, tenant_id, service_id):
        return session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == tenant_id,
            TeamComponentRelation.service_id == service_id)).scalars().all()

    def get_dependency_by_dep_id(self, session, tenant_id, dep_service_id):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == tenant_id,
            TeamComponentRelation.dep_service_id == dep_service_id))).scalars().all()

    def get_dependency_by_dep_service_ids(self, session, tenant_id, service_id, dep_service_ids):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == tenant_id,
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.dep_service_id.in_(dep_service_ids)))).scalars().all()

    def get_depency_by_serivce_id_and_dep_service_id(self, session, tenant_id, service_id, dep_service_id):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == tenant_id,
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.dep_service_id == dep_service_id))).scalars().first()

    def add_service_dependency(self, session, **tenant_service_relation):
        tsr = TeamComponentRelation(**tenant_service_relation)
        session.add(tsr)

    def delete(self, session, dependency):
        session.delete(dependency)


class GatewayCustom(BaseRepository[GatewayCustomConfiguration]):

    def delete_by_rule_ids(self, session, rule_ids):
        session.execute(delete(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id.in_(rule_ids)))

    def list_by_rule_ids(self, session, rule_ids):
        return (session.execute(select(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id.in_(rule_ids)))).scalars().all()

    def get_configuration_by_rule_id(self, session, rule_id):
        return (session.execute(select(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id == rule_id))).scalars().first()

    def add_configuration(self, session, **configuration_info):
        gcc = GatewayCustomConfiguration(**configuration_info)
        session.add(gcc)
        return gcc

    def save(self, session, gcc):
        session.merge(gcc)


class ServiceAuthRepository(BaseRepository[TeamComponentAuth]):

    def delete_service_auth(self, session, service_id):
        session.execute(delete(TeamComponentAuth).where(
            TeamComponentAuth.service_id == service_id))

    def get_service_auth(self, session, service_id):
        return (session.execute(select(TeamComponentAuth).where(
            TeamComponentAuth.service_id == service_id))).scalars().all()


class CompileEnvRepository(BaseRepository[TeamComponentEnv]):

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(TeamComponentEnv).where(
            TeamComponentEnv.service_id.in_(component_ids)))).scalars().all()

    def delete_service_compile_env(self, session, service_id):
        session.execute(delete(TeamComponentEnv).where(
            TeamComponentEnv.service_id == service_id))

    def save_service_compile_env(self, session, **params):
        tse = TeamComponentEnv(**params)
        session.add(tse)

    def save(self, session, new_compile_env):
        session.merge(new_compile_env)

    def get_service_compile_env(self, session, service_id):
        return (session.execute(select(TeamComponentEnv).where(
            TeamComponentEnv.service_id == service_id))).scalars().first()

    def update_service_compile_env(self, session, service_id, **update_params):
        tse = TeamComponentEnv(**update_params)
        session.merge(tse)


class ServiceAttachInfoRepository(BaseRepository[ComponentAttachInfo]):

    def delete_service_attach(self, session, service_id):
        session.execute(
            delete(ComponentAttachInfo).where(ComponentAttachInfo.service_id == service_id)
        )


class ServiceStepRepository(BaseRepository[ComponentCreateStep]):

    def delete_create_step(self, session, service_id):
        session.execute(
            delete(ComponentCreateStep).where(ComponentCreateStep.service_id == service_id)
        )


class ServicePaymentRepository(BaseRepository[ComponentPaymentNotify]):

    def delete_service_payment(self, session, service_id):
        session.execute(
            delete(ComponentPaymentNotify).where(ComponentPaymentNotify.service_id == service_id)
        )


app_config_group_repo = ApplicationConfigGroupRepository(ConfigGroupService)
port_repo = TenantServicePortRepository(TeamComponentPort)
domain_repo = ServiceDomainRepository(ServiceDomain)
tcp_domain = ServiceTcpDomainRepository(ServiceTcpDomain)
service_endpoints_repo = TenantServiceEndpoints(ThirdPartyComponentEndpoints)
extend_repo = ServiceExtendRepository(ComponentExtendMethod)
mnt_repo = TenantServiceMntRelationRepository(TeamComponentMountRelation)
volume_repo = TenantServiceVolumnRepository(TeamComponentVolume)
dep_relation_repo = TenantServiceRelationRepository(TeamComponentRelation)
configuration_repo = GatewayCustom(GatewayCustomConfiguration)
auth_repo = ServiceAuthRepository(TeamComponentAuth)
compile_env_repo = CompileEnvRepository(TeamComponentEnv)
service_attach_repo = ServiceAttachInfoRepository(ComponentAttachInfo)
create_step_repo = ServiceStepRepository(ComponentCreateStep)
service_payment_repo = ServicePaymentRepository(ComponentPaymentNotify)
