# FastAPI 应用入口

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SRE-agent", version="0.1.0")

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


# 路由注册（后续启用）
# from app.api import chat, dashboard, audit
# app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
# app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
