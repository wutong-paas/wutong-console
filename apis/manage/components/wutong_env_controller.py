from typing import Any, Optional

from fastapi import Request, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core import deps
from core.utils.reqparse import parse_item
from core.utils.return_message import general_message
from database.session import SessionClass
from exceptions.main import AbortRequest
from repository.component.group_service_repo import service_info_repo
from schemas.response import Response
from service.app_env_service import env_var_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/envs", response_model=Response, name="获取组件的环境变量参数")
async def get_env(request: Request,
                  serviceAlias: Optional[str] = None,
                  db: SessionClass = Depends(deps.get_session),
                  team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件的环境变量参数
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
        - name: env_type
          description: 环境变量类型[对内环境变量（inner）|对外环境变量（outer）]
          required: true
          type: string
          paramType: query
    """
    env_type = request.query_params.get("env_type", None)
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    env_name = request.query_params.get("env_name", None)

    service = service_info_repo.get_service(db, serviceAlias, team.tenant_id)

    if not env_type:
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    if env_type not in ("inner", "outer"):
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    env_list = []
    if env_type == "inner":
        if env_name:
            # 获取总数
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_id='{0}' and \
                    service_id='{1}' and scope='inner' and attr_name like '%{2}%';".format(
                service.tenant_id, service.service_id, env_name))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_id, service_id, container_port, name, attr_name, \
                    attr_value, is_change, scope, create_time from tenant_service_env_var \
                        where tenant_id='{0}' and service_id='{1}' and scope='inner' and \
                            attr_name like '%{2}%' order by attr_name LIMIT {3},{4};".format(
                service.tenant_id, service.service_id, env_name, start, end))).fetchall()
        else:
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_id='{0}' and service_id='{1}'\
                     and scope='inner';".format(service.tenant_id, service.service_id))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_id, service_id, container_port, name, attr_name, attr_value,\
                     is_change, scope, create_time from tenant_service_env_var where tenant_id='{0}' \
                         and service_id='{1}' and scope='inner' order by attr_name LIMIT {2},{3};".format(
                service.tenant_id, service.service_id, start, end))).fetchall()
        if len(env_tuples) > 0:
            for env_tuple in env_tuples:
                env_dict = dict()
                env_dict["ID"] = env_tuple[0]
                env_dict["tenant_id"] = env_tuple[1]
                env_dict["service_id"] = env_tuple[2]
                env_dict["container_port"] = env_tuple[3]
                env_dict["name"] = env_tuple[4]
                env_dict["attr_name"] = env_tuple[5]
                env_dict["attr_value"] = env_tuple[6]
                env_dict["is_change"] = env_tuple[7]
                env_dict["scope"] = env_tuple[8]
                env_dict["create_time"] = env_tuple[9]
                env_list.append(env_dict)
        bean = {"total": total}

    else:
        if env_name:
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_id='{0}' and service_id='{1}'\
                     and scope='outer' and attr_name like '%{2}%';".format(service.tenant_id,
                                                                           service.service_id,
                                                                           env_name))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_id, service_id, container_port, name, attr_name, attr_value, is_change, \
                    scope, create_time from tenant_service_env_var where tenant_id='{0}' and service_id='{1}'\
                         and scope='outer' and attr_name like '%{2}%' order by attr_name LIMIT {3},{4};".format(
                service.tenant_id, service.service_id, env_name, start, end))).fetchall()
        else:

            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_id='{0}' and service_id='{1}' \
                    and scope='outer';".format(service.tenant_id, service.service_id))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_id, service_id, container_port, name, attr_name, attr_value, is_change,\
                     scope, create_time from tenant_service_env_var where tenant_id='{0}' and service_id='{1}'\
                          and scope='outer' order by attr_name LIMIT {2},{3};".format(
                service.tenant_id, service.service_id, start, end))).fetchall()
        if len(env_tuples) > 0:
            for env_tuple in env_tuples:
                env_dict = dict()
                env_dict["ID"] = env_tuple[0]
                env_dict["tenant_id"] = env_tuple[1]
                env_dict["service_id"] = env_tuple[2]
                env_dict["container_port"] = env_tuple[3]
                env_dict["name"] = env_tuple[4]
                env_dict["attr_name"] = env_tuple[5]
                env_dict["attr_value"] = env_tuple[6]
                env_dict["is_change"] = env_tuple[7]
                env_dict["scope"] = env_tuple[8]
                env_dict["create_time"] = env_tuple[9]
                env_list.append(env_dict)
        bean = {"total": total}

    result = general_message(200, "success", "查询成功", bean=bean, list=jsonable_encoder(env_list))
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/envs", response_model=Response, name="为组件添加环境变量")
async def add_env(request: Request,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user),
                  team=Depends(deps.get_current_team)) -> Any:
    """
    为组件添加环境变量
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
        - name: name
          description: 环境变量说明
          required: false
          type: string
          paramType: form
        - name: attr_name
          description: 环境变量名称 大写
          required: true
          type: string
          paramType: form
        - name: attr_value
          description: 环境变量值
          required: true
          type: string
          paramType: form
        - name: scope
          description: 生效范围 inner(对内),outer(对外)
          required: true
          type: string
          paramType: form
        - name: is_change
          description: 是否可更改 (默认可更改)
          required: false
          type: string
          paramType: form

    """
    data = await request.json()
    name = data.get("name", "")
    attr_name = data.get("attr_name", "")
    attr_value = data.get("attr_value", "")
    scope = data.get('scope', "")
    is_change = data.get('is_change', True)
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    # try:
    if not scope or not attr_name:
        return JSONResponse(general_message(400, "params error", "参数异常"), status_code=400)
    if scope not in ("inner", "outer"):
        return JSONResponse(general_message(400, "params error", "scope范围只能是inner或outer"), status_code=400)
    code, msg, data = env_var_service.add_service_env_var(session=session, tenant=team, service=service,
                                                          container_port=0, name=name, attr_name=attr_name,
                                                          attr_value=attr_value,
                                                          is_change=is_change, scope=scope, user_name=user.nick_name)
    if code != 200:
        result = general_message(code, "add env error", msg)
        return JSONResponse(result, status_code=code)
    result = general_message(code, msg, "环境变量添加成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/envs/{env_id}", response_model=Response, name="删除组件环境变量")
async def delete_env(serviceAlias: Optional[str] = None,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    删除组件的某个环境变量
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
        - name: attr_name
          description: 环境变量名称 大写
          required: true
          type: string
          paramType: path

    """
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    if not env_id:
        return JSONResponse(general_message(400, "env_id not specify", "环境变量ID未指定"))
    env_var_service.delete_env_by_env_id(session=session, tenant=team, service=service, env_id=env_id,
                                         user_name=user.nick_name)
    result = general_message(200, "success", "删除成功")
    return JSONResponse(result, status_code=result["code"])


@router.patch("/teams/{team_name}/apps/{serviceAlias}/envs/{env_id}", response_model=Response, name="变更环境变量范围")
async def move_env(request: Request,
                   serviceAlias: Optional[str] = None,
                   env_id: Optional[str] = None,
                   session: SessionClass = Depends(deps.get_session),
                   user=Depends(deps.get_current_user),
                   team=Depends(deps.get_current_team)) -> Any:
    """变更环境变量范围"""
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    # todo await
    scope = await parse_item(request, 'scope', required=True, error="scope is is a required parameter")
    env = env_var_service.patch_env_scope(session=session, tenant=team, service=service, env_id=env_id, scope=scope,
                                          user_name=user.nick_name)
    if env:
        return JSONResponse(general_message(code=200, msg="success", msg_show="更新成功", bean=jsonable_encoder(env)),
                            status_code=200)
    else:
        return JSONResponse(general_message(code=200, msg="success", msg_show="更新成功", bean={}), status_code=200)


@router.put("/teams/{team_name}/apps/{serviceAlias}/envs/{env_id}", response_model=Response, name="修改组件环境变量")
async def modify_env(request: Request,
                     serviceAlias: Optional[str] = None,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user),
                     team=Depends(deps.get_current_team)) -> Any:
    """
    修改组件环境变量
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
        - name: env_id
          description: 环境变量ID
          required: true
          type: string
          paramType: path
         - name: name
          description: 环境变量说明
          required: false
          type: string
          paramType: form
        - name: attr_value
          description: 环境变量值
          required: true
          type: string
          paramType: form

    """
    if not env_id:
        return JSONResponse(general_message(400, "env_id not specify", "环境变量ID未指定"))
    data = await request.json()
    name = data.get("name", "")
    attr_value = data.get("attr_value", "")

    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)

    code, msg, env = env_var_service.update_env_by_env_id(session=session, tenant=team, service=service,
                                                          env_id=env_id, name=name, attr_value=attr_value,
                                                          user_name=user.nick_name)
    if code != 200:
        raise AbortRequest(msg="update value error", msg_show=msg, status_code=code)
    result = general_message(200, "success", "更新成功", bean=jsonable_encoder(env))
    return JSONResponse(result, status_code=result["code"])
