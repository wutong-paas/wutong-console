import re
from typing import Any, Optional

from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse

from core import deps
from core.utils.constants import DomainType
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_repo
from repository.component.service_domain_repo import domain_repo
from schemas.response import Response
from service.app_config.domain_service import domain_service

router = APIRouter()
dns1123_subdomain_max_length = 253


def validate_domain(domain):
    if len(domain) > dns1123_subdomain_max_length:
        return False, "域名长度不能超过{}".format(dns1123_subdomain_max_length)

    dns1123_label_fmt = "[a-z0-9]([-a-z0-9]*[a-z0-9])?"
    dns1123_subdomain_fmt = dns1123_label_fmt + "(\\." + dns1123_label_fmt + ")*"
    fmt = "^" + dns1123_subdomain_fmt + "$"
    wildcard_dns1123_subdomain_fmt = "\\*\\." + dns1123_subdomain_fmt
    wildcard_fmt = "^" + wildcard_dns1123_subdomain_fmt + "$"
    if domain.startswith("*"):
        pattern = re.compile(wildcard_fmt)
    else:
        pattern = re.compile(fmt)
    if not pattern.match(domain):
        return False, "非法域名"
    return True, ""


@router.post("/teams/{team_name}/apps/{serviceAlias}/domain", response_model=Response, name="组件端口添加域名")
async def get_dependency_component(request: Request,
                                   serviceAlias: Optional[str] = None,
                                   session: SessionClass = Depends(deps.get_session),
                                   user=Depends(deps.get_current_user),
                                   team=Depends(deps.get_current_team)) -> Any:
    """
    组件端口绑定域名
    ---
    parameters:
        - name: tenantName
          description: 团队名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: domain_name
          description: 域名
          required: true
          type: string
          paramType: form
        - name: container_port
          description: 组件端口
          required: true
          type: string
          paramType: form
        - name: protocol
          description: 端口协议（http,https,httptohttps,httpandhttps）
          required: true
          type: string
          paramType: form
        - name: certificate_id
          description: 证书ID
          required: false
          type: string
          paramType: form

    """
    data = await request.json()
    container_port = data.get("container_port", None)
    domain_name = data.get("domain_name", None)
    flag, msg = validate_domain(domain_name)
    if not flag:
        result = general_message(400, "invalid domain", msg)
        return JSONResponse(result, status_code=400)
    protocol = data.get("protocol", None)
    certificate_id = data.get("certificate_id", None)
    rule_extensions = data.get("rule_extensions", None)

    service = service_repo.get_service(session, serviceAlias, team.tenant_id)

    # 判断策略是否存在
    service_domain = domain_repo.get_domain_by_name_and_port_and_protocol(session,
                                                                          service.service_id, container_port,
                                                                          domain_name, protocol)
    if service_domain:
        result = general_message(400, "failed", "策略已存在")
        return JSONResponse(result, status_code=400)

    domain_service.bind_domain(session=session, tenant=team, user=user, service=service, domain_name=domain_name,
                               container_port=container_port, protocol=protocol,
                               certificate_id=certificate_id,
                               domain_type=DomainType.WWW, rule_extensions=rule_extensions)
    # htt与https共存的协议需存储两条数据(创建完https数据再创建一条http数据)
    if protocol == "httpandhttps":
        certificate_id = 0
        domain_service.bind_domain(session=session, tenant=team, user=user, service=service, domain_name=domain_name,
                                   container_port=container_port, protocol=protocol,
                                   certificate_id=certificate_id,
                                   domain_type=DomainType.WWW, rule_extensions=rule_extensions)
    result = general_message(200, "success", "域名绑定成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/domain", response_model=Response, name="组件端口解绑域名")
async def delete_port_domain(request: Request,
                             serviceAlias: Optional[str] = None,
                             session: SessionClass = Depends(deps.get_session),
                             team=Depends(deps.get_current_team)) -> Any:
    """
    组件端口解绑域名
    ---
    parameters:
        - name: tenantName
          description: 团队名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: domain_name
          description: 域名
          required: true
          type: string
          paramType: form
        - name: container_port
          description: 组件端口
          required: true
          type: string
          paramType: form

    """
    data = await request.json()
    container_port = data.get("container_port", None)
    domain_name = data.get("domain_name", None)
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    flag, msg = validate_domain(domain_name)
    if not flag:
        result = general_message(400, "invalid domain", msg)
        return JSONResponse(result, status_code=400)
    is_tcp = data.get("is_tcp", False)
    if not container_port or not domain_name:
        return JSONResponse(general_message(400, "params error", "参数错误"), status_code=400)
    domain_service.unbind_domain(session=session, tenant=team, service=service, container_port=container_port,
                                 domain_name=domain_name, is_tcp=is_tcp)
    result = general_message(200, "success", "域名解绑成功")
    return JSONResponse(result, status_code=result["code"])
