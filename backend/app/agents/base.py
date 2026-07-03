"""
Agent 基类 — Tool 分区、调用封装、每个 Agent 有自己的 system prompt
"""
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from app.llm.providers import get_llm_provider
from app.mcp_plugins.base import registry
from app.mcp_plugins._common import make_response as _make_response

_logger=logging.getLogger("xikiy_aiops.agents")


@dataclass
class AgentResult:
    agent_name:str
    tool_results:List[Dict]=field(default_factory=list)
    summary:str=""

# ── Tool 分区定义 ──────────────────────────

#感知Agent: 所有只读工具 (系统感知 + 安全审计)
PERCEPTION_TOOLS=[t for t in registry.list_all() if t.get("risk_level")=="read_only"]

#执行Agent: 危险/受限写操作工具
EXECUTION_TOOLS=[t for t in registry.list_all() if t.get("risk_level") in ("dangerous","restricted")]

#安全Agent: 无工具, 纯逻辑层
SECURITY_TOOLS=[]


# ── Agent 基类 ─────────────────────────────

class BaseAgent:
    agent_name:str="base"
    system_prompt:str=""
    allowed_tools:List[Dict]=[]

    def get_tools(self)->List[Dict]:
        return self.allowed_tools

    def build_messages(self, user_content:str, rag_context:str="")->List[Dict]:
    # 构建 LLM messages: system prompt + 用户输入
        system=self.system_prompt
        if rag_context:
            system+=rag_context
        return [
            {"role":"system","content":system},
            {"role":"user","content":user_content},
        ]

    async def chat(self, messages:List[Dict], tools:List[Dict], max_rounds:int=5):
        """Agent 对话循环 — 调 LLM + 执行 Tool (由外部审批)"""
        provider=get_llm_provider()
        tool_results=[]

        for _ in range(max_rounds):
            assistant_content=""
            tool_calls=[]

            async for event in provider.chat_stream(messages, tools):
                if event["type"]=="token":
                    assistant_content+=event["content"]
                elif event["type"]=="tool_calls":
                    tool_calls=event["calls"]
                elif event["type"]=="done":
                    break

            if not tool_calls:
                break

            #追加 assistant 消息
            messages.append({
                "role":"assistant",
                "content":assistant_content,
                "tool_calls":tool_calls,
            })

            #执行工具 (审批由外部 Orchestrator/Security 完成)
            for tc in tool_calls:
                fn=tc.get("function",{})
                tool_name=fn.get("name","")
                args=json.loads(fn.get("arguments","{}"))
                result=registry.call(tool_name, args)
                if result:
                    result["_tool_call_id"]=tc.get("id","")
                tool_results.append({
                    "tool":tool_name,
                    "args":args,
                    "result":result,
                })
                messages.append({
                    "role":"tool",
                    "tool_call_id":tc.get("id",""),
                    "content":json.dumps(result,ensure_ascii=False) if result else "{}",
                })

        return tool_results, assistant_content
