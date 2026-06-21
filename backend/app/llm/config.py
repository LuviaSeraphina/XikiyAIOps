import os
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger("sre_agent.llm")

# 显式指定 .env 路径，避免依赖 CWD
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

LLM_PROVIDER=os.getenv("LLM_PROVIDER", "deepseek")
LLM_BASE_URL=os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL=os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_API_KEY=os.getenv("LLM_API_KEY", "")
REQUEST_TIMEOUT=int(os.getenv("REQUEST_TIMEOUT","120"))
MAX_TOOL_ROUNDS=5

if LLM_PROVIDER != "ollama" and not LLM_API_KEY:
    logger.warning(
        "LLM_PROVIDER=%s 但 LLM_API_KEY 为空 — API 调用将返回 401, 请在 .env 中配置 LLM_API_KEY",
        LLM_PROVIDER,
    )