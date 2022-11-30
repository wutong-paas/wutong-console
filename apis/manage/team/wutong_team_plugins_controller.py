import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import Params, paginate
from loguru import logger

from core import deps
from core.perm.perm import check_perm
from core.utils.constants import DefaultPluginConstants
from core.utils.crypt import make_uuid
from core.utils.return_message import general_message, error_message
from database.session import SessionClass
from exceptions.main import NoPermissionsError
from models.application.plugin import PluginConfigGroup, PluginConfigItems
from repository.component.service_share_repo import component_share_repo
from repository.plugin.plugin_config_repo import config_group_repo, config_item_repo
from repository.plugin.plugin_version_repo import plugin_version_repo
from repository.teams.team_plugin_repo import plugin_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.plugin.app_plugin_service import app_plugin_service
from service.plugin.plugin_config_service import plugin_config_service
from service.plugin.plugin_version_service import plugin_version_service
from service.plugin_service import plugin_service, allow_plugins
from service.region_service import region_services

router = APIRouter()

default_plugins = [
    DefaultPluginConstants.DOWNSTREAM_NET_PLUGIN, DefaultPluginConstants.PERF_ANALYZE_PLUGIN,
    DefaultPluginConstants.INANDOUT_NET_PLUGIN, DefaultPluginConstants.FILEBEAT_LOG_PLUGIN,
    DefaultPluginConstants.LOGTAIL_LOG_PLUGIN, DefaultPluginConstants.MYSQLD_EXPORTER_PLUGIN,
    DefaultPluginConstants.FILEBROWSER_PLUGIN, DefaultPluginConstants.MYSQL_DBGATE_PLUGIN,
    DefaultPluginConstants.REDIS_DBGATE_PLUGIN
]


@router.get("/teams/{team_name}/plugins/all", response_model=Response, name="获取租户下所有插件基础信息")
async def get_team_all_plugins(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    获取插件基础信息
    ---
    parameters:
        - name: tenantName
          description: 租户名
          required: true
          type: string
          paramType: path
    """
    if not team:
        return JSONResponse(general_message(400, "tenant not exist", "团队不存在"), status_code=400)

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    plugin_list = plugin_service.get_tenant_plugins(session=session, region=region_name, tenant=team)
    return general_message(200, "success", "查询成功", list=plugin_list)


@router.post("/teams/{team_name}/plugins/default", response_model=Response, name="默认插件创建")
async def add_default_plugins(request: Request,
                              session: SessionClass = Depends(deps.get_session),
                              user=Depends(deps.get_current_user),
                              team=Depends(deps.get_current_team)) -> Any:
    """
           插件创建
           ---
           parameters:
               - name: tenantName
                 description: 团队名
                 required: true
                 type: string
                 paramType: path
               - name: plugin_type
                 description: 插件类型
                 required: true
                 type: string
                 paramType: form
           """
    from_data = await request.json()
    plugin_type = from_data["plugin_type"]
    if not plugin_type:
        return JSONResponse(general_message(400, "plugin type is null", "请指明插件类型"), status_code=400)
    if plugin_type not in default_plugins:
        return JSONResponse(general_message(400, "plugin type not support", "插件类型不支持"), status_code=400)

    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    plugin_service.add_default_plugin(session=session, user=user, tenant=team, region=region_name,
                                      plugin_type=plugin_type)
    return general_message(200, "success", "创建成功")


@router.get("/teams/{team_name}/plugins/default", response_model=Response, name="获取默认插件")
async def get_default_plugins(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    查询安装的默认插件
    ---
    parameters:
        - name: tenantName
          description: 团队名
          required: true
          type: string
          paramType: path
    """
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    default_plugin_dict = plugin_service.get_default_plugin_from_cache(session=session, region=region_name, tenant=team)

    return general_message(200, "success", "查询成功", list=[])


@router.post("/teams/{team_name}/plugins", response_model=Response, name="插件创建")
async def create_plugins(request: Request,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user),
                         team=Depends(deps.get_current_team)) -> Any:
    is_perm = check_perm(session, user, team, "plugin_create")
    if not is_perm:
        raise NoPermissionsError

    data = await request.json()
    # 必要参数
    plugin_alias = data.get("plugin_alias", None)
    build_source = data.get("build_source", None)
    min_memory = data.get("min_memory", 0)
    category = data.get("category", None)
    desc = data.get("desc", None)
    # 非必要参数
    build_cmd = data.get("build_cmd", None)
    code_repo = data.get("code_repo", None)
    code_version = data.get("code_version", None)
    image = data.get("image", None)
    min_cpu = data.get("min_cpu", None)
    # username and password is used for private docker hub or private git repo
    username = data.get("username", None)
    password = data.get("password", None)
    tenant_plugin = None
    plugin_build_version = None
    try:
        if not plugin_alias:
            return JSONResponse(general_message(400, "plugin alias is null", "插件名称未指明"), status_code=400)
        if not build_source:
            return JSONResponse(general_message(400, "build source is null", "构建来源未指明"), status_code=400)
        if not category:
            return JSONResponse(general_message(400, "plugin category is null", "插件类别未指明"), status_code=400)
        else:
            if category not in allow_plugins:
                return JSONResponse(general_message(400, "plugin category is wrong", "插件类别参数错误，详情请参数API说明"), status=400)
        if not desc:
            return JSONResponse(general_message(400, "plugin desc is null", "请填写插件描述"), status_code=400)

        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        image_tag = ""
        if image and build_source == "image":
            image_and_tag = image.rsplit(":", 1)
            if len(image_and_tag) > 1:
                image = image_and_tag[0]
                image_tag = image_and_tag[1]
            else:
                image = image_and_tag[0]
                image_tag = "latest"
        # 创建基本信息
        plugin_params = {
            "tenant_id": team.tenant_id,
            "region": response_region,
            "create_user": user.user_id,
            "desc": desc,
            "plugin_alias": plugin_alias,
            "category": category,
            "build_source": build_source,
            "image": image,
            "code_repo": code_repo,
            "username": username,
            "password": password
        }
        code, msg, tenant_plugin = plugin_service.create_tenant_plugin(session, plugin_params)
        if code != 200:
            return JSONResponse(general_message(code, "create plugin error", msg), status_code=code)

        # 创建插件版本信息
        plugin_build_version = plugin_version_service.create_build_version(
            session,
            response_region,
            tenant_plugin.plugin_id,
            team.tenant_id,
            user.user_id,
            "",
            "unbuild",
            min_memory,
            build_cmd,
            image_tag,
            code_version,
            min_cpu=min_cpu)
        # 数据中心创建插件
        code, msg = plugin_service.create_region_plugin(session, response_region, team, tenant_plugin, image_tag)
        if code != 200:
            plugin_service.delete_console_tenant_plugin(session, team.tenant_id, tenant_plugin.plugin_id)
            plugin_version_service.delete_build_version_by_id_and_version(session,
                                                                          team.tenant_id,
                                                                          tenant_plugin.plugin_id,
                                                                          plugin_build_version.build_version, True)
            return JSONResponse(general_message(code, "create plugin error", msg), status_code=code)

        bean = jsonable_encoder(tenant_plugin)
        bean["build_version"] = plugin_build_version.build_version
        bean["code_version"] = plugin_build_version.code_version
        bean["build_status"] = plugin_build_version.build_status
        bean["update_info"] = plugin_build_version.update_info
        bean["image_tag"] = plugin_build_version.image_tag

        result = general_message(200, "success", "创建成功", bean=bean)
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
        if tenant_plugin:
            plugin_service.delete_console_tenant_plugin(session, team.tenant_id, tenant_plugin.plugin_id)
        if plugin_build_version:
            plugin_version_service.delete_build_version_by_id_and_version(session,
                                                                          team.tenant_id,
                                                                          tenant_plugin.plugin_id,
                                                                          plugin_build_version.build_version, True)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/build-history", response_model=Response, name="插件构建历史信息展示")
async def get_build_history(request: Request,
                            plugin_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("page_size", 8)
    pbvs = plugin_version_repo.get_plugin_versions(session, plugin.plugin_id)
    params = Params(page=page, size=page_size)
    event_paginator = paginate(pbvs, params)
    total = event_paginator.total
    show_pbvs = event_paginator.items

    # update_status_thread = threading.Thread(
    #     target=plugin_version_service.update_plugin_build_status, args=(response_region, team))
    # update_status_thread.start()

    plugin_version_service.update_plugin_build_status(session, response_region, team)

    data = [jsonable_encoder(pbv) for pbv in show_pbvs]
    result = general_message(
        200, "success", "查询成功", list=data, total=total, current_page=int(page), next_page=int(page) + 1)

    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/used_services", response_model=Response, name="获取插件被哪些当前团队哪些组件使用")
async def get_used_services(request: Request,
                            plugin_id: Optional[str] = None,
                            session: SessionClass = Depends(deps.get_session),
                            team=Depends(deps.get_current_team)) -> Any:
    page = request.query_params.get("page", 1)
    page_size = request.query_params.get("page_size", 10)
    plugin = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
    data, total = app_plugin_service.get_plugin_used_services(session,
                                                              plugin.plugin_id, team.tenant_id, page,
                                                              page_size)

    result = general_message(200, "success", "查询成功", list=data, total=total)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/share/record", response_model=Response, name="查询插件分享记录")
async def get_share_record(plugin_id: Optional[str] = None,
                           session: SessionClass = Depends(deps.get_session)) -> Any:
    share_record = component_share_repo.get_service_share_record_by_groupid(session, plugin_id)
    if share_record:
        if not share_record.is_success and share_record.step < 3:
            result = general_message(20021, "share record not complete", "分享流程未完成", bean=jsonable_encoder(share_record))
            return JSONResponse(result, status_code=200)

    result = general_message(200, "not found uncomplete share record", "无未完成分享流程")
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/config", response_model=Response,
            name="获取某个插件的配置信息")
async def get_plugin_config(
        request: Request,
        plugin_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    config_groups = plugin_config_service.get_config_details(session=session, plugin_id=plugin_version.plugin_id,
                                                             build_version=plugin_version.build_version)
    data = jsonable_encoder(plugin_version)
    main_url = region_services.get_region_wsurl(session, response_region)
    data["web_socket_url"] = "{0}/event_log".format(main_url)

    result = general_message(200, "success", "查询成功", bean=data, list=config_groups)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}", response_model=Response,
            name="获取插件某个版本的信息")
async def get_plugin_version(
        request: Request,
        plugin_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    base_info = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
    if base_info.image and base_info.build_source == "image":
        base_info.image = base_info.image + ":" + plugin_version.image_tag
    data = jsonable_encoder(base_info)
    data.update(jsonable_encoder(plugin_version))
    # update_status_thread = threading.Thread(
    #     target=plugin_version_service.update_plugin_build_status, args=(response_region, team))
    # update_status_thread.start()
    plugin_version_service.update_plugin_build_status(session, response_region, team)
    session.rollback()
    result = general_message(200, "success", "查询成功", bean=data)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}", response_model=Response,
            name="修改插件某个版本的信息")
async def modify_plugin_version(request: Request,
                                plugin_id: Optional[str] = None,
                                session: SessionClass = Depends(deps.get_session),
                                team=Depends(deps.get_current_team),
                                user=Depends(deps.get_current_user)) -> Any:
    is_perm = check_perm(session, user, team, "plugin_edit")
    if not is_perm:
        raise NoPermissionsError

    try:
        data = await request.json()
        region = await region_services.get_region_by_request(session, request)
        if not region:
            return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
        response_region = region.region_name
        plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                                 tenant_id=team.tenant_id,
                                                                                 plugin_id=plugin_id)
        plugin = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
        plugin_alias = data.get("plugin_alias", plugin.plugin_alias)
        update_info = data.get("update_info", plugin_version.update_info)
        build_cmd = data.get("build_cmd", plugin_version.build_cmd)
        image = data.get("image", plugin.image)
        code_repo = data.get("code_repo", plugin.code_repo)
        code_version = data.get("code_version", plugin_version.code_version)
        min_memory = data.get("min_memory", plugin_version.min_memory)
        min_cpu = data.get("min_cpu", 0)
        if type(min_cpu) != int or min_cpu < 0:
            min_cpu = 0
        # if get username and password is "", means user remove the username and password
        username = data.get("username", "")
        password = data.get("password", "")
        image_tag = ""  # if build_source is dockerfile, image_tag should be empty
        if image and plugin.build_source == "image":
            ref = image.split(":")
            image = ref[0]
            if len(ref) > 1:
                image_tag = ':'.join(ref[1:])
            else:
                image_tag = "latest"

        plugin.image = image
        plugin.code_repo = code_repo
        plugin.username = username
        plugin.password = password
        plugin.plugin_alias = plugin_alias
        plugin.desc = update_info
        plugin_version.update_info = update_info
        plugin_version.build_cmd = build_cmd
        plugin_version.image_tag = image_tag
        plugin_version.code_version = code_version
        plugin_version.min_memory = min_memory
        plugin_version.min_cpu = min_cpu

        plugin_service.update_region_plugin_info(session, response_region, team, plugin, plugin_version)
        # # 保存基本信息
        # self.plugin.save()
        # # 保存版本信息
        # self.plugin_version.save()
        result = general_message(200, "success", "操作成功")
    except Exception as e:
        logger.exception(e)
        result = error_message("失败")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/build", response_model=Response,
             name="构建插件")
async def build_plugin(
        request: Request,
        plugin_id: Optional[str] = None,
        update_info: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    plugin = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
    # update_info = data.get("update_info", None)
    if plugin_version.build_status == "building":
        return JSONResponse(general_message(409, "too offen", "构建中，请稍后再试"), status_code=409)
    if update_info:
        plugin_version.update_info = update_info
        # plugin_version.save()
    event_id = make_uuid()
    plugin_version.build_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # plugin_version.save()
    # prepare image info for
    image_info = {
        "hub_user": plugin.username,
        "hub_password": plugin.password,
    }
    try:
        plugin_service.build_plugin(session, response_region, plugin, plugin_version, user, team,
                                    event_id, image_info)
        plugin_version.build_status = "building"
        plugin_version.event_id = event_id
        # self.plugin_version.save()
        bean = {"event_id": event_id}
        result = general_message(200, "success", "操作成功", bean=bean)
    except Exception as e:
        logger.exception(e)
        result = general_message(500, "region invoke error", "构建失败，请查看镜像或源代码是否正确")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/status", response_model=Response,
            name="获取插件构建状态")
async def get_build_status(
        request: Request,
        plugin_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    pbv = plugin_version_service.get_plugin_build_status(session, response_region, team,
                                                         plugin_version.plugin_id,
                                                         plugin_version.build_version)
    result = general_message(200, "success", "查询成功", {"status": pbv.build_status, "event_id": pbv.event_id})
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/event-log", response_model=Response,
            name="获取event事件")
async def get_build_log(request: Request,
                        plugin_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    level = request.query_params.get("level", "info")
    event_id = plugin_version.event_id
    logs = plugin_service.get_plugin_event_log(session, response_region, team, event_id, level)
    result = general_message(200, "success", "查询成功", list=logs)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/config", response_model=Response,
             name="增加插件配置")
async def add_plugin_config(
        request: Request,
        plugin_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    config = await request.json()

    injection = config.get("injection")
    service_meta_type = config.get("service_meta_type")
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)

    config_groups = plugin_config_service.get_config_group(session,
                                                           plugin_version.plugin_id,
                                                           plugin_version.build_version)
    is_pass, msg = plugin_config_service.check_group_config(service_meta_type, injection, config_groups)

    if not is_pass:
        return JSONResponse(general_message(400, "param error", msg), status_code=400)
    create_data = [config]
    plugin_config_service.create_config_groups(session, plugin_version.plugin_id, plugin_version.build_version,
                                               create_data)

    result = general_message(200, "success", "添加成功")

    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/config", response_model=Response,
            name="修改插件配置")
async def modify_plugin_config(request: Request,
                               plugin_id: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    plugin_version = plugin_version_service.get_newest_usable_plugin_version(session=session,
                                                                             tenant_id=team.tenant_id,
                                                                             plugin_id=plugin_id)
    config = await request.json()
    injection = config.get("injection")
    service_meta_type = config.get("service_meta_type")
    config_name = config.get("config_name")
    config_group_pk = config.get("ID")

    config_groups = plugin_config_service.get_config_group_by_pk_build_version(session,
                                                                               plugin_version.plugin_id,
                                                                               plugin_version.build_version,
                                                                               config_group_pk)
    is_pass, msg = plugin_config_service.check_group_config(service_meta_type, injection, config_groups)

    if not is_pass:
        return JSONResponse(general_message(400, "param error", msg), status_code=400)
    config_group = plugin_config_service.get_config_group_by_pk(session, config_group_pk)
    old_meta_type = config_group.service_meta_type
    plugin_config_service.update_config_group_by_pk(session, config_group_pk, config_name, service_meta_type, injection)

    # 删除原有配置项
    plugin_config_service.delet_config_items(session,
                                             plugin_version.plugin_id, plugin_version.build_version,
                                             old_meta_type)
    options = config.get("options")
    plugin_config_service.create_config_items(session,
                                              plugin_version.plugin_id, plugin_version.build_version,
                                              service_meta_type, *options)

    result = general_message(200, "success", "修改成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/plugins/{plugin_id}/version/{build_version}/config", response_model=Response,
               name="删除插件配置")
async def delete_plugin_config(
        request: Request,
        session: SessionClass = Depends(deps.get_session)) -> Any:


    data = await request.json()
    config_group_id = data.get("config_group_id")
    if not config_group_id:
        return JSONResponse(general_message(400, "param error", "参数错误"), status_code=400)

    config_group = plugin_config_service.get_config_group_by_pk(session, config_group_id)
    if not config_group:
        return JSONResponse(general_message(404, "config group not exist", "配置组不存在"), status_code=404)
    plugin_config_service.delete_config_group_by_meta_type(session,
                                                           config_group.plugin_id, config_group.build_version,
                                                           config_group.service_meta_type)

    result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/plugins/{plugin_id}", response_model=Response, name="删除插件")
async def delete_plugin(request: Request,
                        plugin_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team),
                        user=Depends(deps.get_current_user)) -> Any:
    is_perm = check_perm(session, user, team, "plugin_delete")
    if not is_perm:
        raise NoPermissionsError

    data = await request.json()
    is_force = data.get("is_force", False)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    response_region = region.region_name
    plugin = plugin_repo.get_plugin_by_plugin_id(session, team.tenant_id, plugin_id)
    plugin_service.delete_plugin(session, response_region, team, plugin.plugin_id, is_force=is_force)
    result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/plugins/{plugin_id}/share", response_model=Response, name="团队插件共享")
async def plugin_share(request: Request,
                       plugin_id: Optional[str] = None,
                       session: SessionClass = Depends(deps.get_session),
                       user=Depends(deps.get_current_user),
                       team=Depends(deps.get_current_team)) -> Any:
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    plugin_version = plugin_version_service.get_plugin_version_by_id(session, team.tenant_id, plugin_id)
    if plugin_version.build_status != "build_success":
        if plugin_version.build_status == "building":
            status = plugin_version_service.get_region_plugin_build_status(session, region.region_name,
                                                                           team.tenant_name,
                                                                           plugin_version.plugin_id,
                                                                           plugin_version.build_version)
            plugin_version.build_status = status
            if status == "building":
                result = general_message(400, "failed", "插件正在构建中,请稍后再试")
                return JSONResponse(result, status_code=result["code"])
        else:
            return JSONResponse(general_message(400, "failed", "请构建成功后再共享"),
                                status_code=400)
    plugin = plugin_service.get_by_plugin_id(session, team.tenant_id, plugin_id)
    plugin_params = jsonable_encoder(plugin)
    plugin_params.update({"origin": "shared"})
    plugin_params.update({"ID": None})
    code, msg, tenant_plugin = plugin_service.create_tenant_plugin(session, plugin_params)
    if code != 200:
        return JSONResponse(general_message(code, "create plugin error", msg), status_code=code)

    # 创建插件版本信息
    plugin_build_version = plugin_version_service.create_build_version(
        session,
        region.region_name,
        tenant_plugin.plugin_id,
        team.tenant_id,
        user.user_id,
        "",
        "unbuild",
        plugin_version.min_memory,
        plugin_version.build_cmd,
        plugin_version.image_tag,
        plugin_version.code_version,
        min_cpu=plugin_version.min_cpu)
    # 数据中心创建插件
    code, msg = plugin_service.create_region_plugin(session, region.region_name, team, tenant_plugin,
                                                    plugin_build_version.image_tag)
    if code != 200:
        plugin_service.delete_console_tenant_plugin(session, team.tenant_id, tenant_plugin.plugin_id)
        plugin_version_service.delete_build_version_by_id_and_version(session,
                                                                      team.tenant_id,
                                                                      tenant_plugin.plugin_id,
                                                                      plugin_build_version.build_version, True)
        return JSONResponse(general_message(code, "create plugin error", msg), status_code=code)

    config_groups = config_group_repo.get_config_group_by_id_and_version(session=session, plugin_id=plugin_id,
                                                                         build_version=plugin_version.build_version)
    if config_groups:
        for config_group in config_groups:
            config_group_params = jsonable_encoder(config_group)
            config_group_params.update({"build_version": plugin_build_version.build_version})
            config_group_params.update({"plugin_id": tenant_plugin.plugin_id})
            config_group_params.update({"ID": None})
            cg = PluginConfigGroup(**config_group_params)
            session.add(cg)

    pcgs = config_item_repo.list_by_plugin_id(session=session, plugin_id=plugin_id)
    if pcgs:
        for p in pcgs:
            config_item_params = jsonable_encoder(p)
            config_item_params.update({"build_version": plugin_build_version.build_version})
            config_item_params.update({"plugin_id": tenant_plugin.plugin_id})
            config_item_params.update({"ID": None})
            ci = PluginConfigItems(**config_item_params)
            session.add(ci)

    event_id = make_uuid()
    plugin_build_version.build_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    image_info = {
        "hub_user": tenant_plugin.username,
        "hub_password": tenant_plugin.password,
    }
    try:
        plugin_service.build_plugin(session, region.region_name, tenant_plugin, plugin_build_version, user, team,
                                    event_id, image_info)
        plugin_build_version.build_status = "building"
        plugin_build_version.event_id = event_id
        session.merge(plugin_build_version)
        bean = {"event_id": event_id}
        result = general_message(200, "success", "共享成功", bean=bean)
    except Exception as e:
        logger.exception(e)
        result = general_message(500, "region invoke error", "构建失败，请查看镜像或源代码是否正确")
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/plugins/share/list", response_model=Response, name="团队共享插件列表")
async def plugin_share_list(session: SessionClass = Depends(deps.get_session),
                            user=Depends(deps.get_current_user),
                            team=Depends(deps.get_current_team)) -> Any:
    tenant_id = team.tenant_id
    plugins = plugin_service.get_by_share_plugins(session, tenant_id, "shared")
    return JSONResponse(general_message(200, "success", "查询成功", list=jsonable_encoder(plugins)), status_code=200)
