# 消息队列redis客户端
# from loguru import logger
#
# from core.setting import settings
# from service.event.redis_service import RedisService, RedisStreamService
#
# stream_redis_service = RedisService(host=settings.REDIS_STREAM_HOST,
#                                     port=int(settings.REDIS_STREAM_PORT),
#                                     pwd=settings.REDIS_STREAM_PASSWORD,
#                                     db=int(settings.REDIS_STREAM_DATABASE))
# init_redis_service = stream_redis_service.get_redis_client_from_pool()
# if not init_redis_service.exists(settings.REDIS_STREAM_NAME):
#     logger.info("Redis消息队列不存在,初始化队列,stream_name:{},group_name:{}",
#                 settings.REDIS_STREAM_NAME,
#                 settings.REDIS_STREAM_GROUP_NAME)
#     init_redis_stream = RedisStreamService(redis_client=init_redis_service,
#                                            stream_name=settings.REDIS_STREAM_NAME,
#                                            consumer_group=settings.REDIS_STREAM_GROUP_NAME)
#     init_redis_stream.stream_init({"message": "init_stream"}, id="0", max_len=10, target=None)


# def send_message(message):
#     message = message.__dict__
#     redis_service = stream_redis_service.get_redis_client_from_pool()
#     redis_stream = RedisStreamService(redis_client=redis_service,
#                                       stream_name=settings.REDIS_STREAM_NAME,
#                                       consumer_group=settings.REDIS_STREAM_GROUP_NAME)
#
#     redis_stream.add(message)
#





    # if not redis_service.exists(settings.REDIS_STREAM_NAME):
    #     redis_stream.stream_init(message, id="0", max_len=10, target=None)
    # else:
    #     redis_stream.add(message)
