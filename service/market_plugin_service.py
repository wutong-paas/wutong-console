from clients.remote_plugin_client import remote_plugin_client
from database.session import SessionClass
from repository.market.center_repo import center_app_repo


def get_sync_event_result(session: SessionClass, region_name, tenant_env, record_event):
    """
    获取插件同步结果

    :param region_name:
    :param tenant_name:
    :param record_event:
    :return:
    """
    res, body = remote_plugin_client.share_plugin_result(session,
                                                         region_name, tenant_env, record_event.plugin_id,
                                                         record_event.region_share_id)
    ret = body.get('bean')
    if ret and ret.get('status'):
        record_event.event_status = ret.get("status")
        # record_event.save()
    return record_event


def get_paged_plugins(
        session: SessionClass,
        plugin_name="",
        is_complete=None,
        scope="",
        source="",
        tenant=None,
        page=1,
        limit=10,
        order_by="",
        category=""):
    """

    :param plugin_name:
    :param is_complete:
    :param scope:
    :param source:
    :param tenant:
    :param page:
    :param limit:
    :param order_by:
    :param category:
    :return:
    """
    data = center_app_repo.get_paged_plugins(session, plugin_name, is_complete, scope, source, tenant, page, limit,
                                             order_by, category)
    return data
