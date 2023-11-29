import nacos
from loguru import logger

from core.setting import settings

client = nacos.NacosClient(
    settings.NACOS_HOST,
    namespace=settings.SERVER_NAMESPACE_ID)


async def beat():
    logger.info("==========发送nacos心跳包===========")
    # client.send_heartbeat(
    #     settings.SERVICE_NAME, settings.SERVICE_IP, settings.SERVICE_PORT,
    #     group_name=settings.SERVICE_GROUP_NAME)


# 微服务注册nacos
def register_nacos():
    client.add_naming_instance(
        settings.SERVICE_NAME, settings.SERVICE_IP, settings.SERVICE_PORT,
        group_name=settings.SERVICE_GROUP_NAME)


# 注销微服务
def remove_nacos():
    client.remove_naming_instance(
        settings.SERVICE_NAME, settings.SERVICE_IP, settings.SERVICE_PORT,
        group_name=settings.SERVICE_GROUP_NAME, ephemeral=False)
