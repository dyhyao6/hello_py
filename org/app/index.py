from fastapi import APIRouter, FastAPI

router = APIRouter()

from loguru import logger
@router.get("/fast")
def index():
    logger.info("访问首页")
    return "你好，我是首页"


