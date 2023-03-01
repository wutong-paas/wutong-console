import json
from datetime import datetime
from json import JSONDecodeError
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Params, paginate
from loguru import logger

from appstore.app_store_client import app_store_client
from clients.remote_build_client import remote_build_client
from database.session import SessionClass
from exceptions.bcode import ErrLastRecordUnfinished, ErrAppUpgradeWrongStatus, ErrAppUpgradeRecordCanNotDeploy, \
    ErrAppUpgradeDeployFailed, ErrAppUpgradeRecordCanNotRollback
from exceptions.main import AbortRequest, ServiceHandleException
from models.application.models import ApplicationUpgradeStatus, ServiceUpgradeRecord, ApplicationUpgradeRecord, \
    ApplicationUpgradeRecordType, \
    Application
from models.market.models import CenterAppVersion, AppMarket, CenterApp
from models.teams import TeamEnvInfo
from repository.application.app_upgrade_repo import upgrade_repo
from repository.application.application_repo import app_market_repo
from repository.component.component_repo import tenant_service_group_repo, service_source_repo
from repository.component.component_upgrade_record_repo import component_upgrade_record_repo
from repository.market.center_repo import center_app_repo
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.component_group import ComponentGroup
from service.market_app.app_restore import AppRestore
from service.market_app.app_upgrade import AppUpgrade


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

    @staticmethod
    def list_rollback_record(session, upgrade_record: ApplicationUpgradeRecord):
        records = upgrade_repo.list_by_rollback_records(session, upgrade_record.ID)
        return [record.to_dict() for record in records]

    def restore(self, session, tenant, region, user, app, record: ApplicationUpgradeRecord):
        if not record.can_rollback():
            raise ErrAppUpgradeRecordCanNotRollback

        component_group = tenant_service_group_repo.get_component_group(session, record.upgrade_group_id)
        app_restore = AppRestore(session, tenant, region, user, app, component_group, record)
        record, component_group = app_restore.restore(session)
        return self.serialized_upgrade_record(record), component_group.group_alias

    @staticmethod
    def _update_component_records(session, app_record: ApplicationUpgradeRecord, component_records, events):
        if not events:
            return
        event_ids = {event["service_id"]: event["event_id"] for event in events}
        status = ApplicationUpgradeStatus.UPGRADING.value \
            if app_record.record_type == ApplicationUpgradeRecordType.UPGRADE.value else ApplicationUpgradeStatus.ROLLING.value
        for component_record in component_records:
            event_id = event_ids.get(component_record.service_id)
            if not event_id:
                continue
            component_record.status = status
            component_record.event_id = event_id
        component_upgrade_record_repo.bulk_update(session, component_records)

    def deploy(self, session, tenant_env, region_name, user, record: ApplicationUpgradeRecord):
        if not record.can_deploy():
            raise ErrAppUpgradeRecordCanNotDeploy

        # failed events
        component_records = component_upgrade_record_repo.list_by_app_record_id(session, record.ID)
        component_records = [record for record in component_records]
        failed_component_records = {
            record.event_id: record
            for record in component_records if record.status in
                                               [ApplicationUpgradeStatus.PARTIAL_UPGRADED.value,
                                                ApplicationUpgradeStatus.PARTIAL_ROLLBACK.value,
                                                ApplicationUpgradeStatus.DEPLOY_FAILED.value]
        }

        component_ids = [record.service_id for record in failed_component_records.values()]

        try:
            events = app_manage_service.batch_operations(session, tenant_env, region_name, user, "deploy", component_ids)
            status = ApplicationUpgradeStatus.UPGRADING.value \
                if record.record_type == ApplicationUpgradeRecordType.UPGRADE.value else ApplicationUpgradeStatus.ROLLING.value
            upgrade_repo.change_app_record_status(session, record, status)
        except ServiceHandleException as e:
            upgrade_repo.change_app_record_status(session, record, ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise ErrAppUpgradeDeployFailed(e.msg)
        except Exception as e:
            upgrade_repo.change_app_record_status(session, record, ApplicationUpgradeStatus.DEPLOY_FAILED.value)
            raise e
        self._update_component_records(session, record, failed_component_records.values(), events)

    def get_app_upgrade_record(self, session, tenant_name, region_name, record_id):
        record = upgrade_repo.get_by_record_id(session, record_id)
        if not record.is_finished():
            self.sync_record(session, tenant_name, region_name, record)
        return self.serialized_upgrade_record(record)

    @staticmethod
    def serialized_upgrade_record(app_record):
        """序列化升级记录
        :type : AppUpgradeRecord
        """
        return dict(
            service_record=[{
                "status": service_record.status,
                "update_time": service_record.update_time,
                "event_id": service_record.event_id,
                "update": json.loads(service_record.update) if service_record.update else None,
                "app_upgrade_record": service_record.app_upgrade_record_id,
                "service_cname": service_record.service_cname,
                "create_time": service_record.create_time,
                "service_id": service_record.service_id,
                "upgrade_type": service_record.upgrade_type,
                "ID": service_record.ID,
                "service_key": service_record.service.service_key
            } for service_record in app_record.service_upgrade_records],
            **app_record.to_dict())

    def upgrade(self, session, tenant, region, user, app, version, record: ApplicationUpgradeRecord,
                component_keys=None):
        """
        Upgrade application market applications
        """
        if not record.can_upgrade():
            raise ErrAppUpgradeWrongStatus
        component_group = tenant_service_group_repo.get_component_group(session, record.upgrade_group_id)

        app_template_source = self._app_template_source(session, record.group_id, record.group_key,
                                                        record.upgrade_group_id)
        app_template = self._app_template(session, user.enterprise_id, component_group.group_key, version,
                                          app_template_source)

        app_upgrade = AppUpgrade(
            session,
            tenant.enterprise_id,
            tenant,
            region,
            user,
            app,
            version,
            component_group,
            app_template,
            app_template_source.is_install_from_cloud(),
            app_template_source.get_market_name(),
            record,
            component_keys,
            is_deploy=True)
        record = app_upgrade.upgrade(session)
        app_template_name = component_group.group_alias
        return self.serialized_upgrade_record(record), app_template_name

    @staticmethod
    def _app_template_source(session, app_id, app_model_key, upgrade_group_id):
        components = application_service.get_wutong_services(session, app_id, app_model_key, upgrade_group_id)
        if not components:
            raise AbortRequest("components not found", "找不到组件", status_code=404, error_code=404)
        component = components[0]
        component_source = service_source_repo.get_service_source(session, component.tenant_id, component.service_id)
        return component_source

    def get_property_changes(self, session, tenant, region, user, app, upgrade_group_id, version):
        component_group = tenant_service_group_repo.get_component_group(session, upgrade_group_id)

        app_template_source = self._app_template_source(session, app.app_id, component_group.group_key,
                                                        upgrade_group_id)
        app_template = self._app_template(session, user.enterprise_id, component_group.group_key, version,
                                          app_template_source)

        app_upgrade = AppUpgrade(session, user.enterprise_id, tenant, region, user, app, version, component_group,
                                 app_template,
                                 app_template_source.is_install_from_cloud(), app_template_source.get_market_name())

        return app_upgrade.changes()

    def upgrade_cloud_app_model_to_db_model(self, market: AppMarket, app_id, version, for_install=False):
        app = app_store_client.get_app(market, app_id)
        app_version = None
        app_template = None
        try:
            if version:
                app_template = app_store_client.get_app_version(market, app_id, version, for_install=for_install,
                                                                get_template=True)
        except ServiceHandleException as e:
            if e.status_code != 404:
                logger.exception(e)
            app_template = None
        wutong_app = CenterApp(
            app_id=app.app_key_id,
            app_name=app.name,
            dev_status=app.dev_status,
            source="market",
            scope="wutong",
            describe=app.desc,
            details=app.introduction,
            pic=app.logo,
            create_time=app.create_time,
            update_time=app.update_time)
        wutong_app.market_name = market.name
        if app_template:
            app_version = CenterAppVersion(
                app_id=app.app_key_id,
                app_template=app_template.template,
                version=app_template.version,
                version_alias=app_template.version_alias,
                template_version=app_template.rainbond_version,
                app_version_info=app_template.description,
                update_time=app_template.update_time,
                is_official=1)
            app_version.template_type = app_template.template_type
        return wutong_app, app_version

    def _app_template(self, session, enterprise_id, app_model_key, version, app_template_source):
        if not app_template_source.is_install_from_cloud():
            _, app_version = center_app_repo.get_wutong_app_and_version(session, enterprise_id, app_model_key, version)
        else:
            market = app_market_repo.get_app_market_by_name(
                session, enterprise_id, app_template_source.get_market_name(), raise_exception=True)
            _, app_version = self.upgrade_cloud_app_model_to_db_model(market, app_model_key, version)

        if not app_version:
            raise AbortRequest("app template not found", "找不到应用模板", status_code=404, error_code=404)

        try:
            app_template = json.loads(app_version.app_template)
            app_template["update_time"] = app_version.update_time
            return app_template
        except JSONDecodeError:
            raise AbortRequest("invalid app template", "该版本应用模板已损坏, 无法升级")

    def upgrade_component(self, session, tenant, region, user, app, component, version):
        component_group = tenant_service_group_repo.get_component_group(session, component.upgrade_group_id)
        app_template_source = service_source_repo.get_service_source(session, component.tenant_id,
                                                                     component.component_id)
        app_template = self._app_template(session, user.enterprise_id, component_group.group_key, version,
                                          app_template_source)

        app_upgrade = AppUpgrade(
            session,
            tenant.enterprise_id,
            tenant,
            region,
            user,
            app,
            version,
            component_group,
            app_template,
            app_template_source.is_install_from_cloud(),
            app_template_source.get_market_name(),
            component_keys=[component.service_key],
            is_deploy=True,
            is_upgrade_one=True)
        app_upgrade.upgrade(session)

    def create_upgrade_record(self, session, enterprise_id, tenant: TeamEnvInfo, app: Application, upgrade_group_id):
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

    def sync_unfinished_records(self, session: SessionClass, tenant_env, region_name, records):
        for record in records:
            if record.is_finished:
                continue
            # synchronize the last unfinished record
            self.sync_record(session=session, tenant_env=tenant_env, region_name=region_name, record=record)
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
        component_upgrade_record_repo.save(session, app_upgrade_record)
        component_upgrade_record_repo.bulk_update(session, component_upgrade_records)

    def sync_record(self, session: SessionClass, tenant_env, region_name, record: ApplicationUpgradeRecord):
        # list component records
        component_records = component_upgrade_record_repo.list_by_app_record_id(session, record.ID)
        # filter out the finished records
        unfinished = {record.event_id: record for record in component_records if not record.is_finished()}
        # list events
        event_ids = [event_id for event_id in unfinished.keys()]
        body = remote_build_client.get_tenant_events(session, region_name, tenant_env, event_ids)
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
            if component_record.status not in [ApplicationUpgradeStatus.ROLLBACK_FAILED.value,
                                               ApplicationUpgradeStatus.UPGRADE_FAILED.value]:
                return False
            return True

    def _is_upgrade_status_success(self, session: SessionClass, component_records):
        for component_record in component_records:
            if component_record.status in [ApplicationUpgradeStatus.UPGRADING.value,
                                           ApplicationUpgradeStatus.ROLLING.value]:
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

    def list_records(self, session: SessionClass, tenant_env, region_name, app_id, record_type=None, page=1,
                     page_size=10):
        # list records and pagination
        records = upgrade_repo.list_records_by_app_id(session, app_id, record_type)
        params = Params(page=page, size=page_size)
        event_paginator = paginate(records, params)
        records = event_paginator.items
        self.sync_unfinished_records(session=session, tenant_env=tenant_env, region_name=region_name, records=records)
        return [record.to_dict() for record in records], event_paginator.total

    def get_latest_upgrade_record(self, session: SessionClass, tenant: TeamEnvInfo, app: Application,
                                  upgrade_group_id=None, record_type=None):
        if upgrade_group_id:
            # check upgrade_group_id
            tenant_service_group_repo.get_component_group(session=session, service_group_id=upgrade_group_id)
        record = upgrade_repo.get_last_upgrade_record(session, tenant.tenant_id, app.app_id, upgrade_group_id,
                                                      record_type)
        return jsonable_encoder(record) if record else None


upgrade_service = UpgradeService()
