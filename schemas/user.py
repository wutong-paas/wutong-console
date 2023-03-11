from typing import Optional

from pydantic import BaseModel


class UserInfo(BaseModel):
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    nick_name: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    token: Optional[str] = None


class CreateAccessTokenParam(BaseModel):
    note: Optional[str] = None
    age: Optional[str] = None


class CreateUserParam(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    re_password: Optional[str] = None
    phone: Optional[str] = None
    realname: Optional[str] = None
    user_name: Optional[str] = None
    oauth_user_id: Optional[str] = None
