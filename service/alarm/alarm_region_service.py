from loguru import logger
from repository.alarm.alarm_region_repo import alarm_region_repo
from repository.teams.team_region_repo import team_region_repo
from service.alarm.alarm_service import alarm_service


class AlarmRegionService:

    def add_or_update_alarm_region(self, session, request, users_info, group_id, alarm_group, contacts):
        address = []
        err_message = None
        status = False
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
        regions = team_region_repo.get_regions(session)
        for region in regions:
            region_code = region.region_name
            try:
                alarm_region_rel = alarm_region_repo.get_alarm_region(session, group_id, region_code, "email")
                body = alarm_service.obs_service_alarm(request, "/v1/alert/contact", body, region)
            except Exception as err:
                logger.warning(err)
                continue
            if body and body["code"] == 200:
                data = {
                    "group_id": group_id,
                    "alarm_type": "email",
                    "code": alarm_group.group_code,
                    "region_code": region_code
                }
                if not alarm_region_rel:
                    alarm_region_repo.create_alarm_region(session, data)
                contacts = list(set(contacts))
                contacts = ','.join(contacts)
                alarm_group.contacts = contacts
                status = True
            else:
                err_message = body["message"]
                logger.warning(err_message)

        return status, err_message


alarm_region_service = AlarmRegionService()
