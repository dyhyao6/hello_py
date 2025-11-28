import random

from fastapi import Query
from fastapi import Body
from typing import Type, List, Dict, Any
from fastapi import APIRouter, Request

from ..common import iresponse
from ..common.ierrors import ErrorCodes
from ..dao import Page
from ..models.reqs import FileUploadRequest
from ..models.resps import FileResponse
from org.doris.entities import File
from loguru import logger
from org.doris.service import file_service

router = APIRouter(prefix="/file", tags=["file"])


@router.get("/list")
def get_files(user_id: int = Query(default=None)):
    logger.info(f"访问文件列表接口, user_id: {user_id}")
    if not user_id:
        return iresponse.error(ErrorCodes.PARAM_ERROR)
    files: list[File] = file_service.list_files(user_id)
    # 转成可序列化的列表
    pay_load = [{"id": f.id, "name": f.name, "size": f.size, "bucket": f.bucket} for f in files]
    return iresponse.success_with_data(pay_load)


@router.post("/save")
def get_files(file: FileUploadRequest = Body(...)):
    logger.info(f"保存文件信息, file: {file}")
    if not file:
        return iresponse.error(ErrorCodes.PARAM_ERROR)
    # 使用 ** 解包简化赋值
    file_data = file.dict()  # 将 Pydantic 模型转成 dict
    if not file_data.get("id"):
        file_data["id"] = random.randint(100, 10000)

    # 创建 ORM 对象
    file_obj = File(**file_data)

    is_save = file_service.save_file(file_obj)
    return iresponse.success_with_data(is_save)


@router.get("/{file_id}")
def get_file_by_id(file_id: int):
    logger.info(f"查询文件信息, file_id: {file_id}")
    if not file_id:
        return iresponse.error(ErrorCodes.PARAM_ERROR)

    file: File = file_service.get_file_by_id(file_id)
    if not file:
        return iresponse.error(ErrorCodes.DATA_NOT_EXIST)

    return iresponse.success_with_data(FileResponse.from_orm(file))


def filter_dict_from_query(model_cls: Type, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    从请求 query 参数中筛选出 ORM 模型存在的字段
    """
    valid_keys = set(model_cls.__table__.columns.keys())
    return {k: v for k, v in query_params.items() if k in valid_keys and v is not None}


@router.post("/list_by_args")
async def list_files_post(request: Request):
    """
    通用 File 列表查询接口（POST），自动根据 JSON 参数过滤
    """
    # 获取请求 JSON
    query_params = await request.json()
    if not isinstance(query_params, dict):
        return iresponse.error("参数格式错误，应为 JSON 对象")

    # 过滤掉 ORM 不存在的字段
    filters = filter_dict_from_query(File, query_params)

    # 查询数据库
    file_list: List[File] = file_service.list_files_by_args(**filters)

    # 序列化成 Pydantic 模型
    result = [FileResponse.from_orm(f).dict() for f in file_list]

    return iresponse.success_with_data(data=result)


@router.get("/delete/{file_id}")
def remove_file(file_id: int):
    logger.info(f"删除文件信息, file_id: {file_id}")
    if not file_id:
        return iresponse.error(ErrorCodes.PARAM_ERROR)
    deleted = file_service.delete_file(file_id)
    return iresponse.success_with_data(deleted)


@router.post("/remove_by_args")
async def remove_files_by_args(request: Request):
    # 获取请求 JSON
    query_params = await request.json()
    if not isinstance(query_params, dict):
        return iresponse.error("参数格式错误，应为 JSON 对象")

    # 过滤掉 ORM 不存在的字段
    filters = filter_dict_from_query(File, query_params)
    # 查询数据库
    removed: bool = file_service.delete_file_by_args(**filters)
    return iresponse.success_with_data(removed)


@router.post("/update_by_id")
def update_file_by_id(file: FileUploadRequest = Body(...)):
    # 使用 ** 解包简化赋值
    file_data = file.dict()  # 将 Pydantic 模型转成 dict
    # 创建 ORM 对象
    file_obj = File(**file_data)
    # 查询数据库
    removed: bool = file_service.update_file_by_id(file_obj)
    return iresponse.success_with_data(removed)


@router.post("/exec")
async def exec_sql(request: Request):
    # 获取请求 JSON（必须 await）
    query_params = await request.json()
    sql = query_params.get("sql", "")
    if not sql:
        return iresponse.error(ErrorCodes.PARAM_ERROR)
    result = file_service.exec_sql(sql)
    return iresponse.success_with_data(result)


@router.post("/page")
def get_file_pages(user_id: int = Query(default=None),
                     page_num: int = Query(default=1),
                     page_size: int = Query(default=10)):
    _part_keys_filters = [
        File.user_id.__eq__(user_id) if user_id else None
    ]
    _part_key_kwargs = {
        "order_by": "created_at",
        "page_num": page_num,
        "page_size": page_size
    }
    page: Page[File] = file_service.page(*_part_keys_filters, **_part_key_kwargs)
    resp_data = []
    if page.records:
        for record in page.records:
            resp_data.append({
                "name": record.name,
                "bucket": record.bucket,
                "path": record.path,
                "size": record.size,
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),

            })
    return iresponse.success_with_data(iresponse.PageData(
        total=page.total,
        pages=page.pages,
        page_num=page.page_num,
        page_size=page.page_size,
        data=resp_data
    ))
