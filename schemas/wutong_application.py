from typing import Optional

from pydantic import BaseModel


class CommonOperation(BaseModel):
    action: Optional[str] = None
    group_id: Optional[str] = None
