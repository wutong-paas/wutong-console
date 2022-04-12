from typing import Generic, TypeVar, Type, Optional, Any, List, Union, Dict

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session

from database.session import Base
from models.users.users import Users

ModelType = TypeVar("ModelType", bound=Base)


# CreateSchemaType = TypeVar("CreateSchemaType", bound=Base)
# UpdateSchemaType = TypeVar("UpdateSchemaType", bound=Base)

# , CreateSchemaType, UpdateSchemaType
class BaseRepository(Generic[ModelType]):
    """
    BaseRepository
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_by_primary_key(self, session: Session, primary_key: Any) -> Optional[ModelType]:
        """
        根据主键查询记录
        :param session: session
        :param primary_key: id
        :return: model
        """
        if self.model.__name__ == Users.__name__:
            return (session.execute(select(self.model).where(self.model.user_id == primary_key))).scalars().first()
        return (session.execute(select(self.model).where(self.model.ID == primary_key))).scalars().first()

    def get_multi(self, session: Session, *, skip: int = 0, limit: int = 20) -> List[ModelType]:
        """
        查询多条记录
        :param session:
        :param skip:
        :param limit:
        :return:
        """
        return (session.execute(select(self.model).offset(skip).limit(limit))).scalars().all()

    def delete_by_primary_key(self, session: Session, *, primary_key: int):
        """
        根据主键删除记录

        :param session:
        :param primary_key:
        """
        session.execute(delete(self.model).where(self.model.ID == primary_key))
        session.flush()

    @staticmethod
    def base_create(session: Session, *, add_model: ModelType) -> ModelType:
        """
        新增记录
        :param session:
        :param add_model:
        :return:
        """
        session.add(add_model)
        session.flush()
        session.refresh(add_model)
        return add_model

    def update_by_primary_key(self, session: Session, *, update_model: Union[ModelType, Dict[str, Any]]):
        """
        更新记录
        :param session:
        :param update_model:
        :return:
        """
        obj_data = jsonable_encoder(update_model)
        session.execute(update(self.model).where(self.model.ID == update_model.ID).values(obj_data))
        session.flush()

    def get_one_by_model(self, session: Session, *, query_model: Union[ModelType, Dict[str, Any]]) -> ModelType:
        """
        获取单条记录
        :param session:
        :param query_model:
        :return:
        """
        query_data: dict = jsonable_encoder(query_model)
        model = (session.execute(select(self.model).filter_by(**query_data))).scalars().first()
        return model

    def list_by_model(self, session: Session, *, query_model: Union[ModelType, Dict[str, Any]]) -> ModelType:
        """
        查询列表
        :param session:
        :param query_model:
        :return:
        """
        query_data: dict = jsonable_encoder(query_model)
        list_data = (session.execute(select(self.model).filter_by(**query_data))).scalars().all()
        return list_data

    def get_all(self, session: Session) -> ModelType:
        """
        查询列表
        :param session:
        :return:
        """
        list_data = (session.execute(select(self.model))).scalars().all()
        return list_data
