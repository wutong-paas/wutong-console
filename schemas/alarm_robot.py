from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class AlarmRobotParam(BaseModel):
    """
    机器人参数
    """
    robot_name: Annotated[str, Field(title="机器人名称")] = None
    webhook_addr: Annotated[str, Field(title="webhook地址")] = None
    team_code: Annotated[str, Field(title="团队标识")] = None


class UpdateAlarmRobotParam(BaseModel):
    """
    更新机器人参数
    """
    robot_id: Annotated[str, Field(title="机器人ID")] = None
    robot_name: Annotated[str, Field(title="机器人名称")] = None
    webhook_addr: Annotated[str, Field(title="webhook地址")] = None