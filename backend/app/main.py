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
    """健康检查"""
    llm_status="unknown"
    llm_detail=""
    try:
        import os,httpx
        url=os.getenv("LLM_BASE_URL","https://api.deepseek.com")

        #通用连通检查: GET /models (兼容 DeepSeek / OpenAI / Ollama)
        headers={}
        api_key=os.getenv("LLM_API_KEY","")
        if api_key:
            headers["Authorization"]=f"Bearer {api_key}"
        async with httpx.AsyncClient(timeout=5) as cli:
            resp=await cli.get(f"{url}/models",headers=headers)
            #200=通, 401=Key问题, 403=权限问题(但API可达)
            if resp.status_code in (200,401,403):
                llm_status="ok"
                llm_detail=f"HTTP {resp.status_code}"
            else:
                llm_status="error"
                llm_detail=f"HTTP {resp.status_code}"
    except (httpx.ConnectError,httpx.ReadTimeout):
        llm_status="error"
        llm_detail=f"无法连接 {url}"
    except Exception as e:
        llm_status="error"
        llm_detail=str(e)[:100]
    return {"status":"ok","service":"sre-agent","llm":llm_status,"llm_detail":llm_detail}

#路由注册 (必须在静态文件挂载之前, 否则 /api 路由被静态文件拦截)
from app.api import chat
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

from app.api.audit import router as audit_router
app.include_router(audit_router, prefix="/api/audit", tags=["audit"])

#挂载前端静态文件 (dist/ 存在时)
_FRONTEND_DIST=os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST) and os.path.isfile(os.path.join(_FRONTEND_DIST, "index.html")):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
