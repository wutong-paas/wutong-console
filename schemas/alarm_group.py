from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class CreateAlarmGroupParam(BaseModel):
    """
    创建告警分组参数
    """
    group_name: Annotated[str, Field(title="分组名称")] = None
    team_name: Annotated[str, Field(title="团队名称")] = None

