from __future__ import annotations

from .entities import *
from org.service import IService, T
from org.common.iexception import IException
from org.dao.doris import doris_engine


class DorisBaseService(IService[T]):
    def __init__(self):
        super().__init__(db_engine=doris_engine)


class FileService(DorisBaseService[File]):
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


def save_file(file: File) -> bool:
    """
    保存 File
    """
    if file is None:
        raise IException(message="file 不能为空")
    is_save = file_service.save(file)
    return is_save


def save_batch_files(files: list[File]) -> bool:
    """
    批量保存 File
    """
    if not files:
        raise IException(message="files 不能为空")
    return file_service.insert_entities(files)


def update_file_by_id(file: File) -> bool:
    """
    更新 file
    """
    if file is None:
        raise IException(message="file 不能为空")
    return file_service.update_by_id(file)


def get_file_by_id(file_id: int) -> File:
    """
    查询 file by id
    """
    if file_id is None:
        raise IException(message="file_id 不能为空")
    file: File = file_service.get_by_id(file_id)
    return file


def list_files_by_args(*args, **kwargs) -> list[File]:
    """
    获取 File 列表，可按 user_id 等 过滤
    """
    file_list = file_service.list_by_args(*args, **kwargs)
    return file_list


def delete_file(file_id: int) -> bool:
    """
    删除 file
    """
    if file_id is None:
        raise IException(message="file_id 不能为空")
    return file_service.remove_by_id(file_id)


def delete_file_by_args(*args, **kwargs) -> bool:
    """
    删除 file
    """
    if not args and not kwargs:
        raise IException(message="args 和 kwargs 不能同时为空")
    return file_service.remove_by_args(*args, **kwargs)


