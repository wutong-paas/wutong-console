import os

from loguru import logger
from sqlalchemy import select, delete, update

from core.utils.oauth.oauth_types import support_oauth_type, get_oauth_instance
from database.session import SessionClass
from models.users.oauth import OAuthServices, UserOAuthServices
from repository.base import BaseRepository


class UserOauthRepository(BaseRepository[UserOAuthServices]):

    def get_user_oauth_by_id(self, session, service_id, id):
        return session.execute(select(UserOAuthServices).where(
                UserOAuthServices.ID == id,
                UserOAuthServices.service_id == service_id,
            )).scalars().first()

    def get_user_oauth_by_code(self, session, service_id, code):
        return session.execute(select(UserOAuthServices).where(
                UserOAuthServices.code == code,
                UserOAuthServices.service_id == service_id,
            )).scalars().first()

    def save_oauth(self, session, *args, **kwargs):
        user = None
        try:
            user = session.execute(select(UserOAuthServices).where(
                UserOAuthServices.oauth_user_id == kwargs.get("oauth_user_id"),
                UserOAuthServices.service_id == kwargs.get("service_id"),
                UserOAuthServices.user_id == kwargs.get("user_id"),
            )).scalars().first()
            if not user:
                user = UserOAuthServices(
                    oauth_user_id=kwargs.get("oauth_user_id"),
                    oauth_user_name=kwargs.get("oauth_user_name"),
                    oauth_user_email=kwargs.get("oauth_user_email"),
                    service_id=kwargs.get("service_id"),
                    is_auto_login=kwargs.get("is_auto_login"),
                    is_authenticated=kwargs.get("is_authenticated"),
                    is_expired=kwargs.get("is_expired"),
                    access_token=kwargs.get("access_token"),
                    refresh_token=kwargs.get("refresh_token"),
                    user_id=kwargs.get("user_id"),
                    code=kwargs.get("code"))
                session.add(user)
                session.flush()
        except Exception as e:
            logger.exception(e)
        return user

    def user_oauth_exists(self, session, service_id, oauth_user_id):
        return session.execute(select(UserOAuthServices).where(
            UserOAuthServices.service_id == service_id,
            UserOAuthServices.oauth_user_id == oauth_user_id
        )).scalars().first()

    def delete_users_by_services_id(self, session, service_id):
        session.execute(delete(UserOAuthServices).where(
            UserOAuthServices.service_id == service_id
        ))
        session.flush()

    def get_enterprise_center_user_by_user_id(self, session: SessionClass, user_id):
        q = session.execute(select(OAuthServices).where(OAuthServices.oauth_type == "enterprisecenter",
                                                        OAuthServices.ID == 1))
        oauth_service = q.scalars().first()
        pre_enterprise_center = os.getenv("PRE_ENTERPRISE_CENTER", None)
        if pre_enterprise_center:
            q = session.execute(
                select(OAuthServices).where(OAuthServices.oauth_type == "enterprisecenter",
                                            OAuthServices.name == pre_enterprise_center))
            oauth_service = q.scalars().first()
        if not oauth_service:
            return None, None
        #        logger.debug(oauth_service.ID, user_id)
        q = session.execute(
            select(UserOAuthServices).where(UserOAuthServices.service_id == oauth_service.ID,
                                            UserOAuthServices.user_id == user_id))
        oauth_user = q.scalars().first()
        return oauth_user, oauth_service

    def del_all_user_oauth(self, session: SessionClass, user_id):
        session.execute(delete(UserOAuthServices).where(UserOAuthServices.user_id == user_id))


class OAuthRepo(BaseRepository[OAuthServices]):

    def delete_oauth_service(self, session, service_id):
        session.execute(delete(OAuthServices).where(
            OAuthServices.ID == service_id
        ))
        session.flush()

    def create_or_update_console_oauth_services(self, session, values, eid):
        for value in values:
            if value["oauth_type"] in list(support_oauth_type.keys()):
                instance = get_oauth_instance(value["oauth_type"])
                auth_url = instance.get_auth_url(home_url=value["home_url"])
                access_token_url = instance.get_access_token_url(home_url=value["home_url"])
                api_url = instance.get_user_url(home_url=value["home_url"])
                is_git = instance.is_git_oauth()
                if value.get("service_id") is None:
                    oauth_service = OAuthServices(
                        name=value["name"],
                        client_id=value["client_id"],
                        eid=value["eid"],
                        client_secret=value["client_secret"],
                        redirect_uri=value["redirect_uri"],
                        oauth_type=value["oauth_type"],
                        home_url=value["home_url"],
                        auth_url=auth_url,
                        access_token_url=access_token_url,
                        api_url=api_url,
                        enable=value["enable"],
                        is_auto_login=value["is_auto_login"],
                        is_console=value["is_console"],
                        is_git=is_git)
                    session.add(oauth_service)
                    session.flush()
                else:
                    session.execute(update(OAuthServices).where(
                        OAuthServices.ID == value["service_id"]
                    ).values({
                        "name": value["name"],
                        "eid": value["eid"],
                        "redirect_uri": value["redirect_uri"],
                        "home_url": value["home_url"],
                        "auth_url": auth_url,
                        "access_token_url": access_token_url,
                        "api_url": api_url,
                        "enable": value["enable"],
                        "is_auto_login": value["is_auto_login"],
                        "is_console": value["is_console"]
                    }))
                    session.flush()
            else:
                raise Exception("未找到该OAuth类型")
        rst = session.execute(select(OAuthServices).where(
                    OAuthServices.eid == eid,
                    OAuthServices.is_console == 1
                )).scalars().all()
        return rst

    def get_all_oauth_services(self, session, eid):
        return session.execute(
            select(OAuthServices).where(OAuthServices.eid == eid,
                                        OAuthServices.is_deleted == 0)
        ).scalars().all()

    def get_conosle_oauth_service(self, session, eid):
        return session.execute(
            select(OAuthServices).where(OAuthServices.eid == eid,
                                        OAuthServices.is_deleted == 0,
                                        OAuthServices.is_console == 1)
        ).scalars().first()

    def get_user_oauth_by_user_id(self, session: SessionClass, service_id, user_id):
        result_oauth_user = session.execute(
            select(UserOAuthServices).where(UserOAuthServices.service_id == service_id,
                                            UserOAuthServices.user_id == user_id)
        )
        oauth_user = result_oauth_user.scalars().first()
        return oauth_user

    def get_user_oauth_services_info(self, session: SessionClass, eid, user_id):
        oauth_services = []
        results_services = session.execute(
            select(OAuthServices).where(OAuthServices.eid == eid, OAuthServices.is_deleted == False,
                                        OAuthServices.enable == True)
        )
        services = results_services.scalars().all()
        for service in services:
            user_service = self.get_user_oauth_by_user_id(session=session, service_id=service.ID, user_id=user_id)
            api = get_oauth_instance(service.oauth_type, service, None)
            authorize_url = api.get_authorize_url()
            if user_service:
                oauth_services.append({
                    "service_id": service.ID,
                    "service_name": service.name,
                    "oauth_type": service.oauth_type,
                    "is_authenticated": user_service.is_authenticated,
                    "is_expired": user_service.is_expired,
                    "auth_url": service.auth_url,
                    "client_id": service.client_id,
                    "redirect_uri": service.redirect_uri,
                    "is_git": service.is_git,
                    "authorize_url": authorize_url,
                    "oauth_user_name": user_service.oauth_user_name,
                })
            else:
                oauth_services.append({
                    "service_id": service.ID,
                    "service_name": service.name,
                    "oauth_type": service.oauth_type,
                    "is_authenticated": False,
                    "is_expired": False,
                    "auth_url": service.auth_url,
                    "client_id": service.client_id,
                    "redirect_uri": service.redirect_uri,
                    "is_git": service.is_git,
                    "authorize_url": authorize_url,
                    "oauth_user_name": "",
                })
        return oauth_services


oauth_repo = OAuthRepo(OAuthServices)
oauth_user_repo = UserOauthRepository(UserOAuthServices)
