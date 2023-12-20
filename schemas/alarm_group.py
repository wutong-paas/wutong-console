from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class CreateAlarmGroupParam(BaseModel):
    """
    创建告警分组参数
    """
    group_name: Annotated[str, Field(title="分组名称")] = None
    team_name: Annotated[str, Field(title="团队名称")] = None


class PutAlarmGroupParam(BaseModel):
    """
    修改告警分组参数
    """
    group_id: Annotated[str, Field(title="分组id")] = None
    group_name: Annotated[str, Field(title="分组名称")] = None
