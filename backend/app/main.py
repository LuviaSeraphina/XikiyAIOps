# FastAPI 应用入口

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    #启动时: 初始化数据库表
    await init_db()
    yield
    #关闭时: 清理资源 (如有需要)

app=FastAPI(title="SRE-agent", version="0.1.0", lifespan=lifespan)

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

#路由注册
from app.api import chat
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

from app.api.audit import router as audit_router
app.include_router(audit_router, prefix="/api/audit", tags=["audit"])
