import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.enum.component_enum import Kind
from core.utils.return_message import general_message
from database.session import SessionClass
from models.users.users import Users
from schemas.response import Response
from jsonpath import jsonpath

router = APIRouter()


# 获取Helm市场应用列表
@router.get("/teams/{tenant_name}/region/{region_name}/helm/apps", response_model=Response, name="获取Helm市场应用列表")
async def get_helm_apps(
        request: Request,
        tenant_name: Optional[str] = None,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    helm_namespace = data.get("helm_namespace")
    helm_list = remote_component_client.get_helm_chart_apps(session,
                                                            region_name,
                                                            tenant_name,
                                                            {"helm_namespace": helm_namespace})

    return JSONResponse(general_message(200, "success", msg_show="查询成功", list=helm_list), status_code=200)


# 获取Helm市场应用资源
@router.get("/teams/{tenant_name}/region/{region_name}/helm/apps/resource", response_model=Response,
            name="获取Helm市场应用资源")
async def get_helm_app_resource(
        request: Request,
        tenant_name: Optional[str] = None,
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user: Users = Depends(deps.get_current_user)) -> Any:
    data = await request.json()
    helm_namespace = data.get("helm_namespace")
    helm_name = data.get("helm_name")
    helm_list = remote_component_client.get_helm_chart_resources(session,
                                                                 region_name,
                                                                 tenant_name,
                                                                 {"helm_name": helm_name,
                                                                  "helm_namespace": helm_namespace})

    helm_json = json.dumps(helm_list)

    data = []
    kind_service = []
    kind_deployment = []
    kind_configmap = []
    kind_persistent_volume_claim = []
    kind_secret = []
    kind_statefulset = []

    for helm in helm_list:
        info = helm.get("info")
        kind = info.get("kind")
        if kind == Kind.Service.value:
            kind_service.append(helm.get("apiResource"))
        elif kind == Kind.Deployment.value:
            kind_deployment.append(helm.get("apiResource"))
        elif kind == Kind.ConfigMap.value:
            kind_configmap.append(helm.get("apiResource"))
        elif kind == Kind.PersistentVolumeClaim.value:
            kind_persistent_volume_claim.append(helm.get("apiResource"))
        elif kind == Kind.Secret.value:
            kind_secret.append(helm.get("apiResource"))
        elif kind == Kind.StatefulSet.value:
            kind_deployment.append(helm.get("apiResource"))

    for deployment in kind_deployment:
        helm_data = []
        new_ports = []
        secret_info = []
        configmap_info = []
        volume_claim_info = []
        status = False
        enable = False
        deployment_name = jsonpath(deployment, '$.metadata..labels')[0].get("app.kubernetes.io/name")
        ports_deployment = jsonpath(deployment, '$.spec..template...spec')[0].get("containers")[0].get("ports")
        for service in kind_service:
            service_name = jsonpath(service, '$.metadata..labels')[0].get("app.kubernetes.io/name")
            if deployment_name != service_name:
                continue
            status = True
            ports_service = jsonpath(service, '$.spec..ports')[0]
            for port in ports_deployment:
                enable = False
                port_name = port.get("name")
                deployment_port = port.get("containerPort")
                for port_service in ports_service:
                    port_service_target_port = port_service.get("targetPort")
                    if port_name == port_service_target_port or deployment_port == port_service_target_port:
                        enable = True
                        break
                port.update({"enable": enable})
                new_ports.append(port)

        if not status:
            for port in ports_deployment:
                port.update({"enable": enable})
                new_ports.append(port)

        for secret in kind_secret:
            secret_name = jsonpath(secret, '$.metadata..labels')[0].get("app.kubernetes.io/name")
            if deployment_name != secret_name:
                continue
            secret_info = jsonpath(secret, '$.data')

        for configmap in kind_configmap:
            configmap_name = jsonpath(configmap, '$.metadata..labels')[0].get("app.kubernetes.io/name")
            if deployment_name != configmap_name:
                continue
            configmap_info = jsonpath(configmap, '$.data')

        for volume_claim in kind_persistent_volume_claim:
            volume_claim_name = jsonpath(volume_claim, '$.metadata..labels')[0].get("app.kubernetes.io/name")
            if deployment_name != volume_claim_name:
                continue
            volume_claim_info = jsonpath(volume_claim, '$.spec')

        envs = jsonpath(deployment, '$.spec..template...spec')[0].get("containers")[0].get("env")
        image = jsonpath(deployment, '$.spec..template...spec')[0].get("containers")[0].get("image")
        resources = jsonpath(deployment, '$.spec..template...spec')[0].get("containers")[0].get("resources")
        volume_mounts = jsonpath(deployment, '$.spec..template...spec')[0].get("containers")[0].get("volumeMounts")

        helm_data.append({"ports": new_ports})
        helm_data.append({"envs": envs})
        helm_data.append({"image": image})
        helm_data.append({"resources": resources})
        helm_data.append({"volume_mounts": volume_mounts})
        helm_data.append({"secret": secret_info})
        helm_data.append({"configmap": configmap_info})
        helm_data.append({"persistent_volume_claim": volume_claim_info})
        data.append(helm_data)

    return JSONResponse(general_message(200, "success", msg_show="查询成功", bean=data), status_code=200)
