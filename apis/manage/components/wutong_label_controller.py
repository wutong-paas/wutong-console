from typing import Any, Optional

from fastapi import Request, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.component.service_label_repo import node_label_repo, label_repo, service_label_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.label_service import label_service

router = APIRouter()


@router.get("/teams/{team_name}/apps/{serviceAlias}/labels", response_model=Response, name="获取组件已使用和未使用的标签")
async def get_env(serviceAlias: Optional[str] = None,
                  session: SessionClass = Depends(deps.get_session),
                  team=Depends(deps.get_current_team)) -> Any:
    """
    获取组件已使用和未使用的标签
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
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    bean = label_service.get_service_labels(session=session, service=service)
    result = general_message(200, "success", "查询成功", bean=jsonable_encoder(bean))
    return JSONResponse(result, status_code=result["code"])


@router.get("/teams/{team_name}/apps/{serviceAlias}/labels/available", response_model=Response, name="添加特性获取可用标签")
async def get_available_labels(serviceAlias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               team=Depends(deps.get_current_team)) -> Any:
    """
    添加特性获取可用标签
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    region = team_region_repo.get_region_by_tenant_id(session, team.tenant_id)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    # 节点添加的标签和数据中心查询回来的标签才可被组件使用
    node_labels = node_label_repo.get_all_labels(session)
    labels_list = list()
    labels_name_list = list()
    if node_labels:
        node_labels_id_list = [label.label_id for label in node_labels]
        label_obj_list = label_repo.get_labels_by_label_ids(session, node_labels_id_list)
        for label_obj in label_obj_list:
            labels_name_list.append(label_obj.label_name)
    # 查询数据中心可使用的标签
    labels = label_service.list_available_labels(session=session, tenant=team, region_name=region_name)
    for label in labels:
        labels_name_list.append(label.label_name)

    # 去除该组件已绑定的标签
    service_labels = service_label_repo.get_service_labels(session, service.service_id)
    if service_labels:
        service_labels_id_list = [label.label_id for label in service_labels]
        label_obj_list = label_repo.get_labels_by_label_ids(session, service_labels_id_list)
        service_labels_name_list = [label.label_name for label in label_obj_list]
        for service_labels_name in service_labels_name_list:
            if service_labels_name in labels_name_list:
                labels_name_list.remove(service_labels_name)
    for labels_name in labels_name_list:
        label_dict = dict()
        label_oj = label_repo.get_labels_by_label_name(session, labels_name)
        label_dict["label_id"] = label_oj.label_id
        label_dict["label_alias"] = label_oj.label_alias
        labels_list.append(label_dict)

    result = general_message(200, "success", "查询成功", list=labels_list)
    return JSONResponse(result, status_code=result["code"])


@router.post("/teams/{team_name}/apps/{serviceAlias}/labels", response_model=Response, name="添加组件标签")
async def set_available_labels(request: Request,
                               serviceAlias: Optional[str] = None,
                               session: SessionClass = Depends(deps.get_session),
                               user=Depends(deps.get_current_user),
                               team=Depends(deps.get_current_team)) -> Any:
    """
    添加组件标签
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
        - name: body
          description: 组件标签 ["label_id1","label_id2"]
          required: true
          type: string
          paramType: body
    """
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    data = await request.json()
    label_ids = data.get("label_ids", None)
    if not label_ids:
        return JSONResponse(general_message(400, "param error", "标签ID未指定"), status_code=400)
    code, msg, event = label_service.add_service_labels(session=session, tenant=team, service=service,
                                                        label_ids=label_ids, user_name=user.nick_name)
    if code != 200:
        return JSONResponse(general_message(code, "add labels error", msg), status_code=code)
    result = general_message(200, "success", "标签添加成功")
    return JSONResponse(result, status_code=result["code"])


@router.delete("/teams/{team_name}/apps/{serviceAlias}/labels", response_model=Response, name="删除组件标签")
async def delete_available_labels(request: Request,
                                  serviceAlias: Optional[str] = None,
                                  session: SessionClass = Depends(deps.get_session),
                                  user=Depends(deps.get_current_user),
                                  team=Depends(deps.get_current_team)) -> Any:
    """
    删除组件标签
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
        - name: label_id
          description: 组件标签 id
          required: true
          type: string
          paramType: form
    """
    service = service_info_repo.get_service(session, serviceAlias, team.tenant_id)
    data = await request.json()
    label_id = data.get("label_id", None)
    if not label_id:
        return JSONResponse(general_message(400, "param error", "标签ID未指定"), status_code=400)
    service_label = service_label_repo.get_service_label(session, service.service_id, label_id)
    if not service_label:
        return JSONResponse(general_message(400, "tag does not exist", "标签不存在"), status_code=400)
    code, msg, event = label_service.delete_service_label(session=session, tenant=team, service=service,
                                                          label_id=label_id, user_name=user.nick_name)
    if code != 200:
        return JSONResponse(general_message(code, "add labels error", msg), status_code=code)
    result = general_message(200, "success", "标签删除成功")
    return JSONResponse(result, status_code=result["code"])
