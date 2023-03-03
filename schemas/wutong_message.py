from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UpdateResourceEventBody(BaseModel):
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    application_id: Optional[int] = None
    application_name: Optional[str] = None
    component_id: Optional[str] = None
    component_name: Optional[str] = None
    type: Optional[str] = None
    value: Optional[str] = None
    namespace: Optional[str] = None
    operator: Optional[str] = None
    operate_time: Optional[datetime] = None
    min_node: Optional[int] = 0


class UpdateResourceEvent(BaseModel):
    message_id: Optional[str] = None
    timestamp: Optional[int] = None
    body: Optional[dict] = None
