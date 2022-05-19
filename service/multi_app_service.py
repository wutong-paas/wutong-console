from loguru import logger

from exceptions.main import AbortRequest
from repository.component.component_repo import service_source_repo
from repository.component.group_service_repo import service_repo
from repository.component.service_group_relation_repo import service_group_relation_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.component_service import component_check_service


class MultiAppService(object):

    def save_multi_services(self, session, region_name, tenant, group_id, service, user, service_infos):
        service_source = service_source_repo.get_service_source(session, tenant.tenant_id, service.service_id)
        service_ids = []
        for service_info in service_infos:
            code, msg_show, new_service = application_service \
                .create_source_code_app(session, region_name, tenant, user,
                                        service.code_from,
                                        service_info["cname"],
                                        service.clone_url,
                                        service.git_project_id,
                                        service.code_version,
                                        service.server_type,
                                        oauth_service_id=service.oauth_service_id,
                                        git_full_name=service.git_full_name)
            if code != 200:
                raise AbortRequest("Multiple services; Service alias: {}; error creating service".format(service.service_alias),
                                   "创建多组件应用失败")
            # add username and password
            if service_source:
                git_password = service_source.password
                git_user_name = service_source.user_name
                if git_password or git_user_name:
                    application_service.create_service_source_info(session, tenant, new_service, git_user_name, git_password)
            #  add group
            code, msg_show = application_service.add_service_to_group(session, tenant, region_name, group_id, new_service.service_id)
            if code != 200:
                logger.debug("Group ID: {0}; Service ID: {1}; error adding service to group".format(
                    group_id, new_service.service_id))
                raise AbortRequest("app not found", "创建多组件应用失败", 404, 404)
            # save service info, such as envs, ports, etc
            component_check_service.save_service_info(session, tenant, new_service, service_info)
            new_service = application_service.create_region_service(session, tenant, new_service, user.nick_name)
            new_service.create_status = "complete"
            # new_service.save()
            service_ids.append(new_service.service_id)

        return service_ids

    def create_services(self, session, region_name, tenant, user, service_alias, service_infos):
        # get temporary service
        temporary_service = service_repo.get_service_by_tenant_and_alias(session, tenant.tenant_id, service_alias)
        if not temporary_service:
            raise AbortRequest("service not found", "组件不存在", status_code=404, error_code=11005)

        group_id = service_group_relation_repo.get_group_id_by_service(session, temporary_service)

        # save services
        service_ids = self.save_multi_services(
            session=session,
            region_name=region_name,
            tenant=tenant,
            group_id=group_id,
            service=temporary_service,
            user=user,
            service_infos=service_infos)

        code, msg = app_manage_service.delete(session, user, tenant, temporary_service, True)
        if code != 200:
            raise AbortRequest(
                "Service id: " + temporary_service.service_id + "; error deleting temporary service",
                msg,
                status_code=400,
                error_code=code)

        return group_id, service_ids

    def list_services(self, session, region_name, tenant, check_uuid):
        # get detection information from data center(region)
        # first result(code) is always 200
        code, msg, data = component_check_service.get_service_check_info(session, tenant, region_name, check_uuid)
        if code != 200:
            raise AbortRequest("error listing service check info", msg, status_code=400, error_code=11006)
        if not data["check_status"] or data["check_status"].lower() != "success":
            raise AbortRequest("not finished", "检测尚未完成", status_code=400, error_code=11001)
        if data["service_info"] and len(data["service_info"]) < 2:
            raise AbortRequest("not multiple services", "不是多组件项目", status_code=400, error_code=11002)

        return data["service_info"]


multi_app_service = MultiAppService()
