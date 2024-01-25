from typing import Any, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.responses import StreamingResponse
from clients.remote_component_scheduling_client import remote_scheduling_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from schemas.response import Response
from schemas.components import LabelSchedulingParam, TaintTolerationsParam, AddNodeSchedulingParam

router = APIRouter()


@router.get("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/rule", response_model=Response,
            name="获取组件调度配置")
async def get_service_scheduling_rule(
        service_alias: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    获取组件调度配置
    """
    try:
        rules = remote_scheduling_client.get_service_scheduling_rule(session, env.region_code, env, service_alias)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "get error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(400, "get error", "获取失败"),
            status_code=200,
        )

    return JSONResponse(general_message(200, "get success", "获取成功", bean=rules), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/label", response_model=Response,
             name="新增组件标签调度")
async def add_service_label_scheduling(
        service_alias: Optional[str] = None,
        params: Optional[LabelSchedulingParam] = LabelSchedulingParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    新增组件标签调度
    """
    key = params.label_key
    value = params.label_value
    if not key:
        return JSONResponse(
            general_message(400, "add error", "key不能为空"),
            status_code=200,
        )
    body = {
        "label_key": key,
        "label_value": value,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.add_service_label_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "add error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "add error", "新增失败"),
            status_code=200,
        )

    return JSONResponse(general_message(200, "add success", "新增成功"), status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/label", response_model=Response,
            name="更新组件标签调度")
async def update_service_label_scheduling(
        service_alias: Optional[str] = None,
        params: Optional[LabelSchedulingParam] = LabelSchedulingParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    更新组件标签调度
    """
    key = params.label_key
    value = params.label_value
    if not key:
        return JSONResponse(
            general_message(400, "update error", "key不能为空"),
            status_code=200,
        )
    body = {
        "label_key": key,
        "label_value": value,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.update_service_label_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "update error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "update error", "更新失败"),
            status_code=200,
        )

    return JSONResponse(general_message(200, "update success", "更新成功"), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/label", response_model=Response,
               name="删除组件标签调度")
async def delete_service_label_scheduling(
        service_alias: Optional[str] = None,
        label_key: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件标签调度
    """
    if not label_key:
        return JSONResponse(
            general_message(400, "delete error", "key不能为空"),
            status_code=200,
        )
    body = {
        "label_key": label_key,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.delete_service_label_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "delete error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "delete error", "删除失败"),
            status_code=200,
        )

    return JSONResponse(general_message(200, "delete success", "删除成功"), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/node", response_model=Response,
             name="新增组件节点调度")
async def add_service_node_scheduling(
        service_alias: Optional[str] = None,
        params: Optional[AddNodeSchedulingParam] = AddNodeSchedulingParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    新增组件节点调度
    """
    node_name = params.node_name
    body = {
        "node_name": node_name,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.add_service_node_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "add error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "add error", "新增失败"),
            status_code=200,
        )

    return JSONResponse(general_message(200, "add success", "新增成功"), status_code=200)


@router.post("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/tolerations", response_model=Response,
             name="新增组件污点容忍")
async def add_service_tolerations(
        service_alias: Optional[str] = None,
        params: Optional[TaintTolerationsParam] = TaintTolerationsParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    新增组件污点容忍
    """
    key = params.taint_key
    effect = params.effect
    if not key:
        return JSONResponse(
            general_message(400, "key not null", "污点键不能为空"),
            status_code=200,
        )
    if not effect:
        return JSONResponse(
            general_message(400, "effect not null", "效果不能为空"),
            status_code=200,
        )

    body = {
        "taint_key": key,
        "op": params.op,
        "taint_value": params.taint_value,
        "effect": effect,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.add_service_taint_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "add error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "add error", "新增失败"),
            status_code=200,
        )
    return JSONResponse(general_message(200, "add success", "新增成功"), status_code=200)


@router.put("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/tolerations", response_model=Response,
            name="更新组件污点容忍")
async def update_service_tolerations(
        service_alias: Optional[str] = None,
        params: Optional[TaintTolerationsParam] = TaintTolerationsParam(),
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    更新组件污点容忍
    """
    key = params.taint_key
    effect = params.effect
    if not key:
        return JSONResponse(
            general_message(400, "key not null", "污点键不能为空"),
            status_code=200,
        )
    if not effect:
        return JSONResponse(
            general_message(400, "effect not null", "效果不能为空"),
            status_code=200,
        )

    body = {
        "taint_key": key,
        "op": params.op,
        "taint_value": params.taint_value,
        "effect": effect,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.update_service_taint_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "add error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "add error", "更新失败"),
            status_code=200,
        )
    return JSONResponse(general_message(200, "add success", "更新成功"), status_code=200)


@router.delete("/teams/{team_name}/env/{env_id}/services/{service_alias}/scheduling/tolerations",
               response_model=Response,
               name="删除组件污点容忍")
async def delete_service_tolerations(
        service_alias: Optional[str] = None,
        taint_key: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session),
        user=Depends(deps.get_current_user),
        env=Depends(deps.get_current_team_env)) -> Any:
    """
    删除组件污点容忍
    """

    if not taint_key:
        return JSONResponse(
            general_message(400, "key not null", "污点键不能为空"),
            status_code=200,
        )

    body = {
        "taint_key": taint_key,
        "operator": user.nick_name
    }
    try:
        remote_scheduling_client.delete_service_taint_scheduling(session, env.region_code, env, service_alias, body)
    except remote_scheduling_client.CallApiError as e:
        return JSONResponse(
            general_message(e.message['http_code'], "add error", e.message['body']['msg']),
            status_code=200,
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            general_message(500, "add error", "删除失败"),
            status_code=200,
        )
    return JSONResponse(general_message(200, "add success", "删除成功"), status_code=200)
