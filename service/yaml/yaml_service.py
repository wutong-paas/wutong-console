import base64

from sqlalchemy import select

from core.utils.crypt import make_uuid
from exceptions.main import AbortRequest
from models.application.models import Application
from repository.teams.team_region_repo import team_region_repo
from service.autoscaler_service import autoscaler_service
from service.market_app.app_upgrade import AppUpgrade
from service.market_app_service import market_app_service


class YamlService(object):

    def is_resource_dup(self, ports, type):
        ports_temp = []
        for port in ports:
            container_port = port.get(type)
            if container_port in ports_temp:
                return container_port
            else:
                ports_temp.append(container_port)
                continue
        return None

    def install_yaml_service(self,
                             session,
                             user,
                             env,
                             app_id,
                             region_name,
                             yaml_data):
        app = (
            session.execute(select(Application).where(Application.ID == app_id))
        ).scalars().first()

        if not app:
            raise AbortRequest("app not found", "应用不存在", status_code=404, error_code=404)

        yaml_apps, autoscaler_datas, err_msg = self.get_all_yaml_info(yaml_data)
        if err_msg:
            return err_msg
        app_template = {"plugins": None, "app_config_groups": [], "template_version": "v1"}
        app_template.update({"apps": yaml_apps})
        region = team_region_repo.get_region_info_by_region_name(session, env.env_id, region_name)

        component_group = market_app_service._create_tenant_service_group(session, region_name, env.env_id,
                                                                          app.app_id,
                                                                          "", "", "yaml")
        app_upgrade = AppUpgrade(
            session,
            env,
            region,
            user,
            app,
            "",
            component_group,
            app_template,
            False,
            "yamlApplication",
            is_deploy=False,
            create_type="yaml")
        app_upgrade.install(session)

        for autoscaler_data in autoscaler_datas:
            autoscaler_service.create_autoscaler_rule(session, region_name, env,
                                                      "wt" + autoscaler_data["service_id"][-6:],
                                                      autoscaler_data)
        return None

    def get_all_yaml_info(self, data):

        err_msg = []
        svc_data = []
        autoscaler_data = []

        deployment_data = data.get("Deployment", [])
        stateful_set_data = data.get("StatefulSet", [])
        service_data = data.get("Service", None)
        ingress_data = data.get("Ingress", None)
        secret_data = data.get("Secret", [])
        configmap_data = data.get("ConfigMap", None)
        persistent_volume_claim_data = data.get("PersistentVolumeClaim", [])
        horizontal_pod_auto_scaler_data = data.get("HorizontalPodAutoscaler", [])
        commpoent_datas = deployment_data + stateful_set_data

        for commpoent_data in commpoent_datas:
            helm_data = {}
            new_ports = []
            my_uuid = make_uuid()
            svc_name = commpoent_data["metadata"]["name"]
            match_labels = commpoent_data["spec"]["selector"]["matchLabels"]
            keys = match_labels.keys()
            spec = commpoent_data["spec"]["template"]["spec"]
            volume_claim_templates = commpoent_data["spec"].get("volumeClaimTemplates", None)
            containers = spec["containers"]
            container = containers[0]
            ports = container.get("ports", [])
            envs = container.get("env", [])
            env_froms = container.get("envFrom", None)
            image = container.get("image", None)
            resources = container.get("resources")
            volume_mounts = container.get("volumeMounts")
            volumes = spec.get("volumes", [])
            for port in ports:
                outer_enable = False
                inner_enable = False
                service_name = None
                service_port = None
                protocol = "tcp"
                port_name = port.get("name", None)
                deployment_port = port.get("containerPort")
                if service_data:
                    for service in service_data:
                        service_name = service["metadata"]["name"]
                        selectors = service["spec"]["selector"]
                        src_keys = selectors.keys()
                        ports_service = service["spec"]["ports"]
                        for port_service in ports_service:
                            service_port = port_service.get("port", None)
                            port_service_target_port = port_service.get("targetPort", None)
                            node_port = port_service.get("nodePort", None)
                            for src_key in src_keys:
                                if src_key in keys:
                                    if match_labels.get(src_key) == selectors.get(src_key):
                                        if deployment_port == port_service_target_port or \
                                                port_name == port_service_target_port:
                                            if node_port:
                                                outer_enable = True
                                                port.update({"outer_url": "0:0:0:0:" + str(node_port)})
                                            inner_enable = True
                                            port.update({"inner_url": "127.0.0.1:" + str(port_service_target_port)})
                                            break
                    if ingress_data:
                        for ingress in ingress_data:
                            rules = ingress["spec"]["rules"]
                            for rule in rules:
                                paths = rule["http"]["paths"]
                                host = rule["host"]
                                for path in paths:
                                    path_url = path["path"]
                                    target_service_name = path["backend"]["serviceName"]
                                    target_service_port = path["backend"]["servicePort"]
                                    if target_service_name == service_name and target_service_port == service_port:
                                        protocol = "http"
                                        outer_enable = True
                                        port.update({"outer_url": host + path_url})
                container_port = port.get("containerPort")
                port_alias = "wt" + my_uuid[-6:] + str(container_port)
                k8s_name = "wt" + my_uuid[-6:] + '-' + str(container_port)
                port.update({"port_alias": port_alias.upper()})
                port.update({"k8s_service_name": k8s_name.lower()})
                port.update({"container_port": container_port})
                port.update({"is_outer_service": outer_enable})
                port.update({"is_inner_service": inner_enable})
                port.update({"protocol": protocol})
                port.pop("containerPort")
                new_ports.append(port)

            dup_port = self.is_resource_dup(new_ports, "container_port")
            if dup_port:
                err_msg.append({
                    "file_name": commpoent_data["file_name"],
                    "resource_name": commpoent_data["kind"],
                    "err_msg": "存在相同端口 " + str(dup_port)
                })

            for env in envs:
                attr_name = env.get("name")
                env.update({"attr_name": attr_name})
                env.update({"attr_value": env.get("value")})
                env.update({"is_change": True})
                if not env.get("attr_value") and env.get("valueFrom"):
                    value_from = env.get("valueFrom").get("secretKeyRef")
                    if value_from:
                        value_name = value_from.get("name")
                        value_key = value_from.get("key")
                        for secret in secret_data:
                            secret_name = secret.get("metadata").get("name")
                            secret_s_data = secret.get("data")
                            if secret_name == value_name:
                                value = secret_s_data.get(value_key)
                                env.update({"attr_value": str(base64.b64decode(value), 'utf-8')})
                elif env_froms and env.get("attr_value")[:1] == '$':
                    for env_from in env_froms:
                        value_from = env_from.get("secretRef")
                        value_name = value_from.get("name")
                        env_name = env.get("attr_value")[2:-1]
                        for secret in secret_data:
                            secret_name = secret.get("metadata").get("name")
                            secret_s_data = secret.get("data")
                            if secret_name == value_name:
                                value = secret_s_data.get(env_name)
                                if value:
                                    env.update({"attr_value": str(base64.b64decode(value), 'utf-8')})
                if not env.get("attr_value"):
                    env.update({"attr_value": ""})

            dup_env = self.is_resource_dup(envs, "attr_name")
            if dup_env:
                err_msg.append({
                    "file_name": commpoent_data["file_name"],
                    "resource_name": commpoent_data["kind"],
                    "err_msg": "存在相同环境变量 " + str(dup_env)
                })

            if volume_mounts:
                for volume_mount in volume_mounts:
                    v_name = volume_mount.get("name")
                    volume_mount.update({"volume_type": "config-file"})
                    volume_mount.update({"volume_name": v_name})
                    volume_mount.update({"file_content": ""})
                    volume_mount.update({"access_mode": "RWX"})
                    for volume in volumes:
                        volume_name = volume.get("name")
                        if v_name == volume_name:
                            is_config_map = "configMap" in volume.keys()
                            is_pvc = "persistentVolumeClaim" in volume.keys()
                            if is_pvc:
                                volume_mount.update({"volume_type": "share-file"})
                                claim_name = volume.get("persistentVolumeClaim").get("claimName")
                                for persistent_volume_claim in persistent_volume_claim_data:
                                    persistent_volume_claim_name = persistent_volume_claim["metadata"]["name"]
                                    if claim_name == persistent_volume_claim_name:
                                        volume_claim_templates_spec = persistent_volume_claim["spec"]
                                        access_mode = volume_claim_templates_spec["accessModes"][0]
                                        storage = volume_claim_templates_spec["resources"]["requests"]["storage"]
                                        volume_mount.update({"volume_name": volume_mount.get("name")})
                                        volume_mount.update({"volume_capacity": int(storage[:-2])})
                                        volume_mount.update({"access_mode": access_mode})

                            if is_config_map:
                                try:
                                    sub_path = volume_mount["subPath"]
                                except:
                                    sub_path = volume_mount["mountPath"]
                                config_map = volume["configMap"]
                                config_name = config_map["name"]
                                volume_mount.update({"volume_type": "config-file"})
                                volume_mount.update({"volume_name": sub_path if sub_path else config_name})
                                for configmap in configmap_data:
                                    configmap_info = configmap.get("data")
                                    if sub_path == {}:
                                        sub_path = ''
                                    file_content = ''
                                    is_config = sub_path in configmap_info.keys()
                                    if is_config:
                                        file_content = configmap_info.get(sub_path)
                                    volume_mount.update({"file_content": file_content})
                        is_volume_name = "volume_name" in volume_mount.keys()
                        if not is_volume_name:
                            volume_mount.update({"volume_name": volume_mount.get("name")})
                    if volume_claim_templates:
                        for volume_claim_template in volume_claim_templates:
                            volume_claim_templates_name = volume_claim_template["metadata"]["name"]
                            if volume_claim_templates_name == v_name:
                                volume_claim_templates_spec = volume_claim_template["spec"]
                                access_mode = volume_claim_templates_spec["accessModes"][0]
                                storage = volume_claim_templates_spec["resources"]["requests"]["storage"]
                                volume_mount.update({"volume_type": "share-file"})
                                volume_mount.update({"volume_name": volume_claim_templates_name})
                                volume_mount.update({"volume_capacity": int(storage[:-2])})
                                volume_mount.update({"access_mode": access_mode})
                    volume_mount.update({"mode": 755})
                    volume_mount.update({"volume_path": volume_mount.get("mountPath")})

            dup_volume = self.is_resource_dup(volume_mounts, "volume_name")
            if dup_volume:
                err_msg.append({
                    "file_name": commpoent_data["file_name"],
                    "resource_name": commpoent_data["kind"],
                    "err_msg": "存在相同存储名 " + str(dup_volume)
                })

            for horizontal_pod_auto_scaler in horizontal_pod_auto_scaler_data:
                scaler_spec = horizontal_pod_auto_scaler["spec"]
                if scaler_spec:
                    scaler_target_name = scaler_spec["scaleTargetRef"]["name"]
                    if scaler_target_name == svc_name:
                        metrics_list = []
                        metrics = scaler_spec["metrics"]
                        min_replicas = scaler_spec["minReplicas"]
                        max_replicas = scaler_spec["maxReplicas"]
                        for metric in metrics:
                            scaler_type = metric.get("type", None)
                            if scaler_type == "Resource":
                                scaler_resource = metric.get("resource", None)
                                scaler_name = scaler_resource["name"]
                                value = scaler_resource["target"]["averageUtilization"]
                                metrics_list.append({
                                    "metric_type": "resource_metrics",
                                    "metric_name": scaler_name,
                                    "metric_target_type": "average_value",
                                    "metric_target_value": value if value else 1,
                                })

                        autoscaler_data.append({
                            "service_id": my_uuid,
                            "xpa_type": "hpa",
                            "enable": True,
                            "min_replicas": min_replicas if min_replicas else 1,
                            "max_replicas": max_replicas if max_replicas else 1,
                            "metrics": metrics_list
                        })

            requests = None
            limits = None
            if resources:
                requests = resources.get("requests")
                limits = resources.get("limits")

            helm_data.update({"service_cname": svc_name})
            helm_data.update({"port_map_list": new_ports})
            helm_data.update({"service_env_map_list": envs})
            helm_data.update({"service_connect_info_map_list": []})
            helm_data.update({"image": image})
            helm_data.update({"extend_method_map": {
                "max_memory": int(limits.get("memory")[:-2]) * 1024 if limits else 0,
                "min_memory": int(limits.get("memory")[:-2]) * 1024 if limits else 0,
                "init_memory": int(requests.get("memory")[:-2]) * 1024 if requests else 0,
                "container_cpu": int(requests.get("cpu")[:-1]) if requests else 0,
                "step_memory": int(limits.get("memory")[:-2]) * 1024 if limits else 0,
                "min_node": 1,
                "max_node": 1,
                "step_node": 1,
                "is_restart": 1
            }})
            helm_data.update({"service_volume_map_list": volume_mounts})
            helm_data.update({"extend_method": "stateless"})
            helm_data.update({"version": ''.join(image.split(":")[-1:])})
            helm_data.update({"service_key": my_uuid})
            helm_data.update({"service_id": my_uuid})
            helm_data.update({"service_share_uuid": my_uuid})
            svc_data.append(helm_data)

        return svc_data, autoscaler_data, err_msg


yaml_service = YamlService()
