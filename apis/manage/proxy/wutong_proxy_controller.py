import os
from typing import Optional, Any
from fastapi import APIRouter, Request, Depends
from starlette.responses import JSONResponse
from clients.remote_app_client import remote_app_client
from core import deps
from core.utils.return_message import general_message
from database.session import SessionClass
from schemas.response import Response
from service.region_service import region_services

router = APIRouter()


@router.api_route(
    "/wt-proxy/{url:path}",
    methods=[
        "post",
        "get",
        "delete",
        "put",
        "patch"],
    include_in_schema=False,
    response_model=Response, name="接口代理")
async def proxy(
        request: Request,
        url: Optional[str] = None,
        session: SessionClass = Depends(deps.get_session)) -> Any:
    body = await request.body()
    try:
        data_json = await request.json()
    except:
        data_json = {}
    region = await region_services.get_region_by_request(session, request)
    if not region:
        return JSONResponse(general_message(400, "not found region", "数据中心不存在"), status_code=400)

    remoteurl = "http://{0}:{1}/{2}".format(
        os.getenv("ADAPTOR_HOST", "127.0.0.1"), os.getenv("ADAPTOR_PORT", "8089"), url)
    response = await remote_app_client.proxy(
        request,
        remoteurl,
        region,
        data_json,
        body)
    return response
