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
    """健康检查 — 含 LLM 连通性探测"""
    llm_status="unknown"
    llm_detail=""
    try:
        import os,httpx,subprocess
        url=os.getenv("LLM_BASE_URL","http://localhost:11434")
        provider=os.getenv("LLM_PROVIDER","ollama")

        if provider=="ollama":
            #先查进程是否在跑
            try:
                out=subprocess.run(["pgrep","-f","ollama.*serve"],capture_output=True,text=True,timeout=3)
                if not out.stdout.strip():
                    llm_status="error"
                    llm_detail="ollama serve 进程未运行, 请执行: nohup ollama serve &"
            except Exception:
                pass

            #再查 API 是否可达
            if llm_status!="error":
                try:
                    async with httpx.AsyncClient(timeout=5) as cli:
                        resp=await cli.get(f"{url}/api/tags")
                        if resp.status_code==200:
                            llm_status="ok"
                            try:
                                models=[m["name"] for m in resp.json().get("models",[])]
                                if models:
                                    llm_detail="models: "+",".join(models[:5])
                                else:
                                    llm_status="error"
                                    llm_detail="Ollama 已连接但无模型, 请执行: ollama pull <模型名称>"
                            except Exception:
                                llm_detail="connected"
                        else:
                            llm_status="error"
                            llm_detail=f"HTTP {resp.status_code}"
                except httpx.ConnectError:
                    llm_status="error"
                    llm_detail=f"无法连接 {url}, 请确认 ollama serve 已启动"
                except Exception as e:
                    llm_status="error"
                    llm_detail=str(e)[:100]
        else:
            #非 Ollama: 简单连通检查
            try:
                async with httpx.AsyncClient(timeout=5) as cli:
                    resp=await cli.get(f"{url}/models",headers={"Authorization":f"Bearer {os.getenv('LLM_API_KEY','')}"} if os.getenv("LLM_API_KEY") else {})
                    llm_status="ok" if resp.status_code in (200,401,403) else "error"
                    llm_detail=f"HTTP {resp.status_code}"
            except httpx.ConnectError:
                llm_status="error"
                llm_detail=f"无法连接 {url}"
            except Exception as e:
                llm_status="error"
                llm_detail=str(e)[:100]
    except Exception:
        llm_status="error"
        llm_detail="health check 内部异常"
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
