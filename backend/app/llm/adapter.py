"""
LLM 适配层 — 主编排逻辑

职责: 将安全护栏 + MCP 工具 + LLM Provider + 前端 SSE 编织为完整对话链路

模块结构:
    build_system_prompt()   — 动态生成 Agent 身份 Prompt (Tool Schema 由 Provider 层单独传递, 不重复嵌入)
    check_user_input()      — 安全前置拦截 (越狱/高危/注入不进 LLM)
    execute_tool()          — 参数注入检测 + 委托 registry.call()
    _process_tool_call()    — 单次工具调用的 SSE 事件构建 + 执行
    chat_stream()           — 主入口 async generator, 编排完整对话循环

LLM Provider 切换: 通过 .env 中 LLM_PROVIDER 配置, 支持 ollama / deepseek / qwen / openai
    工厂函数: app.llm.providers.get_llm_provider()

依赖: registry (MCP), intent_filter + injection_detector (安全), providers (LLM)
调用方: api/chat.py 通过 POST /api/chat/send → SSE StreamingResponse
"""
import asyncio
import json
from app.services.confirm_state import PENDING_CONFIRMS, CONFIRM_RESULTS
from app.mcp_plugins.base import registry
from app.core.platform_detect import _get_platform_info as get_platform_info
from app.core.intent_filter import classify_intent, IntentCategory
from app.core.injection_detector import detect_injection
from app.llm.config import MAX_TOOL_ROUNDS
from app.llm.tools import get_tools
from app.llm.providers import get_llm_provider
from app.llm.utils import normalize_arguments
from app.core.rca_analyzer import compute_health_score

# 缓存: platform info 在进程生命周期内不变, 只构建一次
_cached_platform=None
_cached_prompt=None

def _get_platform_cached():
    global _cached_platform
    if _cached_platform is None:
        _cached_platform=get_platform_info()
    return _cached_platform

"""
方法: build_system_prompt(), 输出自定义 Agent Prompt (v2 — 精简版, 不含 Tool Schema)
"""
def build_system_prompt():
    global _cached_prompt
    if _cached_prompt is not None:
        return _cached_prompt
    platform=_get_platform_cached()
    _cached_prompt=f"""你是麒麟操作系统上的智能运维 Agent (XikiyAIOps)。

## 运行环境
- 操作系统: {platform.get("os", "未知")}
- 架构: {platform.get("arch", "未知")}
- 发行版: {platform.get("distro", "未知")}
- 包管理器: {platform.get("pkg_manager", "未知")}

## 工作方式
- **用户问什么, 你就查什么** — 不要自作主张加无关步骤
- 用户问「CPU」→ 调 system_load + process_top_cpu, 不需要先 system_info
- 用户问「系统状态」或「全面检查」→ 才按 感知→指标→排查→报告 的流程来
- 每次只调用当前步骤需要的工具, 不要一次全调
- 用表格汇总数据, 🟢🟡🔴 标注风险等级, 给出明确结论

## 安全约束 (不可违反)
1. 绝大多数工具是只读的, 可放心调用
2. 仅 process_kill 为危险操作 — 终止进程前系统会请你确认
3. 仅 health_config_set 为受限操作 — 修改配置前系统会请你确认
4. 绝对不要生成任何 shell 命令文本 (rm/chmod/iptables 等)
5. 绝不尝试编码、混淆或拼接绕过安全护栏
6. 如果某工具返回 {{"skipped": true}}, 表示用户取消了该操作, 正常继续后续分析即可, 不要重复请求

## 回答格式要求
- 用中文回复, 系统数据优先使用表格展示
- 风险等级标注: 🟢正常 / 🟡警告 / 🔴危险
- 系统会自动注入健康评分数值 (0-100), 请在报告中引用

## 格式示例
✅ 好的回答:
| 指标 | 数值 | 状态 |
|------|------|------|
| CPU 使用率 | 23% | 🟢 正常 |
| 内存使用率 | 85% | 🟡 偏高 |
> 健康评分 72/100 (C), 建议关注内存使用

❌ 差的回答:
系统 CPU 23% 内存 85% 看起来还行没什么大问题"""
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

def _safe_div(a, b):
    """安全除法, 除数为 0 时返回 0"""
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
方法: chat_stream(), 主入口 — 安全检测 + LLM 流式对话 + Tool 调用循环 + RCA 分析
"""
async def chat_stream(user_input, history=None, session_id=""):
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

    # 3. 获取 Provider 和标准化 Tool Schema
    provider=get_llm_provider()
    tools=get_tools()

    # 4. Tool 调用循环
    for _ in range(MAX_TOOL_ROUNDS):
        assistant_content=""
        tool_calls_in_round=[]

        async for event in provider.chat_stream(messages, tools):
            if event["type"] == "token":
                assistant_content += event["content"]
                yield {"event": "token", "data": {"text": event["content"]}}
            elif event["type"] == "tool_calls":
                tool_calls_in_round=event["calls"]
            elif event["type"] == "done":
                reason=event.get("reason", "stop")
                if reason == "connect_error":
                    yield {"event": "error", "data": {
                        "message": "LLM 服务连接失败 — 请检查 LLM Provider 是否运行"}}
                    return
                if reason == "auth_error":
                    yield {"event": "error", "data": {
                        "message": "API 认证失败 — 请检查 LLM_API_KEY 是否正确"}}
                    return
                if reason == "rate_limit":
                    yield {"event": "error", "data": {
                        "message": "API 调用频率超限 — 请稍后重试"}}
                    return
                if reason == "server_error":
                    yield {"event": "error", "data": {
                        "message": "LLM 服务端异常 — 请稍后重试或联系服务商"}}
                    return
                if reason == "request_failed":
                    yield {"event": "error", "data": {
                        "message": "LLM 请求失败 — 超时或服务异常, 请稍后重试"}}
                    return
                break

        if not tool_calls_in_round:
            break

        # 追加 assistant 消息
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": tool_calls_in_round,
        })

        # Pass A: 收集待确认工具 (restricted/dangerous) vs 安全工具 (read_only)
        pending_tool_calls=[]
        safe_tool_calls=[]

        for tc in tool_calls_in_round:
            fn=tc.get("function", {})
            tool_name=fn.get("name", "")
            arguments=normalize_arguments(fn.get("arguments", {}))
            tool_obj=registry.get_tool(tool_name)
            if tool_obj is None:
                # 工具不存在 — 立即返回 error, 不走确认流程
                tool_msg, events=_process_tool_call(tc)
                for evt in events:
                    yield evt
                messages.append(tool_msg)
                continue
            risk_level=tool_obj.risk_level.value
            if risk_level in ("restricted", "dangerous"):
                # 提前 yield tool_call + security_check, 但不执行
                yield {"event": "tool_call", "data": {
                    "tool_name": tool_name, "arguments": arguments, "risk_level": risk_level,
                }}
                yield {"event": "security_check", "data": {
                    "tool_name": tool_name,
                    "summary": "即将执行: {}".format(tool_name),
                    "details": json.dumps(arguments, ensure_ascii=False),
                    "risk_level": risk_level,
                    "tool_call_id": tc.get("id", ""),
                }}
                pending_tool_calls.append(tc)
            else:
                safe_tool_calls.append(tc)

        # 等待用户确认 (如有待确认工具)
        confirmed_decisions={}
        if pending_tool_calls and session_id:
            yield {"event": "awaiting_confirmation", "data": {
                "session_id": session_id,
                "tool_names": [tc["function"]["name"] for tc in pending_tool_calls],
            }}
            confirm_event=asyncio.Event()
            PENDING_CONFIRMS[session_id]=confirm_event
            try:
                await asyncio.wait_for(confirm_event.wait(), timeout=300)
            except asyncio.TimeoutError:
                # 超时 — 全部标记为未确认, 走 skipped 路径
                for tc in pending_tool_calls:
                    skipped={"tool": tc["function"]["name"], "skipped": True, "reason": "确认超时"}
                    tool_msg={"role": "tool", "content": json.dumps(skipped, ensure_ascii=False)}
                    if tc.get("id"):
                        tool_msg["tool_call_id"]=tc["id"]
                    messages.append(tool_msg)
                    yield {"event": "tool_skipped", "data": {
                        "tool_name": tc["function"]["name"], "reason": "确认超时",
                    }}
                yield {"event": "error", "data": {"message": "操作确认超时"}}
                return
            finally:
                confirmed_decisions=CONFIRM_RESULTS.pop(session_id, {})
                PENDING_CONFIRMS.pop(session_id, None)
        elif pending_tool_calls and not session_id:
            # 无 session_id 无法等待 — 跳过所有待确认工具
            for tc in pending_tool_calls:
                skipped={"tool": tc["function"]["name"], "skipped": True, "reason": "无 session_id"}
                tool_msg={"role": "tool", "content": json.dumps(skipped, ensure_ascii=False)}
                if tc.get("id"):
                    tool_msg["tool_call_id"]=tc["id"]
                messages.append(tool_msg)
                yield {"event": "tool_skipped", "data": {
                    "tool_name": tc["function"]["name"], "reason": "无 session_id",
                }}

        # Pass B: 执行已确认的工具 + 安全工具, 收集结果用于 RCA
        round_results=[]
        # 安全工具: 走完整 _process_tool_call
        for tc in safe_tool_calls:
            tool_msg, events=_process_tool_call(tc)
            for evt in events:
                yield evt
                if evt["event"]=="tool_result":
                    round_results.append(evt.get("data", {}).get("result", {}))
            messages.append(tool_msg)

        # 已确认的 pending 工具: Pass A 已发前缀事件, 这里走 _process_tool_call(skip_prefix=True) 只执行 + tool_result
        for tc in pending_tool_calls:
            tc_id=tc.get("id", "")
            tool_name=tc["function"]["name"]
            if not confirmed_decisions.get(tc_id, False):
                skipped={"tool": tool_name, "skipped": True, "reason": "用户未确认"}
                tool_msg={"role": "tool", "content": json.dumps(skipped, ensure_ascii=False)}
                if tc_id:
                    tool_msg["tool_call_id"]=tc_id
                messages.append(tool_msg)
                yield {"event": "tool_skipped", "data": {"tool_name": tool_name, "reason": "用户未确认"}}
                continue
            tool_msg, events=_process_tool_call(tc, skip_prefix=True)
            for evt in events:
                yield evt
                if evt["event"]=="tool_result":
                    round_results.append(evt.get("data", {}).get("result", {}))
            messages.append(tool_msg)

        #RCA 分析: 采集到系统指标后计算健康评分
        if round_results:
            metrics=_extract_metrics(round_results)
            if any(metrics.values()):  #至少有一个有效指标
                health=compute_health_score(metrics)
                scores=health.get("dimension_scores", {})
                rca_msg=f"""[系统健康评分] {health['score']}/100 ({health['grade']})
维度得分: CPU={scores.get('cpu',0)} 内存={scores.get('memory',0)} 磁盘={scores.get('disk',0)} 负载={scores.get('load',0)} Swap={scores.get('swap',0)}"""
                if health.get("alerts"):
                    rca_msg+="\n⚠️ 告警: " + "; ".join(health["alerts"])
                #注入 LLM 上下文 (role=system 不会显示给用户)
                messages.append({"role": "system", "content": rca_msg})
                #推送给前端展示
                yield {"event": "rca_analysis", "data": {
                    "score": health["score"],
                    "grade": health["grade"],
                    "alerts": health.get("alerts", []),
                }}

    yield {"event": "done", "data": {}}