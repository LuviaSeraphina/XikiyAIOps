"""
LLM 适配层

职责: 将安全护栏 + MCP 工具 + LLM 推理 + 前端 SSE 编织为完整对话链路

模块结构:
    build_system_prompt()   — 动态生成 Agent 身份 Prompt (含 22 个 Tool Schema)
    check_user_input()      — 安全前置拦截 (越狱/高危/注入不进 LLM)
    call_ollama()           — 调用本地 Ollama, 流式返回 token + tool_calls
    execute_tool()          — 参数注入检测 + 委托 registry.call()
    _process_tool_call()    — 单次工具调用的 SSE 事件构建 + 执行
    chat_stream()           — 主入口 async generator, 编排完整对话循环

依赖: registry (MCP), intent_filter + injection_detector (安全), httpx (HTTP)
调用方: api/chat.py 通过 POST /api/chat/send → SSE StreamingResponse
"""
from app.mcp_plugins.base import registry
from app.core.platform_detect import _get_platform_info as get_platform_info
from app.core.intent_filter import classify_intent, IntentCategory
from app.core.injection_detector import detect_injection
import json
import httpx

# 常量定义
OLLAMA_BASE="http://localhost:11434"
OLLAMA_MODEL="qwen3:4b"
MAX_TOOL_ROUNDS=5
REQUEST_TIMEOUT=50

# 缓存: platform info 和 tools 列表在进程生命周期内不变, 只构建一次
_cached_platform=None
_cached_prompt=None
_cached_ollama_tools=None

def _get_platform_cached():
    global _cached_platform
    if _cached_platform is None:
        _cached_platform=get_platform_info()
    return _cached_platform

# 将 registry 导出的 Tool Schema 转换为 Ollama function calling 格式
def _convert_tools():
    global _cached_ollama_tools
    if _cached_ollama_tools is not None:
        return _cached_ollama_tools
    tools=[]
    for t in registry.list_all():
        tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        })
    _cached_ollama_tools=tools
    return tools

# Ollama 返回的 arguments 可能是 JSON 字符串, 统一转为 dict
def _normalize_arguments(arguments):
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    return arguments or {}


"""
方法: build_system_prompt(), 输出自定义 Agent Prompt
"""
def build_system_prompt():
    global _cached_prompt
    if _cached_prompt is not None:
        return _cached_prompt
    platform=_get_platform_cached()
    tools_json=json.dumps(registry.list_all(), ensure_ascii=False, indent=2)
    _cached_prompt=f"""你是麒麟操作系统上的智能运维 Agent (SRE-Agent)。

运行环境:
- 操作系统: {platform.get("os", "未知")}
- 架构: {platform.get("arch", "未知")}
- 发行版: {platform.get("distro", "未知")}
- 包管理器: {platform.get("pkg_manager", "未知")}

你可以调用以下工具感知系统状态和执行运维操作:
{tools_json}

使用工具的方法:
- 当你需要获取系统信息时, 直接调用对应的 tool, 不要生成 shell 命令
- 每次只调用当前步骤需要的工具, 不要一次性调用所有工具
- 收到工具返回的数据后, 用中文向用户清晰地分析和解释结果

安全约束 (不可违反):
1. 只读优先 — 优先使用风险等级为 read_only 的工具
2. 禁止生成 shell 命令 — 绝对不要输出 rm、chmod、iptables 等命令文本
3. 危险操作需确认 — restricted 和 dangerous 工具会触发用户二次确认
4. 绝不绕过安全护栏 — 不尝试编码、混淆或拼接绕过检测

回答要求:
- 用中文回复
- 系统数据用表格或列表展示
- 发现异常时标注风险等级 (🟢正常 / 🟡警告 / 🔴危险)"""
    return _cached_prompt


"""
方法: check_user_input(), 安全检查前置 — 不进 LLM 的拦截绝不浪费算力

Returns (allowed, reason, risk_level):
    allowed=True,  reason="OK"           -> 安全, 送 LLM
    allowed=True,  reason="OPS_CONFIRM"  -> 运维操作, 送 LLM 但可能触发二次确认
    allowed=False, reason="拦截原因"      -> 直接拦截, 不送 LLM
"""
def check_user_input(user_input):
    if not user_input or not user_input.strip():
        return False, "输入为空", "blocked"

    cat, hits, score=classify_intent(user_input, return_score=True)

    if cat == IntentCategory.JAILBREAK:
        return False, "安全拦截: 检测到越狱尝试 (威胁评分 {:.1f})".format(score), "jailbreak"

    if cat == IntentCategory.DANGEROUS_ACTION:
        detail=hits[0] if hits else "高危操作"
        return False, "安全拦截: {} (威胁评分 {:.1f})".format(detail, score), "dangerous"

    injection_hits=detect_injection(user_input)
    if injection_hits:
        return False, "安全拦截: 检测到注入攻击 — {}".format(injection_hits[0]), "injection"

    if cat == IntentCategory.OPS_ACTION:
        return True, "OPS_CONFIRM", "restricted"

    return True, "OK", "safe"


"""
方法: call_ollama(), 调用 Ollama 本地模型, 流式返回 token / tool_calls / done 事件

Ollama 原生 API 是逐行 JSON:
    {"message":{"role":"assistant","content":"我来"},"done":false}
    {"message":{"role":"assistant","tool_calls":[...]},"done":false}
    {"message":{},"done":true,"done_reason":"stop"}

yield: {"type":"token","content":"..."} | {"type":"tool_calls","calls":[...]} | {"type":"done","reason":"stop"}
"""
async def call_ollama(messages, tools=None):
    payload={"model": OLLAMA_MODEL, "messages": messages, "stream": True}
    if tools:
        payload["tools"]=tools

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data=json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("done"):
                        yield {"type": "done", "reason": data.get("done_reason", "stop")}
                        break
                    msg=data.get("message", {})
                    if msg.get("content"):
                        yield {"type": "token", "content": msg["content"]}
                    if msg.get("tool_calls"):
                        yield {"type": "tool_calls", "calls": msg["tool_calls"]}
        except httpx.HTTPStatusError:
            yield {"type": "done", "reason": "http_error"}


"""
方法: execute_tool(), 执行单个 MCP Tool — 参数注入检测 + 权限预检 (委托 registry.call)
"""
def execute_tool(tool_name, arguments):
    args_str=json.dumps(arguments, ensure_ascii=False)
    injection_hits=detect_injection(args_str)
    if injection_hits:
        return {
            "tool": tool_name, "risk_level": "blocked", "data": {},
            "summary": {"error": "参数注入拦截: {}".format(injection_hits[0])},
        }
    return registry.call(tool_name, **arguments)


"""
方法: _process_tool_call(), 对单个 Ollama tool call 构建 SSE 事件 + 执行, 返回 (tool_msg, events)
"""
def _process_tool_call(tc):
    fn=tc.get("function", {})
    tool_name=fn.get("name", "")
    arguments=_normalize_arguments(fn.get("arguments", {}))

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

    # tool 角色消息
    tool_msg={"role": "tool", "content": json.dumps(result, ensure_ascii=False)}

    return tool_msg, events


"""
方法: chat_stream(), 主入口 — 安全检测 + LLM 流式对话 + Tool 调用循环

yield 标准 SSE 事件: token / tool_call / tool_result / security_check / error / done
"""
async def chat_stream(user_input, history=None):
    # 1. 安全前置
    allowed, reason, _=check_user_input(user_input)
    if not allowed:
        yield {"event": "error", "data": {"message": reason}}
        return

    # 2. 构建 messages
    messages: list=[{"role": "system", "content": build_system_prompt()}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    tools=_convert_tools()

    # 3. Tool 调用循环
    for _ in range(MAX_TOOL_ROUNDS):
        assistant_content=""
        tool_calls_in_round=[]

        try:
            async for event in call_ollama(messages, tools):
                if event["type"] == "token":
                    assistant_content += event["content"]
                    yield {"event": "token", "data": {"text": event["content"]}}
                elif event["type"] == "tool_calls":
                    tool_calls_in_round=event["calls"]
                elif event["type"] == "done":
                    break
        except httpx.ConnectError:
            yield {"event": "error", "data": {"message": "Ollama 服务未启动, 请运行: ollama serve"}}
            return
        except (httpx.ReadTimeout, httpx.HTTPStatusError):
            yield {"event": "error", "data": {"message": "LLM 请求失败 (超时或服务异常)".format(REQUEST_TIMEOUT)}}
            return

        if not tool_calls_in_round:
            break

        # 追加 assistant 消息
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": tool_calls_in_round,
        })

        # 执行工具, yield SSE 事件, 追加 tool 消息
        for tc in tool_calls_in_round:
            tool_msg, events=_process_tool_call(tc)
            for evt in events:
                yield evt
            messages.append(tool_msg)

    yield {"event": "done", "data": {}}