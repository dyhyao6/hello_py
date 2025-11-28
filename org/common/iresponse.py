#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import annotations

# from dataclasses import dataclass, field
from typing import Any, List, TypeVar
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from .ienums import BaseEnum

T = TypeVar('T')

SUCCESS_CODE: int = 0
SUCCESS_MSG: str = 'ok'
FAIL_CODE: int = -1
FAIL_MSG: str = 'error'


# @dataclass
class IResponse(BaseModel):
    code: int = SUCCESS_CODE
    msg: str = SUCCESS_MSG
    data: object = Field(default=None)


# @dataclass
class PageData(BaseModel):
    total: int = 0
    pages: int = 0
    page_num: int = 1
    page_size: int = 10
    data: List[T] = Field(default_factory=list)


def success(code: int = SUCCESS_CODE, msg: str = SUCCESS_MSG, data=None):
    if data is None:
        data = {}
    return IResponse(code=code, msg=msg, data=data)


def success_with_code(code: int = SUCCESS_CODE):
    return success(code=code)


def success_with_msg(msg: str = SUCCESS_MSG):
    return success(msg=msg)


def success_with_data(data=None):
    return success(data=data)


def error_with_code(code: int = FAIL_CODE, msg: str = FAIL_MSG):
    return IResponse(code=code, msg=msg)


def error(_error: str | BaseEnum):
    if isinstance(_error, str):
        return error_with_code(msg=_error)
    return error_with_code(code=_error.code, msg=_error.desc)


def json_response_error(status_code: int = 500,
                        code: int = FAIL_CODE,
                        msg: str = FAIL_MSG,
                        data=None):
    return JSONResponse(
        status_code=status_code,
        content={"code": code if code else FAIL_CODE, "msg": msg, "data": data}
    )
