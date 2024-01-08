import json
from typing import Any, Optional
from service.application_service import application_service
from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from service.app_actions.app_manage import app_manage_service
from clients.remote_plugin_client import remote_plugin_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import ServiceHandleException, ResourceNotEnoughException
from repository.application.application_repo import application_repo
from repository.component.app_component_relation_repo import app_component_relation_repo
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import volume_repo
from repository.plugin.plugin_config_repo import config_group_repo, config_item_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo
from repository.plugin.service_plugin_repo import service_plugin_config_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_plugin_repo import plugin_repo
from schemas.plugin import InstallPlugin, BatchInstallPlugin, UpdatePluginConfig
from schemas.response import Response
from service.plugin.app_plugin_service import app_plugin_service
from service.plugin.plugin_version_service import plugin_version_service
from service.plugin_service import default_plugins, plugin_service
from service.region_service import region_services

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/pluginlist", response_model=Response,
            name="获取组件可用的插件列表")
async def get_plugin_list(request: Request,
                          serviceAlias: Optional[str] = None,
                          session: SessionClass = Depends(deps.get_session),
                          env=Depends(deps.get_current_team_env),
                          user=Depends(deps.get_current_user)) -> Any:
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
    origin = request.query_params.get("origin", "sys")
    if origin:
        if origin not in ("sys", "tenant", "shared"):
            return JSONResponse(general_message(400, "param can only be sys or tenant、shared", "参数错误"),
                                status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    installed_plugins, not_install_plugins = service_plugin_config_repo.get_plugins_by_origin(session=session,
                                                                                              region=service.service_region,
                                                                                              tenant_env=env,
                                                                                              service=service,
                                                                                              origin=origin,
                                                                                              user=user)
    bean = {"installed_plugins": installed_plugins, "not_install_plugins": not_install_plugins}
    result = general_message("0", "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=200)


@router.get("/teams/pluginlist", response_model=Response,
            name="获取系统插件列表")
async def get_plugin_list() -> Any:
    """
    获取系统插件列表
    """
    plugins = service_plugin_config_repo.get_sys_plugins_by_origin()
    bean = {"sys_plugins": plugins}
    result = general_message("0", "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/plugins/services", response_model=Response,
            name="查询组件列表")
async def get_service_list(
        plugin_id: Optional[str] = None,
        plugin_type: Optional[str] = None,
        env=Depends(deps.get_current_team_env),
        session: SessionClass = Depends(deps.get_session)) -> Any:
    if not plugin_id and not plugin_type:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

    apps_data = []
    if not plugin_id:
        plugins = plugin_service.get_by_type_plugins(session, plugin_type, "sys", env.region_code)
        for plugin in plugins:
            plugin_id = plugin.plugin_id
    apps = application_repo.get_groups_by_env_id(session, env.env_id)
    for app in apps:
        app_id = app.app_id
        app_name = app.group_name
        services_data = []
        gsr = app_component_relation_repo.get_services_by_group(session, app_id)
        service_ids = [service.service_id for service in gsr]
        services = service_info_repo.list_by_component_ids(session, service_ids)
        for service in services:
            status = True
            service_id = service.service_id
            service_name = service.service_cname
            if plugin_id:
                sprs = app_plugin_relation_repo.get_relation_by_service_and_plugin(session=session,
                                                                                   service_id=service_id,
                                                                                   plugin_id=plugin_id)
                if sprs:
                    status = False
            service_data = {"service_id": service_id, "service_name": service_name, "status": status}
            services_data.append(service_data)
        apps_data.append({"app_name": app_name, "app_id": app_id, "services": services_data})
    result = general_message("0", "success", "查询成功", list=apps_data)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/plugins/batch-install", response_model=Response,
             name="批量开通插件")
async def install_sys_plugin(request: Request,
                             params: Optional[BatchInstallPlugin] = BatchInstallPlugin(),
                             env=Depends(deps.get_current_team_env),
                             session: SessionClass = Depends(deps.get_session),
                             user=Depends(deps.get_current_user)) -> Any:
    service_ids = params.service_ids
    build_version = params.build_version
    plugin_id = params.plugin_id
    err_msg = []
    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin_id", "参数错误"), status_code=400)

    response_region = env.region_code

    for service_id in service_ids:
        service = service_info_repo.get_service_by_tenant_and_id(session, env.env_id, service_id)
        try:
            app_plugin_service.check_the_same_plugin(session=session, plugin_id=plugin_id, tenant_env_id=env.env_id,
                                                     service_id=service.service_id)
            app_plugin_service.install_new_plugin(session=session, region=response_region, tenant_env=env,
                                                  service=service,
                                                  plugin_id=plugin_id, plugin_version=build_version, user=user)
        except ServiceHandleException as e:
            msg = {
                "err_msg": e.msg_show,
                "service_id": service.service_id,
            }
            err_msg.append(msg)
        except Exception as e:
            logger.error(e)
            msg = {
                "service_id": "未知错误"
            }
            err_msg.append(msg)

    result = general_message("0", "success", "安装成功", list=err_msg)
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/sys/install", response_model=Response,
             name="安装并开通系统插件")
async def install_sys_plugin(
        params: Optional[InstallPlugin] = InstallPlugin(),
        env=Depends(deps.get_current_team_env),
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    plugin_type = params.plugin_type
    build_version = params.build_version
    configs = params.configs

    if not plugin_type:
        return JSONResponse(general_message(400, "plugin type is null", "请指明插件类型"), status_code=400)
    if plugin_type not in default_plugins:
        return JSONResponse(general_message(400, "plugin type not support", "插件类型不支持"), status_code=400)

    response_region = env.region_code
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    plugins = plugin_service.get_by_type_plugins(session, plugin_type, "sys", service.service_region)
    if not plugins:
        plugin_id = plugin_service.add_default_plugin(session=session, user=user, tenant_env=env,
                                                      region=response_region,
                                                      plugin_type=plugin_type, build_version=build_version)
    else:
        plugin_id = None
        for plugin in plugins:
            plugin_id = plugin.plugin_id
            pbvs = plugin_version_repo.get_plugin_versions(session, plugin_id)
            if pbvs:
                for pbv in pbvs:
                    # 判断存储是否已存在
                    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)
                    if plugin_info:
                        if plugin_info.origin_share_id == "java_agent_plugin":
                            volume = volume_repo.get_service_volume_by_path(session, service.service_id, "/agent")
                            if volume:
                                return JSONResponse(general_message(500, "path already exists", "持久化路径[/agent]已存在"),
                                                    status_code=501)
                    # 判断是否需要更新
                    if pbv.build_version != build_version:
                        all_default_config = service_plugin_config_repo.all_default_config
                        config_item_repo.delete_item_by_id(session=session, plugin_id=plugin_id)
                        plugin_version_repo.delete_version_by_id(session=session, plugin_id=plugin_id)
                        config_group_repo.delete_config_group_by_plugin_id(session=session,
                                                                           plugin_id=plugin_id)

                        needed_plugin_config = all_default_config[plugin_type]
                        plugin.image = needed_plugin_config.get("image", "")
                        plugin.build_source = needed_plugin_config.get("build_source", "")
                        plugin.plugin_alias = needed_plugin_config["plugin_alias"]
                        plugin.category = needed_plugin_config["category"]
                        plugin.code_repo = needed_plugin_config["code_repo"]
                        plugin_build_version = service_plugin_config_repo.update_sys_plugin(session, plugin, env,
                                                                                            plugin_type,
                                                                                            user,
                                                                                            service.service_region,
                                                                                            needed_plugin_config,
                                                                                            build_version)
                        try:
                            plugin_repo.build_plugin(session=session, region=service.service_region, plugin=plugin,
                                                     plugin_version=plugin_build_version, user=user,
                                                     tenant_env=env,
                                                     event_id=plugin_build_version.event_id)
                        except remote_plugin_client.CallApiError as e:
                            logger.error(e)
                            if "body" in e.message and "msg" in e.message["body"]:
                                return JSONResponse(general_message(500, "failed", e.message["body"]["msg"]),
                                                    status_code=501)
                            return JSONResponse(general_message(500, "failed", "开通失败"), status_code=501)
                        except Exception as e:
                            logger.error(e)
                            return JSONResponse(general_message(500, "failed", "开通失败"), status_code=501)
                        plugin_build_version.build_status = "build_success"

        if not plugin_id:
            plugin_id = plugin_service.add_default_plugin(session=session, user=user, tenant_env=env,
                                                          region=response_region,
                                                          plugin_type=plugin_type, build_version=build_version)

    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin", "未找到插件"), status_code=400)
    app_plugin_service.check_the_same_plugin(session=session, plugin_id=plugin_id, tenant_env_id=None,
                                             service_id=service.service_id)
    app_plugin_service.install_new_plugin(session=session, region=response_region, tenant_env=env, service=service,
                                          plugin_id=plugin_id, plugin_version=build_version, user=user)

    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)
    app_plugin_service.add_filemanage_port(session=session, tenant_env=env, service=service, plugin_info=plugin_info,
                                           user=user)
    app_plugin_service.add_filemanage_mount(session=session, tenant_env=env, service=service, plugin_info=plugin_info,
                                            plugin_id=plugin_id, plugin_version=build_version, user=user)
    app_plugin_service.add_init_agent_mount(session=session, tenant_env=env, service=service, user=user,
                                            plugin_info=plugin_info)

    app_plugin_service.update_obs_monitor(service=service, plugin_info=plugin_info, operate="install")

    # 配置插件环境变量
    app_plugin_service.update_plugin_configs(session=session, env=env, service=service, plugin_info=plugin_info,
                                             plugin_id=plugin_id, build_version=build_version, config=configs,
                                             user=user, memory=params.min_memory, cpu=params.min_cpu)

    result = general_message("0", "success", "安装成功")
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/{plugin_id}/install", response_model=Response,
             name="组件安装插件")
async def install_plugin(request: Request,
                         env_id: Optional[str] = None,
                         plugin_id: Optional[str] = None,
                         serviceAlias: Optional[str] = None,
                         params: Optional[InstallPlugin] = InstallPlugin(),
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user)) -> Any:
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
    configs = params.configs
    build_version = params.build_version

    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    response_region = env.region_code
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)

    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin_id", "参数错误"), status_code=400)
    pbv = plugin_version_repo.get_by_id_and_version(session, plugin_id, build_version)
    if not pbv:
        return JSONResponse(general_message(400, "no usable plugin version", "无最新更新的版本信息，无法更新配置"), status_code=400)

    if pbv.build_status == "building":
        status = plugin_version_service.get_region_plugin_build_status(session, response_region, env,
                                                                       pbv.plugin_id,
                                                                       pbv.build_version)
        pbv.build_status = status
        if status == "building":
            result = general_message(400, "failed", "插件正在构建中,请稍后再试")
            return JSONResponse(result, status_code=result["code"])
    if pbv.build_status != "build_success":
        result = general_message(400, "failed", "插件构建失败,不能开通")
        return JSONResponse(result, status_code=result["code"])

    app_plugin_service.check_the_same_plugin(session=session, plugin_id=plugin_id, tenant_env_id=env.env_id,
                                             service_id=service.service_id)
    app_plugin_service.install_new_plugin(session=session, region=response_region, tenant_env=env, service=service,
                                          plugin_id=plugin_id, plugin_version=build_version, user=user)

    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)
    # 配置插件环境变量
    app_plugin_service.update_plugin_configs(session=session, env=env, service=service, plugin_info=plugin_info,
                                             plugin_id=plugin_id, build_version=build_version, config=configs,
                                             user=user, memory=params.min_memory, cpu=params.min_cpu)

    result = general_message("0", "success", "安装成功")
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/{plugin_id}/install",
               response_model=Response,
               name="组件卸载插件")
async def delete_plugin(
        request: Request,
        env_id: Optional[str] = None,
        plugin_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
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
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)

    response_region = env.region_code
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    body = dict()
    body["operator"] = user.nick_name
    plugin = plugin_repo.get_plugin_detail_by_plugin_id(session, plugin_id)
    if plugin.origin == 'sys':
        result_bean = service_plugin_config_repo.get_sys_service_plugin_config(session, plugin_id)
    else:
        result_bean = service_plugin_config_repo.get_service_plugin_config(session, service.service_id, plugin_id)
    remote_plugin_client.uninstall_service_plugin(session,
                                                  response_region, env, plugin_id,
                                                  service.service_alias, body)
    app_plugin_service.delete_service_plugin_relation(session=session, service=service, plugin_id=plugin_id)
    app_plugin_service.delete_service_plugin_config(session=session, service=service, plugin_id=plugin_id)

    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)

    if result_bean:
        attrs = json.loads(result_bean.attrs)

        config_attr_port = attrs.get("FB_PORT")

        if not config_attr_port:
            config_attr_port = attrs.get("PORT")

        app_plugin_service.delete_filemanage_service_plugin_port(session=session, tenant_env=env, service=service,
                                                                 response_region=response_region,
                                                                 plugin_info=plugin_info,
                                                                 container_port=config_attr_port, user=user)

    app_plugin_service.delete_java_agent_plugin_volume(session=session, env=env, service=service,
                                                       volume_path="/agent", user=user, plugin_info=plugin_info)

    app_plugin_service.update_obs_monitor(service=service, operate="uninstall", plugin_info=plugin_info)

    return JSONResponse(general_message("0", "success", "卸载成功"), status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/{plugin_id}/open", response_model=Response,
            name="启停组件插件")
async def open_or_stop_plugin(request: Request,
                              env_id: Optional[str] = None,
                              plugin_id: Optional[str] = None,
                              serviceAlias: Optional[str] = None,
                              user=Depends(deps.get_current_user),
                              session: SessionClass = Depends(deps.get_session)) -> Any:
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
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if not plugin_id:
        return JSONResponse(general_message(400, "not found plugin_id", "参数异常"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    data = await request.json()
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
    is_switch = data.get("is_switch")

    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)
    app_plugin_service.update_plugin_cpu_mem(session=session, service=service, plugin_id=plugin_id, memory=memory,
                                             cpu=cpu, build_version=build_version, user=user, env=env,
                                             is_switch=is_switch, plugin_info=plugin_info)
    result = general_message("0", "success", "操作成功")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/{plugin_id}/configs", response_model=Response,
            name="启停组件插件")
async def get_plugin_config(request: Request,
                            plugin_id: Optional[str] = None,
                            serviceAlias: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            env=Depends(deps.get_current_team_env)) -> Any:
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
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    result_bean = app_plugin_service.get_service_plugin_config(session=session, tenant_env=env, service=service,
                                                               plugin_id=plugin_id, build_version=build_version)
    svc_plugin_relation = app_plugin_service.get_service_plugin_relation(session=session, service_id=service.service_id,
                                                                         plugin_id=plugin_id)
    pbv = plugin_version_service.get_by_id_and_version(session=session, tenant_env_id=env.env_id, plugin_id=plugin_id,
                                                       plugin_version=build_version)
    if pbv:
        result_bean["build_info"] = pbv.update_info
        result_bean["memory"] = svc_plugin_relation.min_memory if svc_plugin_relation else pbv.min_memory
    result = general_message("0", "success", "查询成功", bean=result_bean)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/plugins/{plugin_id}/configs", response_model=Response,
            name="组件插件配置并更新组件")
async def update_plugin_config(
        env_id: Optional[str] = None,
        plugin_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        params: Optional[UpdatePluginConfig] = UpdatePluginConfig(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    """
    组件插件配置并更新组件
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
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    configs = params.configs
    if not configs:
        return JSONResponse(general_message(400, "params error", "参数配置不可为空"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    pbv = plugin_version_service.get_newest_usable_plugin_version(session=session, tenant_env_id=env.env_id,
                                                                  plugin_id=plugin_id)
    if not pbv:
        return JSONResponse(general_message(400, "no usable plugin version", "无最新更新的版本信息，无法更新配置"), status_code=400)

    plugin_info = plugin_repo.get_plugin_by_plugin_id(session, env.env_id, plugin_id)
    # 配置插件环境变量
    app_plugin_service.update_plugin_configs(session=session, env=env, service=service, plugin_info=plugin_info,
                                             plugin_id=plugin_id, build_version=pbv.build_version, config=configs,
                                             user=user, memory=params.min_memory, cpu=params.min_cpu, )

    # 更新组件
    is_dep_running = app_manage_service.is_dep_service_running(session, env, service)
    status_map = application_service.get_service_status(session=session, tenant_env=env, service=service)
    status = status_map.get("status")
    if status != "closed" and status != "undeploy" and is_dep_running:
        try:
            code, msg, _ = app_manage_service.upgrade(session=session, tenant_env=env, service=service, user=user)
            bean = {}
            if code != 200:
                return JSONResponse(general_message(code, "upgrade app error", msg, bean=bean), status_code=code)
        except ResourceNotEnoughException as re:
            raise re
        except AccountOverdueException as re:
            logger.exception(re)
            return JSONResponse(general_message(10410, "resource is not enough", "操作失败"), status_code=412)

    result = general_message("0", "success", "配置更新成功")
    return JSONResponse(result, 200)
