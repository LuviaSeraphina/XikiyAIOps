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

async def plan_execute_chat(user_input: str) -> AsyncGenerator[Dict[str,Any], None]:
    """PlanAndExecute 模式: 适合复杂多步任务, 支持 Replan"""
    from app.mcp_plugins.base import registry
    llm=_build_llm()
    
    # Phase 1: Planning
    yield {"event":"phase","data":{"phase":"planning","message":"正在规划..."}}
    
    plan_text=llm.invoke([
        ("system",_PLANNER_PROMPT),
        ("user",user_input),
    ]).content
    
    try:
        #提取 JSON
        start=plan_text.find("{")
        end=plan_text.rfind("}")+1
        plan=json.loads(plan_text[start:end])
    except json.JSONDecodeError:
        yield {"event":"error","data":{"message":"规划失败: LLM 输出非 JSON"}}
        return
    
    intent=plan.get("intent","未知")
    steps=plan.get("steps",[])
    
    yield {"event":"plan","data":{"intent":intent,"strategy":"LangChain PlanExecute","steps":steps}}
    
    # Phase 2: Execution with Replan
    yield {"event":"phase","data":{"phase":"executing","message":"执行中..."}}
    
    results=[]
    step_idx=0
    max_replans=2
    replan_count=0
    
    while step_idx<len(steps):
        step=steps[step_idx]
        tool_name=step.get("tool","")
        tool=registry.get_tool(tool_name)
        
        if not tool:
            step_idx+=1
            continue
        
        yield {"event":"step_start","data":{"step_id":step["id"],"tool":tool_name,"description":step.get("description","")}}
        
        params=step.get("params",{})
        result=registry.call(tool_name, **params)
        
        # 执行失败 → Replan
        if result.get("status")=="error" and replan_count<max_replans:
            replan_count+=1
            error_msg=result.get("summary",{}).get("error","未知错误")
            _logger.info(f"步骤 {step['id']} 失败: {error_msg}, 触发 Replan ({replan_count}/{max_replans})")
            
            yield {"event":"step_result","data":{"step_id":step["id"],"tool":tool_name,"status":"FAILED","error":error_msg}}
            
            #生成新计划
            replan_prompt=f"步骤 {step['id']} ({tool_name}) 失败: {error_msg}。请重新规划剩余步骤。只输出 JSON。"
            new_plan_text=llm.invoke([
                ("system",_PLANNER_PROMPT),
                ("user",replan_prompt),
            ]).content
            try:
                s=new_plan_text.find("{")
                e=new_plan_text.rfind("}")+1
                new_plan=json.loads(new_plan_text[s:e])
                #替换剩余步骤
                steps=steps[:step_idx]+new_plan.get("steps",[])
                continue
            except json.JSONDecodeError:
                pass
        
        yield {"event":"step_result","data":{"step_id":step["id"],"tool":tool_name,"status":"DONE","summary":result.get("summary",{})}}
        results.append(result)
        step_idx+=1
    
    # Phase 3: Summarize
    yield {"event":"phase","data":{"phase":"summarizing","message":"生成报告..."}}
    
    report=llm.invoke([
        ("system","用中文生成运维报告, 含操作概览表 + 总结建议, Markdown 格式。不要编造工具未返回的信息。"),
        ("user",f"执行结果: {json.dumps([r.get('summary',{}) for r in results],ensure_ascii=False)}"),
    ]).content
    
    yield {"event":"agent_answer","data":{"content":report}}
