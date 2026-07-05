"""
Orchestrator — 调度中心: 意图分析 → 拆解 → 路由 → 聚合 → 总结

不调 MCP Tool, 纯编排逻辑
"""
import json
import logging
from typing import List, Dict, AsyncGenerator
from .base import BaseAgent
from .security import SecurityAgent
from .perception import PerceptionAgent
from .execution import ExecutionAgent
from .prompts import ORCHESTRATOR_PROMPT
from app.llm.providers import get_llm_provider

_logger=logging.getLogger("xikiy_aiops.orchestrator")

#意图 → Agent 映射
INTENT_ROUTING={
    "SAFE_QUERY":       ["perception"],                    #CPU/内存/磁盘 → 感知
    "OPS_ACTION":       ["perception","execution"],        #重启/杀进程 → 感知+执行
    "JAILBREAK":        [],                                #越狱 → 被Security拦截
    "UNKNOWN":          ["perception"],                    #兜底 → 感知
}


class Orchestrator:
    """主调度器"""

    def __init__(self):
        self.security=SecurityAgent()
        self.perception=PerceptionAgent()
        self.execution=ExecutionAgent()

    # ── 意图分析 ──────────────────────────

    def classify(self, user_input:str)->str:
    # 分析用户意图 → 意图类别
        from app.core.intent_filter import classify_intent, IntentCategory
        cat, hits, _=classify_intent(user_input, return_score=True)
        #直接返回枚举值的字符串
        intent=cat.value if isinstance(cat, IntentCategory) else str(cat)
        _logger.info(f"意图分析: '{user_input[:30]}...' → {intent} (hits={hits[:2] if hits else '无'})")
        return intent

    # ── 主编排入口 ────────────────────────

    async def run(self, user_input:str, history:List[Dict]=None, session_id:str="")->AsyncGenerator:
        """
        完整编排流程:
          1. Security 审查输入
          2. 意图分析 + 路由
          3. 依次调 Agent → 安全审批 → 执行
          4. 聚合结果 → LLM 总结 → SSE 流式输出
        """
        #1. 安全审查
        allowed, reason, risk_level=self.security.review_input(user_input)
        if not allowed:
            yield {"event":"error","data":{"message":reason}}
            return

        #2. 意图分析 + 路由
        intent=self.classify(user_input)
        agent_names=INTENT_ROUTING.get(intent, ["perception"])
        _logger.info(f"路由: {intent} → {agent_names}")

        #3. 获取 LLM Provider (用于最终总结)
        provider=get_llm_provider()

        #4. 按序调用 Agent
        all_tool_results=[]
        confirm_needed=False

        #使用标准化的 Tool Schema (OpenAI 格式: type=function)
        from app.llm.tools import get_tools as _get_all_tools
        all_tools=_get_all_tools()

        for agent_name in agent_names:
            agent=self.perception if agent_name=="perception" else self.execution
            #过滤出该Agent允许的工具 (标准化 Schema: {type:function, function:{name:...}})
            allowed_names={t["name"] for t in agent.get_tools()}
            agent_tools=[t for t in all_tools if t.get("function",{}).get("name") in allowed_names]
            if not agent_tools:
                _logger.warning(f"{agent_name}: 无可用工具 (allowed={len(allowed_names)}, standard={len(all_tools)})")
                continue

            #构建 messages
            rag_ctx=""
            try:
                from app.rag.inject import inject_context
                rag_ctx=inject_context(user_input)
            except Exception:
                pass

            messages=agent.build_messages(user_input, rag_ctx)

            #Agent 对话循环 (带审批)
            for round_idx in range(3):
                assistant_content=""
                tool_calls=[]

                async for event in provider.chat_stream(messages, agent_tools):
                    if event["type"]=="token":
                        assistant_content+=event["content"]
                    elif event["type"]=="tool_calls":
                        tool_calls=event["calls"]
                    elif event["type"]=="done":
                        break

                if not tool_calls:
                    #Agent 无更多工具调用 → 结束, 不输出中间思考
                    break

                #追加 assistant 消息
                messages.append({
                    "role":"assistant",
                    "content":assistant_content,
                    "tool_calls":tool_calls,
                })

                #审批 + 执行
                for tc in tool_calls:
                    fn=tc.get("function",{})
                    tool_name=fn.get("name","")
                    raw_args=fn.get("arguments","{}")
                    args=json.loads(raw_args) if isinstance(raw_args,str) else raw_args

                    #获取工具风险等级
                    #获取工具风险等级 (从原始 Schema)
                    tool_info=next((t for t in agent.get_tools() if t.get("name")==tool_name), None)
                    risk=tool_info.get("risk_level","read_only") if tool_info else "read_only"

                    #安全审批
                    approved, reason=self.security.approve_tool(tool_name, args, risk)
                    if not approved:
                        yield {"event":"error","data":{"message":f"安全拦截: {tool_name} — {reason}"}}
                        continue

                    if reason=="NEED_CONFIRM":
                        yield {"event":"confirm","data":{"tool":tool_name,"args":args,"risk":risk}}
                        #等待用户确认 (由前端通过 SSE confirm 事件传回)
                        confirm_needed=True

                    #显示工具调用
                    yield {"event":"tool_start","data":{"agent":agent_name,"tool":tool_name}}

                    #执行工具 — _raw=True 获取原始数据供 Agent 感知分析
                    from app.mcp_plugins.base import registry
                    from app.mcp_plugins._common import sanitize_response
                    raw_result=registry.call(tool_name, _raw=True, **args)
                    if raw_result:
                        raw_result["_tool_call_id"]=tc.get("id","")

                    #审计 (用原始数据)
                    self.security.audit(session_id, tool_name, args, raw_result)

                    all_tool_results.append({
                        "agent":agent_name,
                        "tool":tool_name,
                        "args":args,
                        "result":raw_result,
                    })

                    #前端展示: 脱敏后返回
                    safe_result=sanitize_response(tool_name, dict(raw_result)) if raw_result else raw_result
                    yield {"event":"tool_result","data":{"agent":agent_name,"tool":tool_name,"result":safe_result}}

                    #追加 tool 消息 — 原始数据给 LLM, Agent 需要完整信息做判断
                    messages.append({
                        "role":"tool",
                        "tool_call_id":tc.get("id",""),
                        "content":json.dumps(raw_result,ensure_ascii=False) if raw_result else "{}",
                    })

        #5. 聚合 + LLM 总结
        if all_tool_results:
            summary_prompt=self._build_summary_prompt(user_input, all_tool_results)
            messages=[
                {"role":"system","content":ORCHESTRATOR_PROMPT},
                {"role":"user","content":summary_prompt},
            ]
            async for event in provider.chat_stream(messages, []):
                if event["type"]=="token":
                    yield {"event":"token","data":{"text":event["content"]}}
                elif event["type"]=="done":
                    break
        elif not confirm_needed:
            yield {"event":"token","data":{"text":"未找到可用的工具或数据来回答您的问题。"}}

    # ── 构造 LLM 总结 prompt ──────────────

    def _build_summary_prompt(self, user_query:str, tool_results:List[Dict])->str:
    # 将各Agent返回的数据聚合为一个总结 prompt
        lines=[f"用户查询: {user_query}\n"]
        lines.append("各 Agent 采集的数据如下:\n")

        for tr in tool_results:
            result=tr.get("result",{})
            data=result.get("data",{})
            summary=result.get("summary",{})
            lines.append(f"--- {tr['agent']}/{tr['tool']} ---")
            if summary:
                lines.append(json.dumps(summary,ensure_ascii=False))
            elif data:
                #截断过长数据
                data_str=json.dumps(data,ensure_ascii=False)
                if len(data_str)>2000:
                    data_str=data_str[:2000]+"..."
                lines.append(data_str)
            lines.append("")

        lines.append("请根据以上数据, 用中文生成一份简洁的系统状态报告。用表格展示关键指标, 🟢🟡🔴 标注风险等级。")
        return "\n".join(lines)
