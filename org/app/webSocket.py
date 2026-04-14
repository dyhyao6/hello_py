"""
WebSocket - 占位模块
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ws/health")
def health():
    return {"status": "ok"}