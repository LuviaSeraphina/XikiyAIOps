"""
确认状态管理 — adapter.py (chat_stream generator) 与 chat.py (confirm 端点) 共享

模块级全局 dict 用于跨协程协调:

PENDING_CONFIRMS — session_id → asyncio.Event
    SSE generator 在等待用户确认时挂起在此 Event 上;
    confirm 端点通过 set() 唤醒对应的 generator。

CONFIRM_RESULTS — session_id → {tool_call_id: bool}
    用户对每个待确认工具的选择结果;
    同一轮可能有多个工具需要确认, decisions 支持逐个放行/拒绝。
"""
import asyncio

# session_id → asyncio.Event（用于唤醒等待中的 SSE generator）
PENDING_CONFIRMS: dict[str, asyncio.Event] = {}
# session_id → {tool_call_id: bool}（用户对每个工具的选择）
CONFIRM_RESULTS: dict[str, dict[str, bool]] = {}
