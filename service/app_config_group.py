import time

from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Params, paginate

from clients.remote_app_client import remote_app_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.bcode import ErrAppConfigGroupNotFound
from models.application.models import ApplicationConfigGroup
from repository.application.config_group_repo import app_config_group_service_repo, app_config_group_item_repo
from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import app_config_group_repo
from repository.region.region_app_repo import region_app_repo


def create_items_and_services(session: SessionClass, app_config_group, config_items, service_ids):
    # create application config group items
    if config_items:
        for item in config_items:
            group_item = {
                "update_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                "app_id": app_config_group.app_id,
                "config_group_name": app_config_group.config_group_name,
                "item_key": item["item_key"],
                "item_value": item["item_value"],
                "config_group_id": app_config_group.config_group_id,
            }
            app_config_group_item_repo.create(session, **group_item)

    # create application config group services takes effect
    if service_ids is not None:
        for sid in service_ids:
            s = service_repo.get_service_by_service_id(session, sid)
            group_service = {
                "update_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                "app_id": app_config_group.app_id,
                "config_group_name": app_config_group.config_group_name,
                "service_id": s.service_id,
                "config_group_id": app_config_group.config_group_id,
            }
            app_config_group_service_repo.create(session, **group_service)


def convert_todict(session: SessionClass, cgroup_items, cgroup_services):
    # Convert application config group items to dict
    config_group_items = []
    if cgroup_items:
        for i in cgroup_items:
            cgi = i.__dict__
            config_group_items.append(cgi)
    # Convert application config group services to dict
    config_group_services = []
    if cgroup_services:
        for s in cgroup_services:
            service = service_repo.get_service_by_service_id(session, s.service_id)
            if not service:
                continue
            cgs = jsonable_encoder(s)
            if service:
                cgs["service_cname"] = service.service_cname
                cgs["service_alias"] = service.service_alias
            config_group_services.append(cgs)
    return config_group_items, config_group_services


def build_response(session: SessionClass, cgroup):
    cgroup_services = app_config_group_service_repo.list(session=session, config_group_id=cgroup.config_group_id)
    cgroup_items = app_config_group_item_repo.list(session=session, config_group_id=cgroup.config_group_id)
    config_group_items, config_group_services = convert_todict(session=session, cgroup_items=cgroup_items,
                                                               cgroup_services=cgroup_services)

    config_group_info = jsonable_encoder(cgroup)
    config_group_info["services"] = config_group_services
    config_group_info["config_items"] = config_group_items
    config_group_info["services_num"] = len(config_group_services)
    return config_group_info


class AppConfigGroupService(object):
    def get_config_group(self, session: SessionClass, region_name, app_id, config_group_name):
        cgroup = app_config_group_repo.get(session, region_name, app_id, config_group_name)
        if len(cgroup) == 0:
            raise ErrAppConfigGroupNotFound
        config_group_info = build_response(session=session, cgroup=cgroup[0])
        return config_group_info

    def list_config_groups(self, session: SessionClass, region_name, app_id, page, page_size, query=None):
        cgroup_info = []
        config_groups = app_config_group_repo.list(session, region_name, app_id)
        if query:
            config_groups = config_groups.filter(config_group_name__contains=query)
        params = Params(page=page, size=page_size)
        config_groups_paginator = paginate(config_groups, params)
        config_groups_item = config_groups_paginator.items
        total = config_groups_paginator.total
        for cgroup in config_groups_item:
            config_group_info = build_response(session=session, cgroup=cgroup)
            cgroup_info.append(config_group_info)
        return cgroup_info, total

    def create_config_group(self, session: SessionClass, app_id, config_group_name, config_items, deploy_type, enable,
                            service_ids,
                            region_name,
                            team_name):
        # create application config group
        group_req = {
            "app_id": app_id,
            "config_group_name": config_group_name,
            "deploy_type": deploy_type,
            "enable": enable,
            "region_name": region_name,
            "config_group_id": make_uuid(),
        }

        config_groups = app_config_group_repo.get(session, region_name, app_id, config_group_name)
        if len(config_groups) == 0:
            cgroup = app_config_group_repo.create(session, **group_req)
            create_items_and_services(session=session, app_config_group=cgroup, config_items=config_items,
                                      service_ids=service_ids)
            region_app_id = region_app_repo.get_region_app_id(session, region_name, app_id)
            remote_app_client.create_app_config_group(
                session, region_name, team_name, region_app_id, {
                    "app_id": region_app_id,
                    "config_group_name": config_group_name,
                    "deploy_type": deploy_type,
                    "service_ids": service_ids,
                    "config_items": config_items,
                    "enable": enable,
                })
        # else:
        #     raise ErrAppConfigGroupExists
        return self.get_config_group(session=session, region_name=region_name, app_id=app_id,
                                     config_group_name=config_group_name)

    def delete_config_group(self, session: SessionClass, region_name, team_name, app_id, config_group_name):
        cgroup = app_config_group_repo.get(session, region_name, app_id, config_group_name)
        region_app_id = region_app_repo.get_region_app_id(session, cgroup[0].region_name, app_id)
        try:
            remote_app_client.delete_app_config_group(session,
                                                      cgroup[0].region_name, team_name, region_app_id,
                                                      cgroup[0].config_group_name)
        except remote_app_client.CallApiError as e:
            if e.status != 404:
                raise e

        app_config_group_item_repo.delete_by_config_group_id(session=session, config_group_id=cgroup[0].config_group_id)
        app_config_group_service_repo.delete_by_config_group_id(session=session,
                                                                config_group_id=cgroup[0].config_group_id)
        app_config_group_repo.delete_by_region_name(session=session, region_name=cgroup[0].region_name, app_id=app_id,
                                                    config_group_name=config_group_name)

    def update_config_group(self, session: SessionClass, region_name, app_id, config_group_name, config_items, enable,
                            service_ids, team_name):
        group_req = {
            "app_id": app_id,
            "region_name": region_name,
            "config_group_name": config_group_name,
            "enable": enable,
            "update_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
        }
        try:
            cgroup = app_config_group_repo.get(session, region_name, app_id, config_group_name)
        except ApplicationConfigGroup.DoesNotExist:
            raise ErrAppConfigGroupNotFound
        else:
            app_config_group_repo.update(session, **group_req)
            app_config_group_item_repo.delete_by_config_group_id(session=session,
                                                                 config_group_id=cgroup[0].config_group_id)
            app_config_group_service_repo.delete_by_config_group_id(session=session,
                                                                    config_group_id=cgroup[0].config_group_id)
            create_items_and_services(session=session, app_config_group=cgroup[0], config_items=config_items,
                                      service_ids=service_ids)
            region_app_id = region_app_repo.get_region_app_id(session, cgroup[0].region_name, app_id)
            remote_app_client.update_app_config_group(session,
                                                      cgroup[0].region_name, team_name, region_app_id,
                                                      cgroup[0].config_group_name, {
                                                          "service_ids": service_ids,
                                                          "config_items": config_items,
                                                          "enable": enable,
                                                      })
        return self.get_config_group(session=session, region_name=region_name, app_id=app_id,
                                     config_group_name=config_group_name)


app_config_group_service = AppConfigGroupService()
