"""
File Controller - 占位模块
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/file/health")
def health():
    return {"status": "ok"}