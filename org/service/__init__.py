from typing import Generic, Type, TypeVar, Callable

from ..common.ierrors import ErrorCodes
from ..common.iexception import IException
from ..dao import Page
from ..dao.engine import DbEngine
from ..dao.mysql import mysql_engine
from ..dao.pgsql import pgsql_engine

T = TypeVar('T')


class IService(Generic[T]):
    entity_cls: Type[T]
    db_engine: DbEngine

    def __init__(self, db_engine: DbEngine = None):
        self.db_engine = db_engine
        if not self.db_engine:
            self.db_engine = mysql_engine

    def list_by_args(self, *args, **kwargs) -> list[T]:
        results = self.db_engine.select_list(self.entity_cls, *args, **kwargs)
        return results

    def get_one(self, *args, **kwargs):
        return self.db_engine.select_one(self.entity_cls, *args, **kwargs)

    def count_by_args(self, *args, **kwargs) -> int:
        return self.db_engine.select_count(self.entity_cls, *args, **kwargs)

    def exist_by_args(self, *args, **kwargs) -> bool:
        return self.count_by_args(*args, **kwargs) > 0

    def page(self, *args, **kwargs) -> Page:
        ...
        """
        分页查询
        """
        return self.db_engine.page(self.entity_cls, *args, **kwargs)

    def get_by_id(self, eid: int, **kwargs) -> T:
        """
        查询 by id
        """
        if not eid:
            return None
        return self.db_engine.select_by_id(cls=self.entity_cls, eid=eid, **kwargs)

    def select(self, _colexpr, filters=None):
        return self.db_engine.exec_select(_colexpr, filters)

    def save(self, entity: T):
        """
        保存
        """
        if not entity:
            raise IException(error=ErrorCodes.DATA_NOT_EXIST)
        # if hasattr(entity, 'update_time'):
        #     setattr(entity, 'update_time', datetime.now())
        # mysql
        # if entity.id:
        #     # # 更新操作，不能更新创建人和创建时间
        #     # if hasattr(entity, 'create_by'):
        #     #     setattr(entity, 'create_by', None)
        #     # if hasattr(entity, 'create_time'):
        #     #     setattr(entity, 'create_time', None)
        #     affected_rows = self.db_engine.update_by_id(entity)
        #     if affected_rows == 1:
        #         return True
        #     else:
        #         raise IException(error=ErrorCodes.DB_ERROR)
        # else:
        #     # if hasattr(entity, 'create_time'):
        #     #     setattr(entity, 'create_time', datetime.now())
        #     self.db_engine.insert(entity)
        #     if entity.id:
        #         return True
        #     else:
        #         raise IException(error=ErrorCodes.DB_ERROR)
        # doris
        if entity.id:
            # 判断是否存在该id
            old = self.db_engine.select_by_id(cls=self.entity_cls, eid=entity.id)
            if old:
                self.db_engine.update_by_id(entity)
            else:
                self.db_engine.insert(entity)
        else:
            self.db_engine.insert(entity)
        if entity.id:
            return True
        else:
            raise IException(error=ErrorCodes.DB_ERROR)

    def insert(self, entity: T):
        """
        保存
        """
        if not entity:
            raise IException(error=ErrorCodes.DATA_NOT_EXIST)
        # if not entity.update_time:
        #     entity.update_time = datetime.now()
        # if not entity.create_time:
        #     entity.create_time = datetime.now()
        self.db_engine.insert(entity)
        if entity.id:
            return True
        else:
            raise IException(error=ErrorCodes.DB_ERROR)

    def insert_entities(self, entities: list[T]) -> bool:
        """
        批量插入
        """
        if not entities:
            raise IException(error=ErrorCodes.DATA_NOT_EXIST)
        row = self.db_engine.insert_batch(entities)
        if row > 0:
            return True
        else:
            return False

    def update_by_id(self, entity: T) -> bool:
        """
        更新
        """
        if not entity:
            return False
        id = entity.id
        if not id:
            return False
        count = self.db_engine.update_by_id(entity=entity)
        if count != 1:
            raise IException(error=ErrorCodes.DB_ERROR)
        return True

    def update(self, entity: T, *args, **kwargs) -> bool:
        """
        更新
        """
        if not entity:
            return False
        self.db_engine.update(entity, *args, **kwargs)
        return True

    def upsert(self, value: dict, **kwargs):
        """
        upsert方式写入
        """
        return self.upsert_values(values=[value], **kwargs)

    def upsert_values(self, values: list, **kwargs):
        """
        ON DUPLICATE KEY UPDATE方式写入
        """
        if not values:
            raise IException(error=ErrorCodes.DATA_NOT_EXIST)
        count = self.db_engine.upsert(cls=self.entity_cls, values=values, **kwargs)
        if count > 0:
            return True
        else:
            return False

    def delete_by_id(self, id):
        """
        逻辑删除
        """
        if not id:
            return
        old = self.db_engine.select_by_id(cls=self.entity_cls, eid=id)
        if not old:
            raise IException(error=ErrorCodes.DATA_NOT_EXIST)
        count = self.db_engine.update_by_id(self.entity_cls(id=id, is_delete=True))
        return True if count == 1 else False

    def remove_by_id(self, id) -> bool:
        if not id:
            return False
        count = self.db_engine.remove_by_id(cls=self.entity_cls, eid=id)
        return True if count == 1 else False

    def remove_by_args(self, *args, **kwargs) -> bool:
        _rows = self.db_engine.remove_by_args(self.entity_cls, *args, **kwargs)
        return _rows > 0

    def fetch_one(self, *args, **kwargs) -> bool:
        return self.db_engine.fetchone(self.entity_cls, *args, **kwargs)

    def execute(self, *args, **kwargs) -> bool:
        return self.db_engine.exec(*args, **kwargs)

    def transaction(self, func: Callable):
        return self.db_engine.transaction(func)
    def exec_sql(self, sql: str, *args, **kwargs):
        return self.db_engine.exec_sql(sql, *args, **kwargs)
