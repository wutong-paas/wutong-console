from functools import cmp_to_key
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import paginate, Params
from loguru import logger

from core import deps
from core.utils.return_message import general_message
from core.utils.validation import is_qualified_name
from database.session import SessionClass
from exceptions.bcode import ErrQualifiedName, ErrNamespaceExists
from exceptions.main import ServiceHandleException
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.enterprise.enterprise_repo import enterprise_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_applicants_repo import apply_repo
from repository.teams.team_region_repo import team_region_repo
from repository.teams.team_repo import team_repo
from repository.users.user_repo import user_repo
from schemas.response import Response
from schemas.team import CloseTeamAppParam
from service.app_actions.app_log import event_service
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.region_service import region_services
from service.team_service import team_services

router = APIRouter()


@router.post("/teams/{team_name}/apps/close", response_model=Response, name="关闭团队应用")
async def close_teams_app(params: Optional[CloseTeamAppParam] = CloseTeamAppParam(),
                          session: SessionClass = Depends(deps.get_session),
                          user=Depends(deps.get_current_user),
                          team=Depends(deps.get_current_team)) -> Any:
    if params.region_name:
        app_manage_service.close_all_component_in_tenant(session=session, tenant=team, region_name=params.region_name,
                                                         user=user)
    else:
        app_manage_service.close_all_component_in_team(session=session, tenant=team, user=user)
    return JSONResponse(general_message(200, "success", "操作成功"), status_code=200)


def __sort_events(event1, event2):
    event1_start_time = event1.get("StartTime") if isinstance(event1, dict) else event1.start_time
    event2_start_time = event2.get("StartTime") if isinstance(event2, dict) else event2.start_time
    if event1_start_time < event2_start_time:
        return 1
    if event1_start_time > event2_start_time:
        return -1
    if event1_start_time == event2_start_time:
        event1_ID = event1.get("ID") if isinstance(event1, dict) else event1.ID
        event2_ID = event2.get("ID") if isinstance(event2, dict) else event2.ID
        if event1_ID < event2_ID:
            return 1
        if event1_ID > event2_ID:
            return -1
        return 0


@router.post("/teams/add-teams", response_model=Response, name="新建团队")
async def add_team(request: Request,
                   session: SessionClass = Depends(deps.get_session),
                   user=Depends(deps.get_current_user)) -> Any:
    from_data = await request.json()
    team_alias = from_data["team_alias"]
    useable_regions = from_data["useable_regions"]
    namespace = from_data["namespace"]
    if not is_qualified_name(namespace):
        raise ErrQualifiedName(msg="invalid namespace name", msg_show="命名空间只能由小写字母、数字或“-”组成，并且必须以字母开始、以数字或字母结尾")
    enterprise_id = user.enterprise_id

    if not team_alias:
        result = general_message(400, "failed", "团队名不能为空")
        return JSONResponse(status_code=400, content=result)

    regions = []
    if useable_regions:
        regions = useable_regions.split(",")

    team = team_repo.team_is_exists_by_team_name(session, team_alias, enterprise_id)
    if team:
        result = general_message(400, "failed", "该团队名已存在")
        return JSONResponse(status_code=400, content=result)

    team = team_repo.team_is_exists_by_namespace(session, namespace, enterprise_id)
    if team:
        result = general_message(400, "failed", "该团队英文名已存在")
        return JSONResponse(status_code=400, content=result)

    enterprise = enterprise_repo.get_enterprise_by_enterprise_id(session, enterprise_id)
    if not enterprise:
        result = general_message(500, "user's enterprise is not found", "无企业信息")
        return JSONResponse(status_code=500, content=result)

    team = team_repo.create_team(session, user, enterprise, regions, team_alias, namespace)
    exist_namespace_region_names = []

    for r in regions:
        try:
            region_services.create_tenant_on_region(session=session, enterprise_id=enterprise.enterprise_id,
                                                    team_name=team.tenant_name, region_name=r, namespace=team.namespace)
        except ErrNamespaceExists:
            exist_namespace_region_names.append(r)
        except ServiceHandleException as e:
            logger.error(e)
        except Exception as e:
            logger.error(e)
    if len(exist_namespace_region_names) > 0:
        exist_namespace_region = ""
        for region_name in exist_namespace_region_names:
            region = region_repo.get_region_by_region_name(session, region_name)
            exist_namespace_region += " {}".format(region.region_alias)
        session.rollback()
        return JSONResponse(
            general_message(400, "success", "团队在集群【{} 】中已存在命名空间 {}".format(exist_namespace_region, team.namespace),
                            bean=jsonable_encoder(team)))
    result = general_message(200, "success", "团队添加成功", bean=jsonable_encoder(team))
    return JSONResponse(status_code=200, content=result)


@router.delete("/teams/{team_name}/delete", response_model=Response, name="删除团队")
async def delete_team(request: Request,
                      team_name: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session),
                      user=Depends(deps.get_current_user),
                      team=Depends(deps.get_current_team)) -> Any:
    """
    删除当前团队
    """
    try:
        team_services.delete_by_tenant_id(session=session, user=user, tenant=team)
        request.app.state.redis.delete("team_%s" % team_name)
        result = general_message(200, "delete a team successfully", "删除团队成功")
        return JSONResponse(result, status_code=result["code"])
    except ServiceHandleException as e:
        return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)


@router.post("/teams/{team_name}/add_team_user", response_model=Response, name="团队添加用户")
async def add_team_user(request: Request,
                        team_name: Optional[str] = None,
                        session: SessionClass = Depends(deps.get_session),
                        team=Depends(deps.get_current_team)) -> Any:
    try:
        from_data = await request.json()
        user_ids = from_data['user_ids']
        role_ids = from_data['role_ids']
        if not user_ids:
            return JSONResponse(general_message(400, "failed", "用户名为空"), status_code=400)
        if not role_ids:
            return JSONResponse(general_message(400, "failed", "角色ID为空"), status_code=400)
        try:
            user_ids = [int(user_id) for user_id in user_ids.split(",")]
            role_ids = [int(user_id) for user_id in role_ids.split(",")]
        except Exception as e:
            code = 400
            logger.exception(e)
            result = general_message(code, "Incorrect parameter format", "参数格式不正确")
            return JSONResponse(result, status_code=result["code"])

        user_id = team_services.user_is_exist_in_team(session=session, user_list=user_ids, tenant_name=team_name)
        if user_id:
            user_obj = user_repo.get_user_by_user_id(session=session, user_id=user_id)
            code = 400
            result = general_message(code, "user already exist", "用户{}已经存在".format(user_obj.nick_name))
            return JSONResponse(result, status_code=result["code"])

        code = 200
        team_services.add_user_role_to_team(session=session, tenant=team, user_ids=user_ids, role_ids=role_ids)
        result = general_message(code, "success", "用户添加到{}成功".format(team_name))
    except ServiceHandleException as e:
        code = 404
        result = general_message(code, e.msg, e.msg_show)
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps", response_model=Response, name="总览团队应用信息")
async def overview_team_app_info(request: Request,
                                 page: int = Query(default=1, ge=1, le=9999),
                                 page_size: int = Query(default=10, ge=1, le=500),
                                 team_name: Optional[str] = None,
                                 session: SessionClass = Depends(deps.get_session),
                                 team=Depends(deps.get_current_team)) -> Any:
    """
    总览 团队应用信息
    """
    query = request.query_params.get("query", "")
    # page = int(request.query_params.get("page", 1))
    # page_size = int(request.query_params.get("page_size", 10))

    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    # region_name = request.headers.get("X_REGION_NAME")
    region_name = region.region_name

    groups = application_repo.get_tenant_region_groups(session, team.tenant_id, region_name, query)
    total = len(groups)
    app_num_dict = {"total": total}
    start = (page - 1) * page_size
    end = page * page_size
    apps = []
    if groups:
        group_ids = [group.ID for group in groups]
        group_ids = group_ids[start:end]
        apps = application_service.get_multi_apps_all_info(session=session, app_ids=group_ids, region=region_name,
                                                           tenant_name=team_name, tenant=team)

    return JSONResponse(general_message(200, "success", "查询成功", list=jsonable_encoder(apps), bean=app_num_dict),
                        status_code=200)


@router.get("/teams/{team_name}/services/event", response_model=Response, name="应用事件动态")
async def team_services_event(
        # request: Request,
        page: int = Query(default=1, ge=1, le=9999),
        page_size: int = Query(default=3, ge=1, le=500),
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    组件事件动态
    """
    # page = request.query_params.get("page", 1)
    # page_size = request.query_params.get("page_size", 3)

    total = 0
    region_list = region_repo.get_team_opened_region(session, team.tenant_name)
    event_service_dynamic_list = []
    if region_list:
        for region in region_list:
            try:
                events, event_count, has_next = event_service.get_target_events(session=session, target="tenant",
                                                                                target_id=team.tenant_id,
                                                                                tenant=team,
                                                                                region=region.region_name,
                                                                                page=int(page),
                                                                                page_size=int(page_size))
                event_service_dynamic_list = event_service_dynamic_list + events
                total = total + event_count
            except Exception as e:
                logger.error("Region api return error {0}, ignore it".format(e))

    event_service_dynamic_list = sorted(event_service_dynamic_list, key=cmp_to_key(__sort_events))

    service_ids = []
    for event in event_service_dynamic_list:
        if event["Target"] == "service":
            service_ids.append(event["TargetID"])

    services = service_info_repo.list_by_component_ids(session, service_ids)

    event_service_list = []
    for event in event_service_dynamic_list:
        if event["Target"] == "service":
            for service in services:
                if service.service_id == event["TargetID"]:
                    event["service_alias"] = service.service_alias
                    event["service_name"] = service.service_cname
        event_service_list.append(event)

    params = Params(page=page, size=page_size)
    pg = paginate(event_service_list, params)
    total = pg.total
    event_page_list = pg.items
    event_list = [event for event in event_page_list]
    result = general_message(200, 'success', "查询成功", list=event_list, total=total)
    return JSONResponse(result, status_code=200)


@router.get("/teams/{team_name}/applicants", response_model=Response, name="获取当前团队所有的申请者")
async def get_applicants_info(request: Request,
                              team_name: Optional[str] = None,
                              session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    初始化团队和数据中心信息
    """
    page_num = int(request.query_params.get("page_num", 1))
    page_size = int(request.query_params.get("page_size", 5))
    rt_list = []
    applicants = apply_repo.get_applicants(session=session, team_name=team_name)
    for applicant in applicants:
        is_pass = applicant.is_pass
        if is_pass == 0:
            rt_list.append(jsonable_encoder(applicant))
    params = Params(page=page_num, size=page_size)
    pg = paginate(rt_list, params)
    total = pg.total
    page_aplic = pg.items
    rt_list = [apc for apc in page_aplic]
    # 返回
    result = general_message(200, "success", "查询成功", list=jsonable_encoder(rt_list), total=total)
    return JSONResponse(result, status_code=200)


@router.put("/teams/{team_name}/applicants", response_model=Response, name="管理员审核用户")
async def put_applicants(request: Request,
                         team_name: Optional[str] = None,
                         session: SessionClass = Depends(deps.get_session),
                         team=Depends(deps.get_current_team)) -> Any:
    """管理员审核用户"""
    from_data = await request.json()
    user_id = from_data.get("user_id")
    action = from_data.get("action")
    role_ids = from_data.get("role_ids")
    join = apply_repo.get_applicants_by_id_team_name(session=session, user_id=user_id, team_name=team_name)
    if action is True:
        join.is_pass = 1
        try:
            team_services.add_user_to_team(session=session, tenant=team, user_id=user_id, role_ids=role_ids)
        except ServiceHandleException as e:
            return JSONResponse(general_message(e.status_code, e.msg, e.msg_show), status_code=e.status_code)
        # 发送通知
        info = "同意"
        team_repo.send_user_message_for_apply_info(session=session, user_id=user_id, team_name=team.tenant_name,
                                                   info=info)
        return JSONResponse(general_message(200, "join success", "加入成功"), status_code=200)
    else:
        join.is_pass = 2
        info = "拒绝"
        team_repo.send_user_message_for_apply_info(session=session, user_id=user_id, team_name=team_name, info=info)
        return JSONResponse(general_message(200, "join rejected", "拒绝成功"), status_code=200)


@router.get("/teams/{team_name}/exit", response_model=Response, name="退出当前团队")
async def exit_team(team_name: Optional[str] = None,
                    session: SessionClass = Depends(deps.get_session),
                    user=Depends(deps.get_current_user),
                    team=Depends(deps.get_current_team)) -> Any:
    """
    退出当前团队
    """
    if team.creater == user.user_id:
        return JSONResponse(general_message(409, "not allow exit.", "您是当前团队创建者，不能退出此团队"), status_code=409)
    code, msg_show = team_services.exit_current_team(session=session, team_name=team_name, user_id=user.user_id)
    if code == 200:
        result = general_message(code=code, msg="success", msg_show=msg_show)
    else:
        result = general_message(code=code, msg="failed", msg_show=msg_show)
    return JSONResponse(result, status_code=result.get("code", 200))


@router.delete("/teams/{team_name}/again_delete", response_model=Response, name="二次确认删除应用")
async def again_delete_app(request: Request,
                           session: SessionClass = Depends(deps.get_session),
                           user=Depends(deps.get_current_user),
                           team=Depends(deps.get_current_team)) -> Any:
    """
    二次确认删除组件
    """
    data = await request.json()
    service_id = data.get("service_id", None)
    service = service_info_repo.get_service_by_service_id(session, service_id)
    app_manage_service.delete_again(session, user, team, service, is_force=True)
    result = general_message(200, "success", "操作成功", bean={})
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/modifyname", response_model=Response, name="修改团队名称")
async def modify_team_name(
        request: Request,
        session: SessionClass = Depends(deps.get_session),
        team=Depends(deps.get_current_team)) -> Any:
    """
    修改团队名
    ---
    parameters:
        - name: team_name
          description: 旧团队名
          required: true
          type: string
          paramType: path
        - name: new_team_alias
          description: 新团队名
          required: true
          type: string
          paramType: body
    """
    data = await request.json()
    new_team_alias = data.get("new_team_alias", "")
    if new_team_alias:
        try:
            code = 200
            team = team_services.update_tenant_alias(session=session, tenant_name=team.tenant_name,
                                                     new_team_alias=new_team_alias)
            result = general_message(code, "update success", "团队名修改成功", bean=jsonable_encoder(team))
        except Exception as e:
            code = 500
            result = general_message(code, "update failed", "团队名修改失败")
            logger.exception(e)
    else:
        result = general_message(400, "failed", "修改的团队名不能为空")
        code = 400
    return JSONResponse(result, status_code=code)
