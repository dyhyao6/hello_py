from __future__ import annotations

from enum import Enum


class BaseEnum(Enum):
    def __new__(cls, code, desc, group=None):
        obj = object.__new__(cls)
        obj._value_ = code
        obj.code = code
        obj.desc = desc
        obj.group = group
        return obj

    @classmethod
    def get_desc_by_code(cls, code):
        for item in cls:
            if item.code == code:
                return item.desc
        return None

    @classmethod
    def get_by_code(cls, code):
        for item in cls:
            if item.code == code:
                return item
        return None

    @classmethod
    def get_by_desc(cls, desc):
        for item in cls:
            if item.desc == desc:
                return item
        return None
