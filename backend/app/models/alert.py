"""
告警模型 — 接收外部告警 + 存储 Agent 诊断结果

状态流转:
  pending → processing → resolved (已修复) / ignored (已忽略)
"""
from sqlalchemy import Column, String, DateTime, Boolean, func
from sqlalchemy.types import JSON
from app.models.base import Base
from app.models._utils import _new_uuid, _now


class Alert(Base):
    __tablename__="alerts"

    #主键
    id=Column(String(36), primary_key=True, default=_new_uuid)

    #告警来源标识 (Alertmanager fingerprint, 用于去重)
    fingerprint=Column(String(64), nullable=True, index=True)

    #告警基本信息
    alert_name=Column(String(128), nullable=False, index=True)
    instance=Column(String(256), nullable=True)
    severity=Column(String(32), nullable=False, default="warning")
    status=Column(String(32), nullable=False, default="firing")

    #标签和注释 (JSON)
    labels=Column(JSON, nullable=True)
    annotations=Column(JSON, nullable=True)

    #触发时间
    starts_at=Column(DateTime, nullable=True)

    #Agent 诊断结果
    diagnosis=Column(JSON, nullable=True)
    #格式: {"tools_called": [...], "tool_results": [...], "rag_matches": [...], "llm_analysis": "..."}

    resolution=Column(String(512), nullable=True)  #修复建议
    resolved=Column(Boolean, nullable=False, default=False)
    resolved_at=Column(DateTime, nullable=True)

    #元数据
    created_at=Column(DateTime, server_default=func.now())
    updated_at=Column(DateTime, onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Alert {self.alert_name} {self.severity} {'✅' if self.resolved else '🔴'}>"
