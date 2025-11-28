import uvicorn
from fastapi import FastAPI

from org.app.index import router as index_router


app = FastAPI(title="My Project API")


from org.app.FileController import router as file_router
from org.app.webSocket import router as webSocket_router
# 注册路由
app.include_router(index_router, prefix="/index", tags=["fast"])
app.include_router(file_router)  # prefix="/file" 已在 file_api.py 里定义
app.include_router(webSocket_router)


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8888)