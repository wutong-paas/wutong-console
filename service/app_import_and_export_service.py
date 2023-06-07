import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from loguru import logger

from appstore.app_store import app_store
from clients.remote_migrate_client import remote_migrate_client_api
from core.setting import settings
from core.utils.crypt import make_uuid
from exceptions.main import RegionNotFound, RecordNotFound, RbdAppNotFound, ExportAppError
from models.market.models import CenterApp, CenterAppVersion
from repository.application.app_repository import app_repo
from repository.market.center_repo import center_app_repo, app_import_record_repo, app_export_record_repo
from repository.region.region_info_repo import region_repo
from service.region_service import region_services


class AppImportService(object):

    def delete_import_app_dir_by_event_id(self, session, event_id):
        try:
            import_record = app_import_record_repo.get_import_record_by_event_id(session, event_id)
            remote_migrate_client_api.delete_enterprise_import(session, import_record.region,
                                                               event_id)
        except Exception as e:
            logger.exception(e)

        app_import_record_repo.delete_by_event_id(session, event_id)

    def start_import_apps(self, session, scope, event_id, file_names, team_name):
        import_record = app_import_record_repo.get_import_record_by_event_id(session, event_id)
        if not import_record:
            raise RecordNotFound("import_record not found")
        import_record.scope = scope
        if team_name:
            import_record.team_name = team_name

        service_image = app_store.get_app_hub_info(session=session)
        data = {"service_image": service_image, "event_id": event_id, "apps": file_names}
        if scope == "enterprise":
            remote_migrate_client_api.import_app_2_enterprise(session, import_record.region,
                                                              data)
        else:
            res, body = remote_migrate_client_api.import_app(session, import_record.region, data)
        import_record.status = "importing"
        # import_record.save()

    def get_import_app_dir(self, session, event_id):
        """获取应用目录下的包"""
        import_record = app_import_record_repo.get_import_record_by_event_id(session, event_id)
        if not import_record:
            raise RecordNotFound("import_record not found")
        res, body = remote_migrate_client_api.get_enterprise_import_file_dir(session,
                                                                             import_record.region,
                                                                             event_id)
        app_tars = body["bean"]["apps"]
        return app_tars

    def create_app_version(self, session, app, import_record, app_template):
        version = CenterAppVersion(
            scope=import_record.scope,
            app_id=app.app_id,
            app_template=json.dumps(app_template),
            version=app_template["group_version"],
            template_version=app_template["template_version"],
            record_id=import_record.ID,
            share_user=0,
            share_env="",
            is_complete=1,
            app_version_info=app_template.get("annotations", {}).get("version_info", ""),
            version_alias=app_template.get("annotations", {}).get("version_alias", ""),
        )
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
            app = center_app_repo.get_wutong_app_by_app_id(session,
                                                           app_template["group_key"])
            # if app exists, update it
            if app:
                app.scope = import_record.scope
                app.describe = app_describe
                app.create_team = import_record.team_name
                # app.save()
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
                    wutong_app_versions.append(self.create_app_version(session, app, import_record, app_template))
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
                wutong_app = CenterApp(
                    app_id=app_template["group_key"],
                    app_name=app_template["group_name"],
                    source="import",
                    create_team=import_record.team_name,
                    scope=import_record.scope,
                    describe=app_describe,
                    pic=pic_url,
                )
                wutong_apps.append(wutong_app)
                # create a new app version
                wutong_app_versions.append(self.create_app_version(session, wutong_app, import_record, app_template))
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
                                                                               event_id)
        status = body["bean"]["status"]
        if import_record.status != "success":
            if status == "success":
                logger.debug("app import success !")
                self.__save_enterprise_import_info(session, import_record, body["bean"]["metadata"])
                import_record.source_dir = body["bean"]["source_dir"]
                import_record.format = body["bean"]["format"]
                import_record.status = "success"
                # 成功以后删除数据中心目录数据
                try:
                    remote_migrate_client_api.delete_enterprise_import_file_dir(session,
                                                                                import_record.region,
                                                                                event_id)
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

    def select_handle_region(self, session):
        data = region_services.get_enterprise_regions(session, level="safe", status=1, check_status=True)
        if data:
            for region in data:
                if region["rbd_version"] != "":
                    return region_services.get_region_by_region_id(session, data[0]["region_id"])
        raise RegionNotFound("暂无可用的集群、应用导入功能不可用")

    def get_user_not_finish_import_record_in_enterprise(self, session, user):
        return app_import_record_repo.get_user_not_finished_import_record_in_enterprise(session, user.nick_name)

    def create_app_import_record_2_enterprise(self, session, user_name):
        event_id = make_uuid()
        region = self.select_handle_region(session)
        import_record_params = {
            "event_id": event_id,
            "status": "uploading",
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


class AppExportService(object):

    def encode_image(self, image_url):
        if not image_url:
            return None
        if image_url.startswith("http"):
            response = urllib.request.urlopen(image_url)
        else:
            image_url = "{}/media/uploads/{}".format(settings.DATA_DIR, image_url.split('/')[-1])
            response = open(image_url, mode='rb')
        image_base64_string = base64.encodebytes(response.read()).decode('utf-8')
        response.close()
        return image_base64_string

    def __get_app_metata(self, app, app_version):
        picture_path = app.pic
        suffix = picture_path.split('.')[-1]
        describe = app.describe
        try:
            image_base64_string = self.encode_image(picture_path)
        except IOError as e:
            logger.warning("path: {}; error encoding image: {}".format(picture_path, e))
            image_base64_string = ""

        app_template = json.loads(app_version.app_template)
        app_template["annotations"] = {
            "suffix": suffix,
            "describe": describe,
            "image_base64_string": image_base64_string,
            "version_info": app_version.app_version_info,
            "version_alias": app_version.version_alias,
        }
        return json.dumps(app_template, cls=MyEncoder)

    def select_handle_region(self, session):
        data = region_services.get_enterprise_regions(session, level="safe", status=1, check_status=True)
        if data:
            for region in data:
                if region["rbd_version"] != "":
                    return region_services.get_region_by_region_id(session, data[0]["region_id"])
        raise RegionNotFound("暂无可用的集群，应用导出功能不可用")

    def export_app(self, session, app_id, version, export_format, is_export_image):
        app, app_version = center_app_repo.get_wutong_app_and_version(session, app_id, version)
        if not app or not app_version:
            raise RbdAppNotFound("未找到该应用")

        # get region TODO: get region by app publish meta info
        region = self.select_handle_region(session)
        region_name = region.region_name
        export_record = app_export_record_repo.get_export_record(session, app_id, version, export_format)
        if export_record:
            if export_record.status == "success":
                raise ExportAppError(msg="exported", status_code=409)
            if export_record.status == "exporting":
                logger.debug("export record exists: event_id :{0}".format(export_record.event_id))
                return export_record
        # did not export, make a new export record
        # make export data
        event_id = make_uuid()
        data = {
            "event_id": event_id,
            "group_key": app.app_id,
            "version": app_version.version,
            "format": export_format,
            "group_metadata": self.__get_app_metata(app, app_version),
            "with_image_data": is_export_image
        }

        try:
            remote_migrate_client_api.export_app(session, region_name, data)
        except remote_migrate_client_api.CallApiError as e:
            logger.exception(e)
            raise ExportAppError()

        params = {
            "event_id": event_id,
            "group_key": app_id,
            "version": version,
            "format": export_format,
            "status": "exporting",
            "region_name": region.region_name,
            "is_export_image": is_export_image
        }

        return app_export_record_repo.create_app_export_record(session, **params)

    def _wrapper_director_download_url(self, session, region_name, raw_url):
        region = region_repo.get_region_by_region_name(session, region_name)
        if region:
            splits_texts = region.wsurl.split("://")
            if splits_texts[0] == "wss":
                return "https://" + splits_texts[1] + raw_url
            else:
                return "http://" + splits_texts[1] + raw_url

    def get_export_status(self, session, app, app_version):
        app_export_records = app_export_record_repo.get_enter_export_record_by_key_and_version(
            session, app.app_id, app_version.version)
        wutong_app_init_data = {
            "is_export_before": False,
        }
        docker_compose_init_data = {
            "is_export_before": False,
        }
        helm_chart_init_data = {
            "is_export_before": False,
        }
        yaml_init_data = {
            "is_export_before": False,
        }

        if app_export_records:
            for export_record in app_export_records:
                if not export_record.region_name:
                    continue
                region = region_repo.get_enterprise_region_by_region_name(session,
                                                                          export_record.region_name)
                if not region:
                    continue
                if export_record.event_id and export_record.status == "exporting":
                    try:
                        res, body = remote_migrate_client_api.get_app_export_status(session,
                                                                                    export_record.region_name,
                                                                                    export_record.event_id)
                        result_bean = body["bean"]
                        if result_bean["status"] in ("failed", "success"):
                            export_record.status = result_bean["status"]
                        export_record.file_path = result_bean["tar_file_href"]
                        # export_record.save()
                    except Exception as e:
                        logger.exception(e)

                if export_record.format == "wutong-app":
                    wutong_app_init_data.update({
                        "is_export_before":
                            True,
                        "status":
                            export_record.status,
                        "file_path":
                            self._wrapper_director_download_url(session,
                                                                export_record.region_name,
                                                                export_record.file_path.replace(
                                                                    "/v2", "")),
                        "is_export_image": True if export_record.is_export_image else False
                    })
                if export_record.format == "docker-compose":
                    docker_compose_init_data.update({
                        "is_export_before":
                            True,
                        "status":
                            export_record.status,
                        "file_path":
                            self._wrapper_director_download_url(session,
                                                                export_record.region_name,
                                                                export_record.file_path.replace(
                                                                    "/v2", "")),
                        "is_export_image": True if export_record.is_export_image else False
                    })
                if export_record.format == "helm_chart":
                    helm_chart_init_data.update({
                        "is_export_before":
                            True,
                        "status":
                            export_record.status,
                        "file_path":
                            self._wrapper_director_download_url(session, export_record.region_name,
                                                                export_record.file_path.replace(
                                                                    "/v2", "")),
                        "is_export_image": True if export_record.is_export_image else False
                    })
                if export_record.format == "yaml":
                    yaml_init_data.update({
                        "is_export_before":
                            True,
                        "status":
                            export_record.status,
                        "file_path":
                            self._wrapper_director_download_url(session,
                                                                export_record.region_name,
                                                                export_record.file_path.replace(
                                                                    "/v2", "")),
                        "is_export_image": True if export_record.is_export_image else False
                    })

        result = {"wutong_app": wutong_app_init_data, "docker_compose": docker_compose_init_data,
                  "helm_chart": helm_chart_init_data, "yaml": yaml_init_data}
        return result


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return str(obj, encoding='utf-8')
        return json.JSONEncoder.default(self, obj)


import_service = AppImportService()
export_service = AppExportService()
