# -*- coding: utf8 -*-
import json
from datetime import datetime
from loguru import logger
from sqlalchemy import select
from core.enum.component_enum import ComponentType
from core.enum.enterprise_enum import ActionType
from core.utils.constants import AppConstants, DomainType
from core.utils.crypt import make_uuid
from exceptions.bcode import ErrK8sServiceNameExists
from exceptions.main import AbortRequest, ErrVolumePath
from models.application.models import ComponentApplicationRelation
from models.teams import RegionConfig, ServiceDomain, GatewayCustomConfiguration
from models.component.models import Component as TeamComponentInfo, ComponentSourceInfo, ComponentEnvVar, TeamComponentPort, \
    TeamComponentConfigurationFile, ComponentExtendMethod, ComponentMonitor, ComponentGraph, ComponentLabels
from service.app_config.port_service import port_service
from service.app_config.promql_service import promql_service
from service.app_config.volume_service import volume_service
from service.base_services import baseService
from service.market_app.app_template import AppTemplate
from service.market_app.component import Component
from service.market_app.property_changes import is_same_component
from service.probe_service import probe_service


class NewComponents(object):
    def __init__(self,
                 session,
                 tenant_env,
                 region: RegionConfig,
                 user,
                 original_app,
                 app_model_key,
                 app_template,
                 version,
                 install_from_cloud,
                 components_keys,
                 create_type,
                 market_name="",
                 is_deploy=False,
                 support_labels=None,):
        """
        components_keys: component keys that the user select.
        """
        self.tenant_env = tenant_env
        self.region = region
        self.region_name = region.region_name
        self.user = user
        self.original_app = original_app
        self.app_model_key = app_model_key
        self.app_template = AppTemplate(app_template)
        self.version = version
        self.install_from_cloud = install_from_cloud
        self.market_name = market_name
        self.is_deploy = is_deploy
        self.create_type = create_type
        self.support_labels = support_labels if support_labels else []

        self.components_keys = components_keys
        self.components = self.create_components(session)

    def create_components(self, session):
        """
        create component and related attributes
        """
        # new component templates
        exist_components = self.original_app.components()
        templates = self.app_template.component_templates()
        new_component_tmpls = self._get_new_component_templates(exist_components, templates)

        components = [self._template_to_component(self.tenant_env.env_id, self.create_type, template) for template in new_component_tmpls]
        if self.components_keys:
            components = [cpt for cpt in components if cpt.service_key in self.components_keys]

        # make a map of templates
        templates = {tmpl.get("service_key"): tmpl for tmpl in templates}

        result = []
        for cpt in components:
            component_tmpl = templates.get(cpt.service_key)

            # component source
            component_source = self._template_to_component_source(cpt, component_tmpl)
            # ports
            port_map_list = component_tmpl.get("port_map_list")
            ports = self._template_to_ports(session, cpt, port_map_list)
            # envs
            inner_envs = component_tmpl.get("service_env_map_list")
            outer_envs = component_tmpl.get("service_connect_info_map_list")
            envs = self._template_to_envs(cpt, inner_envs, outer_envs)
            # volumes
            volumes, config_files = self._template_to_volumes(session, cpt,
                                                              component_tmpl.get("service_volume_map_list"))
            # probe
            probes = self._template_to_probes(session, cpt, component_tmpl.get("probes"))
            # extend info
            extend_info = self._template_to_extend_info(cpt, component_tmpl.get("extend_method_map"))
            # service monitors
            monitors = self._template_to_service_monitors(session, cpt, component_tmpl.get("component_monitors"))
            # graphs
            graphs = self._template_to_component_graphs(cpt, component_tmpl.get("component_graphs"))
            service_group_rel = ComponentApplicationRelation(
                service_id=cpt.service_id,
                group_id=self.original_app.app_id,
                tenant_env_id=self.tenant_env.env_id,
                region_name=self.region_name,
            )
            # ingress
            http_rules, http_rule_configs = self._template_to_service_domain(cpt, ports)
            # labels
            labels = self._template_to_labels(cpt, component_tmpl.get("labels"))
            component = Component(
                cpt,
                component_source,
                envs,
                ports,
                volumes,
                config_files,
                probes,
                extend_info,
                monitors,
                graphs, [],
                http_rules=http_rules,
                http_rule_configs=http_rule_configs,
                service_group_rel=service_group_rel,
                labels=labels,
                support_labels=self.support_labels)
            component.ensure_port_envs(self.original_app.governance_mode)
            component.action_type = ActionType.BUILD.value
            result.append(component)
        return result

    def _get_new_component_templates(self, exist_components: [Component], component_templates):
        tmpls = []
        for tmpl in component_templates:
            if self._component_exists(exist_components, tmpl):
                continue
            tmpls.append(tmpl)
        return tmpls

    @staticmethod
    def _component_exists(exist_components: [Component], component_tmpl):
        for component in exist_components:
            if is_same_component(component, component_tmpl):
                return True
        return False

    def _template_to_component(self, env_id, create_type, template):
        component = TeamComponentInfo()
        service_id = None
        if create_type == "market":
            component.desc = "install from market app"
            component.service_source = AppConstants.MARKET
        else:
            service_id = template.get("service_id", None)
            component.desc = "install from yaml"
            component.service_source = AppConstants.DOCKER_IMAGE
        component.tenant_env_id = env_id
        component.service_id = service_id if service_id else make_uuid()
        component.service_cname = template.get("service_cname", "default-name")
        component.service_alias = "wt" + component.service_id[-6:]
        component.creater = self.user.nick_name
        component.image = template.get("share_image", template["image"])
        component.cmd = template.get("cmd", "")
        component.service_region = self.region_name
        component.service_key = template.get("service_key")
        component.category = "app_publish"
        component.version = template.get("version")
        component.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        component.deploy_version = template.get("deploy_version")
        component.service_type = "application"
        component.create_status = "complete"
        component.tenant_service_group_id = self.original_app.upgrade_group_id
        component.build_upgrade = self.is_deploy
        component.k8s_component_name = template["k8s_component_name"] if template.get(
            "k8s_component_name") else component.service_alias

        # component type
        extend_method = template["extend_method"]
        if extend_method:
            if extend_method == "state":
                component.extend_method = ComponentType.state_multiple.value
            elif extend_method == "stateless":
                component.extend_method = ComponentType.stateless_multiple.value
            else:
                component.extend_method = extend_method

        component.min_node = template.get("extend_method_map", {}).get("min_node")
        min_memory = template.get("extend_method_map", {}).get("init_memory")
        if min_memory is not None:
            component.min_memory = min_memory
        elif template.get("extend_method_map", {}).get("min_memory"):
            component.min_memory = template.get("extend_method_map", {}).get("min_memory")
        else:
            component.min_memory = 512

        container_cpu = template.get("extend_method_map", {}).get("container_cpu")
        if container_cpu is not None:
            component.min_cpu = template["extend_method_map"]["container_cpu"]
        else:
            component.min_cpu = 2000
        component.total_memory = component.min_node * component.min_memory

        return component

    def _template_to_component_source(self, component: TeamComponentInfo, tmpl: map):
        extend_info = tmpl.get("service_image")
        if not extend_info:
            extend_info = {}
        extend_info["source_deploy_version"] = tmpl.get("deploy_version")
        extend_info["source_service_share_uuid"] = tmpl.get("service_share_uuid") if tmpl.get(
            "service_share_uuid", None) else tmpl.get("service_key", "")
        update_time = self.app_template.app_template.get("update_time")
        if update_time:
            if type(update_time) == datetime:
                extend_info["update_time"] = update_time.strftime('%Y-%m-%d %H:%M:%S')
            elif type(update_time) == str:
                extend_info["update_time"] = update_time
        if self.install_from_cloud:
            extend_info["install_from_cloud"] = True
            extend_info["market"] = "default"
            extend_info["market_name"] = self.market_name
        return ComponentSourceInfo(
            tenant_env_id=component.tenant_env_id,
            service_id=component.service_id,
            extend_info=json.dumps(extend_info),
            group_key=self.app_model_key,
            version=self.version,
            service_share_uuid=tmpl.get("service_share_uuid")
            if tmpl.get("service_share_uuid", None) else tmpl.get("service_key"),
        )

    def _template_to_envs(self, component, inner_envs, outer_envs):
        if not inner_envs and not outer_envs:
            return []
        envs = []
        for env in inner_envs:
            if not env.get("attr_name"):
                continue
            envs.append(
                ComponentEnvVar(
                    tenant_env_id=component.tenant_env_id,
                    service_id=component.service_id,
                    container_port=0,
                    name=env.get("name"),
                    attr_name=env.get("attr_name"),
                    attr_value=env.get("attr_value"),
                    is_change=env.get("is_change", True),
                    scope="inner"))
        for env in outer_envs:
            if not env.get("attr_name"):
                continue
            container_port = env.get("container_port", 0)
            if env.get("attr_value") == "**None**":
                env["attr_value"] = make_uuid()[:8]
            envs.append(
                ComponentEnvVar(
                    tenant_env_id=component.tenant_env_id,
                    service_id=component.service_id,
                    container_port=container_port,
                    name=env.get("name"),
                    attr_name=env.get("attr_name"),
                    attr_value=env.get("attr_value"),
                    is_change=env.get("is_change", True),
                    scope="outer"))
        # port envs
        return envs

    def _template_to_ports(self, session, component, ports):
        if not ports:
            return []
        new_ports = []
        for port in ports:
            component_port = port["container_port"]
            k8s_service_name = component.service_alias + "-" + str(component_port)
            try:
                port_service.check_k8s_service_name(session, component.tenant_env_id, k8s_service_name)
            except ErrK8sServiceNameExists:
                k8s_service_name = k8s_service_name + "-" + make_uuid()[:4]
            except AbortRequest:
                k8s_service_name = component.service_alias + "-" + str(component_port)
            port_alias = component.service_alias.upper() + str(component_port)
            port = TeamComponentPort(
                tenant_env_id=component.tenant_env_id,
                service_id=component.service_id,
                container_port=int(component_port),
                mapping_port=int(component_port),
                lb_mapping_port=0,
                protocol=port.get("protocol", "tcp"),
                port_alias=port_alias,
                is_inner_service=port.get("is_inner_service", False),
                is_outer_service=port.get("is_outer_service", False),
                k8s_service_name=k8s_service_name,
            )
            new_ports.append(port)
        return new_ports

    @staticmethod
    def _create_port_env(component: TeamComponentInfo, port: TeamComponentPort, name, attr_name, attr_value):
        return ComponentEnvVar(
            tenant_env_id=component.tenant_env_id,
            service_id=component.service_id,
            container_port=port.container_port,
            name=name,
            attr_name=attr_name,
            attr_value=attr_value,
            is_change=False,
            scope="outer",
            create_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

    def _create_default_gateway_rule(self, component: TeamComponentInfo, port: TeamComponentPort):
        domain_name = self._create_default_domain(component.service_alias, port.container_port)
        return ServiceDomain(
            service_id=component.service_id,
            service_name=component.service_alias,
            domain_name=domain_name,
            create_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            container_port=port.container_port,
            protocol="http",
            http_rule_id=make_uuid(domain_name),
            tenant_env_id=self.tenant_env.env_id,
            service_alias=component.service_cname,
            region_id=self.region.region_id,
            domain_path="/",
            domain_cookie="",
            domain_heander="",
            domain_type="www",
            auto_ssl=0,
            certificate_id=0,
            is_senior=0,
            is_outer_service=1,
            path_rewrite=0,
            the_weight=100,
            rule_extensions="",
            type=0)

    def _template_to_volumes(self, session, component, volumes):
        if not volumes:
            return [], []
        volumes2 = []
        config_files = []
        for volume in volumes:
            config_file = None
            try:
                if volume["volume_type"] == "config-file" and volume["file_content"] != "":
                    settings = None
                    config_file = TeamComponentConfigurationFile(
                        service_id=component.service_id,
                        volume_name=volume["volume_name"],
                        file_content=volume["file_content"])
                else:
                    settings = volume_service.get_best_suitable_volume_settings(session,
                                                                                self.tenant_env, component,
                                                                                volume["volume_type"],
                                                                                volume.get("access_mode"),
                                                                                volume.get("share_policy"),
                                                                                volume.get("backup_policy"), None,
                                                                                volume.get("volume_provider_name"))
                    if settings["changed"]:
                        logger.debug('volume type changed from {0} to {1}'.format(volume["volume_type"],
                                                                                  settings["volume_type"]))
                        volume["volume_type"] = settings["volume_type"]
                        if volume["volume_type"] == "share-file":
                            volume["volume_capacity"] = 0
                    else:
                        settings["volume_capacity"] = volume.get("volume_capacity", 0)

                vol = volume_service.create_service_volume(
                    session,
                    self.tenant_env,
                    component,
                    volume["volume_path"],
                    volume["volume_type"],
                    volume["volume_name"],
                    settings=settings,
                    mode=volume.get("mode"))
                session.add(vol)
                session.flush()
                if config_file:
                    config_file.volume_id = vol.ID
                    config_files.append(config_file)
                volumes2.append(vol)
            except ErrVolumePath:
                logger.warning("Volume {0} Path {1} error".format(volume["volume_name"], volume["volume_path"]))

        return volumes2, config_files

    def _template_to_probes(self, session, component, probes):
        if not probes:
            return []
        result = []
        for probe in probes:
            result.append(probe_service.create_probe(session, self.tenant_env, component, probe))
        return result

    def _template_to_extend_info(self, component, extend_info):
        if not extend_info:
            return None
        version = component.version
        if len(version) > 255:
            version = version[:255]
        container_cpu = extend_info.get("container_cpu")
        if container_cpu is None:
            container_cpu = baseService.calculate_service_cpu(component.service_region, component.min_memory)
        return ComponentExtendMethod(
            service_key=component.service_key,
            app_version=version,
            min_node=extend_info["min_node"],
            max_node=extend_info["max_node"],
            step_node=extend_info["step_node"],
            min_memory=extend_info["min_memory"],
            max_memory=extend_info["max_memory"],
            step_memory=extend_info["step_memory"],
            is_restart=extend_info["is_restart"],
            container_cpu=container_cpu)

    def _template_to_service_monitors(self, session, component, service_monitors):
        if not service_monitors:
            return []
        monitors = []
        for monitor in service_monitors:
            # Optimization: check all monitor names at once
            sm = session.execute(select(ComponentMonitor).where(
                ComponentMonitor.tenant_env_id == component.tenant_env_id,
                ComponentMonitor.name == monitor["name"]
            )).scalars().all()
            if len(sm) > 0:
                monitor["name"] = "-".join([monitor["name"], make_uuid()[-4:]])
            data = ComponentMonitor(
                name=monitor["name"],
                tenant_env_id=component.tenant_env_id,
                service_id=component.service_id,
                path=monitor["path"],
                port=monitor["port"],
                service_show_name=monitor["service_show_name"],
                interval=monitor["interval"])
            monitors.append(data)
        return monitors

    def _template_to_component_graphs(self, component, graphs):
        if not graphs:
            return []
        new_graphs = {}
        for graph in graphs:
            try:
                promql = promql_service.add_or_update_label(component.service_id, graph.get("promql"))
            except AbortRequest as e:
                logger.warning("promql: {}, {}".format(graph.get("promql"), e))
                continue
            new_graph = ComponentGraph(
                component_id=component.service_id,
                graph_id=make_uuid(),
                title=graph.get("title"),
                promql=promql,
                sequence=graph.get("sequence"),
            )
            new_graphs[new_graph.title] = new_graph
        return new_graphs.values()

    def _template_to_service_domain(self, component: TeamComponentInfo, ports: [TeamComponentPort]):
        new_ports = {port.container_port: port for port in ports}
        ingress_http_routes = self.app_template.list_ingress_http_routes_by_component_key(component.service_key)

        service_domains = []
        configs = []
        for ingress in ingress_http_routes:
            port = new_ports.get(ingress["port"])
            if not port:
                logger.warning("component id: {}; port not found for ingress".format(component.service_id))
                continue

            service_domain = ServiceDomain(
                http_rule_id=make_uuid(),
                region_id=self.region.region_id,
                tenant_env_id=self.tenant_env.env_id,
                service_id=component.service_id,
                service_name=component.service_alias,
                create_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                container_port=ingress["port"],
                protocol="http",
                domain_type=DomainType.WWW,
                service_alias=component.service_cname,
                domain_path=ingress["location"],
                domain_cookie=self._domain_cookie_or_header(ingress["cookies"]),
                domain_heander=self._domain_cookie_or_header(ingress["headers"]),
                path_rewrite=ingress["path_rewrite"] if ingress.get("path_rewrite") else False,
                rewrites=ingress["rewrites"] if ingress.get("rewrites") else None,
                type=0 if ingress["default_domain"] else 1,
                the_weight=100,
                is_outer_service=port.is_outer_service,
                auto_ssl=False,
                rule_extensions=self._ingress_load_balancing(ingress["load_balancing"]),
            )
            if service_domain.type == 0:
                service_domain.domain_name = self._create_default_domain(component.service_alias, port.container_port)
            else:
                service_domain.domain_name = make_uuid()[:6] + self._create_default_domain(
                    component.service_alias, port.container_port)
            service_domain.is_senior = len(service_domain.domain_cookie) > 0 or len(service_domain.domain_heander) > 0
            service_domains.append(service_domain)

            # config
            config = self._ingress_config(service_domain.http_rule_id, ingress)
            configs.append(config)

        self._ensure_default_http_rule(component, service_domains, ports)

        return service_domains, configs

    def _ensure_default_http_rule(self, component: Component, http_rules: [ServiceDomain],
                                  ports: [TeamComponentPort]):
        new_http_rules = {}
        for rule in http_rules:
            rules = new_http_rules.get(rule.container_port, [])
            rules.append(rule)
            new_http_rules[rule.container_port] = rules

        for port in ports:
            port_http_rules = new_http_rules.get(port.container_port, [])

            # only create gateway rule for http port now
            if not port.is_outer_service or port.protocol != "http":
                return None

            # Create a default http rule if there is no http rules
            if len(port_http_rules) == 0:
                http_rule = self._create_default_gateway_rule(component, port)
                http_rules.append(http_rule)
                continue

            # If there is no default rule, make the first rule the default rule
            if not self._contains_default_rule(port_http_rules):
                http_rule = port_http_rules[0]
                http_rule.type = 0
                http_rule.domain_name = self._create_default_domain(component.service_alias, port.container_port)

    @staticmethod
    def _contains_default_rule(rules: [ServiceDomain]):
        for rule in rules:
            if rule.type == 0:
                return True
        return False

    def _create_default_domain(self, service_alias: str, port: int):
        return str(port) + "." + service_alias + "." + self.tenant_env.env_name + "." + self.region.httpdomain

    @staticmethod
    def _domain_cookie_or_header(items):
        res = []
        for key in items:
            res.append(key + "=" + items[key])
        return ";".join(res)

    @staticmethod
    def _ingress_config(rule_id, ingress):
        return GatewayCustomConfiguration(
            rule_id=rule_id,
            value=json.dumps({
                "proxy_buffer_numbers":
                    ingress["proxy_buffer_numbers"] if ingress.get("proxy_buffer_numbers") else 4,
                "proxy_buffer_size":
                    ingress["proxy_buffer_size"] if ingress.get("proxy_buffer_size") else 4,
                "proxy_body_size":
                    ingress["request_body_size_limit"] if ingress.get("request_body_size_limit") else 0,
                "proxy_connect_timeout":
                    ingress["connection_timeout"] if ingress.get("connection_timeout") else 5,
                "proxy_read_timeout":
                    ingress["response_timeout"] if ingress.get("response_timeout") else 60,
                "proxy_send_timeout":
                    ingress["request_timeout"] if ingress.get("request_timeout") else 60,
                "proxy_buffering":
                    "off",
                "WebSocket":
                    ingress["websocket"] if ingress.get("websocket") else False,
                "set_headers":
                    ingress.get("proxy_header"),
            }))

    @staticmethod
    def _ingress_load_balancing(lb):
        if lb == "cookie-session-affinity":
            return "lb-type:cookie-session-affinity"
        # round-robin is the default value of load balancing
        return "lb-type:round-robin"

    def _template_to_labels(self, component, labels):
        support_labels = {label.label_name: label for label in self.support_labels}
        if not labels:
            return []
        new_labels = []
        for label in labels:
            lab = support_labels.get(label)
            if not lab:
                continue
            new_labels.append(
                ComponentLabels(
                    tenant_env_id=component.tenant_env_id,
                    service_id=component.service_id,
                    label_id=lab.label_id,
                    region=self.region_name,
                    create_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        return new_labels
