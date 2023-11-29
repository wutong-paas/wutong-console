import nacos

from core.setting import settings

client = nacos.NacosClient(
    settings.NACOS_HOST,
    namespace=settings.SERVER_NAMESPACE_ID)


def beat():
    client.send_heartbeat(service_name=settings.SERVICE_GROUP_NAME + "@@" + settings.SERVICE_NAME,
                          ip=settings.SERVICE_IP, port=settings.SERVICE_PORT)


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
