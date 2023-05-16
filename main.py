# 初始化app实例
import atexit
import fcntl

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.responses import JSONResponse

from apis.apis import api_router
from common.api_base_http_client import ApiBaseHttpClient
from core import nacos
from core.nacos import register_nacos
from core.utils.return_message import general_message
from database.session import engine, Base, settings, SessionClass
from exceptions.main import ServiceHandleException
from middleware import register_middleware
from service.scheduler import recycle

if settings.ENV == "PROD":
    # 生产关闭swagger
    app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None)
else:
    app = FastAPI(title=settings.APP_NAME, openapi_url=f"{settings.API_PREFIX}/openapi.json")


@app.exception_handler(ApiBaseHttpClient.CallApiError)
async def exception_handler(request: Request, exc: ApiBaseHttpClient.CallApiError):
    """
    捕获请求参数
    :param request:
    :param exc:
    :return:
    """
    logger.error("catch exception,request:{},error_message:{}", request.url, exc.body.msg)
    return JSONResponse(general_message(exc.message["http_code"], exc.body.msg, exc.body.msg),
                        status_code=exc.message["http_code"])


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


# jobstores={'default': RedisJobStore(db=int(settings.REDIS_DATABASE) + 1,
#                                                                  host=settings.REDIS_HOST,
#                                                                  password=settings.REDIS_PASSWORD,
#                                                                  port=int(settings.REDIS_PORT))}
scheduler = AsyncIOScheduler()


@scheduler.scheduled_job('cron', second="0", minute='0', hour="*", day="*", month="*", year="*")
def scheduler_delete_task():
    scheduler_session = SessionClass()
    try:
        logger.info("初始化定时清理回收站任务")
        recycle.recycle_delete_task(session=scheduler_session)
        scheduler_session.commit()
    except:
        scheduler_session.rollback()
    scheduler_session.expunge_all()
    scheduler_session.close()


@scheduler.scheduled_job('interval', seconds=5)
def scheduler_nacos_beat():
    if not settings.DEBUG:
        nacos.beat()


def start_scheduler():
    f = open("scheduler.lock", "wb")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scheduler.start()
    except:
        pass

    def unlock():
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

    atexit.register(unlock)


@app.on_event('startup')
def startup_event():
    """
    获取链接
    :return:
    """
    Base.metadata.create_all(engine)
    # 微服务注册
    if not settings.DEBUG:
        register_nacos()
    # 启动定时任务调度器
    start_scheduler()


@app.on_event('shutdown')
def shutdown_event():
    """
    关闭
    :return:
    """
    scheduler.shutdown()


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
        reload=settings.RELOAD,
        workers=settings.WORKERS
    )
