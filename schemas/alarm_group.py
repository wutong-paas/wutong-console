from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class CreateAlarmGroupParam(BaseModel):
    """
    创建告警分组参数
    """
    group_name: Annotated[str, Field(title="分组名称")] = None
    group_type: Annotated[str, Field(title="分组类型")] = None
    team_name: Annotated[str, Field(title="团队名称")] = None


class PutAlarmGroupParam(BaseModel):
    """
    修改告警分组参数
    """
    group_id: Annotated[int, Field(title="分组id")] = None
    group_name: Annotated[str, Field(title="分组名称")] = None


class AddAlarmUserParam(BaseModel):
    """
    添加联系人参数
    """
    group_id: Annotated[int, Field(title="分组id")] = None
    users: Annotated[list, Field(title="联系人列表")] = None


class DeleteAlarmUserParam(BaseModel):
    """
    删除联系人参数
    """
    group_id: Annotated[int, Field(title="分组id")] = None
    user_names: Annotated[list, Field(title="联系人账号列表")] = None


class AddAlarmRobotParam(BaseModel):
    """
    添加机器人参数
    """
    robot_name: Annotated[str, Field(title="机器人名称")] = None
    webhook_address: Annotated[str, Field(title="webhook地址")] = None
