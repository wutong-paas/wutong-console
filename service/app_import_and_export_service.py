import base64
import json
import os

from loguru import logger

from clients.remote_migrate_client import remote_migrate_client_api
from core.setting import settings
from core.utils.crypt import make_uuid
from exceptions.main import RegionNotFound, RecordNotFound
from models.market.models import CenterApp, CenterAppVersion
from repository.application.app_repository import app_repo
from repository.market.center_repo import center_app_repo, app_import_record_repo
from repository.region.region_info_repo import region_repo
from service.region_service import region_services


class AppImportService(object):
    def get_import_app_dir(self, session, event_id):
        """获取应用目录下的包"""
        import_record = app_import_record_repo.get_import_record_by_event_id(session, event_id)
        if not import_record:
            raise RecordNotFound("import_record not found")
        res, body = remote_migrate_client_api.get_enterprise_import_file_dir(session,
                                                                             import_record.region,
                                                                             import_record.enterprise_id, event_id)
        app_tars = body["bean"]["apps"]
        return app_tars

    def create_app_version(self, session, app, import_record, app_template):
        version = CenterAppVersion(
            scope=import_record.scope,
            enterprise_id=import_record.enterprise_id,
            app_id=app.app_id,
            app_template=json.dumps(app_template),
            version=app_template["group_version"],
            template_version=app_template["template_version"],
            record_id=import_record.ID,
            share_user=0,
            is_complete=1,
            app_version_info=app_template.get("annotations", {}).get("version_info", ""),
            version_alias=app_template.get("annotations", {}).get("version_alias", ""),
        )
        # todo
        # if app_store.is_no_multiple_region_hub(session, import_record.enterprise_id):
        #     version.region_name = import_record.region
        return version

    def decode_image(self, image_base64_string, suffix):
        if not image_base64_string:
            return ""
        try:
            filename = 'uploads/{0}.{1}'.format(make_uuid(), suffix)
            savefilename = os.path.join(settings.MEDIA_ROOT, filename)
            queryfilename = os.path.join(settings.MEDIA_URL, filename)
            with open(savefilename, "wb") as f:
                f.write(base64.decodebytes(image_base64_string.encode('utf-8')))
            return queryfilename
        except Exception as e:
            logger.exception(e)
        return ""

    def __save_enterprise_import_info(self, session, import_record, metadata):
        wutong_apps = []
        wutong_app_versions = []
        metadata = json.loads(metadata)
        key_and_version_list = []
        if not metadata:
            return
        for app_template in metadata:
            annotations = app_template.get("annotations", {})
            app_describe = app_template.pop("describe", "")
            if annotations.get("describe", ""):
                app_describe = annotations.pop("describe", "")
            app = center_app_repo.get_wutong_app_by_app_id(session, import_record.enterprise_id,
                                                           app_template["group_key"])
            # if app exists, update it
            if app:
                app.scope = import_record.scope
                app.describe = app_describe
                app.save()
                app_version = app_repo.get_wutong_app_version_by_app_id_and_version(
                    session, app.app_id, app_template["group_version"])
                if app_version:
                    version_info = annotations.get("version_info")
                    version_alias = annotations.get("version_alias")
                    if not version_info:
                        version_info = app_version.app_version_info
                    if not version_alias:
                        version_alias = app_version.version_alias
                    # update version if exists
                    app_version.scope = import_record.scope
                    app_version.app_template = json.dumps(app_template)
                    app_version.template_version = app_template["template_version"]
                    app_version.app_version_info = version_info,
                    app_version.version_alias = version_alias,
                else:
                    # create a new version
                    wutong_app_versions.append(self.create_app_version(app, import_record, app_template))
            else:
                image_base64_string = app_template.pop("image_base64_string", "")
                if annotations.get("image_base64_string"):
                    image_base64_string = annotations.pop("image_base64_string", "")
                pic_url = ""
                if image_base64_string:
                    suffix = app_template.pop("suffix", "jpg")
                    if annotations.get("suffix"):
                        suffix = annotations.pop("suffix", "jpg")
                    pic_url = self.decode_image(image_base64_string, suffix)
                key_and_version = "{0}:{1}".format(app_template["group_key"], app_template['group_version'])
                if key_and_version in key_and_version_list:
                    continue
                key_and_version_list.append(key_and_version)
                rainbond_app = CenterApp(
                    enterprise_id=import_record.enterprise_id,
                    app_id=app_template["group_key"],
                    app_name=app_template["group_name"],
                    source="import",
                    create_team=import_record.team_name,
                    scope=import_record.scope,
                    describe=app_describe,
                    pic=pic_url,
                )
                wutong_apps.append(rainbond_app)
                # create a new app version
                wutong_app_versions.append(self.create_app_version(rainbond_app, import_record, app_template))
        session.add_all(wutong_app_versions)
        session.add_all(wutong_apps)

    def __wrapp_app_import_status(self, app_status):
        """
        wrapper struct "app1:success,app2:failed" to
        [{"file_name":"app1","status":"success"},{"file_name":"app2","status":"failed"} ]
        """
        status_list = []
        if not app_status:
            return status_list
        k_v_map_list = app_status.split(",")
        for value in k_v_map_list:
            kv_map_list = value.split(":")
            status_list.append({"file_name": kv_map_list[0], "status": kv_map_list[1]})
        return status_list

    def get_and_update_import_by_event_id(self, session, event_id):
        import_record = app_import_record_repo.get_import_record_by_event_id(session, event_id)
        if not import_record:
            raise RecordNotFound("import_record not found")
        # get import status from region
        res, body = remote_migrate_client_api.get_enterprise_app_import_status(session, import_record.region,
                                                                               import_record.enterprise_id, event_id)
        status = body["bean"]["status"]
        if import_record.status != "success":
            if status == "success":
                logger.debug("app import success !")
                self.__save_enterprise_import_info(import_record, body["bean"]["metadata"])
                import_record.source_dir = body["bean"]["source_dir"]
                import_record.format = body["bean"]["format"]
                import_record.status = "success"
                # 成功以后删除数据中心目录数据
                try:
                    remote_migrate_client_api.delete_enterprise_import_file_dir(session,
                                                                                import_record.region,
                                                                                import_record.enterprise_id, event_id)
                except Exception as e:
                    logger.exception(e)
            else:
                import_record.status = status
        apps_status = self.__wrapp_app_import_status(body["bean"]["apps"])

        failed_num = 0
        success_num = 0
        for i in apps_status:
            if i.get("status") == "success":
                success_num += 1
                import_record.status = "partial_success"
            elif i.get("status") == "failed":
                failed_num += 1
        if success_num == len(apps_status):
            import_record.status = "success"
        elif failed_num == len(apps_status):
            import_record.status = "failed"
        if status == "uploading":
            import_record.status = status

        return import_record, apps_status

    def select_handle_region(self, session, eid):
        data = region_services.get_enterprise_regions(session, eid, level="safe", status=1, check_status=True)
        if data:
            for region in data:
                if region["rbd_version"] != "":
                    return region_services.get_region_by_region_id(session, data[0]["region_id"])
        raise RegionNotFound("暂无可用的集群、应用导入功能不可用")

    def get_user_not_finish_import_record_in_enterprise(self, session, eid, user):
        return app_import_record_repo.get_user_not_finished_import_record_in_enterprise(session, eid, user.nick_name)

    def create_app_import_record_2_enterprise(self, session, eid, user_name):
        event_id = make_uuid()
        region = self.select_handle_region(session, eid)
        import_record_params = {
            "event_id": event_id,
            "status": "uploading",
            "enterprise_id": eid,
            "region": region.region_name,
            "user_name": user_name
        }
        return app_import_record_repo.create_app_import_record(session, **import_record_params)

    def get_upload_url(self, session, region, event_id):
        region = region_repo.get_region_by_region_name(session, region)
        raw_url = "/app/upload"
        upload_url = ""
        if region:
            splits_texts = region.wsurl.split("://")
            if splits_texts[0] == "wss":
                upload_url = "https://" + splits_texts[1] + raw_url
            else:
                upload_url = "http://" + splits_texts[1] + raw_url
        return upload_url + "/" + event_id


import_service = AppImportService()
