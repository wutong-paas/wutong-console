from fastapi.security import OAuth2PasswordBearer
from database.session import SessionClass

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
