# FastAPI 应用入口

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    #启动时: 初始化数据库表
    await init_db()
    yield
    #关闭时: 清理资源 (如有需要)

app=FastAPI(title="SRE-agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sre-agent"}

#路由注册 (必须在静态文件挂载之前, 否则 /api 路由被静态文件拦截)
from app.api import chat
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

from app.api.audit import router as audit_router
app.include_router(audit_router, prefix="/api/audit", tags=["audit"])

#挂载前端静态文件 (dist/ 存在时)
_FRONTEND_DIST=os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST) and os.path.isfile(os.path.join(_FRONTEND_DIST, "index.html")):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
