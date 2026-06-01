"""
OllamaProvider — 本地 Ollama 模型

API 格式: POST /api/chat, 逐行 JSON (非标准 SSE)
    {"message":{"role":"assistant","content":"我来"},"done":false}
    {"message":{"role":"assistant","tool_calls":[...]},"done":false}
    {"message":{},"done":true,"done_reason":"stop"}

tool_calls 格式:
    [{"function": {"name": "cpu_get", "arguments": {"seconds": 1}}}]

用法:
    from app.llm.providers.ollama import OllamaProvider
    provider = OllamaProvider("http://localhost:11434", "qwen3:4b")
    async for event in provider.chat_stream(messages, tools):
        ...
"""
from .base import BaseLLMProvider
from app.llm.utils import normalize_arguments
import json
import httpx


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat_stream(self, messages, tools=None):
        payload = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("done"):
                            yield {
                                "type": "done",
                                "reason": data.get("done_reason", "stop"),
                            }
                            return
                        msg = data.get("message", {})
                        if msg.get("content"):
                            yield {"type": "token", "content": msg["content"]}
                        if msg.get("tool_calls"):
                            # 规范化 arguments (浅拷贝避免原地修改原始响应)
                            for tc in msg["tool_calls"]:
                                fn = tc.get("function", {})
                                tc["function"] = {
                                    **fn,
                                    "arguments": normalize_arguments(
                                        fn.get("arguments", {})
                                    ),
                                }
                            yield {"type": "tool_calls", "calls": msg["tool_calls"]}
            except httpx.ConnectError:
                yield {"type": "done", "reason": "connect_error"}
            except (httpx.ReadTimeout, httpx.HTTPStatusError):
                yield {"type": "done", "reason": "request_failed"}