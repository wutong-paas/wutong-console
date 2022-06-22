# 初始化app实例
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from loguru import logger
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

# # 自定义定时任务调度器
# # 使用`RedisJobStore`创建任务存储
scheduler = AsyncIOScheduler(jobstores={'default': RedisJobStore(db=int(settings.REDIS_DATABASE) + 1,
                                                                 host=settings.REDIS_HOST,
                                                                 password=settings.REDIS_PASSWORD,
                                                                 port=int(settings.REDIS_PORT))})


# 定时任务:扫描组件表投递MQ
# 周期: day='*', hour=2, minute=0, second=0
@scheduler.scheduled_job('cron', minute='*')
def scheduler_cron_task_test():
    """
    corn表达式定时任务,参数说明:
    year(int or str)	年,4位数字
    month(int or str)	月（范围1-12）
    day(int or str)	    日（范围1-31）
    hour(int or str)	时（0-23）
    minute(int or str)	分（0-59）
    second(int or str)	秒（0-59）
    """
    logger.info("周期性定时任务开始执行...")


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
    # password=settings.REDIS_PASSWORD,
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

## 测试路由
from worker.app import router

app.include_router(router)
app.state.api = None

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app="main:app",
        host='0.0.0.0',
        port=int(settings.PORT),
        reload=settings.RELOAD
    )
