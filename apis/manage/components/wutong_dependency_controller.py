from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.app_relation_service import dependency_service
from service.app_config.port_service import port_service
from service.application_service import application_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/dependency", response_model=Response, name="获取组件依赖的组件")
async def get_dependency_component(request: Request,
                                   serviceAlias: Optional[str] = None,
                                   session: SessionClass = Depends(deps.get_session),
                                   env=Depends(deps.get_current_team_env)) -> Any:
    """
     获取组件依赖的组件
     ---
     parameters:
         - name: tenantName
           description: 租户名
           required: true
           type: string
           paramType: path
         - name: serviceAlias
           description: 组件别名
           required: true
           type: string
           paramType: path
         - name: page
           description: 页码
           required: false
           type: string
           paramType: query
         - name: page_size
           description: 每页数量
           required: false
           type: string
           paramType: query
     """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    page_num = int(request.query_params.get("page", 1))
    if page_num < 1:
        page_num = 1
    page_size = int(request.query_params.get("page_size", 25))
    dependencies = dependency_service.get_service_dependencies(session=session, tenant_env=env, service=service)
    service_ids = [s.service_id for s in dependencies]
    service_group_map = application_service.get_services_group_name(session=session, service_ids=service_ids)
    dep_list = []
    for dep in dependencies:
        tenant_service_ports = port_service.get_service_ports(session=session, service=dep)
        ports_list = []
        if tenant_service_ports:
            for port in tenant_service_ports:
                ports_list.append(port.container_port)
        dep_service_info = {
            "service_cname": dep.service_cname,
            "service_id": dep.service_id,
            "service_type": dep.service_type,
            "service_alias": dep.service_alias,
            "group_name": service_group_map[dep.service_id]["group_name"],
            "group_id": service_group_map[dep.service_id]["group_id"],
            "ports_list": ports_list,
            "project_id": service_group_map[dep.service_id]["project_id"],
            "env_id": service_group_map[dep.service_id]["env_id"],
            "region_code": service_group_map[dep.service_id]["region_code"],
        }
        dep_list.append(dep_service_info)
    start = (page_num - 1) * page_size
    end = page_num * page_size
    if start >= len(dep_list):
        start = len(dep_list) - 1
        end = len(dep_list) - 1
    rt_list = dep_list[start:end]

    service_ports = port_service.get_service_ports(session=session, service=service)
    port_list = []
    if service_ports:
        for port in service_ports:
            port_list.append(port.container_port)
    bean = {"port_list": port_list, 'total': len(dep_list)}
    result = general_message("0", "success", "查询成功", list=rt_list, total=len(dep_list), bean=bean)
    return JSONResponse(result, status_code=200)


@router.patch("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/dependency", response_model=Response, name="为组件添加依赖组件")
async def add_dependency_component(request: Request,
                                   serviceAlias: Optional[str] = None,
                                   session: SessionClass = Depends(deps.get_session),
                                   user=Depends(deps.get_current_user),
                                   env=Depends(deps.get_current_team_env)) -> Any:
    """
    为组件添加依赖组件
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: dep_service_ids
          description: 依赖的组件的id,多个依赖的组件id，以英文逗号分隔
          required: true
          type: string
          paramType: form

    """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    data = await request.json()
    dep_service_ids = data.get("dep_service_ids", None)
    if not dep_service_ids:
        return JSONResponse(general_message(400, "dependency service not specify", "请指明需要依赖的组件"), status_code=400)
    if service.is_third_party():
        raise AbortRequest(msg="third-party components cannot add dependencies", msg_show="第三方组件不能添加依赖组件")
    dep_service_list = dep_service_ids.split(",")
    code, msg = dependency_service.patch_add_dependency(session=session, tenant_env=env, service=service,
                                                        dep_service_ids=dep_service_list, user_name=user.nick_name)
    if code != 200:
        result = general_message(code, "add dependency error", msg)
        return JSONResponse(result, status_code=code)
    result = general_message(code, msg, "依赖添加成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/dependency/{dep_service_id}",
               response_model=Response,
               name="删除组件的某个依赖")
async def delete_dependency_component(
        serviceAlias: Optional[str] = None,
        dep_service_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件的某个依赖
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: dep_service_id
          description: 需要删除的组件ID
          required: true
          type: string
          paramType: path

    """
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    if not dep_service_id:
        return JSONResponse(general_message(400, "attr_name not specify", "未指定需要删除的依赖组件"), status_code=400)
    code, msg, dependency = dependency_service.delete_service_dependency(session=session, tenant_env=env,
                                                                         service=service, dep_service_id=dep_service_id,
                                                                         user_name=user.nick_name)
    if code != 200:
        return JSONResponse(general_message(code, "delete dependency error", msg), status_code=code)

    result = general_message("0", "success", "删除成功", bean=jsonable_encoder(dependency))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/dependency", response_model=Response,
             name="为组件添加依赖组件")
async def add_dependency_component_post(request: Request,
                                        env_id: Optional[str] = None,
                                        serviceAlias: Optional[str] = None,
                                        session: SessionClass = Depends(deps.get_session),
                                        user=Depends(deps.get_current_user)) -> Any:
    """
    为组件添加依赖组件
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
        - name: serviceAlias
          description: 组件别名
          required: true
          type: string
          paramType: path
        - name: dep_service_id
          description: 依赖的组件的id
          required: true
          type: string
          paramType: form


    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    dep_service_id = data.get("dep_service_id", None)
    open_inner = data.get("open_inner", False)
    container_port = data.get("container_port", None)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    if not dep_service_id:
        return JSONResponse(general_message(400, "dependency service not specify", "请指明需要依赖的组件"), status_code=400)
    if service.is_third_party():
        raise AbortRequest(msg="third-party components cannot add dependencies", msg_show="第三方组件不能添加依赖组件")
    if dep_service_id == service.service_id:
        raise AbortRequest(msg="components cannot rely on themselves", msg_show="组件不能依赖自己")
    code, msg, data = dependency_service.add_service_dependency(session,
                                                                env, service, dep_service_id, open_inner,
                                                                container_port, user.nick_name)
    if code == 201:
        result = general_message(code, "add dependency success", msg, list=data, bean={"is_inner": False})
        return JSONResponse(result, status_code=code)
    if code != 200:
        result = general_message(code, "add dependency error", msg, list=data)
        return JSONResponse(result, status_code=code)
    result = general_message(code, msg, "依赖添加成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=200)
