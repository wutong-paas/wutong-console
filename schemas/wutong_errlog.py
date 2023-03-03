from typing import Optional
from pydantic import BaseModel


class ErrLogCreate(BaseModel):
    """
    创建错误日志
    """

    ID: Optional[int] = 0
    msg: Optional[str] = None
    username: Optional[str] = None
    address: Optional[str] = None

    class Config:
        """
        样例数据
        """
        schema_extra = {
            "example": {
                "msg": "错误：Error: Minified React error #62",
                "username": "admin",
                "address": "test_address"
            }
        }