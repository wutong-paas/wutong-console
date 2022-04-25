# 初始化app实例
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from redis import StrictRedis
from starlette.responses import JSONResponse

from apis.apis import api_router
from core.utils.return_message import general_message
from database.session import engine, Base, settings
from exceptions.main import ServiceHandleException
from middleware import register_middleware

if settings.ENV == "PROD":
    # 生产关闭swagger
    app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None)
else:
    app = FastAPI(title=settings.APP_NAME, openapi_url=f"{settings.API_PREFIX}/openapi.json")


@app.exception_handler(ServiceHandleException)
async def validation_exception_handler(request: Request, exc: ServiceHandleException):
    """
    捕获请求参数
    :param request:
    :param exc:
    :return:
    """
    return JSONResponse(
        general_message(400, exc.msg, exc.msg_show), status_code=400)


def get_redis_pool():
    redis = StrictRedis(host=settings.REDIS_HOST, port=int(settings.REDIS_PORT), db=int(settings.REDIS_DATABASE),
                        password=settings.REDIS_PASSWORD, encoding="utf-8")
    return redis


@app.on_event('startup')
def startup_event():
    """
    获取链接
    :return:
    """
    Base.metadata.create_all(engine)
    app.state.redis = get_redis_pool()


@app.on_event('shutdown')
def shutdown_event():
    """
    关闭
    :return:
    """
    app.state.redis.connection_pool.disconnect()


app.mount("/static", StaticFiles(directory="weavescope"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")
# 设置中间件
register_middleware(app)

# 路由注册
app.include_router(api_router, prefix=settings.API_PREFIX)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app="main:app",
        host='0.0.0.0',
        port=int(settings.PORT),
        reload=settings.RELOAD
    )
