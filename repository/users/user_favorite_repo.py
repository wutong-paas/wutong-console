from sqlalchemy import select

from models.users.users import UserFavorite
from repository.base import BaseRepository


class UserFavoriteRepository(BaseRepository[UserFavorite]):

    def delete_user_favorite_by_id(self, session, user_id, favorite_id):
        user_favorites = self.get_user_favorite(session, user_id)
        tar_user_favorite = self.get_by_primary_key(session=session, primary_key=favorite_id)
        operate_user_favorites = user_favorites[tar_user_favorite.custom_sort:]
        for operate_user_favorite in operate_user_favorites:
            operate_user_favorite.custom_sort -= 1
        session.flush()
        self.delete_by_primary_key(session=session, primary_key=favorite_id)

    def get_user_favorite(self, session, user_id):
        return session.execute(select(UserFavorite).where(
            UserFavorite.user_id == user_id
        ).order_by(UserFavorite.custom_sort.asc())).scalars().all()

    def create_user_favorite(self, session, user_id, name, url, is_default):
        user_favorites = self.get_user_favorite(session, user_id)
        if user_favorites:
            custom_sort = user_favorites[-1].custom_sort + 1
        else:
            custom_sort = 0
        add_model = UserFavorite(user_id=user_id, name=name, url=url, custom_sort=custom_sort, is_default=is_default)
        self.base_create(session=session, add_model=add_model)

    def get_user_favorite_by_name(self, session, user_id, name):
        return session.execute(select(UserFavorite).where(
            UserFavorite.user_id == user_id,
            UserFavorite.name == name
        )).scalars().first()


user_favorite_repo = UserFavoriteRepository(UserFavorite)
