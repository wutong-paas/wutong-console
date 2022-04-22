import datetime
import time
from datetime import timedelta
from fastapi.responses import JSONResponse
from loguru import logger

from apis.manage.user.user_manage_controller import create_access_token
from core.setting import settings
from models.users.users import Users
from repository.users.user_oauth_repo import oauth_user_repo
from repository.users.user_repo import user_repo
from service.enterprise_service import enterprise_services
from service.user_service import user_svc


class OAuthUserService(object):

    def set_oauth_user_relation(self, session, api, oauth_service, oauth_user, access_token, refresh_token, code,
                                user=None):
        oauth_user.id = str(oauth_user.id)
        if api.is_communication_oauth():
            logger.debug(oauth_user.name)
            user = user_repo.get_enterprise_user_by_username(oauth_user.enterprise_id, oauth_user.name)
        authenticated_user = oauth_user_repo.user_oauth_exists(session=session, service_id=oauth_service.ID,
                                                               oauth_user_id=oauth_user.id)
        if authenticated_user is not None:
            authenticated_user.oauth_user_id = oauth_user.id
            authenticated_user.oauth_user_name = oauth_user.name
            authenticated_user.oauth_user_email = oauth_user.email
            authenticated_user.access_token = access_token
            authenticated_user.refresh_token = refresh_token
            authenticated_user.code = code
            if user:
                authenticated_user.user_id = user.user_id
            # authenticated_user.save()
            if authenticated_user.user_id is not None:
                login_user = user_repo.get_by_user_id(session, authenticated_user.user_id)
                access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAY)
                expires = datetime.datetime.utcnow() + access_token_expires
                token = create_access_token(login_user, expires)
                response = JSONResponse({"data": {"bean": {"token": token}}}, status_code=200)
                expiration = int(time.mktime((datetime.datetime.now() + timedelta(days=30)).timetuple()))
                response.set_cookie(key="token", value=token, expires=expiration)
                return response

            else:
                rst = {
                    "oauth_user_name": oauth_user.name,
                    "oauth_user_id": oauth_user.id,
                    "oauth_user_email": oauth_user.email,
                    "service_id": authenticated_user.service_id,
                    "oauth_type": oauth_service.oauth_type,
                    "is_authenticated": authenticated_user.is_authenticated,
                    "code": code,
                }
                msg = "user is not authenticated"
                return JSONResponse({"data": {"bean": {"result": rst, "msg": msg}}}, status_code=200)
        else:
            usr = oauth_user_repo.save_oauth(
                session=session,
                oauth_user_id=oauth_user.id,
                oauth_user_name=oauth_user.name,
                oauth_user_email=oauth_user.email,
                user_id=(user.user_id if user else None),
                code=code,
                service_id=oauth_service.ID,
                access_token=access_token,
                refresh_token=refresh_token,
                is_authenticated=True,
                is_expired=False,
            )
            rst = {
                "oauth_user_name": usr.oauth_user_name,
                "oauth_user_id": usr.oauth_user_id,
                "oauth_user_email": usr.oauth_user_email,
                "service_id": usr.service_id,
                "oauth_type": oauth_service.oauth_type,
                "is_authenticated": usr.is_authenticated,
                "code": code,
            }
            if user:
                access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAY)
                expires = datetime.datetime.utcnow() + access_token_expires
                token = create_access_token(user, expires)
                response = JSONResponse({"data": {"bean": {"token": token}}}, status_code=200)
                expiration = int(time.mktime((datetime.datetime.now() + timedelta(days=30)).timetuple()))
                response.set_cookie(key="token", value=token, expires=expiration)
                return response
            msg = "user is not authenticated"
            return JSONResponse({"data": {"bean": {"result": rst, "msg": msg}}}, status_code=200)

    def get_or_create_user_and_enterprise(self, session, oauth_user):
        user = user_repo.get_enterprise_user_by_username(session, oauth_user.enterprise_id, oauth_user.name)
        if not user:
            user_info = dict()
            user_info["email"] = oauth_user.email
            user_info["nick_name"] = oauth_user.name
            user_info["client_ip"] = oauth_user.client_ip
            user_info["phone"] = oauth_user.phone
            user_info["real_name"] = oauth_user.real_name
            user_info["is_active"] = 1
            password = "goodrain"
            user_info["enterprise_center_user_id"] = oauth_user.id
            user = Users(**user_info)
            user.set_password(password)
            session.add(user)
            session.flush()
        enterprise = enterprise_services.get_enterprise_by_enterprise_id(session, oauth_user.enterprise_id)
        if not enterprise:
            enterprise = enterprise_services.create_oauth_enterprise(session,
                                                                     oauth_user.enterprise_domain,
                                                                     oauth_user.enterprise_name,
                                                                     oauth_user.enterprise_id)
            user_svc.make_user_as_admin_for_enterprise(session, user.user_id, enterprise.enterprise_id)
        user.enterprise_id = enterprise.enterprise_id
        return user


oauth_sev_user_service = OAuthUserService()
