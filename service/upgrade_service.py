from datetime import datetime

from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Params, paginate
from loguru import logger

from clients.remote_build_client import remote_build_client
from database.session import SessionClass
from exceptions.bcode import ErrLastRecordUnfinished
from models.application.models import ApplicationUpgradeStatus, ServiceUpgradeRecord, ApplicationUpgradeRecord, ApplicationUpgradeRecordType, \
    Application
from models.teams import TeamInfo
from repository.application.app_upgrade_repo import upgrade_repo
from repository.component.component_repo import tenant_service_group_repo
from repository.component.component_upgrade_record_repo import component_upgrade_record_repo
from service.component_group import ComponentGroup


class UpgradeService(object):
    def __init__(self):
        self.status_tables = {
            ApplicationUpgradeStatus.UPGRADING.value: {
                "success": ApplicationUpgradeStatus.UPGRADED.value,
                "failure": ApplicationUpgradeStatus.UPGRADE_FAILED.value,
                "timeout": ApplicationUpgradeStatus.UPGRADED.value,
            },
            ApplicationUpgradeStatus.ROLLING.value: {
                "success": ApplicationUpgradeStatus.ROLLBACK.value,
                "failure": ApplicationUpgradeStatus.ROLLBACK_FAILED.value,
                "timeout": ApplicationUpgradeStatus.ROLLBACK.value,
            },
        }

    def create_upgrade_record(self, session, enterprise_id, tenant: TeamInfo, app: Application, upgrade_group_id):
        component_group = tenant_service_group_repo.get_component_group(session, upgrade_group_id)

        # If there are unfinished record, it is not allowed to create new record
        last_record = upgrade_repo.get_last_upgrade_record(session, tenant.tenant_id, app.ID, upgrade_group_id)
        if last_record and not last_record.is_finished():
            raise ErrLastRecordUnfinished

        component_group = ComponentGroup(enterprise_id, component_group)
        app_template_source = component_group.app_template_source(session)

        # create new record
        record = {
            "tenant_id": tenant.tenant_id,
            "group_id": app.app_id,
            "group_key": component_group.app_model_key,
            "group_name": app.app_name,
            "create_time": datetime.now(),
            "is_from_cloud": component_group.is_install_from_cloud(session),
            "market_name": app_template_source.get_market_name(),
            "upgrade_group_id": upgrade_group_id,
            "old_version": component_group.version,
            "record_type": ApplicationUpgradeRecordType.UPGRADE.value,
        }
        record = ApplicationUpgradeRecord(**record)
        session.add(record)
        session.flush()
        return jsonable_encoder(record)

    def get_app_not_upgrade_record(self, session: SessionClass, tenant_id, group_id, group_key):
        """获取未完成升级记录"""
        result = upgrade_repo.get_app_not_upgrade_record(session=session,
                                                         tenant_id=tenant_id,
                                                         group_id=int(group_id),
                                                         group_key=group_key)
        if not result:
            return ApplicationUpgradeRecord()
        return result

    def sync_unfinished_records(self, session: SessionClass, tenant_name, region_name, records):
        for record in records:
            if record.is_finished:
                continue
            # synchronize the last unfinished record
            self.sync_record(session=session, tenant_name=tenant_name, region_name=region_name, record=record)
            break

    def _update_component_record_status(self, session: SessionClass, record: ServiceUpgradeRecord, event_status):
        if event_status == "":
            return
        status_table = self.status_tables.get(record.status, {})
        if not status_table:
            logger.warning("unexpected component upgrade record status: {}".format(record.status))
            return
        status = status_table.get(event_status)
        if not status:
            logger.warning("unexpected event status: {}".format(event_status))
            return
        record.status = status

    def save_upgrade_record(self, session: SessionClass, app_upgrade_record, component_upgrade_records):
        component_upgrade_record_repo.save(app_upgrade_record)
        component_upgrade_record_repo.bulk_update(component_upgrade_records)

    def sync_record(self, session: SessionClass, tenant_name, region_name, record: ApplicationUpgradeRecord):
        # list component records
        component_records = component_upgrade_record_repo.list_by_app_record_id(record.ID)
        # filter out the finished records
        unfinished = {record.event_id: record for record in component_records if not record.is_finished()}
        # list events
        event_ids = [event_id for event_id in unfinished.keys()]
        body = remote_build_client.get_tenant_events(session, region_name, tenant_name, event_ids)
        events = body.get("list", [])

        for event in events:
            component_record = unfinished.get(event["EventID"])
            if not component_record:
                continue
            self._update_component_record_status(session=session, record=component_record, event_status=event["Status"])

        self._update_app_record_status(session=session, app_record=record, component_records=component_records)

        # save app record and component records
        self.save_upgrade_record(session=session, app_upgrade_record=record,
                                 component_upgrade_records=component_records)

    def _is_upgrade_status_unfinished(self, session: SessionClass, component_records):
        for component_record in component_records:
            if component_record.status in [ApplicationUpgradeStatus.NOT.value, ApplicationUpgradeStatus.UPGRADING.value,
                                           ApplicationUpgradeStatus.ROLLING.value]:
                return True
            return False

    def _is_upgrade_status_failed(self, session: SessionClass, component_records):
        for component_record in component_records:
            if component_record.status not in [ApplicationUpgradeStatus.ROLLBACK_FAILED.value, ApplicationUpgradeStatus.UPGRADE_FAILED.value]:
                return False
            return True

    def _is_upgrade_status_success(self, session: SessionClass, component_records):
        for component_record in component_records:
            if component_record.status in [ApplicationUpgradeStatus.UPGRADING.value, ApplicationUpgradeStatus.ROLLING.value]:
                return False
            return True

    def _update_app_record_status(self, session: SessionClass, app_record, component_records):
        if self._is_upgrade_status_unfinished(session=session, component_records=component_records):
            return
        if self._is_upgrade_status_failed(session=session, component_records=component_records):
            if app_record.record_type == ApplicationUpgradeRecordType.ROLLBACK.value:
                app_record.status = ApplicationUpgradeStatus.ROLLBACK_FAILED.value
            else:
                app_record.status = ApplicationUpgradeStatus.UPGRADE_FAILED.value
            return
        if self._is_upgrade_status_success(session=session, component_records=component_records):
            if app_record.record_type == ApplicationUpgradeRecordType.ROLLBACK.value:
                app_record.status = ApplicationUpgradeStatus.ROLLBACK.value
            else:
                app_record.status = ApplicationUpgradeStatus.UPGRADED.value
            return
        # partial
        if app_record.record_type == ApplicationUpgradeRecordType.UPGRADE.value:
            app_record.status = ApplicationUpgradeStatus.PARTIAL_UPGRADED.value
        if app_record.record_type == ApplicationUpgradeRecordType.ROLLBACK.value:
            app_record.status = ApplicationUpgradeStatus.PARTIAL_ROLLBACK.value

    def list_records(self, session: SessionClass, tenant_name, region_name, app_id, record_type=None, page=1,
                     page_size=10):
        # list records and pagination
        records = upgrade_repo.list_records_by_app_id(session, app_id, record_type)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(records, params)
        records = event_paginator.items
        self.sync_unfinished_records(session=session, tenant_name=tenant_name, region_name=region_name, records=records)
        return [record.to_dict() for record in records], event_paginator.total

    def get_latest_upgrade_record(self, session: SessionClass, tenant: TeamInfo, app: Application,
                                  upgrade_group_id=None, record_type=None):
        if upgrade_group_id:
            # check upgrade_group_id
            tenant_service_group_repo.get_component_group(session=session, service_group_id=upgrade_group_id)
        record = upgrade_repo.get_last_upgrade_record(session, tenant.tenant_id, app.app_id, upgrade_group_id,
                                                      record_type)
        return jsonable_encoder(record) if record else None


upgrade_service = UpgradeService()
