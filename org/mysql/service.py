from __future__ import annotations

from .entities import *
from org.service import IService, T
from org.common.iexception import IException
from org.dao.mysql import mysql_engine


class MysqlBaseService(IService[T]):
    def __init__(self):
        super().__init__(db_engine=mysql_engine)

class FileService(MysqlBaseService[File]):
    entity_cls = File

file_service = FileService()


def list_files(user_id: int | None = None) -> list[File]:
    """
    获取 File 列表，可按 user_id 过滤
    """
    if user_id is None:
        raise IException(message="user_id 不能为空")
    file_list = file_service.list_by_args(user_id=user_id)
    return file_list
