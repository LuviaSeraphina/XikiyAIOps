"""
LLM 适配层 — 主编排逻辑

职责: 将安全护栏 + MCP 工具 + LLM Provider + 前端 SSE 编织为完整对话链路

模块结构:
    build_system_prompt()   — 动态生成 Agent 身份 Prompt (Tool Schema 由 Provider 层单独传递, 不重复嵌入)
    check_user_input()      — 安全前置拦截 (越狱签名不进 LLM, 语义审查在 SecurityAgent)
    execute_tool()          — 委托 registry.call()
    _process_tool_call()    — 单次工具调用的 SSE 事件构建 + 执行
    chat_stream()           — 主入口 async generator, 编排完整对话循环

LLM Provider 切换: 通过 .env 中 LLM_PROVIDER 配置, 支持 ollama / deepseek / qwen / openai
    工厂函数: app.llm.providers.get_llm_provider()

依赖: registry (MCP), intent_filter (安全签名), providers (LLM)
调用方: api/chat.py 通过 POST /api/chat/send → SSE StreamingResponse
"""
import asyncio
import json
import os
from app.mcp_plugins.base import registry
from app.core.platform_detect import _get_platform_info as get_platform_info
from app.core.intent_filter import check_jailbreak
from app.llm.config import MAX_TOOL_ROUNDS
from app.llm.tools import get_tools
from app.llm.providers import get_llm_provider
from app.llm.utils import normalize_arguments
from app.core.rca_analyzer import compute_health_score

# 缓存: platform info 在进程生命周期内不变, 只构建一次
_cached_platform=None

def _get_platform_cached():
    global _cached_platform
    if _cached_platform is None:
        _cached_platform=get_platform_info()
    return _cached_platform

"""
方法: check_user_input(), 安全检查前置 — 仅拦截已知越狱签名

v4.0: 意图分类交给 LLM, 这里只做快速签名拦截
语义审查在 SecurityAgent._llm_review_input() 中完成

Returns (allowed, reason, risk_level):
    allowed=True,  reason="OK"  -> 签名层通过, 送 LLM (LLM 会做语义审查)
    allowed=False, reason="..."  -> 已知越狱签名, 直接拦截
"""
def check_user_input(user_input):
    if not user_input or not user_input.strip():
        return False, "输入为空", "blocked"

    #快速签名拦截 (0.1ms)
    is_jailbreak, hits=check_jailbreak(user_input)
    if is_jailbreak:
        return False, "安全拦截: 检测到越狱签名 — {}".format(hits[0]), "jailbreak"

    return True, "OK", "safe"

"""
方法: execute_tool(), 执行单个 MCP Tool — 委托 registry.call()

v4.0: 参数注入检测已移除, LLM 语义审查层会捕获异常参数
      Tool 自身的 inputSchema 校验 + handler 安全检查 + sudoers 白名单兜底
"""
def execute_tool(tool_name, arguments):
    return registry.call(tool_name, **arguments)

"""
方法: _process_tool_call(), 对单个 LLM tool call 构建 SSE 事件 + 执行, 返回 (tool_msg, events)
"""
def _process_tool_call(tc, skip_prefix=False):
    fn=tc.get("function", {})
    tool_name=fn.get("name", "")
    arguments=normalize_arguments(fn.get("arguments", {}))

    tool_obj=registry.get_tool(tool_name)
    if tool_obj is None:
        # 工具不存在 -> 返回 error 事件, LLM 能感知并调整
        error_result={"tool": tool_name, "risk_level": "error", "data": {}, "summary": {"error": "Tool not found: {}".format(tool_name)}}
        return {"role": "tool", "content": json.dumps(error_result, ensure_ascii=False)}, [{
            "event": "tool_result",
            "data": {"tool_name": tool_name, "result": error_result, "status": "error"},
        }]
    risk_level=tool_obj.risk_level.value

    events=[]

    if not skip_prefix:
        # SSE: tool_call
        events.append({"event": "tool_call", "data": {
            "tool_name": tool_name, "arguments": arguments, "risk_level": risk_level,
        }})

        # SSE: security_check (如需要)
        if risk_level in ("restricted", "dangerous"):
            events.append({"event": "security_check", "data": {
                "tool_name": tool_name,
                "summary": "即将执行: {}".format(tool_name),
                "details": json.dumps(arguments, ensure_ascii=False),
                "risk_level": risk_level,
            }})

    # 执行工具
    result=execute_tool(tool_name, arguments)

    # SSE: tool_result
    status="error" if result.get("risk_level") in ("error", "blocked") else "done"
    events.append({"event": "tool_result", "data": {
        "tool_name": tool_name, "result": result, "status": status,
    }})

    # tool 角色消息 (保留 tool_call_id 供 OpenAI 兼容 API 使用)
    tool_msg={"role": "tool", "content": json.dumps(result, ensure_ascii=False)}
    if tc.get("id"):
        tool_msg["tool_call_id"]=tc["id"]

    return tool_msg, events

"""
方法: _safe_div(a, b), 安全除法, 除数为 0 时返回 0

"""

def _safe_div(a, b):
    return a / b if b else 0
_METRIC_EXTRACTORS={
    "system_load": lambda data: {"load_ratio": _safe_div(data.get("load_1min", 0), max(data.get("cpu_cores", 1), 1))},
    "memory_info": lambda data: {"memory_percent": data.get("usage_percent", 0)},
    "disk_inspect_handler": lambda data: {"disk_percent": data.get("usage_percent", 0)},
    "swap_info": lambda data: {"swap_percent": data.get("swap_percent", 0)},
}

def _extract_metrics(tool_results):
    metrics={}
    for result in tool_results:
        name=result.get("tool", "")
        data=result.get("data", {})
        extractor=_METRIC_EXTRACTORS.get(name)
        if extractor:
            metrics.update(extractor(data))
    # cpu_percent 从 load_ratio 近似
    if "cpu_percent" not in metrics:
        metrics["cpu_percent"]=metrics.get("load_ratio", 0) * 100
    return metrics


"""
方法: chat_stream(), 主入口 — 三阶段流水线 (v4.0)
"""
async def chat_stream(user_input, history=None, session_id=""):
    from app.agents import Orchestrator
    orch=Orchestrator()
    async for event in orch.run(user_input, history, session_id):
        yield event