import re
from typing import Any, Optional
from fastapi import Request, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from clients.remote_component_client import remote_component_client
from core import deps
from core.utils.reqparse import parse_argument
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest, ErrVolumePath, ServiceHandleException
from repository.component.group_service_repo import service_info_repo
from repository.component.service_config_repo import volume_repo
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_config.volume_service import volume_service
from service.mnt_service import mnt_service

router = APIRouter()


def ensure_volume_mode(mode):
    if type(mode) != int:
        raise AbortRequest("mode be a number between 0 and 777 (octal)", msg_show="权限必须是在0和777之间的八进制数")
    regex = re.compile(r"^[0-7]{1,3}$")
    if not regex.match(str(mode)):
        raise AbortRequest("mode be a number between 0 and 777 (octal)", msg_show="权限必须是在0和777之间的八进制数")
    return mode


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/volumes", response_model=Response, name="获取组件的持久化路径")
async def get_volume_dir(request: Request,
                         env_id: Optional[str] = None,
                         serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取组件的持久化路径
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
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    is_config = parse_argument(request, 'is_config', value_type=bool, default=False)
    volumes = volume_service.get_service_volumes(session=session, tenant_env=env, service=service,
                                                 is_config_file=is_config)
    volumes_list = []
    if is_config:
        for tenant_service_volume in volumes:
            volume = volume_repo.get_service_volume_by_pk(session, tenant_service_volume["ID"])
            cf_file = volume_repo.get_service_config_file(session, volume)
            if cf_file:
                tenant_service_volume["file_content"] = cf_file.file_content
            volumes_list.append(tenant_service_volume)
    else:
        dependents = mnt_service.get_volume_dependent(session=session, tenant=env, service=service)
        name2deps = {}
        if dependents:
            for dep in dependents:
                if name2deps.get(dep["volume_name"], None) is None:
                    name2deps[dep["volume_name"]] = []
                name2deps[dep["volume_name"]].append(dep)
        for vo in volumes:
            vo["dep_services"] = name2deps.get(vo["volume_name"], None)
            volumes_list.append(vo)
    result = general_message("0", "success", "查询成功", list=jsonable_encoder(volumes_list))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/volumes", response_model=Response, name="为组件添加存储")
async def add_volume(
        request: Request,
        env_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    """
    为组件添加持久化目录
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
        - name: volume_name
          description: 持久化名称
          required: true
          type: string
          paramType: form
        - name: volume_type
          description: 持久化类型
          required: true
          type: string
          paramType: form
        - name: volume_path
          description: 持久化路径
          required: true
          type: string
          paramType: form

    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    data = await request.json()
    volume_name = data.get("volume_name", None)
    r = re.compile('(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])$')
    if not r.match(volume_name):
        raise AbortRequest(msg="volume name illegal", msg_show="持久化名称只支持数字字母下划线")
    volume_type = data.get("volume_type", None)
    volume_path = data.get("volume_path", None)
    file_content = data.get("file_content", None)
    volume_capacity = data.get("volume_capacity", 0)
    provider_name = data.get("volume_provider_name", '')
    access_mode = data.get("access_mode", '')
    share_policy = data.get('share_policy', '')
    backup_policy = data.get('back_policy', '')
    reclaim_policy = data.get('reclaim_policy', '')
    allow_expansion = data.get('allow_expansion', False)
    mode = data.get("mode")
    if mode is not None:
        mode = ensure_volume_mode(mode)

    if len(file_content) > 131070:
        return JSONResponse(general_message(400, "failed", "配置文件长度不能超过131070"), status_code=400)

    settings = {'volume_capacity': volume_capacity, 'provider_name': provider_name, 'access_mode': access_mode,
                'share_policy': share_policy, 'backup_policy': backup_policy, 'reclaim_policy': reclaim_policy,
                'allow_expansion': allow_expansion}

    try:
        data = volume_service.add_service_volume(
            session=session,
            tenant_env=env,
            service=service,
            volume_path=volume_path,
            volume_type=volume_type,
            volume_name=volume_name,
            file_content=file_content,
            settings=settings,
            user_name=user.nick_name,
            mode=mode)
        result = general_message("0", "success", "持久化路径添加成功", bean=jsonable_encoder(data))
        return JSONResponse(result, status_code=200)
    except ErrVolumePath as e:
        result = general_message(e.status_code, e.msg, e.msg_show)
    except ServiceHandleException as e:
        result = general_message(e.status_code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.put("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/volumes/{volume_id}", response_model=Response,
            name="修改存储设置")
async def modify_volume(request: Request,
                        env_id: Optional[str] = None,
                        serviceAlias: Optional[str] = None,
                        volume_id: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        user=Depends(deps.get_current_user)) -> Any:
    """
    修改存储设置
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    new_volume_path = data.get("new_volume_path", None)
    new_file_content = data.get("new_file_content", None)
    if not volume_id:
        return JSONResponse(general_message(400, "volume_id is null", "未指定需要编辑的配置文件存储"), status_code=400)
    volume = volume_repo.get_service_volume_by_pk(session, volume_id)
    if not volume:
        return JSONResponse(general_message(400, "volume is null", "存储不存在"), status_code=400)
    mode = data.get("mode")
    if mode is not None:
        mode = ensure_volume_mode(mode)
    service_config = volume_repo.get_service_config_file(session, volume)
    if volume.volume_type == 'config-file':
        if not service_config:
            return JSONResponse(general_message(400, "file_content is null", "配置文件内容不存在"), status_code=400)
        if new_volume_path == volume.volume_path and new_file_content == service_config.file_content and volume.mode == mode:
            return JSONResponse(general_message(400, "no change", "没有变化，不需要修改"), status_code=400)
    else:
        if new_volume_path == volume.volume_path:
            return JSONResponse(general_message(400, "no change", "没有变化，不需要修改"), status_code=400)

    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    data = {
        "volume_name": volume.volume_name,
        "volume_path": new_volume_path,
        "volume_type": volume.volume_type,
        "file_content": new_file_content,
        "operator": user.nick_name,
        "mode": mode,
    }
    res, body = remote_component_client.upgrade_service_volumes(session,
                                                                service.service_region, env,
                                                                service.service_alias, data)
    if res.status == 200:
        volume.volume_path = new_volume_path
        if mode is not None:
            volume.mode = mode
        if volume.volume_type == 'config-file':
            service_config.volume_name = volume.volume_name
            service_config.file_content = new_file_content
        result = general_message("0", "success", "修改成功")
        return JSONResponse(result, status_code=200)
    return JSONResponse(general_message(405, "success", "修改失败"), status_code=405)


@router.delete("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/volumes/{volume_id}", response_model=Response,
               name="删除组件的某个存储")
async def delete_volume(
        env_id: Optional[str] = None,
        serviceAlias: Optional[str] = None,
        volume_id: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user)) -> Any:
    """
    删除组件的某个持久化路径
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
        - name: volume_id
          description: 需要删除的持久化ID
          required: true
          type: string
          paramType: path

    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if not volume_id:
        return JSONResponse(general_message(400, "attr_name not specify", "未指定需要删除的持久化路径"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    code, msg, volume = volume_service.delete_service_volume_by_id(session=session, tenant_env=env, service=service,
                                                                   volume_id=int(volume_id),
                                                                   user_name=user.nick_name)
    result = general_message("0", "success", "删除成功")
    if code != 200:
        result = general_message(code=code, msg="delete volume error", msg_show=msg)
        return JSONResponse(result, status_code=result["code"])
    return JSONResponse(result, status_code=200)
