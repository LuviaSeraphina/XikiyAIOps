"""
流水线追踪模型 — 记录 Planner→Executor→Summarizer 全链路决策过程

每条记录对应一次对话，包含:
- planning: Planner 为什么选这些工具、原始 LLM 输出
- execution: 每步调了什么工具、参数、返回结果、耗时
- replanning: 失败后重规划的过程
- summarization: 最终报告
"""
import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from app.models import Base

class PipelineTrace(Base):
    __tablename__="pipeline_traces"

    id=Column(Integer, primary_key=True, autoincrement=True)
    session_id=Column(String(64), nullable=False, index=True, comment="会话ID")
    user_input=Column(Text, nullable=False, comment="用户原始输入")
    intent=Column(String(128), nullable=True, comment="Planner 识别意图")
    plan_json=Column(Text, nullable=True, comment="Planner 输出的原始计划 JSON")
    trace_json=Column(Text, nullable=True, comment="""
全链路追踪 JSON:
{
  "planning": {"llm_output": "...", "elapsed_ms": 123},
  "steps": [
    {"id":1, "tool":"disk_inspect", "params":{...}, "result":{...}, "elapsed_ms":45, "status":"ok"},
    ...
  ],
  "replans": [{"step_failed":2, "new_plan":"...", "llm_output":"..."}],
  "summarization": {"elapsed_ms": 567}
}
""")
    summary=Column(Text, nullable=True, comment="最终报告文本")
    total_elapsed_ms=Column(Integer, nullable=True, comment="总耗时(毫秒)")
    created_at=Column(DateTime, default=datetime.utcnow, comment="创建时间")

    def to_dict(self):
        return {
            "id":self.id,
            "session_id":self.session_id,
            "user_input":self.user_input,
            "intent":self.intent,
            "plan_json":json.loads(self.plan_json) if self.plan_json else None,
            "trace_json":json.loads(self.trace_json) if self.trace_json else None,
            "summary":self.summary,
            "total_elapsed_ms":self.total_elapsed_ms,
            "created_at":self.created_at.isoformat() if self.created_at else None,
        }
