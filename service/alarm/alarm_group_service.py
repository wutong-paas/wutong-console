from loguru import logger

from repository.alarm.alarm_region_repo import alarm_region_repo
from repository.region.region_info_repo import region_repo
from service.alarm.alarm_service import alarm_service


class AlarmGroupService:

    async def update_alarm_group(self, session, request, users_info, alarm_group):
        address = []
        for user_info in users_info:
            email = user_info.get("email")
            if email:
                address.append(email)
        body = {
            "name": alarm_group.group_name,
            "type": "email",
            "address": ';'.join(address),
        }

        status = 0
        alarm_region_rels = alarm_region_repo.get_alarm_regions(session, alarm_group.ID, "email")
        for alarm_region_rel in alarm_region_rels:
            region = region_repo.get_region_by_region_name(session, alarm_region_rel.region_code)
            try:
                if alarm_region_rel:
                    obs_uid = alarm_region_rel.obs_uid
                    body.update({"uid": obs_uid})
                    body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact", body,
                                                                 region,
                                                                 method="POST")
                    if body and body["code"] == 200:
                        status = 1
                    elif body:
                        logger.warning(body["message"])
            except Exception as err:
                logger.warning(err)
                continue
        return status


alarm_group_service = AlarmGroupService()
