from loguru import logger

from repository.alarm.alarm_region_repo import alarm_region_repo
from repository.region.region_info_repo import region_repo
from service.alarm.alarm_service import alarm_service


class AlarmGroupService:

    def update_alarm_group(self, session, request, users_info, alarm_group):
        address = []
        err_message = None
        for user_info in users_info:
            email = user_info.get("email")
            if email:
                address.append(email)
        body = {
            "name": alarm_group.group_name,
            "code": alarm_group.group_code,
            "type": "email",
            "address": ';'.join(address),
        }

        status = False
        alarm_region_rels = alarm_region_repo.get_alarm_regions(session, alarm_group.ID, "email")
        if not alarm_region_rels:
            return True, None

        for alarm_region_rel in alarm_region_rels:
            region = region_repo.get_region_by_region_name(session, alarm_region_rel.region_code)
            try:
                if alarm_region_rel:
                    res = alarm_service.obs_service_alarm(request, "/v1/alert/contact", body,
                                                                 region,
                                                                 method="POST")
                    if res and res["code"] == 200:
                        status = True
                    if res and res["code"] != 200 and res["code"] != 404:
                        logger.warning(res["message"])
                        err_message = res["message"]
                    if res and res["code"] != 200:
                        logger.warning(res["message"])
            except Exception as err:
                logger.warning(err)
                continue
        return status, err_message


alarm_group_service = AlarmGroupService()
