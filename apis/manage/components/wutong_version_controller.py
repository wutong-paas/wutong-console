import operator
from typing import Any, Optional

from fastapi import Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi_pagination import Params, paginate

from clients.remote_build_client import remote_build_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from repository.teams.team_region_repo import team_region_repo
from schemas.response import Response
from service.region_service import region_services

router = APIRouter()

BUILD_KIND_MAP = {
    "build_from_source_code": "源码构建",
    "build_from_image": "镜像构建",
    "build_from_market_image": "云市镜像构建",
    "build_from_market_slug": "云市slug包构建"
}


@router.get("/teams/{team_name}/env/{env_id}/apps/{serviceAlias}/version", response_model=Response, name="获取组件的构建版本")
async def get_version(request: Request,
                      env_id: Optional[str] = None,
                      serviceAlias: Optional[str] = None,
                      session: SessionClass = Depends(deps.get_session)) -> Any:
    """
    获取组件的构建版本
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
        return JSONResponse(general_message(400, "not found env", "环境不存在"), status_code=400)
    page = int(request.query_params.get("page_num", 1))
    page_size = int(request.query_params.get("page_size", 10))
    service = service_info_repo.get_service(session, serviceAlias, env.tenant_id)
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)
    region_name = region.region_name

    body = remote_build_client.get_service_build_versions(session, region_name, env,
                                                          service.service_alias)
    build_version_sort = body["bean"]["list"]
    run_version = body["bean"]["deploy_version"]
    total_num_list = list()
    for build_version_info in build_version_sort:
        if build_version_info["final_status"] in ("success", "failure"):
            total_num_list.append(build_version_info)
    total_num = len(total_num_list)
    success_num = 0
    failure_num = 0
    for build_info in build_version_sort:
        if build_info["final_status"]:
            if build_info["final_status"] == "success":
                success_num += 1
            else:
                failure_num += 1
    build_version_sort.sort(key=operator.itemgetter('build_version'), reverse=True)
    params = Params(page=page, size=page_size)
    version_paginator = paginate(build_version_sort, params)
    build_version_list = version_paginator.items
    versions_info = build_version_list
    version_list = []

    for info in versions_info:
        version = {
            "event_id": info["event_id"],
            "build_version": info["build_version"],
            "kind": BUILD_KIND_MAP.get(info["kind"]),
            "service_type": info["delivered_type"],
            "repo_url": info["repo_url"],
            "create_time": info["create_time"],
            "status": info["final_status"],
            "build_user": "",
            # source code
            "code_commit_msg": info["code_commit_msg"],
            "code_version": info["code_version"],
            "code_branch": info.get("code_branch", "未知"),
            "code_commit_author": info["code_commit_author"],
            # image
            "image_repo": info["image_repo"],
            "image_domain": info.get("image_domain") if info.get("image_domain", "") else "docker.io",
            "image_tag": info.get("image_tag") if info.get("image_tag", "") else "latest",
        }

        if info["finish_time"] != "0001-01-01T00:00:00Z":
            version["finish_time"] = info["finish_time"]
        else:
            version["finish_time"] = ""

        version_list.append(version)
    res_versions = sorted(version_list, key=lambda version: version["build_version"], reverse=True)
    for res_version in res_versions:
        # 1:support upgrade
        # -1: support rollback
        # 2: do not support upgrade and rollback
        if res_version["status"] == "failure" or run_version == "":
            upgrade_or_rollback = 2
        else:
            # get deploy version from region
            if res_version["status"] == "failure":
                upgrade_or_rollback = 2
            elif int(res_version["build_version"]) > int(run_version):
                upgrade_or_rollback = 1
            elif int(res_version["build_version"]) == int(run_version):
                upgrade_or_rollback = 0
            else:
                upgrade_or_rollback = -1
        res_version.update({"upgrade_or_rollback": upgrade_or_rollback})
    is_upgrade = False
    if res_versions and run_version != "":
        latest_version = res_versions[0]["build_version"]
        if int(latest_version) > int(run_version):
            is_upgrade = True
    bean = {
        "is_upgrade": is_upgrade,
        "current_version": run_version,
        "success_num": str(success_num),
        "failure_num": str(failure_num)
    }
    result = general_message(200, "success", "查询成功", bean=bean, list=res_versions, total=str(total_num))
    return JSONResponse(result, status_code=result["code"])
