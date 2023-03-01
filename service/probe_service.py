import copy

from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlalchemy import select

from clients.remote_component_client import remote_component_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.main import AbortRequest, ServiceHandleException
from models.component.models import ComponentProbe
from repository.component.service_probe_repo import probe_repo


class ProbeService(object):
    PROBE_MODE = ("readiness", "liveness", "ignore")

    def add_service_probe(self, session: SessionClass, tenant_env, service, data):
        probe = self.create_probe(session, tenant_env, service, data)
        new_probe = probe.__dict__
        # deep copy
        logger.debug("create status: {}".format(service.create_status))
        if service.create_status == "complete":
            new_probe = copy.deepcopy(new_probe)
            new_probe["enterprise_id"] = tenant_env.enterprise_id
            res, body = remote_component_client.add_service_probe(session,
                                                                  service.service_region, tenant_env,
                                                                  service.service_alias, jsonable_encoder(new_probe))
            logger.debug("add probe action status {0}".format(res.status))
        session.add(probe)
        session.flush()
        return 200, "success", probe

    def create_probe(self, session: SessionClass, tenant, service, data):
        code, msg = self.__check_probe_data(data)
        if code != 200:
            raise AbortRequest("invalid probe", msg_show=msg)

        probe = (
            session.execute(select(ComponentProbe).where(ComponentProbe.mode == data["mode"],
                                                         ComponentProbe.service_id == service.service_id))
        ).scalars().first()

        if probe:
            raise AbortRequest("probe exists", msg_show="已设置过该类型探针", status_code=409, error_code=409)
        is_used = 1 if data.get("is_used", 1) else 0
        probe = {
            "service_id": service.service_id,
            "scheme": data.get("scheme", "tcp"),
            "path": data.get("path", ""),
            "port": int(data.get("port")),
            "cmd": data.get("cmd", ""),
            "http_header": data.get("http_header", ""),
            "initial_delay_second": data.get("initial_delay_second", 4),
            "period_second": data.get("period_second", 3),
            "timeout_second": data.get("timeout_second", 5),
            "failure_threshold": data.get("failure_threshold", 3),
            "success_threshold": data.get("success_threshold", 1),
            "is_used": is_used,
            "probe_id": make_uuid(),
            "mode": data["mode"],
        }
        return ComponentProbe(**probe)

    def __check_probe_data(self, data):
        mode = data.get("mode", None)
        if mode:
            if mode not in self.PROBE_MODE:
                return 400, "参数错误,不健康处理方式只能为readiness或liveness或ignore"
        port = data.get("port", None)
        if port is not None:
            if port < 1:
                return 400, "端口号只能为1到65535的整数"
        else:
            return 400, "端口不能为空"

        initial_delay_second = data.get("initial_delay_second", 1)
        if initial_delay_second is not None:
            if initial_delay_second < 1:
                return 400, "初始等候时间不能小于1秒"

        period_second = data.get("period_second", 1)
        if period_second is not None:
            if period_second < 1:
                return 400, "检测间隔不能小于1秒"

        timeout_second = data.get("timeout_second", 1)
        if timeout_second < 1:
            return 400, "超时时间不能小于1秒"

        failure_threshold = data.get("failure_threshold", 3)
        if failure_threshold is not None:
            if failure_threshold < 1:
                return 400, "标志为失败的检测次数不能少于1"

        success_threshold = data.get("success_threshold", 3)
        if success_threshold is not None:
            if success_threshold < 1:
                return 400, "标志为成功的检测次数不能少于1"

        return 200, "success"

    def delete_service_probe(self, session: SessionClass, tenant_env, service, probe_id):
        probe = probe_repo.get_probe_by_probe_id(service.service_id, probe_id)
        if not probe:
            return 404, "未找到探针"
        body = {"probe_id": probe_id}
        remote_component_client.delete_service_probe(session,
                                                     service.service_region, tenant_env,
                                                     service.service_alias, body)
        probe_repo.delete(session, service.service_id, probe_id)
        return 200, "success"

    def update_service_probea(self, session: SessionClass, tenant_env, service, data, user_name=''):
        code, msg = self.__check_probe_data(data)
        if code != 200:
            raise ServiceHandleException(status_code=code, msg_show=msg, msg="error")
        probes = probe_repo.get_service_probes(session, service.service_id)
        if not probes:
            if service.service_source == "third_party":
                code, msg, new_probe = self.add_service_probe(session, tenant_env, service, data)
                return new_probe
            raise ServiceHandleException(status_code=404, msg="no found", msg_show="组件未设置探针，无法进行修改操作")
        probe = probes[0]
        # delete more probe without first, one service will have one probe
        if len(probes) > 1:
            for index in range(len(probes)):
                if index > 0:
                    self.delete_service_probe(session=session, tenant_env=tenant_env, service=service,
                                              probe_id=probes[index].probe_id)
        if not probe:
            raise ServiceHandleException(status_code=404, msg="no found", msg_show="组件未设置探针，无法进行修改操作")
        is_used = data.get("is_used", None)
        if is_used is None:
            is_used = probe.is_used
        else:
            is_used = 1 if is_used else 0
        prob_data = {
            "service_id": service.service_id,
            "scheme": data.get("scheme", probe.scheme),
            "path": data.get("path", probe.path),
            "port": data.get("port", probe.port),
            "cmd": data.get("cmd", probe.cmd),
            "http_header": data.get("http_header", probe.http_header),
            "initial_delay_second": data.get("initial_delay_second", probe.initial_delay_second),
            "period_second": data.get("period_second", probe.period_second),
            "timeout_second": data.get("timeout_second", probe.timeout_second),
            "failure_threshold": data.get("failure_threshold", probe.failure_threshold),
            "success_threshold": data.get("success_threshold", probe.success_threshold),
            "is_used": is_used,
            "probe_id": probe.probe_id,
            "mode": data["mode"]
        }
        console_probe = copy.deepcopy(prob_data)
        prob_data["enterprise_id"] = tenant_env.enterprise_id
        prob_data["operator"] = user_name
        if service.create_status == "complete":
            try:
                res, body = remote_component_client.update_service_probec(session,
                                                                          service.service_region,
                                                                          tenant_env,
                                                                          service.service_alias,
                                                                          prob_data)
                logger.debug("update probe action status {0}".format(res.status))
            except remote_component_client.CallApiError as e:
                logger.debug(e)
                if e.message.get("httpcode") == 404:
                    probe.delete()
        probe_repo.update_service_probeb(session, **console_probe)
        new_probe = probe_repo.get_probe_by_probe_id(session, service.service_id, probe.probe_id)
        return new_probe

    def get_service_probe_by_mode(self, session: SessionClass, service, mode):
        if not mode:
            m_list = []
            for m in self.PROBE_MODE:
                probe = probe_repo.get_probe_by_mode(session, service.service_id, m)
                if not probe:
                    m_list.append({m: False})
                else:
                    m_list.append({m: bool(probe.is_used)})

            return 200, "success", m_list
        if mode not in self.PROBE_MODE:
            return 400, "参数错误,不健康处理方式只能为readiness或liveness或ignore", None
        probe = probe_repo.get_probe_by_mode(session, service.service_id, mode)
        if not probe:
            return 404, "探针不存在，您可能并未设置检测探针", None
        return 200, "success", probe

    def get_service_probe(self, session: SessionClass, service):
        probe = probe_repo.get_probe(session, service.service_id)
        if not probe:
            return 404, "探针不存在，您可能并未设置检测探针", None
        return 200, "success", probe


probe_service = ProbeService()
