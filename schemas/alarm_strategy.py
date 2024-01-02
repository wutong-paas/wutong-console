from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class AlarmStrategyParam(BaseModel):
    """
    告警策略参数
    """
    strategy_name: Annotated[str, Field(title="策略名")] = None
    strategy_code: Annotated[str, Field(title="策略标识")] = None
    desc: Annotated[str, Field(title="策略描述")] = None
    team_code: Annotated[str, Field(title="团队标识")] = None
    env_code: Annotated[str, Field(title="环境标识")] = None
    alarm_object: Annotated[list, Field(title="告警对象")] = None
    alarm_rules: Annotated[list, Field(title="告警规则")] = None
    alarm_notice: Annotated[dict, Field(title="告警通知")] = None


class StrategyEnableParam(BaseModel):
    """
    告警策略开关参数
    """
    strategy_code: Annotated[str, Field(title="策略标识")] = None
    enable: Annotated[bool, Field(title="是否启用")] = None
