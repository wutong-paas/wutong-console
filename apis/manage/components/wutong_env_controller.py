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
from repository.teams.env_repo import env_repo
from schemas.response import Response
from service.app_env_service import env_var_service

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/batch_envs", response_model=Response,
            name="批量获取组件的环境变量文本参数")
async def batch_get_envs(request: Request,
                         serviceAlias: Optional[str] = None,
                         db: SessionClass = Depends(deps.get_session),
                         env=Depends(deps.get_current_team_env)) -> Any:
    """
    批量获取组件的环境变量文本参数
    """
    env_type = request.query_params.get("env_type", None)
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))
    env_name = request.query_params.get("env_name", None)

    service = service_info_repo.get_service(db, serviceAlias, env.env_id)

    if not env_type:
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    if env_type not in ("inner", "outer"):
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    env_list = []
    if env_name:
        # 获取总数
        env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and \
                service_id='{1}' and scope='inner' and attr_name like '%{2}%';".format(
            service.tenant_env_id, service.service_id, env_name))).fetchall()

        total = env_count[0][0]
        start = (page - 1) * page_size
        remaining_num = total - (page - 1) * page_size
        end = page_size
        if remaining_num < page_size:
            end = remaining_num

        env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, \
                attr_value, is_change, scope, create_time from tenant_service_env_var \
                    where tenant_env_id='{0}' and service_id='{1}' and scope='inner' and \
                        attr_name like '%{2}%' order by attr_name LIMIT {3},{4};".format(
            service.tenant_env_id, service.service_id, env_name, start, end))).fetchall()
    else:
        env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}'\
                 and scope='inner';".format(service.tenant_env_id, service.service_id))).fetchall()

        total = env_count[0][0]
        start = (page - 1) * page_size
        remaining_num = total - (page - 1) * page_size
        end = page_size
        if remaining_num < page_size:
            end = remaining_num

        env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, attr_value,\
                 is_change, scope, create_time from tenant_service_env_var where tenant_env_id='{0}' \
                     and service_id='{1}' and scope='inner' order by attr_name LIMIT {2},{3};".format(
            service.tenant_env_id, service.service_id, start, end))).fetchall()
    if len(env_tuples) > 0:
        for env_tuple in env_tuples:
            env_dict = dict()
            env_dict["ID"] = env_tuple[0]
            env_dict["tenant_env_id"] = env_tuple[1]
            env_dict["service_id"] = env_tuple[2]
            env_dict["container_port"] = env_tuple[3]
            env_dict["name"] = env_tuple[4]
            env_dict["attr_name"] = env_tuple[5]
            env_dict["attr_value"] = env_tuple[6]
            env_dict["is_change"] = env_tuple[7]
            env_dict["scope"] = env_tuple[8]
            env_dict["create_time"] = env_tuple[9]
            env_list.append(env_dict)

    data = ""
    for env in env_list:
        desc = env["name"]
        attr_name = env["attr_name"]
        attr_value = env["attr_value"]
        content = "{0}|{1}|{2}\n".format(attr_name, attr_value, desc)
        data += content

    result = general_message("0", "success", "查询成功", content=data, total=total)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/envs", response_model=Response, name="获取组件的环境变量参数")
async def get_env(request: Request,
                  serviceAlias: Optional[str] = None,
                  db: SessionClass = Depends(deps.get_session),
                  env=Depends(deps.get_current_team_env)) -> Any:
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

    service = service_info_repo.get_service(db, serviceAlias, env.env_id)

    if not env_type:
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    if env_type not in ("inner", "outer"):
        return JSONResponse(general_message(400, "param error", "参数异常"), status_code=400)
    env_list = []
    if env_type == "inner":
        if env_name:
            # 获取总数
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and \
                    service_id='{1}' and scope='inner' and attr_name like '%{2}%';".format(
                service.tenant_env_id, service.service_id, env_name))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, \
                    attr_value, is_change, scope, create_time from tenant_service_env_var \
                        where tenant_env_id='{0}' and service_id='{1}' and scope='inner' and \
                            attr_name like '%{2}%' order by attr_name LIMIT {3},{4};".format(
                service.tenant_env_id, service.service_id, env_name, start, end))).fetchall()
        else:
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}'\
                     and scope='inner';".format(service.tenant_env_id, service.service_id))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, attr_value,\
                     is_change, scope, create_time from tenant_service_env_var where tenant_env_id='{0}' \
                         and service_id='{1}' and scope='inner' order by attr_name LIMIT {2},{3};".format(
                service.tenant_env_id, service.service_id, start, end))).fetchall()
        if len(env_tuples) > 0:
            for env_tuple in env_tuples:
                env_dict = dict()
                env_dict["ID"] = env_tuple[0]
                env_dict["tenant_env_id"] = env_tuple[1]
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
            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}'\
                     and scope='outer' and attr_name like '%{2}%';".format(service.tenant_env_id,
                                                                           service.service_id,
                                                                           env_name))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, attr_value, is_change, \
                    scope, create_time from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}'\
                         and scope='outer' and attr_name like '%{2}%' order by attr_name LIMIT {3},{4};".format(
                service.tenant_env_id, service.service_id, env_name, start, end))).fetchall()
        else:

            env_count = (db.execute("select count(*) from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}' \
                    and scope='outer';".format(service.tenant_env_id, service.service_id))).fetchall()

            total = env_count[0][0]
            start = (page - 1) * page_size
            remaining_num = total - (page - 1) * page_size
            end = page_size
            if remaining_num < page_size:
                end = remaining_num

            env_tuples = (db.execute("select ID, tenant_env_id, service_id, container_port, name, attr_name, attr_value, is_change,\
                     scope, create_time from tenant_service_env_var where tenant_env_id='{0}' and service_id='{1}'\
                          and scope='outer' order by attr_name LIMIT {2},{3};".format(
                service.tenant_env_id, service.service_id, start, end))).fetchall()
        if len(env_tuples) > 0:
            for env_tuple in env_tuples:
                env_dict = dict()
                env_dict["ID"] = env_tuple[0]
                env_dict["tenant_env_id"] = env_tuple[1]
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

    result = general_message("0", "success", "查询成功", bean=bean, list=jsonable_encoder(env_list))
    return JSONResponse(result, status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/batch_envs", response_model=Response,
             name="为组件批量添加环境变量")
async def batch_add_envs(request: Request,
                         env_id: Optional[str] = None,
                         serviceAlias: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         user=Depends(deps.get_current_user)) -> Any:
    """
    为组件批量添加环境变量
    """
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    content = data.get("content", "")
    scope = data.get('scope', "inner")
    is_change = data.get('is_change', True)
    row_datas = content.split("\n")
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)

    if not scope:
        return JSONResponse(general_message(400, "params error", "参数异常"), status_code=400)
    if scope not in ("inner", "outer"):
        return JSONResponse(general_message(400, "params error", "scope范围只能是inner或outer"), status_code=400)

    # 批量更新、新增、删除操作
    result = env_var_service.batch_update_service_env(session=session, row_datas=row_datas, env=env,
                                                      service=service,
                                                      is_change=is_change, scope=scope, user=user)
    if result:
        return JSONResponse(result, status_code=result["code"])

    return JSONResponse(general_message(200, "success", "添加成功"), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/envs", response_model=Response, name="为组件添加环境变量")
async def add_env(request: Request,
                  env_id: Optional[str] = None,
                  serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  user=Depends(deps.get_current_user)) -> Any:
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
    env = env_repo.get_env_by_env_id(session, env_id)
    if not env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    data = await request.json()
    name = data.get("name", "")
    attr_name = data.get("attr_name", "")
    attr_value = data.get("attr_value", "")
    scope = data.get('scope', "")
    is_change = data.get('is_change', True)
    service = service_info_repo.get_service(session, serviceAlias, env.env_id)
    # try:
    if not scope or not attr_name:
        return JSONResponse(general_message(400, "params error", "参数异常"), status_code=400)
    if scope not in ("inner", "outer"):
        return JSONResponse(general_message(400, "params error", "scope范围只能是inner或outer"), status_code=400)
    code, msg, data = env_var_service.add_service_env_var(session=session, tenant_env=env, service=service,
                                                          container_port=0, name=name, attr_name=attr_name,
                                                          attr_value=attr_value,
                                                          is_change=is_change, scope=scope, user_name=user.nick_name)
    if code != 200:
        result = general_message(code, "add env error", msg)
        return JSONResponse(result, status_code=code)
    result = general_message(code, msg, "环境变量添加成功", bean=jsonable_encoder(data))
    return JSONResponse(result, status_code=200)


@router.delete("/teams/{team_name}/env/{tenant_env_id}/apps/{serviceAlias}/envs/{env_id}", response_model=Response,
               name="删除组件环境变量")
async def delete_env(serviceAlias: Optional[str] = None,
                     tenant_env_id: Optional[str] = None,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user)) -> Any:
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
    tenant_env = env_repo.get_env_by_env_id(session, tenant_env_id)
    if not tenant_env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, tenant_env.env_id)
    env_var_service.delete_env_by_env_id(session=session, tenant_env=tenant_env, service=service, env_id=env_id,
                                         user_name=user.nick_name)
    result = general_message("0", "success", "删除成功")
    return JSONResponse(result, status_code=200)


@router.patch("/teams/{team_name}/env/{tenant_env_id}/apps/{serviceAlias}/envs/{env_id}", response_model=Response,
              name="变更环境变量范围")
async def move_env(request: Request,
                   serviceAlias: Optional[str] = None,
                   tenant_env_id: Optional[str] = None,
                   env_id: Optional[str] = None,
                   session: SessionClass = Depends(deps.get_session),
                   user=Depends(deps.get_current_user)) -> Any:
    """变更环境变量范围"""
    tenant_env = env_repo.get_env_by_env_id(session, tenant_env_id)
    if not tenant_env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    service = service_info_repo.get_service(session, serviceAlias, tenant_env.env_id)
    # todo await
    scope = await parse_item(request, 'scope', required=True, error="scope is is a required parameter")
    env = env_var_service.patch_env_scope(session=session, tenant_env=tenant_env, service=service, env_id=env_id,
                                          scope=scope,
                                          user_name=user.nick_name)
    if env:
        return JSONResponse(general_message(code=200, msg="success", msg_show="更新成功", bean=jsonable_encoder(env)),
                            status_code=200)
    else:
        return JSONResponse(general_message(code=200, msg="success", msg_show="更新成功", bean={}), status_code=200)


@router.put("/teams/{team_name}/env/{tenant_env_id}/apps/{serviceAlias}/envs/{env_id}", response_model=Response,
            name="修改组件环境变量")
async def modify_env(request: Request,
                     tenant_env_id: Optional[str] = None,
                     serviceAlias: Optional[str] = None,
                     env_id: Optional[str] = None,
                     session: SessionClass = Depends(deps.get_session),
                     user=Depends(deps.get_current_user)) -> Any:
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
    tenant_env = env_repo.get_env_by_env_id(session, tenant_env_id)
    if not tenant_env:
        return JSONResponse(general_message(404, "env not exist", "环境不存在"), status_code=400)
    if not env_id:
        return JSONResponse(general_message(400, "env_id not specify", "环境变量ID未指定"))
    data = await request.json()
    name = data.get("name", "")
    attr_value = data.get("attr_value", "")

    service = service_info_repo.get_service(session, serviceAlias, tenant_env.env_id)

    code, msg, env = env_var_service.update_env_by_env_id(session=session, tenant_env=tenant_env, service=service,
                                                          env_id=env_id, name=name, attr_value=attr_value,
                                                          user_name=user.nick_name)
    if code != 200:
        raise AbortRequest(msg="update value error", msg_show=msg, status_code=code)
    result = general_message("0", "success", "更新成功", bean=jsonable_encoder(env))
    return JSONResponse(result, status_code=200)
