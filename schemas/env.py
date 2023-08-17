from typing import Optional

from pydantic import BaseModel


class CloseEnvAppParam(BaseModel):
    region_name: Optional[str] = ""


class CreateEnvParam(BaseModel):
    """
    创建环境
    """
    env_alias: Optional[str] = ""
    team_alias: Optional[str] = ""
    region_name: Optional[str] = ""
    env_name: Optional[str] = ""
    tenant_id: Optional[str] = ""
    # 批量操作的用户ID 多个以英文逗号分隔
    user_names: Optional[str] = ""
    desc: Optional[str] = ""


class UpdateEnvParam(BaseModel):
    """
    修改环境
    """
    env_alias: Optional[str] = ""
    user_names: Optional[str] = ""
    desc: Optional[str] = ""


class DeleteEnvParam(BaseModel):
    """
    删除环境
    """
    env_alias: Optional[str] = ""
