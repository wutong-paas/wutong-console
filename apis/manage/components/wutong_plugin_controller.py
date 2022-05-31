from typing import Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from clients.remote_plugin_client import remote_plugin_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_repo
from repository.plugin.service_plugin_repo import service_plugin_config_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.plugin.app_plugin_service import app_plugin_service
from service.plugin.plugin_version_service import plugin_version_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/pluginlist", response_model=Response, name="获取组件可用的插件列表")
async def get_plugin_list(request: Request,
                          serviceAlias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件可用的插件列表
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
        - name: category
          description: 插件类型 性能分析（analysis）| 网络治理（net_manage）
          required: true
          type: string
          paramType: query

    """
    category = request.query_params.get("category", "")
    if category:
        if category not in ("analysis", "net_manage"):
            return JSONResponse(general_message(400, "param can only be analysis or net_manage", "参数错误"),
                                status_code=400)
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    installed_plugins, not_install_plugins = service_plugin_config_repo.get_plugins_by_service_id(session=session,
                                                                                                  region=service.service_region,
                                                                                                  tenant_id=team.tenant_id,
                                                                                                  service_id=service.service_id,
                                                                                                  category=category)
    bean = {"installed_plugins": installed_plugins, "not_install_plugins": not_install_plugins}
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/plugins/{plugin_id}/install", response_model=Response,
             name="组件安装插件")
async def install_plugin(request: Request,
                         plugin_id: Optional[str] = None,
                         serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user),
                         team=Depends(deps.get_current_team)) -> Any:
    """
    组件安装插件
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
        - name: plugin_id
          description: 插件ID
          required: true
          type: string
          paramType: path
        - name: build_version
          description: 插件版本
          required: true
          type: string
          paramType: form
    """
    result = {}
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    data = await request.json()
    build_version = data.get("build_version", None)
    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin_id", "参数错误"), status_code=400)
    app_plugin_service.check_the_same_plugin(session=session, plugin_id=plugin_id, tenant_id=team.tenant_id,
                                             service_id=service.service_id)
    app_plugin_service.install_new_plugin(session=session, region=response_region, tenant=team, service=service,
                                          plugin_id=plugin_id, plugin_version=build_version, user=user)
    app_plugin_service.add_filemanage_port(session=session, tenant=team, service=service, plugin_id=plugin_id,
                                           user=user)
    app_plugin_service.add_filemanage_mount(session=session, tenant=team, service=service, plugin_id=plugin_id,
                                            plugin_version=build_version, user=user)

    result = general_message(200, "success", "安装成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/plugins/{plugin_id}/install", response_model=Response,
               name="组件卸载插件")
async def delete_plugin(plugin_id: Optional[str] = None,
                        serviceAlias: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user),
                        team=Depends(deps.get_current_team)) -> Any:
    """
    组件卸载插件
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
        - name: plugin_id
          description: 插件ID
          required: true
          type: string
          paramType: path
    """
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    response_region = region.region_name
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    body = dict()
    body["operator"] = user.nick_name
    remote_plugin_client.uninstall_service_plugin(session,
                                                  response_region, team.tenant_name, plugin_id,
                                                  service.service_alias, body)
    app_plugin_service.delete_service_plugin_relation(session=session, service=service, plugin_id=plugin_id)
    app_plugin_service.delete_service_plugin_config(session=session, service=service, plugin_id=plugin_id)
    app_plugin_service.delete_filemanage_service_plugin_port(session=session, team=team, service=service,
                                                             response_region=response_region, plugin_id=plugin_id,
                                                             user=user)

    return JSONResponse(general_message(200, "success", "卸载成功"), status_code=200)


@router.put("/teams/{team_name}/apps/{serviceAlias}/plugins/{plugin_id}/open", response_model=Response, name="启停组件插件")
async def open_or_stop_plugin(request: Request,
                              plugin_id: Optional[str] = None,
                              serviceAlias: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session),
                              team=Depends(deps.get_current_team)) -> Any:
    """
    启停用组件插件
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
        - name: plugin_id
          description: 插件ID
          required: true
          type: string
          paramType: path
        - name: is_switch
          description: 插件启停状态
          required: false
          type: boolean
          paramType: form
        - name: min_memory
          description: 插件内存
          required: false
          type: boolean
          paramType: form
    """
    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin_id", "参数异常"), status_code=400)
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    response_region = region.region_name
    data = await request.json()
    is_active = data.get("is_switch", True)
    service_plugin_relation = app_plugin_service.get_service_plugin_relation(session=session,
                                                                             service_id=service.service_id,
                                                                             plugin_id=plugin_id)
    if not service_plugin_relation:
        return JSONResponse(general_message(404, "not found plugin relation", "未找到组件使用的插件"), status_code=404)
    else:
        build_version = service_plugin_relation.build_version
    # 更新内存和cpu
    memory = data.get("min_memory")
    cpu = data.get("min_cpu")

    data = dict()
    data["plugin_id"] = plugin_id
    data["switch"] = is_active
    data["version_id"] = build_version
    if memory is not None:
        data["plugin_memory"] = int(memory)
    if cpu is not None:
        data["plugin_cpu"] = int(cpu)
    # 更新数据中心数据参数
    remote_plugin_client.update_plugin_service_relation(session,
                                                        response_region, team.tenant_name,
                                                        service.service_alias,
                                                        data)
    # 更新本地数据
    app_plugin_service.start_stop_service_plugin(session=session, service_id=service.service_id, plugin_id=plugin_id,
                                                 is_active=is_active, cpu=cpu, memory=memory)
    result = general_message(200, "success", "操作成功")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/plugins/{plugin_id}/configs", response_model=Response,
            name="启停组件插件")
async def get_plugin_config(request: Request,
                            plugin_id: Optional[str] = None,
                            serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    """
    组件插件查看配置
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
        - name: plugin_id
          description: 插件ID
          required: true
          type: string
          paramType: path
        - name: build_version
          description: 插件版本
          required: true
          type: string
          paramType: query
    """
    build_version = request.query_params.get("build_version", None)
    if not plugin_id or not build_version:
        logger.error("plugin.relation", '参数错误，plugin_id and version_id')
        return JSONResponse(general_message(400, "params error", "请指定插件版本"), status_code=400)
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    result_bean = app_plugin_service.get_service_plugin_config(session=session, tenant=team, service=service,
                                                               plugin_id=plugin_id, build_version=build_version)
    svc_plugin_relation = app_plugin_service.get_service_plugin_relation(session=session, service_id=service.service_id,
                                                                         plugin_id=plugin_id)
    pbv = plugin_version_service.get_by_id_and_version(session=session, tenant_id=team.tenant_id, plugin_id=plugin_id,
                                                       plugin_version=build_version)
    if pbv:
        result_bean["build_info"] = pbv.update_info
        result_bean["memory"] = svc_plugin_relation.min_memory if svc_plugin_relation else pbv.min_memory
    result = general_message(200, "success", "查询成功", bean=result_bean)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/apps/{serviceAlias}/plugins/{plugin_id}/configs", response_model=Response,
            name="更新组件插件配置")
async def update_plugin_config(request: Request,
                               plugin_id: Optional[str] = None,
                               serviceAlias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    """
    组件插件配置更新
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
        - name: plugin_id
          description: 插件ID
          required: true
          type: string
          paramType: path
        - name: body
          description: 配置内容
          required: true
          type: string
          paramType: body

    """
    config = await request.json()
    if not config:
        return JSONResponse(general_message(400, "params error", "参数配置不可为空"), status_code=400)
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return general_message(400, "not found region", "数据中心不存在")
    response_region = region.region_name
    service = service_repo.get_service(session, serviceAlias, team.tenant_id)
    pbv = plugin_version_service.get_newest_usable_plugin_version(session=session, tenant_id=team.tenant_id,
                                                                  plugin_id=plugin_id)
    if not pbv:
        return JSONResponse(general_message(400, "no usable plugin version", "无最新更新的版本信息，无法更新配置"), status_code=400)
    # update service plugin config
    app_plugin_service.update_service_plugin_config(session=session, tenant=team, service=service,
                                                    plugin_id=plugin_id, build_version=pbv.build_version, config=config,
                                                    response_region=response_region)
    result = general_message(200, "success", "配置更新成功")
    return JSONResponse(result, result["code"])
