import base64
import os
import pickle
from typing import Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.return_message import general_message
from core.utils.validation import validate_endpoints_info
from database.session import SessionClass
from exceptions.bcode import ErrK8sComponentNameExists
from exceptions.main import ServiceHandleException, CheckThirdpartEndpointFailed
from models.component.models import ThirdPartyComponentEndpoints
from repository.component.deploy_repo import deploy_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import service_endpoints_repo
from repository.component.third_party_repo import third_party_repo
from repository.teams.env_repo import env_repo
from schemas.components import ThirdPartyCreateParam
from schemas.response import Response
from service.app_config.port_service import endpoint_service
from service.application_service import application_service
from service.region_service import region_services

router = APIRouter()


@router.post("/teams/{team_name}/env/{env_id}/apps/third_party", response_model=Response, name="第三方组件创建")
async def third_party(request: Request,
                      params: Optional[ThirdPartyCreateParam] = ThirdPartyCreateParam(),
                      session: SessionClass = Depends(deps.get_session),
                      user=Depends(deps.get_current_user),
                      env=Depends(deps.get_current_team_env)) -> Any:
    """
    创建第三方组件

    """

    region_name = env.region_code

    endpoints_type = params.endpoints_type
    # todo 驼峰
    service_name = params.serviceName
    k8s_component_name = params.k8s_component_name
    if k8s_component_name and application_service.is_k8s_component_name_duplicate(session,
                                                                                  params.group_id,
                                                                                  k8s_component_name):
        raise ErrK8sComponentNameExists

    if not params.service_cname:
        return JSONResponse(general_message(400, "service_cname is null", "组件名未指明"), status_code=400)
    if endpoints_type == "static":
        validate_endpoints_info(params.static)
    source_config = {}
    if endpoints_type == "kubernetes":
        if not service_name:
            return JSONResponse(general_message(400, "kubernetes service name is null", "Kubernetes Service名称必须指定"),
                                status_code=400)
        source_config = {"service_name": service_name, "namespace": params.namespace}
    new_service = application_service.create_third_party_app(session=session, region=region_name, tenant_env=env,
                                                             user=user,
                                                             service_cname=params.service_cname,
                                                             static_endpoints=params.static,
                                                             endpoints_type=endpoints_type, source_config=source_config,
                                                             k8s_component_name=k8s_component_name)
    # 添加组件所在组
    code, msg_show = application_service.add_component_to_app(session=session, tenant_env=env, region_name=region_name,
                                                              app_id=params.group_id,
                                                              component_id=new_service.service_id)
    if code != 200:
        new_service.delete()
        raise ServiceHandleException(
            msg="add component to app failure", msg_show=msg_show, status_code=code, error_code=code)
    bean = new_service.__dict__
    if endpoints_type == "api":
        # 生成秘钥
        deploy = deploy_repo.get_deploy_relation_by_service_id(session=session, service_id=new_service.service_id)
        api_secret_key = pickle.loads(base64.b64decode(deploy)).get("secret_key")
        # 从环境变量中获取域名，没有在从请求中获取
        host = os.environ.get('DEFAULT_DOMAIN', "http://" + request.client.host)
        api_url = host + "/console/" + "third_party/{0}".format(new_service.service_id)
        bean["api_service_key"] = api_secret_key
        bean["url"] = api_url

        endpoints = third_party_repo.get_one_by_model(session=session, query_model=ThirdPartyComponentEndpoints(
            service_id=new_service.service_id))

        if not endpoints:
            data = {
                "tenant_env_id": env.env_id,
                "service_id": new_service.service_id,
                "service_cname": new_service.service_cname,
                "endpoints_info": "",
                "endpoints_type": "api"
            }
            add_model: ThirdPartyComponentEndpoints = ThirdPartyComponentEndpoints(**data)
            session.add(add_model)
    result = general_message("0", "success", "创建成功", bean=bean)
    return result


@router.get("/teams/{team_name}/env/{env_id}/apps/{service_alias}/third_party/pods",
            response_model=Response, name="获取第三方组件实例信息")
async def get_third_party_pods(
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service_by_service_alias(session=session, service_alias=service_alias)
    res, body = remote_build_client.get_third_party_service_pods(session,
                                                                 service.service_region, env,
                                                                 service.service_alias)
    if res.status != 200:
        return JSONResponse(general_message(412, "region error", "数据中心查询失败"), status_code=412)
    endpoint_list = body["list"]
    for endpoint in endpoint_list:
        endpoint["ip"] = endpoint["address"]
    bean = {"endpoint_num": len(endpoint_list)}

    result = general_message("0", "success", "查询成功", list=endpoint_list, bean=bean)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{service_alias}/third_party/pods",
             response_model=Response, name="添加第三方组件实例信息")
async def add_third_party_pods(
        request: Request,
        env_id: Optional[str] = None,
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    data = await request.json()
    address = data.get("ip", None)
    if not address:
        return JSONResponse(general_message(400, "end_point is null", "end_point未指明"), status_code=400)
    service = service_info_repo.get_service_by_service_alias(session=session, service_alias=service_alias)
    validate_endpoints_info([address])
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    try:
        endpoint_service.add_endpoint(session, env, service, address)
    except CheckThirdpartEndpointFailed as e:
        session.rollback()
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)

    result = general_message("0", "success", "添加成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{service_alias}/third_party/pods",
               response_model=Response, name="删除第三方组件实例信息")
async def delete_third_party_pods(request: Request,
                                  env_id: Optional[str] = None,
                                  service_alias: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session)) -> Any:
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    ep_id = data.get("ep_id", None)
    if not ep_id:
        return JSONResponse(general_message(400, "end_point is null", "end_point未指明"), status_code=400)
    endpoint_dict = dict()
    endpoint_dict["ep_id"] = ep_id
    service = service_info_repo.get_service_by_service_alias(session=session, service_alias=service_alias)

    response_region = env.region_code
    res, body = remote_build_client.delete_third_party_service_endpoints(session,
                                                                         response_region, env,
                                                                         service.service_alias, endpoint_dict)
    res, new_body = remote_build_client.get_third_party_service_pods(session,
                                                                     service.service_region, env,
                                                                     service.service_alias)
    new_endpoint_list = new_body.get("list", [])
    new_endpoints = [endpoint.address for endpoint in new_endpoint_list]
    service_endpoints_repo.update_or_create_endpoints(session, env, service, new_endpoints)
    logger.debug('-------res------->{0}'.format(res))
    logger.debug('=======body=======>{0}'.format(body))

    if res.status != 200:
        return JSONResponse(general_message(412, "region delete error", "数据中心删除失败"), status_code=412)
    # service_endpoints_repo.delete_service_endpoints_by_service_id(self.service.service_id)
    result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)
