"""
OpenAICompatProvider — 适配 OpenAI 兼容 API (DeepSeek / 通义千问 / Qwen-DashScope)

API 格式: POST {base_url}/v1/chat/completions
    请求头: Authorization: Bearer {api_key}
    请求体: {"model": "...", "messages": [...], "stream": True, "tools": [...]}

SSE 响应格式 (标准 OpenAI):
    data: {"id":"...","choices":[{"delta":{"content":"你好"},"index":0}],"object":"chat.completion.chunk"}

tool_calls 在 delta 中增量累积:
    data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"...","function":{"name":"cpu_get","arguments":""}}]}}]}
    data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"seconds\""}}]}}]}
    ... (逐 token 返回 arguments JSON 片段)

用法:
    from app.llm.providers.openai_compat import OpenAICompatProvider
    provider = OpenAICompatProvider("https://api.deepseek.com", "deepseek-chat", "sk-xxx")
    async for event in provider.chat_stream(messages, tools):
        ...
"""
from .base import BaseLLMProvider
import json
import httpx


class OpenAICompatProvider(BaseLLMProvider):
    def __init__(
        self, base_url: str, model: str, api_key: str, timeout: int = 120
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    @staticmethod
    def _parse_arguments(arg_str: str):
        """OpenAI 流式返回 arguments 是分片的 JSON 字符串, 解析为 dict"""
        if not arg_str:
            return {}
        try:
            return json.loads(arg_str)
        except json.JSONDecodeError:
            return {}

    def _normalize_messages(self, messages: list) -> list:
        """将内部 dict 格式的 tool_calls 转回 OpenAI API 要求的格式

        OpenAI API 要求:
          - assistant.tool_calls[].function.arguments: JSON 字符串 (非 dict)
          - tool.tool_call_id: 必须匹配对应 tool_call 的 id(一一对应,不重复)
        """
        normalized = []
        used_tool_call_ids: set = set()  # 防止多 tool 并发时重复匹配同一个 id
        for msg in messages:
            msg = dict(msg)
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_calls = []
                for tc in msg["tool_calls"]:
                    tc = dict(tc)
                    fn = tc.get("function", {})
                    tc["function"] = {
                        **fn,
                        "arguments": json.dumps(
                            fn.get("arguments", {}), ensure_ascii=False
                        ),
                    }
                    if "type" not in tc:
                        tc["type"] = "function"
                    tool_calls.append(tc)
                msg["tool_calls"] = tool_calls
            if msg.get("role") == "tool" and "tool_call_id" not in msg:
                # 从前面最近的 assistant tool_calls 中推断 tool_call_id
                # 使用 used_tool_call_ids 确保同一轮多个 tool 消息匹配到不同 id
                for prev in reversed(normalized):
                    if prev.get("role") == "assistant" and prev.get("tool_calls"):
                        for tc in prev["tool_calls"]:
                            tid = tc.get("id", "")
                            if tid and tid not in used_tool_call_ids:
                                msg["tool_call_id"] = tid
                                used_tool_call_ids.add(tid)
                                break
                        if "tool_call_id" in msg:
                            break
            normalized.append(msg)
        return normalized

    async def chat_stream(self, messages, tools=None):
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # 标准化 messages — tool_calls 的 arguments 从 dict 转 JSON 字符串
        normalized_messages = self._normalize_messages(messages)
        payload = {
            "model": self.model,
            "messages": normalized_messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST", url, json=payload, headers=headers
                ) as resp:
                    # HTTP 状态码守卫 — 区分不同错误类型给出精准提示
                    if resp.status_code != 200:
                        try:
                            error_body = await resp.aread()
                            error_data = json.loads(error_body)
                            detail = error_data.get("error", {}).get("message", "")
                        except Exception:
                            detail = ""
                        logger = __import__("logging").getLogger("sre_agent.llm")
                        logger.error(
                            "LLM API HTTP %s: %s", resp.status_code, detail or error_body[:200]
                        )
                        # 按状态码细分 reason, 前端可据此展示不同的用户提示
                        if resp.status_code == 401:
                            reason = "auth_error"
                        elif resp.status_code == 429:
                            reason = "rate_limit"
                        elif resp.status_code >= 500:
                            reason = "server_error"
                        else:
                            reason = "request_failed"
                        yield {"type": "done", "reason": reason}
                        return

                    # 累积 tool_calls (OpenAI 流式分片返回)
                    tool_calls_acc: dict[int, dict] = {}
                    has_tool_calls = False

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = data.get("choices", [])

                        # finish_reason 优先检查 — 即使 choices 为空也不能漏掉
                        finish_reason = None
                        if choices:
                            finish_reason = choices[0].get("finish_reason")

                        if finish_reason == "stop":
                            yield {"type": "done", "reason": "stop"}
                            return

                        if finish_reason == "tool_calls" and has_tool_calls:
                            resolved_calls = []
                            for acc in tool_calls_acc.values():
                                acc["function"]["arguments"] = self._parse_arguments(
                                    acc["function"]["arguments"]
                                )
                                # 保留完整结构 (id + type + function) 便于后续 tool 消息匹配
                                resolved_calls.append({
                                    "id": acc.get("id", ""),
                                    "type": "function",
                                    "function": acc["function"],
                                })
                            yield {"type": "tool_calls", "calls": resolved_calls}
                            tool_calls_acc = {}
                            has_tool_calls = False

                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})

                        # 文本增量
                        if delta.get("content"):
                            yield {"type": "token", "content": delta["content"]}

                        # tool_calls 增量 (分片累积)
                        if delta.get("tool_calls"):
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                if idx not in tool_calls_acc:
                                    tool_calls_acc[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "function": {"name": "", "arguments": ""},
                                    }
                                acc = tool_calls_acc[idx]
                                fn_delta = tc_delta.get("function", {})
                                if fn_delta.get("name"):
                                    acc["function"]["name"] = fn_delta["name"]
                                if fn_delta.get("arguments"):
                                    acc["function"]["arguments"] += fn_delta["arguments"]
                                if tc_delta.get("id"):
                                    acc["id"] = tc_delta["id"]
                            has_tool_calls = True

                    # 流正常结束
                    yield {"type": "done", "reason": "stop"}

            except httpx.ConnectError:
                yield {"type": "done", "reason": "connect_error"}
            except (httpx.ReadTimeout, httpx.HTTPStatusError):
                yield {"type": "done", "reason": "request_failed"}