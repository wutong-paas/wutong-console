from typing import Optional, Any

from pydantic import BaseModel


class Response(BaseModel):
    """
    响应模型
    """
    code: Optional[int] = None
    data: Optional[Any] = None
    msg: Optional[str] = "success"
    msg_show: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "code": 20000,
                "data": {},
                "msg": "success"
            }
        }
