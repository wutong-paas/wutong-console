import os

from sqlalchemy import select, delete

from core.utils.oauth_types import get_oauth_instance
from database.session import SessionClass
from models.users.oauth import OAuthServices, UserOAuthServices
from repository.base import BaseRepository


class UserOauthRepository(BaseRepository[UserOAuthServices]):
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
