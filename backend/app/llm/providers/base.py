"""
LLM Provider 抽象基类

所有 Provider 必须实现:
    chat_stream()     — 流式对话, 统一 yield {"type":"token"|"tool_calls"|"done", ...}

可选覆盖:
    convert_tools()   — Tool Schema 格式转换, 默认使用 tools.py::convert_tool_schemas
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator
from app.llm.tools import convert_tool_schemas


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类 — 定义统一的流式对话接口"""

    def convert_tools(self, registry_tools: list) -> list:
    # 将 registry.list_all() 返回的 Tool Schema 列表         转换为该 Provider 所需的 function call
        return convert_tool_schemas(registry_tools)

    @abstractmethod
    def chat_stream(
        self, messages: list, tools: list | None = None
    ) -> AsyncIterator[dict]:
    # 流式对话 — 异步生成器, 统一 yield 三种事件:          {"type": "token",      "content": "文本增量"} 
        ...