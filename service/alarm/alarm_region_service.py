from loguru import logger
from repository.alarm.alarm_region_repo import alarm_region_repo
from repository.teams.team_region_repo import team_region_repo
from service.alarm.alarm_service import alarm_service


class AlarmRegionService:

    async def add_or_update_alarm_region(self, session, request, users_info, group_id, alarm_group, contacts):
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
        regions = team_region_repo.get_regions(session)
        for region in regions:
            region_code = region.region_name
            try:
                alarm_region_rel = alarm_region_repo.get_alarm_region(session, group_id, region_code, "email")
                if alarm_region_rel:
                    obs_uid = alarm_region_rel.obs_uid
                    body.update({"uid": obs_uid})
                body = await alarm_service.obs_service_alarm(request, "/v1/alert/contact", body, region)
            except Exception as err:
                logger.warning(err)
                continue
            if body and body["code"] == 200:
                uid = body["data"]["uid"]
                data = {
                    "group_id": group_id,
                    "alarm_type": "email",
                    "obs_uid": uid,
                    "region_code": region_code
                }
                if not alarm_region_rel:
                    alarm_region_repo.create_alarm_region(session, data)
                contacts = list(set(contacts))
                contacts = ','.join(contacts)
                alarm_group.contacts = contacts


alarm_region_service = AlarmRegionService()
