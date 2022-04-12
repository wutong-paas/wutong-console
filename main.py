# 初始化app实例
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis import StrictRedis
from apis.apis import api_router
from database.session import engine, Base, settings
from middleware import register_middleware

if settings.ENV == "PROD":
    # 生产关闭swagger
    app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None)
else:
    app = FastAPI(title=settings.APP_NAME, openapi_url=f"{settings.API_PREFIX}/openapi.json")


def get_redis_pool():
    # redis = asredis.from_url("redis://localhost", password='123456', encoding="utf-8", decode_responses=True)
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
