from typing import Optional, Any

from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import JSONResponse

from clients.remote_app_client import remote_app_client
from clients.remote_build_client import remote_build_client
from common.base_client_service import get_tenant_region_info
from core import deps
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from repository.component.group_service_repo import service_repo
from schemas.response import Response
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/region/query", response_model=Response, name="获取团队数据中心")
async def get_query(team_name: Optional[str] = None, session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取团队数据中心(详细)
    """
    try:
        code = 200
        region_name_list = region_services.get_region_all_list_by_team_name(session=session, team_name=team_name)
        result = general_message(code, "query the data center is successful.", "数据中心获取成功",
                                 list=jsonable_encoder(region_name_list))
    except Exception as e:
        logger.exception(e)
        result = error_message("错误")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/region/unopen", response_model=Response, name="获取团队未开通的数据中心")
async def get_unopen_region(team_name: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    """
    获取团队未开通的数据中心
    ---
    parameters:
        - name: team_name
          description: 当前团队名字
          required: true
          type: string
          paramType: path
    """
    code = 200
    unopen_regions = region_services.get_team_unopen_region(session=session, team_name=team_name,
                                                            enterprise_id=team.enterprise_id)
    result = general_message(code, "query the data center is successful.", "数据中心获取成功", list=unopen_regions)
    return JSONResponse(result, status_code=code)


@router.post("/teams/{team_name}/region", response_model=Response, name="为团队开通数据中心")
async def open_region(request: Request,
                      session: SessionClass = Depends(deps.get_session),
                      team=Depends(deps.get_current_team)) -> Any:
    """
    为团队开通数据中心
    ---
    parameters:
        - name: team_name
          description: 当前团队名字
          required: true
          type: string
          paramType: path
        - name: region_name
          description: 要开通的数据中心名称
          required: true
          type: string
          paramType: body
    """
    data = await request.json()
    region_name = data.get("region_name", None)
    if not region_name:
        return JSONResponse(general_message(400, "params error", "参数异常"), status_code=400)
    region_services.create_tenant_on_region(session=session, enterprise_id=team.enterprise_id, team_name=team.team_name,
                                            region_name=region_name, namespace=team.namespace)
    result = general_message(200, "success", "数据中心{0}开通成功".format(region_name))
    return JSONResponse(result, result["code"])


@router.patch("/teams/{team_name}/region", response_model=Response, name="为团队开通数据中心")
async def open_regions(request: Request,
                       session: SessionClass = Depends(deps.get_session),
                       team=Depends(deps.get_current_team)) -> Any:
    """
    为团队批量开通数据中心
    """
    data = await request.json()
    region_names = data.get("region_names", None)
    if not region_names:
        result = general_message(400, "params error", "参数异常")
        return JSONResponse(result, result["code"])

    region_list = region_names.split(",")
    for region_name in region_list:
        region_services.create_tenant_on_region(session=session, enterprise_id=team.enterprise_id,
                                                team_name=team.tenant_name,
                                                region_name=region_name, namespace=team.namespace)
    result = general_message(200, "success", "批量开通数据中心成功")
    return JSONResponse(result, result["code"])


@router.get("/teams/{team_name}/regions/{region_name}/features", response_model=Response, name="获取指定数据中心的授权功能列表")
async def team_app_group(region_name: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """
    获取指定数据中心的授权功能列表
    ---

    """
    features = region_services.get_region_license_features(session=session, tenant=team, region_name=region_name)
    result = general_message(200, 'query success', '集群授权功能获取成功', list=features)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/regions/{region_name}/sort_domain/query", response_model=Response, name="获取团队下域名访问量排序")
async def get_sort_domain_query(request: Request,
                                region_name: Optional[str] = None,
                                team_name: Optional[str] = None,
                                team=Depends(deps.get_current_team),
                                session: SessionClass = Depends(deps.get_session)) -> Any:
    """
            获取团队下域名访问量排序
            ---
            parameters:
                - name: team_name
                  description: team name
                  required: true
                  type: string
                  paramType: path
            """
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 5))
    repo = request.query_params.get("repo", "1")

    if repo == "1":
        total_traffic = 0
        total = 0
        domain_list = []
        query = "?query=sort_desc(sum(%20ceil(increase(" \
                + "gateway_requests%7Bnamespace%3D%22{0}%22%7D%5B1h%5D)))%20by%20(host))"
        sufix = query.format(team.tenant_id)
        start = (page - 1) * page_size
        end = page * page_size
        try:
            res, body = remote_build_client.get_query_domain_access(session, region_name, team_name, sufix)
            total = len(body["data"]["result"])
            domains = body["data"]["result"]
            for domain in domains:
                total_traffic += int(domain["value"][1])
                domain_list = body["data"]["result"][start:end]
        except Exception as e:
            logger.debug(e)
        bean = {"total": total, "total_traffic": total_traffic}
        result = general_message(200, "success", "查询成功", list=domain_list, bean=bean)
        return JSONResponse(result, status_code=200)
    else:
        start = request.query_params.get("start", None)
        end = request.query_params.get("end", None)
        body = {}
        sufix = "?query=ceil(sum(increase(gateway_requests%7B" \
                + "namespace%3D%22{0}%22%7D%5B1h%5D)))&start={1}&end={2}&step=60".format(team.tenant_id, start,
                                                                                         end)
        try:
            res, body = remote_build_client.get_query_range_data(session, region_name, team_name, sufix)
        except Exception as e:
            logger.exception(e)
        result = general_message(200, "success", "查询成功", bean=body)
        return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/regions/{region_name}/sort_service/query", response_model=Response, name="获取团队下组件访问量排序")
async def get_sort_service_query(region_name: Optional[str] = None,
                                 team_name: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session),
                                 team=Depends(deps.get_current_team)) -> Any:
    """
            获取团队下组件访问量排序
            ---
            parameters:
                - name: team_name
                  description: team name
                  required: true
                  type: string
                  paramType: path
            """
    sufix_outer = "?query=sort_desc(sum(%20ceil(increase(" \
                  + "gateway_requests%7Bnamespace%3D%22{0}%22%7D%5B1h%5D)))%20by%20(service))".format(
        team.tenant_id)

    sufix_inner = "?query=sort_desc(sum(ceil(increase(app_request%7B" \
                  + "tenant_id%3D%22{0}%22%2Cmethod%3D%22total%22%7D%5B1h%5D)))by%20(service_id))".format(
        team.tenant_id)
    # 对外组件访问量
    try:
        res, body = remote_build_client.get_query_service_access(session, region_name, team_name, sufix_outer)
        outer_service_list = body["data"]["result"][0:10]
    except Exception as e:
        logger.debug(e)
        outer_service_list = []
    # 对外组件访问量
    try:
        res, body = remote_build_client.get_query_service_access(session, region_name, team_name, sufix_inner)
        inner_service_list = body["data"]["result"][0:10]
    except Exception as e:
        logger.debug(e)
        inner_service_list = []

    # 合并
    service_id_list = []
    for service in outer_service_list:
        service_id_list.append(service["metric"]["service"])
    for service_oj in inner_service_list:
        if service_oj["metric"]["service"] not in service_id_list:
            service_id_list.append(service_oj["metric"]["service"])
    service_traffic_list = []
    for service_id in service_id_list:
        service_dict = dict()
        metric = dict()
        value = []
        service_dict["metric"] = metric
        service_dict["value"] = value
        traffic_num = 0
        v1 = 0
        for service in outer_service_list:
            if service["metric"]["service"] == service_id:
                traffic_num += int(service["value"][1])
                v1 = service["value"][0]
        for service_oj in inner_service_list:
            if service_oj["metric"]["service"] == service_id:
                traffic_num += int(service_oj["value"][1])
                v1 = service_oj["value"][0]
        metric["service"] = service_id
        value.append(v1)
        value.append(traffic_num)
        service_traffic_list.append(service_dict)
    for service_traffic in service_traffic_list[::-1]:
        service_obj = service_repo.get_service_by_service_id(session, service_traffic["metric"]["service"])
        if service_obj:
            service_traffic["metric"]["service_cname"] = service_obj.service_cname
            service_traffic["metric"]["service_alias"] = service_obj.service_alias
        if not service_obj:
            service_traffic_list.remove(service_traffic)
    # 排序取前十
    service_list = sorted(service_traffic_list, key=lambda x: x["value"][1], reverse=True)[0:10]

    result = general_message(200, "success", "查询成功", list=service_list)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/protocols", response_model=Response, name="获取数据中心支持的协议")
async def get_protocol_info(request: Request,
                            region_name: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    """
     获取数据中心支持的协议
     ---
     parameters:
         - name: tenantName
           description: 团队名称
           required: true
           type: string
           paramType: path
         - name: region_name
           description: 数据中心名称
           required: false
           type: string
           paramType: query
     """
    try:
        region_name = request.query_params.get("region_name", region_name)
        protocols_info = remote_build_client.get_protocols(session, region_name, team.tenant_name)
        protocols = protocols_info["list"]
        p_list = []
        for p in protocols:
            p_list.append(p["protocol_child"])
        result = general_message(200, "success", "查询成功", list=list(set(p_list)))
    except Exception as e:
        logger.exception(e)
        result = general_message(200, "", "查询成功", list=["http", "stream"])
    return JSONResponse(result, 200)


@router.get("/teams/{team_name}/regions/{region_name}/publickey", response_model=Response, name="获取指定数据中心的Key")
async def get_region_key(
        region_name: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    获取指定数据中心的Key
    ---

    """
    key = region_services.get_public_key(session, team, region_name)
    result = general_message(200, 'query success', '数据中心key获取成功', bean=key)
    return JSONResponse(result, status_code=200)


@router.api_route(
    "/filebrowser/{service_id}/{url:path}",
    methods=[
        "post",
        "get",
        "delete",
        "put"],
    include_in_schema=False,
    response_model=Response, name="文件管理")
async def file_manager(
        request: Request,
        service_id: Optional[str] = None,
        url: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    try:
        if request.method != "GET":
            body = await request.json()
        else:
            body = {}
        service = service_repo.get_service_by_service_id(session, service_id)
        response = await remote_app_client.proxy(session, request,
                                                 '/console/filebrowser/3fb2485d78954e29aad2fa693302cc43/' + url,
                                                 service.service_region,
                                                 body)
    except Exception as exc:
        logger.exception(exc)
        response = None
    # response = self.finalize_response(request, response, *args, **kwargs)
    return response
