from functools import reduce

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from clients.remote_component_client import remote_component_client
from database.session import SessionClass
from models.application.models import ComponentApplicationRelation
from models.teams import ServiceDomain
from models.component.models import TeamComponentInfo, TeamComponentPort
from models.relate.models import TeamComponentRelation
from service.region_service import region_services


class TopologicalService(object):

    def get_group_topological_graph_details(self, session, team, team_id, team_name, service, region_name):
        result = dict()
        # 组件信息
        result['tenant_id'] = team_id
        result['service_alias'] = service.service_alias
        result['service_cname'] = service.service_cname
        result['service_region'] = service.service_region
        result['deploy_version'] = service.deploy_version
        result['total_memory'] = service.min_memory * service.min_node
        result['cur_status'] = 'Unknown'
        # 组件端口信息
        port_list = session.execute(select(TeamComponentPort).where(
            TeamComponentPort.service_id == service.service_id
        )).scalars().all()
        # 域名信息
        service_domain_list = session.execute(select(ServiceDomain).where(
            ServiceDomain.service_id == service.service_id
        )).scalars().all()
        port_map = {}
        # 判断是否存在自定义域名
        for port in port_list:
            port_info = jsonable_encoder(port)
            exist_service_domain = False
            # 打开对外端口
            if port.is_outer_service:
                if port.protocol != 'http' and port.protocol != "https":
                    cur_region = service.service_region.replace("-1", "")
                    domain = "{0}.{1}.{2}-s1.goodrain.net".format(service.service_alias, team_name, cur_region)
                    tcpdomain = region_services.get_region_tcpdomain(session, service.service_region)
                    if tcpdomain:
                        domain = tcpdomain
                    outer_service = {"domain": domain}
                    if port.lb_mapping_port != 0:
                        outer_service['port'] = port.lb_mapping_port
                    else:
                        outer_service['port'] = port.mapping_port

                elif port.protocol == 'http' or port.protocol == 'https':
                    exist_service_domain = True
                    httpdomain = region_services.get_region_httpdomain(session, service.service_region)
                    outer_service = {"domain": "{0}.{1}.{2}".format(service.service_alias, team_name, httpdomain), "port": ""}
                # 外部url
                if outer_service['port'] == '-1':
                    port_info['outer_url'] = 'query error!'
                else:
                    port_info['outer_url'] = ''
            # 自定义域名
            if exist_service_domain:
                if len(service_domain_list) > 0:
                    for domain in service_domain_list:
                        if port.container_port == domain.container_port:
                            domain_path = domain.domain_path if domain.domain_path else '/'
                            if port_info.get('domain_list') is None:
                                if domain.protocol == "https":
                                    port_info['domain_list'] = ["https://" + domain.domain_name + domain_path]
                                else:
                                    port_info['domain_list'] = ["http://" + domain.domain_name + domain_path]
                            else:
                                if domain.protocol == "https":
                                    port_info['domain_list'].append("https://" + domain.domain_name + domain_path)
                                else:
                                    port_info['domain_list'].append("http://" + domain.domain_name + domain_path)
            port_map[port.container_port] = port_info
        result["port_list"] = port_map
        # pod节点信息
        region_data = dict()
        try:
            status_data = remote_component_client.check_service_status(
                session=session,
                region=region_name,
                tenant_name=team_name,
                service_alias=service.service_alias,
                enterprise_id=team.enterprise_id)
            region_data = status_data["bean"]

            pod_list = remote_component_client.get_service_pods(
                session=session,
                region=region_name,
                tenant_name=team_name,
                service_alias=service.service_alias,
                enterprise_id=team.enterprise_id)
            region_data["pod_list"] = pod_list["list"]
        except remote_component_client.CallApiError as e:
            if e.message["httpcode"] == 404:
                region_data = {"status_cn": "创建中", "cur_status": "creating"}
            elif service.create_status != "complete":
                region_data = {"status_cn": "创建中", "cur_status": "creating"}

        result = dict(result, **region_data)

        # 依赖组件信息
        relation_list = session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_id == team_id,
            TeamComponentRelation.service_id == service.service_id
        )).scalars().all()
        relation_id_list = set([x.dep_service_id for x in relation_list])
        relation_service_list = session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(relation_id_list)
        )).scalars().all()
        relation_service_map = {x.service_id: x for x in relation_service_list}
        relation_port_list = session.execute(select(TeamComponentPort).where(
            TeamComponentPort.service_id.in_(relation_id_list)
        )).scalars().all()
        relation_map = {}

        for relation_port in relation_port_list:
            tmp_service_id = relation_port.service_id
            if tmp_service_id in list(relation_service_map.keys()):
                tmp_service = relation_service_map.get(tmp_service_id)
                relation_info = relation_map.get(tmp_service_id)
                if relation_info is None:
                    relation_info = []
                # 处理依赖组件端口
                if relation_port.is_inner_service:
                    relation_info.append({
                        "service_cname": tmp_service.service_cname,
                        "service_alias": tmp_service.service_alias,
                        "mapping_port": relation_port.mapping_port,
                    })
                    relation_map[tmp_service_id] = relation_info
        result["relation_list"] = relation_map
        result["status"] = 200
        if service.service_source == "third_party":
            result["cur_status"] = "third_party"
        return result

    def get_internet_topological_graph(self, session, group_id, team_name):
        result = dict()
        service_groups = session.execute(select(ComponentApplicationRelation).where(
            ComponentApplicationRelation.group_id == group_id
        )).scalars().all()
        service_id_list = [service.service_id for service in service_groups]
        service_list = session.execute(select(TeamComponentInfo).where(
            TeamComponentInfo.service_id.in_(service_id_list)
        )).scalars().all()
        outer_http_service_list = []
        for service in service_list:
            port_list = session.execute(select(TeamComponentPort).where(
                TeamComponentPort.service_id == service.service_id
            )).scalars().all()
            # 判断组件是否有对外端口
            outer_http_service = False
            if len(port_list) > 0:
                outer_http_service = reduce(lambda x, y: x or y,
                                            [t.is_outer_service and t.protocol == 'http' for t in list(port_list)])
            if outer_http_service:
                outer_http_service_list.append(service)
        # 每个对外可访问的组件
        result_list = []
        for service_info in outer_http_service_list:
            service_domain_result = {}
            service_region = service_info.service_region
            port_list = session.execute(select(TeamComponentPort).where(
                TeamComponentPort.service_id == service_info.service_id
            )).scalars().all()
            service_domain_list = session.execute(select(ServiceDomain).where(
                ServiceDomain.service_id == service_info.service_id
            )).scalars().all()
            port_map = {}
            for port in port_list:
                port_info = jsonable_encoder(port)
                exist_service_domain = False
                # 打开对外端口
                if port.is_outer_service:
                    if port.protocol != 'http' and port.protocol != "https":
                        cur_region = service_region.replace("-1", "")
                        domain = "{0}.{1}.{2}-s1.goodrain.net".format(service_info.service_alias, team_name, cur_region)
                        tcpdomain = region_services.get_region_tcpdomain(session, service_region)
                        if tcpdomain:
                            domain = tcpdomain
                        outer_service = {"domain": domain}
                        try:
                            outer_service['port'] = port.mapping_port
                        except Exception as e:
                            logger.exception(e)
                            outer_service['port'] = '-1'
                    elif port.protocol == 'http' or port.protocol != "https":
                        exist_service_domain = True
                        httpdomain = region_services.get_region_httpdomain(session, service_region)
                        outer_service = {
                            "domain": "{0}.{1}.{2}".format(service_info.service_alias, team_name, httpdomain),
                            "port": ""
                        }
                    else:
                        outer_service = {"domain": 'error', "port": '-1'}
                    # 外部url
                    if outer_service['port'] == '-1':
                        port_info['outer_url'] = 'query error!'
                    else:
                        if port.protocol == "http" or port.protocol == "https":
                            port_info['outer_url'] = '{0}.{1}:{2}'.format(port.container_port, outer_service['domain'],
                                                                          outer_service['port'])
                        else:
                            port_info['outer_url'] = '{0}:{1}'.format(outer_service['domain'], outer_service['port'])
                # 自定义域名
                if exist_service_domain:
                    if len(service_domain_list) > 0:
                        for domain in service_domain_list:
                            if port.container_port == domain.container_port:

                                if port_info.get('domain_list') is None:
                                    if domain.protocol == "https":
                                        port_info['domain_list'] = ["https://" + domain.domain_name]
                                    else:
                                        port_info['domain_list'] = ["http://" + domain.domain_name]
                                else:
                                    if domain.protocol == "https":
                                        port_info['domain_list'].append("https://" + domain.domain_name)
                                    else:
                                        port_info['domain_list'].append("http://" + domain.domain_name)

                port_map[port.container_port] = port_info
            service_domain_result["service_alias"] = service_info.service_alias
            service_domain_result["service_cname"] = service_info.service_cname
            service_domain_result["port_map"] = port_map
            result_list.append(service_domain_result)
        result["result_list"] = result_list
        return result

    def get_group_topological_graph(self, session: SessionClass, group_id, region, team_name, enterprise_id):
        topological_info = dict()
        service_group_relation_list = (
            session.execute(select(ComponentApplicationRelation).where(ComponentApplicationRelation.group_id == group_id))
        ).scalars().all()

        service_id_list = [x.service_id for x in service_group_relation_list]
        # 查询组件依赖信息
        service_relation_list = (
            session.execute(
                select(TeamComponentRelation).where(TeamComponentRelation.service_id.in_(service_id_list)))
        ).scalars().all()

        dep_service_id_list = [x.dep_service_id for x in service_relation_list]

        # 查询组件、依赖组件信息
        all_service_id_list = list(set(dep_service_id_list).union(set(service_id_list)))
        service_list = (
            session.execute(
                select(TeamComponentInfo).where(TeamComponentInfo.service_id.in_(all_service_id_list)))
        ).scalars().all()

        service_map = {x.service_id: x for x in service_list}
        json_data = {}
        json_svg = {}
        service_status_map = {}

        # 批量查询组件状态
        if len(service_list) > 0:
            try:
                service_status_list = remote_component_client.service_status(session, region, team_name, {
                    "service_ids": all_service_id_list,
                    "enterprise_id": enterprise_id
                })
                service_status_list = service_status_list["list"]
                if service_status_list:
                    service_status_map = {status_map["service_id"]: status_map for status_map in service_status_list}
            except Exception as e:
                logger.error('batch query service status failed!')
                logger.exception(e)

        # 拼接组件状态
        try:
            dynamic_services_info = remote_component_client.get_dynamic_services_pods(session, region, team_name,
                                                                                      [service.service_id for
                                                                                       service in
                                                                                       service_list])
            dynamic_services_list = dynamic_services_info["list"]
        except Exception as e:
            logger.exception(e)
            dynamic_services_list = []

        for service_info in service_list:
            node_num = 0
            if dynamic_services_list:
                for dynamic_service in dynamic_services_list:
                    if dynamic_service["service_id"] == service_info.service_id:
                        node_num += 1
            else:
                node_num = service_info.min_node
            json_data[service_info.service_id] = {
                "service_id": service_info.service_id,
                "service_cname": service_info.service_cname,
                "service_alias": service_info.service_alias,
                "service_source": service_info.service_source,
                "node_num": node_num,
            }
            json_svg[service_info.service_id] = []
            if service_status_map.get(service_info.service_id):
                status = service_status_map.get(service_info.service_id).get("status", "Unknown")
                status_cn = service_status_map.get(service_info.service_id).get("status_cn", None)
            else:
                status = None
                status_cn = None
            if status:
                if not status_cn:
                    from core.utils.status_translate import status_map
                    status_info_map = status_map().get(status, None)
                    if not status_info_map:
                        status_cn = "未知"
                    else:
                        status_cn = status_info_map["status_cn"]
                json_data[service_info.service_id]['cur_status'] = status
                json_data[service_info.service_id]['status_cn'] = status_cn
            else:
                if service_info.create_status != "complete":
                    json_data[service_info.service_id]['cur_status'] = 'creating'
                    json_data[service_info.service_id]['status_cn'] = '创建中'
                else:
                    json_data[service_info.service_id]['cur_status'] = 'Unknown'
                    json_data[service_info.service_id]['status_cn'] = '未知'

            if json_data[service_info.service_id]["service_source"] == "third_party":
                json_data[service_info.service_id]['cur_status'] = "third_party"

            # 查询是否打开对外组件端口
            port_list = (
                session.execute(
                    select(TeamComponentPort).where(TeamComponentPort.service_id == service_info.service_id))
            ).scalars().all()

            # 判断组件是否有对外端口
            outer_port_exist = False
            if len(port_list) > 0:
                outer_port_exist = reduce(lambda x, y: x or y, [t.is_outer_service for t in list(port_list)])
            json_data[service_info.service_id]['is_internet'] = outer_port_exist

        for service_relation in service_relation_list:
            tmp_id = service_relation.service_id
            tmp_info = service_map.get(tmp_id)
            if tmp_info:
                tmp_dep_id = service_relation.dep_service_id
                tmp_dep_info = service_map.get(tmp_dep_id)
                # 依赖组件的cname
                if tmp_dep_info:
                    tmp_info_relation = []
                    if tmp_info.service_id in list(json_svg.keys()):
                        tmp_info_relation = json_svg.get(tmp_info.service_id)
                    tmp_info_relation.append(tmp_dep_info.service_id)
                    json_svg[tmp_info.service_id] = tmp_info_relation

        topological_info["json_data"] = json_data
        topological_info["json_svg"] = json_svg
        return topological_info


topological_service = TopologicalService()
