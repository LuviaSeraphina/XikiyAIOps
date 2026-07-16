"""
LangChain Agent — ReAct + PlanAndExecute 双模 Agent

将 82 个 MCP Tool 包装为 LangChain Tool, 提供:
- ReAct Agent: 思考→行动→观察 循环 (简单任务)
- PlanAndExecute Agent: 规划→执行→重规划 (复杂任务)
"""
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.llm.config import get_llm_config, REQUEST_TIMEOUT

_logger=logging.getLogger("xikiy_aiops.langchain")

#══════════════════════════════════════════
# 1. LLM 构建
#══════════════════════════════════════════

def _build_llm():
    """从前端配置创建 ChatOpenAI 实例"""
    config=get_llm_config()
    active=config.get("active_preset","deepseek")
    presets=config.get("presets",{})
    preset=presets.get(active,{})
    return ChatOpenAI(
        model=preset.get("model","deepseek-chat"),
        api_key=preset.get("api_key",""),
        base_url=preset.get("base_url","https://api.deepseek.com"),
        temperature=0,
        timeout=REQUEST_TIMEOUT,
    )

#══════════════════════════════════════════
# 2. MCP Tool → LangChain Tool 包装
#══════════════════════════════════════════

def build_langchain_tools(tool_names: List[str] = None) -> list:
    """将所有 MCP Tool(或指定列表) 包装为 LangChain @tool 函数, 返回 tool 列表"""
    from app.mcp_plugins.base import registry
    tools=[]
    for t in sorted(registry._tools.values(), key=lambda x: x.name):
        if tool_names and t.name not in tool_names:
            continue
        #只暴露只读工具给 ReAct; PlanExecute 在全量 82 上跑
        if t.risk_level.value != "read_only":
            continue
        tools.append(_wrap_one_tool(t))
    _logger.info(f"LangChain tools 就绪: {len(tools)} 个 (只读)")
    return tools

def build_all_langchain_tools() -> list:
    """包装全部 82 个 MCP Tool 为 LangChain Tool"""
    from app.mcp_plugins.base import registry
    tools=[]
    for t in sorted(registry._tools.values(), key=lambda x: x.name):
        tools.append(_wrap_one_tool(t))
    _logger.info(f"LangChain tools 就绪: {len(tools)} 个 (全部)")
    return tools

def _wrap_one_tool(mcp_tool) -> callable:
    """将单个 MCPTool 包装为 LangChain @tool"""
    name=mcp_tool.name
    desc=mcp_tool.description
    schema=mcp_tool.to_schema()["inputSchema"]

    # 构建参数签名
    params=[]
    for pname, pschema in schema.get("properties",{}).items():
        ptype=pschema.get("type","string")
        default=pschema.get("default",None)
        if ptype=="integer":
            params.append(f"{pname}:int={default or 0}")
        elif ptype=="boolean":
            params.append(f"{pname}:bool={default if default is not None else False}")
        else:
            params.append(f'{pname}:str="{default or ""}"')
    param_str=", ".join(params) if params else ""

    # 动态创建工具函数
    def make_handler(tool_name):
        from app.mcp_plugins.base import registry
        def handler(**kwargs):
            result=registry.call(tool_name, **kwargs)
            status=result.get("status","ok")
            if status=="error":
                return json.dumps({"error":result.get("summary",{}).get("error","未知错误")})
            if status=="blocked":
                return json.dumps({"error":result.get("summary",{}).get("error","权限拦截")})
            return json.dumps(result.get("summary",{}),ensure_ascii=False)
        return handler

    handler=make_handler(name)
    handler.__name__=name
    handler.__doc__=desc
    #设置参数注解
    annotations={}
    for pname, pschema in schema.get("properties",{}).items():
        ptype=pschema.get("type","string")
        annotations[pname]=int if ptype=="integer" else (bool if ptype=="boolean" else str)
    handler.__annotations__=annotations

    return lc_tool(handler)

#══════════════════════════════════════════
# 3. ReAct Agent (简单任务)
#══════════════════════════════════════════

async def react_chat(user_input: str) -> AsyncGenerator[Dict[str,Any], None]:
    """ReAct 模式: 适合单个简单问题"""
    llm=_build_llm()
    tools=build_langchain_tools()  #只读工具

    agent=create_react_agent(model=llm, tools=tools)
    
    yield {"event":"phase","data":{"phase":"thinking","message":"正在分析..."}}
    result=agent.invoke({"messages":[("user",user_input)]})
    
    messages=result.get("messages",[])
    answer=""
    for msg in messages:
        if hasattr(msg,"content") and msg.type not in ("human","system"):
            answer+=str(msg.content)
    
    yield {"event":"agent_answer","data":{"content":answer}}

#══════════════════════════════════════════
# 4. PlanAndExecute Agent (复杂任务)
#══════════════════════════════════════════

_PLANNER_PROMPT="""你是麒麟智能运维调度中心的规划器。

根据用户输入, 生成一个执行计划。每步调用一个 MCP 工具。

输出 JSON 格式:
{
  "intent":"用户意图概括",
  "steps":[
    {"id":1,"tool":"disk_inspect","description":"检查磁盘","params":{}},
    {"id":2,"tool":"disk_large_files","description":"找大文件","params":{"min_size_mb":100}}
  ]
}

规则:
- 优先用只读工具感知现状, 再用受限/危险工具操作
- 工具间有依赖时用前一步的输出
- 只输出 JSON, 不要输出其他文本
"""

def _build_planner_prompt():
    """动态构建规划器 Prompt, 注入可用工具列表"""
    from app.mcp_plugins.base import registry
    tools_desc=[]
    for t in sorted(registry._tools.values(), key=lambda x: x.name):
        risk=t.risk_level.value
        emoji={"read_only":"👁","restricted":"🔒","dangerous":"⚠️","critical":"🚫"}.get(risk,"")
        params=", ".join(t.parameters.keys()) if t.parameters else "无参数"
        tools_desc.append(f"{emoji} **{t.name}** [{risk}]: {t.description} (参数: {params})")
    
    tool_list="\n".join(tools_desc)
    return _PLANNER_PROMPT+f"\n\n可用工具列表 ({len(tools_desc)} 个):\n{tool_list}"

_RETRY_PROMPT="""你是麒麟智能运维的故障修复器。

一个 MCP 工具调用失败了, 请分析错误并修正参数后重试。

输入:
- 工具名: {tool_name}
- 原始参数: {original_params}
- 错误信息: {error_msg}

输出修正后的参数 JSON:
{{"fixed_params":{{...}}, "reason":"修正原因简述"}}

如果错误是参数类型/值问题, 修正参数; 如果是工具不可用/权限问题, 将 fixed_params 设为 null。只输出 JSON。"""

_REPLAN_PROMPT="""你是麒麟智能运维调度中心的重新规划器。

以下步骤执行失败, 请重新规划剩余步骤。已知上下文:
- 原始意图: {intent}
- 已成功的步骤: {succeeded_steps}
- 失败步骤: {failed_step} 错误: {error_msg}
- 当前计划剩余步骤: {remaining_steps}

请输出新的剩余步骤 JSON(从失败步骤之后开始, id 从 {next_id} 编号):
{{"steps":[{{"id":{next_id},"tool":"...","description":"...","params":{{}}}}]}}
只输出 JSON。"""

async def plan_execute_chat(user_input: str, session_id: str = "") -> AsyncGenerator[Dict[str,Any], None]:
    """PlanAndExecute 模式: 适合复杂多步任务, 支持 参数重试→Replan→后置验证 闭环"""
    from app.mcp_plugins.base import registry
    import time as _time
    llm=_build_llm()
    
    # ── Trace 结构 ──
    trace={
        "planning":{"llm_output":"","elapsed_ms":0},
        "steps":[],
        "retries":[],
        "replans":[],
        "verification":{"passed":False,"feedback":"","elapsed_ms":0},
        "summarization":{"elapsed_ms":0},
    }
    t_start=_time.time()
    
    # Phase 1: Planning
    yield {"event":"phase","data":{"phase":"planning","message":"正在规划..."}}
    
    t0=_time.time()
    plan_text=llm.invoke([
        ("system",_build_planner_prompt()),
        ("user",user_input),
    ]).content
    trace["planning"]["llm_output"]=plan_text
    trace["planning"]["elapsed_ms"]=int((_time.time()-t0)*1000)
    
    try:
        start=plan_text.find("{")
        end=plan_text.rfind("}")+1
        plan=json.loads(plan_text[start:end])
    except json.JSONDecodeError:
        yield {"event":"error","data":{"message":"规划失败: LLM 输出非 JSON"}}
        return
    
    intent=plan.get("intent","未知")
    steps=plan.get("steps",[])
    
    # ── 动态意图审计 (v2.1) ──
    audit_result=_run_intent_audit(intent, steps, session_id)
    trace["intent_audit"]={
        "passed":audit_result["passed"],
        "risk_score":audit_result["risk_score"],
        "blocked":audit_result["blocked"],
        "alerts":audit_result["alerts"],
        "recommendation":audit_result["recommendation"],
    }
    
    #先发 plan 事件 (含审计), 再判断是否拦截 — 确保 persist 能收到审计信息
    yield {"event":"plan","data":{"intent":intent,"strategy":"LangChain PlanExecute(闭环)","steps":steps,"audit":audit_result}}
    
    if audit_result["blocked"]:
        yield {"event":"phase","data":{"phase":"blocked","message":"意图审计拦截"}}
        yield {"event":"agent_answer","data":{"content":f"🚫 **操作已被安全策略拦截**\n\n{audit_result['recommendation']}\n\n风险评分: {audit_result['risk_score']}/100\n\n> {chr(10).join(a['msg'] for a in audit_result['alerts'])}"}}
        await _persist_trace(
            session_id=session_id, user_input=user_input, intent=intent,
            plan_json=plan, trace_json=trace,
            summary=f"意图审计拦截: {audit_result['recommendation']}",
            total_elapsed_ms=int((_time.time()-t_start)*1000),
        )
        return
    
    if not audit_result["passed"]:
        yield {"event":"phase","data":{"phase":"warning","message":audit_result["recommendation"]}}
        yield {"event":"audit_warning","data":audit_result}
    while step_idx<len(steps):
        step=steps[step_idx]
        tool_name=step.get("tool","")
        params=step.get("params",{})
        tool=registry.get_tool(tool_name)
        
        if not tool:
            _logger.warning(f"工具不存在: {tool_name}, 跳过")
            step_idx+=1
            continue
        
        # ── 执行步骤 (含参数重试) ──
        result,retries_done=_execute_step_with_retry(
            llm=llm,
            registry=registry,
            step=step,
            trace=trace,
            max_retries=max_retries,
        )
        
        # Send SSE events
        for r in retries_done:
            yield r
        
        # 判断是否失败(重试耗尽)
        if result.get("status")=="error":
            error_msg=result.get("summary",{}).get("error","未知错误")
            _logger.info(f"步骤 {step['id']} ({tool_name}) 失败(含重试): {error_msg}")
            
            yield {"event":"step_result","data":{"step_id":step["id"],"tool":tool_name,"status":"FAILED","error":error_msg}}
            
            # 触发 Replan
            if replan_count<max_replans:
                replan_count+=1
                new_steps=_try_replan(llm, trace, intent, steps, step_idx, error_msg, results, replan_count, max_replans)
                if new_steps:
                    steps=steps[:step_idx]+new_steps
                    continue
            
            # Replan 失败或耗尽 → 继续执行剩余步骤
            step_idx+=1
        else:
            yield {"event":"step_result","data":{"step_id":step["id"],"tool":tool_name,"status":"DONE","summary":result.get("summary",{})}}
            results.append(result)
            step_idx+=1
    
    # Phase 3: 后置验证 — 执行反馈闭环核心
    yield {"event":"phase","data":{"phase":"verifying","message":"验证结果..."}}
    
    t_verify=_time.time()
    verification_feedback=_verify_results(llm, intent, results, trace["steps"])
    trace["verification"]["elapsed_ms"]=int((_time.time()-t_verify)*1000)
    trace["verification"]["passed"]=verification_feedback.get("passed",True)
    trace["verification"]["feedback"]=verification_feedback.get("feedback","")
    
    # Phase 4: Summarize — 聚合验证反馈
    yield {"event":"phase","data":{"phase":"summarizing","message":"生成报告..."}}
    
    t_summ=_time.time()
    report=_generate_summary(llm, intent, results, trace["steps"], verification_feedback)
    trace["summarization"]["elapsed_ms"]=int((_time.time()-t_summ)*1000)
    
    total_elapsed=int((_time.time()-t_start)*1000)
    
    # ── 持久化追踪 ──
    await _persist_trace(
        session_id=session_id,
        user_input=user_input,
        intent=intent,
        plan_json=plan,
        trace_json=trace,
        summary=report,
        total_elapsed_ms=total_elapsed,
    )
    
    yield {"event":"agent_answer","data":{"content":report}}


# ══════════════════════════════════════════
# 反馈闭环辅助函数
# ══════════════════════════════════════════

def _execute_step_with_retry(llm, registry, step, trace, max_retries):
    """
    执行步骤, 失败时调用 LLM 分析错误 + 修正参数 + 重试
    返回 (最终结果, sse事件列表)
    """
    import time as _time
    tool_name=step.get("tool","")
    params=step.get("params",{}).copy()
    events=[]
    retries=0
    
    while retries<=max_retries:
        t_step=_time.time()
        result=registry.call(tool_name, **params)
        step_elapsed=int((_time.time()-t_step)*1000)
        
        status=result.get("status","?")
        trace_entry={
            "id":step["id"],
            "tool":tool_name,
            "params":params.copy(),
            "result":result.get("summary",{}),
            "elapsed_ms":step_elapsed,
            "status":status,
            "attempt":retries+1,
        }
        trace["steps"].append(trace_entry)
        
        if status!="error":
            return result, events
        
        # 失败 — 尝试 LLM 修正参数
        error_msg=result.get("summary",{}).get("error","未知错误")
        
        if retries>=max_retries:
            _logger.info(f"步骤 {step['id']} 重试耗尽 (已 {retries+1} 次)")
            return result, events
        
        # LLM 分析错误 + 修正参数
        retries+=1
        _logger.info(f"步骤 {step['id']} ({tool_name}) 失败, 触发 LLM 参数修正 (第{retries}次) — {error_msg}")
        
        events.append({"event":"step_result","data":{
            "step_id":step["id"],"tool":tool_name,
            "status":"RETRYING","error":error_msg,"retry":retries,"max_retries":max_retries}})
        
        t_fix=_time.time()
        fix_prompt=_RETRY_PROMPT.format(
            tool_name=tool_name,
            original_params=json.dumps(params, ensure_ascii=False),
            error_msg=error_msg,
        )
        fix_text=llm.invoke([
            ("system","你是运维故障修复器。只输出 JSON。"),
            ("user",fix_prompt),
        ]).content
        
        trace["retries"].append({
            "step_id":step["id"],
            "attempt":retries,
            "error":error_msg,
            "llm_fix_output":fix_text,
            "elapsed_ms":int((_time.time()-t_fix)*1000),
        })
        
        try:
            s=fix_text.find("{")
            e=fix_text.rfind("}")+1
            fix=json.loads(fix_text[s:e])
            fixed_params=fix.get("fixed_params",None)
            if fixed_params is None:
                _logger.info(f"步骤 {step['id']} LLM 判定不可修复: {fix.get('reason','')}")
                return result, events  # 不可修复, 触发 replan
            params.update(fixed_params)
            _logger.info(f"步骤 {step['id']} 参数已修正: {fix.get('reason','')}, 重试中...")
        except json.JSONDecodeError:
            _logger.warning(f"步骤 {step['id']} LLM 修正输出非 JSON, 无法重试")
            return result, events
    
    return result, events


def _try_replan(llm, trace, intent, steps, failed_step_idx, error_msg, results, replan_count, max_replans):
    """LLM 重新规划剩余步骤, 返回新的剩余步骤列表或空"""
    import time as _time
    failed_step=steps[failed_step_idx]
    succeeded=[{
        "step":s.get("description",""),
        "result":r.get("summary",{}) if isinstance(r,dict) else {},
    } for s,r in zip(steps[:failed_step_idx], results)]
    
    t_rp=_time.time()
    replan_prompt=_REPLAN_PROMPT.format(
        intent=intent,
        succeeded_steps=json.dumps(succeeded, ensure_ascii=False),
        failed_step=f"{failed_step['id']}({failed_step['tool']})",
        error_msg=error_msg,
        remaining_steps=json.dumps(steps[failed_step_idx+1:], ensure_ascii=False),
        next_id=failed_step["id"],
    )
    new_plan_text=llm.invoke([
        ("system","你是运维重新规划器。只输出 JSON。"),
        ("user",replan_prompt),
    ]).content
    
    trace["replans"].append({
        "step_failed":failed_step["id"],
        "error":error_msg,
        "llm_output":new_plan_text,
        "elapsed_ms":int((_time.time()-t_rp)*1000),
        "count":replan_count,
    })
    
    try:
        s=new_plan_text.find("{")
        e=new_plan_text.rfind("}")+1
        new_plan=json.loads(new_plan_text[s:e])
        new_steps=new_plan.get("steps",[])
        _logger.info(f"Replan ({replan_count}/{max_replans}) 生成 {len(new_steps)} 个新步骤")
        return new_steps
    except json.JSONDecodeError:
        _logger.warning(f"Replan 输出非 JSON: {new_plan_text[:200]}")
        return []


def _verify_results(llm, intent, results, trace_steps):
    """
    后置验证: 检查所有结果是否满足原始意图
    返回 {"passed":bool, "feedback":str}
    """
    try:
        summary_data=[s.get("result",s.get("summary",{})) for s in trace_steps]
        verify_prompt=f"""验证以下运维执行是否达到了 "意图: {intent}"。
执行结果: {json.dumps(summary_data, ensure_ascii=False)}

输出 JSON: {{"passed":true/false, "feedback":"一句话验证意见"}}
只输出 JSON。"""
        
        verify_text=llm.invoke([
            ("system","你是运维质量验证器。只输出 JSON。"),
            ("user",verify_prompt),
        ]).content
        s=verify_text.find("{")
        e=verify_text.rfind("}")+1
        return json.loads(verify_text[s:e])
    except Exception:
        return {"passed":True,"feedback":"验证跳过(LLM 输出异常)"}


def _generate_summary(llm, intent, results, trace_steps, verification_feedback):
    """
    生成总结报告, 融入验证反馈
    """
    errors=[s for s in trace_steps if s.get("status")=="error"]
    retries=[s for s in trace_steps if s.get("attempt",1)>1]
    passed=verification_feedback.get("passed",True)
    vfb=verification_feedback.get("feedback","无")
    
    summary_data=[{
        "tool":s.get("tool","?")[:30],
        "status":s.get("status","?"),
        "key":str(s.get("result",""))[:200],
    } for s in trace_steps]
    
    context_parts=[]
    if errors:
        context_parts.append(f"⚠️ {len(errors)} 个步骤失败: {[e['tool'] for e in errors]}")
    if retries:
        context_parts.append(f"🔄 {len(retries)} 处参数修正重试")
    context_parts.append(f"{'✅' if passed else '❌'} 意图验证: {vfb}")
    
    report=llm.invoke([
        ("system","""用中文生成运维报告, Markdown 格式。
包含:
1. 📋 操作概览表
2. 🔍 关键发现
3. 💡 总结建议
4. {"⚠️" if errors or not passed else ""} 风险提示(如有异常)

不要编造工具未返回的信息。"""),
        ("user",f"""意图: {intent}
执行摘要: {'; '.join(context_parts)}
详细结果: {json.dumps(summary_data, ensure_ascii=False)}
"""),
    ]).content
    return report


def _run_intent_audit(intent, steps, session_id=""):
    """
    动态意图审计 — 危险模式匹配 + 工具-意图一致性 + 漂移检测
    返回 audit_result dict
    """
    try:
        from app.core.intent_auditor import audit_intent, audit_steps_safety
        
        #主体审计 (历史意图为空, 仅做模式+一致性检查; 漂移检测后续异步补全)
        result=audit_intent(intent, steps, history_intents=None)
        
        #步骤安全审计
        step_audit=audit_steps_safety(steps)
        if not step_audit["safe"]:
            result["alerts"].extend(step_audit["alerts"])
            result["risk_score"]=max(result["risk_score"], 70)
            if result["risk_score"]>=90:
                result["blocked"]=True
                result["passed"]=False
        
        return result
    except Exception as e:
        _logger.error(f"意图审计异常: {e}")
        return {"passed":True,"blocked":False,"risk_score":0,"alerts":[],"recommendation":"审计跳过(异常)"}


async def _persist_trace(session_id, user_input, intent, plan_json, trace_json, summary, total_elapsed_ms):
    """异步持久化流水线追踪记录"""
    try:
        from app.db import async_session
        from app.models.pipeline_trace import PipelineTrace
        import json as _json
        async with async_session() as db:
            trace=PipelineTrace(
                session_id=session_id,
                user_input=user_input,
                intent=intent,
                plan_json=_json.dumps(plan_json, ensure_ascii=False),
                trace_json=_json.dumps(trace_json, ensure_ascii=False, default=str),
                summary=summary,
                total_elapsed_ms=total_elapsed_ms,
            )
            db.add(trace)
            await db.commit()
            _logger.info(f"流水线追踪已保存: session={session_id}, {len(trace_json.get('steps',[]))} 步, {total_elapsed_ms}ms")
    except Exception as e:
        _logger.error(f"持久化追踪失败: {e}")
