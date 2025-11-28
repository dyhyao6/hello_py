from __future__ import annotations

from datetime import datetime
from typing import TypeVar, Optional, Generic

from pydantic import BaseModel
from sqlalchemy import Boolean, String, DateTime, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

T = TypeVar('T')


class Page(BaseModel, Generic[T]):
    total: Optional[int] = 0
    page_num: Optional[int] = 1
    page_size: Optional[int] = 10
    records: Optional[list[T]] = None

    @property
    def pages(self) -> int:
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class Base(DeclarativeBase):
    pass


class BaseEntity(Base):
    __abstract__ = True  # 表示这是一个抽象类，不会创建对应的表
    id: Mapped[Optional[int]] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now(), comment='创建时间')
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now(),
                                                            comment='修改时间')
    create_by: Mapped[Optional[str]] = mapped_column(String, default="SYSTEM", comment='创建人')
    update_by: Mapped[Optional[str]] = mapped_column(String, default="SYSTEM", comment='修改人')
    is_delete: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, comment='是否删除:0: no, 1: yes')

    def to_dict(self, skip_keys: set = None, exclude_none: bool = False):
        """将SQLAlchemy对象转换为字典"""
        if not hasattr(self, '__table__'):
            raise ValueError("对象不是SQLAlchemy模型实例")
        _dict = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if skip_keys and key in skip_keys:
                continue
            if exclude_none and value is None:
                continue
            if isinstance(value, datetime):
                _value = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                _value = value
            _dict[key] = _value
        return _dict

    def model_dump(self, skip_keys: set = None, exclude_none: bool = False):
        """将SQLAlchemy对象转换为字典"""
        if not hasattr(self, '__table__'):
            raise ValueError("对象不是SQLAlchemy模型实例")
        # 获取基础字段
        _dict = {}
        for _col in self.__table__.columns:
            _value = getattr(self, _col.key, None)
            if skip_keys and _col.key in skip_keys:
                continue
            if exclude_none and _value is None:
                continue
            if isinstance(_value, datetime):
                _dict[_col.key] = _value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                _dict[_col.key] = _value
        return _dict
