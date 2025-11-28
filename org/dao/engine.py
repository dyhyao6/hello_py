from __future__ import annotations

import traceback
import urllib.parse

from pydantic import BaseModel, Field
from typing import Optional, Type, List, Iterable, Callable

from loguru import logger
from sqlalchemy import create_engine, text, desc, asc, and_, UniqueConstraint, Engine
from sqlalchemy.sql.dml import Insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker, Session, Query
from sqlalchemy.sql.elements import OperatorExpression

from . import T, Page


# # 获取 SQLAlchemy 的日志记录器
# # sqlalchemy_logger = logging.getLogger("sqlalchemy")
# sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
# sqlalchemy_logger.setLevel(logging.ERROR)
# sqlalchemy_logger.addHandler(logger.InterceptHandler())

def update_attr(entity: T, record: T):
    # 获取 entity 中需要更新的字段
    for field, value in vars(entity).items():
        if value is None:
            continue
        if field.startswith("_") or field.startswith("__"):
            continue
        if not hasattr(record, field) and getattr(record, field) != value:
            continue
        setattr(record, field, value)


def parse_columns(cls: Type[T],
                  select_columns: Iterable[str] = None,
                  exclude_columns: Iterable[str] = None) -> list[str]:
    _parsed_columns: set = set()
    _skip_attrs = ['registry', 'metadata', 'self']

    def filter_fields(fields: Iterable[str]):
        for attr in fields:
            if callable(getattr(cls, attr)) or attr.startswith("_") or attr.startswith("__") or attr in _skip_attrs:
                continue
            _parsed_columns.add(getattr(cls, attr))

    _select_columns = select_columns if select_columns else dir(cls)  # 获取 cls 所有属性作为字段值
    filter_fields(_select_columns)
    _final_columns = []
    # 如果指定了排除列， 则该字段不被查询
    if exclude_columns:
        for col in _parsed_columns:
            if col.name not in exclude_columns:
                _final_columns.append(col)
    else:
        _final_columns = _parsed_columns
    return list(_final_columns)


def parse_filters(cls: Type[T], args=None, kwargs=None):
    filters = []
    if args:
        for _arg in args:
            if _arg is None:
                continue
            if isinstance(_arg, OperatorExpression):
                filters.append(_arg)
    if kwargs:
        for key, value in kwargs.items():
            if value is None:
                continue
            if isinstance(value, OperatorExpression):
                filters.append(value)
            else:
                if hasattr(cls, key):
                    filters.append(getattr(cls, key) == value)
    return filters


def parse_update_columns(stmt: Insert, cls: Type[T], kwargs=None) -> dict:
    all_columns = cls.__table__.columns
    _exclude_columns = set(kwargs.pop('exclude_columns')) if 'exclude_columns' in kwargs.keys() else set()
    # 排除主键
    for col in cls.__table__.primary_key.columns:
        _exclude_columns.add(col.name)
    # 排除唯一主键
    for col in all_columns:
        if not col.unique:
            continue
        _exclude_columns.add(col.name)
    # 排除联合主键
    for _constraint in cls.__table__.constraints:
        if not isinstance(_constraint, UniqueConstraint):
            continue
        for col in _constraint.columns:
            _exclude_columns.add(col.name)

    _update_columns = set(kwargs.pop('update_columns')) if 'update_columns' in kwargs.keys() else set()
    if not _update_columns:
        _update_columns = {col.name for col in all_columns}

    # 如果指定了排除列， 则该字段不被查询
    if _exclude_columns:
        _update_columns = {col for col in _update_columns if col not in _exclude_columns}

    _update_mapping = {field: stmt.inserted[field] for field in _update_columns}

    return _update_mapping


def _wrapper_query(query: Query, cls, args=None, **kwargs):
    # 如果指定了查询列，则只查询这些列
    _columns = kwargs.pop('columns') if 'columns' in kwargs.keys() else None
    _exclude_columns = kwargs.pop('exclude_columns') if 'exclude_columns' in kwargs.keys() else None
    _parsed_columns = parse_columns(cls, _columns, _exclude_columns)
    query = query.with_entities(*_parsed_columns)
    _order_by = kwargs.pop('order_by') if 'order_by' in kwargs.keys() else None
    _is_asc = kwargs.pop('asc') if 'asc' in kwargs.keys() else False
    if isinstance(_order_by, (list, tuple)):
        query = query.order_by(*_order_by)
    elif _order_by is not None and _is_asc is not None:
        query = query.order_by(asc(_order_by) if _is_asc is True else desc(_order_by))
    _group_by = kwargs.pop('group_by') if 'group_by' in kwargs.keys() else None
    if _group_by is not None:
        query = query.group_by(_group_by)
    filters = parse_filters(cls=cls, args=args, kwargs=kwargs)
    if filters:
        query = query.filter(and_(*filters))
    return query


def _wrapper_query_result(result, cls, **kwargs):
    # 如果指定了查询列，则只查询这些列
    _columns = kwargs.pop('columns') if 'columns' in kwargs.keys() else None
    _exclude_columns = kwargs.pop('exclude_columns') if 'exclude_columns' in kwargs.keys() else None
    _parsed_columns = parse_columns(cls, _columns, _exclude_columns)

    def _set_entity(_result):
        _instance = cls()
        for _column, _value in zip(_parsed_columns, _result):
            if _column is None:
                continue
            setattr(_instance, _column.key, _value)
        return _instance

    instances = []
    if result:
        if isinstance(result, list):
            for _result in result:
                instances.append(_set_entity(_result))
            return instances
        else:
            return _set_entity(result)
    return instances


class EngineConfig(BaseModel):
    name: Optional[str] = Field(default='default', description='数据库引擎名称')
    protocol: Optional[str] = Field(default='mysql+pymysql', description='数据库协议')
    host: Optional[str] = Field(default='localhost', description='数据库主机')
    port: Optional[int] = Field(default=3306, description='数据库端口')
    username: Optional[str] = Field(default='', description='数据库用户名')
    password: Optional[str] = Field(default='', description='数据库密码')
    database: Optional[str] = Field(default='?', description='数据库名称')
    query: Optional[dict] = Field(default_factory=dict, description='查询参数')
    charset: Optional[str] = Field(default='utf8', description='数据库字符集')
    pool_size: Optional[int] = Field(default=20, description='连接池大小')
    max_overflow: Optional[int] = Field(default=40, description='最大溢出连接数')
    pool_timeout: Optional[int] = Field(default=60, description='连接池超时时间')
    pool_recycle: Optional[int] = Field(default=3600, description='连接池回收时间')
    echo: Optional[bool] = Field(default=False, description='是否打印SQL语句')
    connect_args: Optional[dict] = Field(default_factory=dict, description='连接参数')

    def get_url(self) -> URL:
        return URL.create(
            drivername=self.protocol,
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query=self.query
        )

    def get_connect_args(self, **kwargs):
        conn_args = self.connect_args.copy()
        conn_args.update(kwargs)
        return conn_args


class DbEngine:
    def __init__(self, config: dict | EngineConfig = EngineConfig()):
        if isinstance(config, dict):
            config = EngineConfig(**config)
        self.config = config
        self.name = self.config.name
        # 对用户名和密码进行URL编码
        username = self.config.username
        if username:
            self.config.username = urllib.parse.quote(username.encode('utf-8'))
        password = self.config.password
        if password:
            self.config.password = urllib.parse.quote(self.config.password.encode('utf-8'))

        # 'mysql+mysqlconnector://username:password@localhost/dbname',
        # self.url = f'{protocol}://{username}:{password}@{host}:{port}/{database}'
        logger.info(f'Init DbEngine: {self.name} ==> {self.config.host}:{self.config.port}/{self.config.database}')
        self._engine = None

    def create(self):
        logger.debug(f'New {self.name} Engine ...')
        return create_engine(url=self.config.get_url(),
                             pool_size=self.config.pool_size,
                             max_overflow=self.config.max_overflow,
                             pool_timeout=self.config.pool_timeout,
                             pool_recycle=self.config.pool_recycle,
                             connect_args=self.config.get_connect_args(),
                             pool_pre_ping=True,
                             echo=self.config.echo)

    def get_engine(self) -> Engine:
        if not self._engine:
            self._engine = self.create()
        # else:
        #     logger.info(f'Exist {self.name} Engine...')
        return self._engine

    def get_session(self) -> Session:
        _sessionmaker = sessionmaker(bind=self.get_engine())
        # logger.debug(f'Use {self.name} Session...')
        return _sessionmaker()

    def insert(self, entity: T) -> int:
        with self.get_session() as session:
            try:
                # 提交即保存到数据库
                session.add(entity)
                session.flush()  # 只发送SQL到数据库，但不提交事务
                session.commit()  # 如果flush成功，则提交事务
                return entity.id  # 假设entity映射到一个数据库行
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to insert entity: {e}")
                raise e
            finally:
                # 关闭会话
                session.close()

    def insert_batch(self, entities: List[T]) -> int:
        with self.get_session() as session:
            try:
                # 提交即保存到数据库
                session.add_all(entities)
                session.flush()  # 只发送SQL到数据库，但不提交事务
                session.commit()  # 如果flush成功，则提交事务
                return len(entities)  # 假设entity映射到一个数据库行
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to insert entity: {e}")
                raise e
            finally:
                # 关闭会话
                session.close()

    def upsert(self, cls: Type[T], values: list, **kwargs) -> int:
        stmt = Insert(cls).values(values)
        # 如果未指定更新字段，则默认更新非主键的所有字段
        update_mapping = parse_update_columns(stmt=stmt, cls=cls, kwargs=kwargs)
        # 添加 ON DUPLICATE KEY UPDATE 部分
        stmt = stmt.on_duplicate_key_update(**update_mapping)
        res = self.exec_stmt(stmt)
        if not res:
            return 0
        return res.rowcount

    def update(self, entity: T, *args, **kwargs) -> int:
        with self.get_session() as session:
            try:
                cls: Type[T] = type(entity)
                # 获取所有满足条件的记录
                query = session.query(cls)
                filters = parse_filters(cls=cls, args=args, kwargs=kwargs)
                if filters:
                    query = query.filter(and_(*filters))
                records = query.all()
                if not records:
                    return 0
                # 遍历所有记录并更新字段
                for record in records:
                    update_attr(entity, record)

                # 提交事务 即保存到数据库
                session.commit()
                # 假设所有查询到的记录都被更新了，返回记录数
                return len(records)
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update entity: {e}")
                raise e
            finally:
                session.close()

    def update_by_id(self, entity: T) -> int:
        with self.get_session() as session:
            try:
                cls: Type[T] = type(entity)
                eid: int = entity.id
                record = session.query(cls).filter(cls.id == eid).one_or_none()
                if record is None:
                    logger.warning(f"没有找到ID为 {eid} 的记录")
                    return 0
                update_attr(entity, record)
                # 提交事务 即保存到数据库
                session.flush()
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update entity by ID: {e}")
                # return 0
                raise e
            finally:
                # 确保会话被关闭
                session.close()

    def select_by_id(self, cls: Type[T], eid: int, **kwargs) -> Optional[T]:
        with self.get_session() as session:
            try:
                query = session.query(cls)
                query = _wrapper_query(query=query, cls=cls, **kwargs)
                result = query.filter(cls.id == eid).one_or_none()
                if result:
                    return _wrapper_query_result(result, cls, **kwargs)
                return None
            except Exception as e:
                logger.error(f"Failed to query entity by ID: {e}")
                raise e
            finally:
                # 确保会话被关闭
                session.close()

    def select_one(self, cls: Type[T], *args, **kwargs) -> Optional[T]:
        """
        查询条数
        """
        with self.get_session() as session:
            try:
                query = session.query(cls)
                query = _wrapper_query(query=query, cls=cls, args=args, **kwargs)
                query = query.limit(1)  # 添加限制条件 limit(1)
                result = query.one_or_none()
                if result:
                    return _wrapper_query_result(result, cls, **kwargs)
                return None
            except Exception as e:
                logger.error(f"Failed to Select One: {e}")
                raise e

    def select_count(self, cls: Type[T], *args, **kwargs) -> int:
        """
        查询条数
        """
        with self.get_session() as session:
            try:
                query = session.query(cls)
                filters = parse_filters(cls=cls, args=args, kwargs=kwargs)
                if filters:
                    query = query.filter(and_(*filters))
                return query.count()
            except Exception as e:
                logger.error(f"Failed to query entities: {e}")
                raise e
            finally:
                session.close()

    def select_list(self, cls: Type[T], *args, **kwargs) -> List[T]:
        with self.get_session() as session:
            try:
                query = session.query(cls)
                query = _wrapper_query(query=query, cls=cls, args=args, **kwargs)
                results = query.all()
                return _wrapper_query_result(results, cls, **kwargs)
            except Exception as e:
                logger.error(f"Failed to query entities: {e}")
                raise e

    def page(self, cls: Type[T], *args, **kwargs) -> Page[T]:
        """
        分页查询
        """
        with self.get_session() as session:
            try:

                # 指定表
                query = session.query(cls)
                # 构建查询条件
                filters = parse_filters(cls=cls, args=args, kwargs=kwargs)
                if filters:
                    query = query.filter(and_(*filters))
                # 总数
                total = query.count()

                # 分页参数
                page_num = kwargs.pop('page_num') if 'page_num' in kwargs.keys() else 1
                page_size = kwargs.pop('page_size') if 'page_size' in kwargs.keys() else 10
                total_pages: int = (total + page_size - 1) // page_size

                # 确保页码在有效范围内
                page_num = max(1, min(page_num, total_pages))

                # 计算分页查询的偏移量
                offset = (page_num - 1) * page_size

                query = _wrapper_query(query=query, cls=cls, **kwargs)

                results = query.offset(offset).limit(page_size).all()
                instances = []
                if results:
                    instances = _wrapper_query_result(results, cls, **kwargs)
                return Page(total=total, pages=total_pages, page_num=page_num, page_size=page_size, records=instances)
            except SQLAlchemyError as e:
                logger.error(f"Failed to query entities: {e}")
                raise e

    def remove_by_id(self, cls: Type[T], eid: int) -> int:
        with self.get_session() as session:
            try:
                record = session.query(cls).filter(cls.id == eid).first()
                if record is None:
                    logger.warning(f"没有找到ID为 {eid} 的记录")
                    return 1
                session.delete(record)
                # 提交事务 即保存到数据库
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                error = traceback.format_exc(limit=3)
                logger.warning(f"Failed Remove By ID: {str(e)} \n {error}")
                return 0

    def remove_by_args(self, cls: Type[T], *args, **kwargs) -> int:
        with self.get_session() as session:
            try:
                query = session.query(cls)
                query = _wrapper_query(query=query, cls=cls, args=args, **kwargs)
                results = query.all()
                if results:
                    for record in results:
                        # 获取主键
                        primary_key = getattr(record, 'id')  # 假设主键字段名为 'id'
                        # 查询实际的 ORM 实例
                        instance = session.query(cls).get(primary_key)
                        if instance:
                            session.delete(instance)
                session.commit()
                return len(results)
            except Exception as e:
                session.rollback()
                error = traceback.format_exc(limit=3)
                logger.warning(f"Failed Remove By Args: {str(e)} \n {error}")
                return 0

    def fetchone(self, cls: Type[T], *args, **kwargs) -> T:
        with self.get_session() as session:
            _result = session.execute(*args, **kwargs).fetchone()
            if _result:
                _result = _wrapper_query_result(_result, cls)
            return _result

    def transaction(self, func: Callable):
        with self.get_session() as session:
            try:
                _res = func(session)
                session.commit()
                return _res
            except Exception as e:
                session.rollback()
                raise e

    def exec(self, *args, **kwargs):
        with self.get_session() as session:
            return session.execute(*args, **kwargs)

    def exec_select(self, _colexpr, filters=None):
        with self.get_session() as session:
            try:
                query = session.query(_colexpr)
                if filters:
                    query = query.filter(filters)
                return query.all()
            except Exception as e:
                logger.error(f"Failed exec select: {e}")
                return []

    def exec_stmt(self, stmt):
        with self._engine.begin() as conn:
            return conn.execute(stmt)

    def exec_sqls(self, sql_statements: list):
        """
        执行批量SQL语句。
        :param sql_statements: SQL语句的列表。
        """
        with self.get_session() as session:
            for sql in sql_statements:
                session.execute(text(sql))
            session.commit()

    def exec_sql(self, sql: str,
                 cls: Type[T] = dict,
                 params=None,
                 execution_options=None) -> list[T]:
        result_list: List[T] = []
        with self.get_session() as session:
            _result = session.execute(
                statement=text(sql),
                params=params,
                execution_options=execution_options
            )
            _rows = _result.all()
            for row in _rows:
                row_data: T = cls(**row._asdict()) if cls else tuple(row)
                result_list.append(row_data)
            session.commit()
        return result_list
