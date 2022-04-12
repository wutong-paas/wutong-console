from typing import Optional

from pydantic import BaseModel


class LoginParam(BaseModel):
    """
    获取token
    """
    nick_name: Optional[str] = None
    password: Optional[str] = None

    class Config:
        """
        example
        """
        schema_extra = {
            "example": {
                "nick_name": "昵称",
                "password": "密码"
            }
        }
