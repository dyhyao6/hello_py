from __future__ import annotations

from .entities import *
from org.service import IService, T
from org.dao.pgsql import pgsql_engine


class PgsqlBaseService(IService[T]):
    def __init__(self):
        super().__init__(db_engine=pgsql_engine)


class FileService(PgsqlBaseService[File]):
    entity_cls = File


file_service = FileService()
