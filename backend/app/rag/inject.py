"""
RAG 对话自动注入 — 每次对话检索相关知识并注入 system prompt
"""
import os
import logging
from typing import List

_logger=logging.getLogger("xikiy_aiops.rag")

_ENABLED=os.getenv("RAG_AUTO_INJECT","1")=="1"
_TOP_K=int(os.getenv("RAG_AUTO_INJECT_TOP_K","5"))
_initialized=False


"""
方法: ensure_updated(), 首次对话时做一次增量更新 (无变更 <0.1s), 后续跳过

"""

def ensure_updated():
    global _initialized
    _initialized=True
    try:
        from .ingestion import build_knowledge_base
        build_knowledge_base(force=False)
    except Exception:
        pass  #RAG 未初始化或不可用, 静默跳过


"""
方法: inject_context(user_input), 根据用户输入自动检索 RAG 知识库, 返回注入到 system prompt 的上下文字符串

"""

def inject_context(user_input:str)->str:
    if not _ENABLED: return ""
    try:
        from .retrieval import search
        docs=search(user_input.strip(), top_k=_TOP_K)
        if not docs: return ""
        lines=["\n\n## 相关知识库 (自动检索)"]
        for d in docs:
            src=d.metadata.get("source","?")
            lines.append(f"- [{src}] {d.content[:200]}")
        return "\n".join(lines)
    except Exception:
        return ""  #RAG 不可用时静默降级, 不影响对话


def is_enabled()->bool:
    return _ENABLED
