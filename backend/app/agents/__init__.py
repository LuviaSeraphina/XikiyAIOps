"""
XikiyAIOps 多 Agent 协作模块

三阶段流水线架构 (v4.0):
  Orchestrator  — 编排器: Planner → Executor → Summarizer
  Planner       — 规划器: 分析意图，生成任务计划
  Executor      — 执行器: 按计划逐步执行工具
  Summarizer    — 总结器: 整合结果，生成报告
  SecurityAgent — 安全守门员: 输入审查 + 工具审批 + 事后审计

用法:
    from app.agents import Orchestrator
    orch = Orchestrator()
    async for event in orch.run(user_input, history, session_id):
        yield event
"""
from .orchestrator import Orchestrator
from .security import SecurityAgent
from .planner import PlannerAgent
from .executor import ExecutorAgent
from .summarizer import SummarizerAgent

__all__=["Orchestrator","SecurityAgent","PlannerAgent","ExecutorAgent","SummarizerAgent"]
