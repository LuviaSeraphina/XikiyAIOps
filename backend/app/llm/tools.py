"""
MCP Tool Schema 转换工具

将 registry.list_all() 返回的原始 Tool Schema
统一转换为 LLM function calling 格式 (OpenAI / Ollama 通用)

格式:
    输入 (registry): [{"name": "...", "description": "...", "inputSchema": {...}}, ...]
    输出 (标准化):   [{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}, ...]
"""
from app.mcp_plugins.base import registry

# 缓存
_cached_tools = None


def convert_tool_schemas(registry_tools: list) -> list:
    """纯函数 — 将 registry Tool Schema 列表转换为 function calling 格式。

    单一事实来源: tools.py::convert_tool_schemas
    调用方: get_tools() (缓存版本) / BaseLLMProvider.convert_tools() (子类可覆盖)
    """
    tools = []
    for t in registry_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        })
    return tools


def get_tools() -> list:
    """获取标准化 Tool Schema 列表 (带缓存, 进程生命周期内不变)"""
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools
    _cached_tools = convert_tool_schemas(registry.list_all())
    return _cached_tools