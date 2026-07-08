"""
三阶段流水线类型定义

Planner → Executor → Summarizer
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any


class PlanType(str, Enum):
    """任务意图类型"""
    CLEAN_GARBAGE = "clean_system_garbage"
    CONFIG_DRIFT = "config_drift"
    IO_ANOMALY = "io_anomaly"
    ZOMBIE_CLEANUP = "zombie_cleanup"
    SERVICE_RECOVERY = "service_recovery"
    SECURITY_AUDIT = "security_audit"
    OOM_DIAGNOSIS = "oom_diagnosis"
    NETWORK_DIAGNOSIS = "network_diagnosis"
    SWAP_DIAGNOSIS = "swap_diagnosis"
    FD_LEAK = "fd_leak"
    SYSTEM_DIAGNOSIS = "system_diagnosis"
    CUSTOM = "custom"


class StepStatus(str, Enum):
    """步骤执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class TaskStep:
    """任务步骤"""
    id: int
    description: str
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    fallback_tool: str = ""
    max_retries: int = 0
    status: StepStatus = StepStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "depends_on": self.depends_on,
            "fallback_tool": self.fallback_tool,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStep":
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            tool=data["tool"],
            params=data.get("params", {}),
            depends_on=data.get("depends_on", []),
            fallback_tool=data.get("fallback_tool", ""),
            max_retries=data.get("max_retries", 0),
        )


@dataclass
class TaskPlan:
    """任务计划"""
    intent: PlanType
    strategy: str
    steps: List[TaskStep] = field(default_factory=list)
    user_input: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value if isinstance(self.intent, PlanType) else self.intent,
            "strategy": self.strategy,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        intent_str = data.get("intent", "custom")
        try:
            intent = PlanType(intent_str)
        except ValueError:
            intent = PlanType.CUSTOM
        return cls(
            intent=intent,
            strategy=data.get("strategy", ""),
            steps=[TaskStep.from_dict(s) for s in data.get("steps", [])],
            user_input=data.get("user_input", ""),
        )


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: int
    tool_name: str
    tool_result: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.SUCCESS
    error: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "status": self.status.value if isinstance(self.status, StepStatus) else self.status,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @property
    def is_success(self) -> bool:
        return self.status == StepStatus.SUCCESS

    @property
    def summary(self) -> Dict[str, Any]:
        return self.tool_result.get("summary", {})

    @property
    def data(self) -> Dict[str, Any]:
        return self.tool_result.get("data", {})
