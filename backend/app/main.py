# FastAPI 应用入口

import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    #启动时: 初始化数据库表
    await init_db()
    yield
    #关闭时: 清理资源 (如有需要)

app=FastAPI(title="XikiyAIOps", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#── Prometheus 指标 ─────────────────────────
_APP_START_TIME=time.time()

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
    return {"status":"ok","service":"xikiy-aiops","llm":llm_status,"llm_detail":llm_detail}


@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点 — 被 Prometheus server 定期抓取"""
    from app.mcp_plugins.base import registry
    import psutil
    uptime_seconds=int(time.time() - _APP_START_TIME)
    tool_count=registry.count
    cpu_percent=psutil.cpu_percent(interval=0.1)
    mem=psutil.virtual_memory()
    disk=psutil.disk_usage("/")
    #手动拼 Prometheus 文本格式, 避免引入额外依赖
    lines=[
        "# HELP xikiy_aiops_uptime_seconds 服务运行时长",
        "# TYPE xikiy_aiops_uptime_seconds gauge",
        f"xikiy_aiops_uptime_seconds {uptime_seconds}",
        "",
        "# HELP xikiy_aiops_tool_count MCP 工具注册总数",
        "# TYPE xikiy_aiops_tool_count gauge",
        f"xikiy_aiops_tool_count {tool_count}",
        "",
        "# HELP xikiy_aiops_cpu_percent 进程 CPU 使用率",
        "# TYPE xikiy_aiops_cpu_percent gauge",
        f"xikiy_aiops_cpu_percent {cpu_percent}",
        "",
        "# HELP xikiy_aiops_memory_usage_bytes 进程内存使用量",
        "# TYPE xikiy_aiops_memory_usage_bytes gauge",
        f"xikiy_aiops_memory_usage_bytes {mem.used}",
        "",
        "# HELP xikiy_aiops_disk_usage_bytes 根分区磁盘使用量",
        "# TYPE xikiy_aiops_disk_usage_bytes gauge",
        f"xikiy_aiops_disk_usage_bytes {disk.used}",
    ]
    return Response(content="\n".join(lines), media_type="text/plain")


#路由注册 (必须在静态文件挂载之前, 否则 /api 路由被静态文件拦截)
from app.api import chat
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

from app.api.audit import router as audit_router
app.include_router(audit_router, prefix="/api/audit", tags=["audit"])

from app.api.alerts import router as alerts_router
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])

#挂载前端静态文件 (dist/ 存在时)
_FRONTEND_DIST=os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST) and os.path.isfile(os.path.join(_FRONTEND_DIST, "index.html")):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
