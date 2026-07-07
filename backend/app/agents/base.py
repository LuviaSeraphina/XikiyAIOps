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

#按风险等级分组 (v4.0 三阶段流水线)
READ_ONLY_TOOLS = [t for t in registry.list_all() if t.get("risk_level") == "read_only"]
RESTRICTED_TOOLS = [t for t in registry.list_all() if t.get("risk_level") == "restricted"]
DANGEROUS_TOOLS = [t for t in registry.list_all() if t.get("risk_level") == "dangerous"]

#写操作工具 (restricted + dangerous)
WRITE_TOOLS = RESTRICTED_TOOLS + DANGEROUS_TOOLS

#向后兼容 (deprecated, 将在 v4.0 重构后移除)
PERCEPTION_TOOLS = READ_ONLY_TOOLS
EXECUTION_TOOLS = WRITE_TOOLS
SECURITY_TOOLS = []


def get_tools_by_risk(max_risk: str = "restricted") -> List[Dict]:
    """根据最大风险等级返回工具子集
    
    Args:
        max_risk: 最大允许的风险等级
            - "read_only": 只返回只读工具
            - "restricted": 返回只读 + 受限工具
            - "dangerous": 返回所有工具 (只读 + 受限 + 危险)
    
    Returns:
        工具列表
    """
    risk_order = {"read_only": 0, "restricted": 1, "dangerous": 2}
    max_level = risk_order.get(max_risk, 2)
    
    tools = READ_ONLY_TOOLS[:]
    if max_level >= 1:
        tools.extend(RESTRICTED_TOOLS)
    if max_level >= 2:
        tools.extend(DANGEROUS_TOOLS)
    
    return tools


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
