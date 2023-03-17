# 初始化app实例
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from loguru import logger
from redis import StrictRedis
from starlette.responses import JSONResponse

from apis.apis import api_router
from core import deps
from core.nacos import register_nacos, beat
from core.utils.return_message import general_message
from database import session
from database.session import engine, Base, settings
from exceptions.main import ServiceHandleException
from middleware import register_middleware
from service.scheduler import recycle

if settings.ENV == "PROD":
    # 生产关闭swagger
    app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None)
else:
    app = FastAPI(title=settings.APP_NAME, openapi_url=f"{settings.API_PREFIX}/openapi.json")


# 微服务注册
# register_nacos()


@app.exception_handler(ServiceHandleException)
async def exception_handler(request: Request, exc: ServiceHandleException):
    """
    捕获请求参数
    :param request:
    :param exc:
    :return:
    """
    logger.error("catch exception,request:{},error_message:{}", request.url, exc.msg_show)
    return JSONResponse(general_message(exc.status_code, exc.msg, exc.msg_show), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exception: RequestValidationError):
    logger.error("catch validation error for Request,request_url:{}, request_path_params:{}, request_query_params:{}",
                 request.url,
                 request.path_params,
                 request.query_params.items())
    logger.exception(exception)
    return JSONResponse(general_message(400, "validation error", "参数异常"), status_code=400)


def get_redis_pool():
    redis = StrictRedis(host=settings.REDIS_HOST, port=int(settings.REDIS_PORT), db=int(settings.REDIS_DATABASE),
                        # password=settings.REDIS_PASSWORD,
                        encoding="utf-8")
    return redis


scheduler = AsyncIOScheduler(jobstores={'default': RedisJobStore(db=int(settings.REDIS_DATABASE) + 1,
                                                                 host=settings.REDIS_HOST,
                                                                 # password=settings.REDIS_PASSWORD,
                                                                 port=int(settings.REDIS_PORT))})


@scheduler.scheduled_job('cron', second="0", minute='0', hour="0", day="*", month="*", year="*")
def scheduler_cron_task_test():
    recycle.recycle_delete_task(session=session.SessionClass())


@app.on_event('startup')
def startup_event():
    """
    获取链接
    :return:
    """
    Base.metadata.create_all(engine)
    app.state.redis = get_redis_pool()

    # 启动定时任务调度器
    scheduler.start()


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

app.state.api = None

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app="main:app",
        host='0.0.0.0',
        port=int(settings.PORT),
        reload=settings.RELOAD
    )
