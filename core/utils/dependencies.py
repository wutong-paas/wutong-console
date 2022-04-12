from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from starlette import status

from core.setting import settings
from database.session import SessionClass
from models.users.users import Users
from service.user_service import UserService

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f'/api/admin/login/access_token/'
)


class DALGetter:
    def __init__(self, dal_cls):
        self.dal_cls = dal_cls

    def __call__(self):
        # with sync_session() as session:
        with SessionClass.begin():
            yield self.dal_cls(SessionClass())


def get_current_user(
        dal: UserService = Depends(DALGetter(UserService)),
        token: str = Depends(reusable_oauth2)
) -> Users:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except (jwt.JWTError, ValidationError):
        raise credentials_exception
    user = dal.get(id=payload['user_id'])
    if user is None:
        raise credentials_exception
    return user
