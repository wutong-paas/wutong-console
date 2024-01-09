from loguru import logger
from repository.teams.team_region_repo import team_region_repo
from service.alarm.alarm_service import alarm_service


class AlarmRobotService:

    async def test_robot(self, session, request, webhook_addr):

        status = False
        err_message = None
        try:
            body = {
                "type": "wechat",
                "address": webhook_addr
            }
            regions = team_region_repo.get_regions(session)
            for region in regions:
                try:
                    body = alarm_service.obs_service_alarm(request, "/v1/alert/contact/test", body, region,
                                                                 method="POST")
                except Exception as err:
                    logger.error(err)
                    continue
                if body and body["code"] == 200:
                    status = True
                if body and body["code"] != 200 and body["code"] != 404:
                    err_message = body["message"]
        except Exception as err:
            logger.error(err)
            return False, None
        return status, err_message


alarm_robot_service = AlarmRobotService()
