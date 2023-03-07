import datetime

from fastapi_pagination import Params, paginate
from loguru import logger
from sqlalchemy import delete

from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.utils.constants import ServiceEventConstants, LogConstants
from core.utils.timeutil import str_to_time, time_to_str
from database.session import SessionClass
from core.setting import settings
from models.component.models import ComponentEvent
from repository.component.service_event_repo import event_repo
from repository.region.region_info_repo import region_repo
from repository.teams.team_region_repo import team_region_repo


class AppEventService:
    def get_event_log(self, session, tenant_env, region_name, event_id):
        content = []
        try:
            res, rt_data = remote_build_client.get_events_log(session, tenant_env, region_name, event_id)
            if int(res.status) == 200:
                content = rt_data["list"]
        except remote_build_client.CallApiError as e:
            logger.debug(e)
        return content

    def checkEventTimeOut(self, session: SessionClass, event):
        """检查事件是否超时，应用起停操作30s超时，其他操作3m超时"""
        start_time = event.start_time
        if event.type == "deploy" or event.type == "create":
            if (datetime.datetime.now() - start_time).seconds > 180:
                event.final_status = "timeout"
                event.status = "timeout"
                event.save()
                return True
        else:
            if (datetime.datetime.now() - start_time).seconds > 30:
                event.final_status = "timeout"
                event.status = "timeout"
                event.save()
                return True
        return False

    def __sync_region_service_event_status(self, session: SessionClass, region, tenant_env, events, timeout=False):
        local_events_not_complete = dict()
        for event in events:
            if not event.final_status or not event.status:
                local_events_not_complete[event.event_id] = event

        if not local_events_not_complete:
            return

        try:
            body = remote_build_client.get_tenant_events(session,
                                                         region, tenant_env,
                                                         list(local_events_not_complete.keys()))
        except Exception as e:
            logger.exception(e)
            return

        region_events = body.get('list')
        for region_event in region_events:
            local_event = local_events_not_complete.get(region_event.get('EventID'))
            if not local_event:
                continue
            if not region_event.get('Status'):
                if timeout:
                    self.checkEventTimeOut(session=session, event=local_event)
            else:
                local_event.status = region_event.get('Status')
                local_event.message = region_event.get('Message')
                local_event.code_version = region_event.get('CodeVersion')
                local_event.deploy_version = region_event.get('DeployVersion')
                local_event.final_status = 'complete'
                endtime = datetime.datetime.strptime(region_event.get('EndTime')[0:19], '%Y-%m-%d %H:%M:%S')
                if endtime:
                    local_event.end_time = endtime
                else:
                    local_event.end_time = datetime.datetime.now()
                local_event.save()

    def get_target_events(self, session: SessionClass, target, target_id, tenant_env, region, page, page_size):
        msg_list = []
        has_next = False
        total = 0
        res, rt_data = remote_build_client.get_target_events_list(session,
                                                                  region, tenant_env, target, target_id,
                                                                  page, page_size)
        if int(res.status) == 200:
            msg_list = rt_data.get("list", [])
            total = rt_data.get("number", 0)
            has_next = True
            if page_size * page >= total:
                has_next = False
        return msg_list, total, has_next

    def wrapper_code_version(self, session: SessionClass, service, event):
        if event.code_version:
            info = event.code_version.split(" ", 2)
            if len(info) == 3:
                versioninfo = {}
                ver = info[0].split(":", 1)
                versioninfo["code_version"] = ver[1]
                user = info[1].split(":", 1)
                versioninfo["user"] = user[1]
                commit = info[2].split(":", 1)
                if len(commit) > 1:
                    versioninfo["commit"] = commit[1]
                else:
                    versioninfo["commit"] = info[2]
                # deprecated
                if event.deploy_version == service.deploy_version:
                    versioninfo["rollback"] = False
                else:
                    versioninfo["rollback"] = True
                return versioninfo
        return {}

    def translate_event_type(self, session: SessionClass, action_type):
        TYPE_MAP = ServiceEventConstants.TYPE_MAP
        return TYPE_MAP.get(action_type, action_type)

    def get_service_event(self, session: SessionClass, tenant_env, service, page, page_size, start_time_str):
        # 前端传入时间到分钟，默认会加上00，这样一来刚部署的组件的日志无法查询到，所有将当前时间添加一分钟
        if start_time_str:
            start_time = str_to_time(start_time_str, fmt="%Y-%m-%d %H:%M")
            start_time_str = time_to_str(start_time + datetime.timedelta(minutes=1))

        events = event_repo.get_events_before_specify_time(tenant_env.env_id, service.service_id, start_time_str)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(events, params)
        total = event_paginator.total
        page_events = event_paginator.items
        has_next = True
        if page_size * page >= total:
            has_next = False
        self.__sync_region_service_event_status(session=session, region=service.service_region,
                                                tenant_env=tenant_env, events=page_events)

        re_events = []
        for event in list(page_events):
            event_re = event.__dict__
            # codeVersion = "版本:4c042b9 上传者:黄峻贤 Commit:Merge branch 'developer' into 'test'"
            version_info = self.wrapper_code_version(session=session, service=service, event=event)
            if version_info:
                event_re["code_version"] = version_info
            type_cn = self.translate_event_type(session=session, action_type=event.type)
            event_re["type_cn"] = type_cn
            re_events.append(event_re)
        return re_events, has_next

    def delete_service_events(self, session: SessionClass, service):
        session.execute(
            delete(ComponentEvent).where(ComponentEvent.service_id == service.service_id)
        )


class AppWebSocketService(object):
    def get_log_domain(self, session, request, region):
        region = region_repo.get_region_by_region_name(session, region_name=region)
        if not region:
            default_uri = settings.LOG_DOMAIN[region]
            if default_uri == "auto":
                host = request.META.get('HTTP_HOST').split(':')[0]
                return '{0}:6060'.format(host)
            return default_uri
        else:
            if region.wsurl == "auto":
                host = request.META.get('HTTP_HOST').split(':')[0]
                return '{0}:6060'.format(host)
            else:
                if "://" in region.wsurl:
                    ws_info = region.wsurl.split("://", 1)
                    if ws_info[0] == "wss":
                        return "https://{0}".format(ws_info[1])
                    else:
                        return "http://{0}".format(ws_info[1])
                return region.wsurl

    def __event_ws(self, session: SessionClass, request, region, sufix_uri):
        region = team_region_repo.get_region_by_region_name(session, region_name=region)
        if not region:
            default_uri = settings.EVENT_WEBSOCKET_URL[region]
            if default_uri == "auto":
                host = request.META.get('HTTP_HOST').split(':')[0]
                return "ws://{0}:6060/{1}".format(host, sufix_uri)
            else:
                return "{0}/{1}".format(default_uri, sufix_uri)
        else:
            if region.wsurl == "auto":
                host = request.META.get('HTTP_HOST').split(':')[0]
                return "ws://{0}:6060/{1}".format(host, sufix_uri)
            else:
                return "{0}/{1}".format(region.wsurl, sufix_uri)

    def get_event_log_ws(self, session: SessionClass, request, region):
        sufix_uri = "event_log"
        ws_url = self.__event_ws(session=session, request=request, region=region, sufix_uri=sufix_uri)
        return ws_url


class AppLogService(object):
    def get_history_log(self, session, tenant_env, service):
        try:
            body = remote_component_client.get_service_log_files(session,
                                                                 service.service_region, tenant_env,
                                                                 service.service_alias)
            file_list = body["list"]
            return 200, "success", file_list
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            return 200, "success", []

    def get_service_logs(self, session: SessionClass, tenant_env, service, action="service", lines=100):
        log_list = []
        try:
            if action == LogConstants.SERVICE:
                body = remote_component_client.get_service_logs(session,
                                                                service.service_region, tenant_env,
                                                                service.service_alias, lines)
                log_list = body["list"]
            return 200, "success", log_list
        except remote_component_client.CallApiError as e:
            logger.exception(e)
            return 200, "success", []


event_service = AppEventService()
ws_service = AppWebSocketService()
log_service = AppLogService()
