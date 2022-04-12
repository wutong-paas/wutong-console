import datetime
from fastapi import Request
from fastapi.openapi.models import Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class AccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = datetime.datetime.now()
        response = await call_next(request)
        end_time = datetime.datetime.now()
        logger.info(
            f"{request.client.host} {request.method} {request.url} {response.status_code} {end_time - start_time}"
        )
        return response
