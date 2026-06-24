"""
对话 API 辅助函数测试 — _build_audit_item + _derive_risk_level

覆盖本次重构新增的 _build_audit_item 函数:
- 正常组装 stages + is_anomaly + anomaly_type
- causal_chain 构建验证
- _derive_risk_level 各种事件流推断
"""
import pytest
from unittest.mock import MagicMock, patch

from app.api.chat import _build_audit_item, _derive_risk_level


# ── helpers ──

def _fake_causal_chain(s1, s2, s3, s4, s5):
    """模拟 build_causal_chain 返回简单 dict"""
    return {"from": s1.get("raw_input", "")[:10], "to": s5.get("action_taken", "")}


# ── _build_audit_item 测试 ──

class TestBuildAuditItem:
    """_build_audit_item: stages 组装 + causal_chain 注入"""

    def test_normal_assembly(self, monkeypatch):
        """正常组装: stages 5 元组 + 标记 + causal_chain"""
        monkeypatch.setattr(
            "app.api.chat.build_causal_chain",
            lambda s1, s2, s3, s4, s5, *a, **k: {"chain": "ok"},
        )

        s1 = {"raw_input": "查看系统"}
        s2 = {"tools_called": ["system_load"]}
        s3 = {"llm_raw_output": "分析中"}
        s4 = {"decision": "allowed"}
        s5 = {"action_taken": "执行 system_load"}
        is_anomaly = False
        anomaly_type = "none"

        item = _build_audit_item(s1, s2, s3, s4, s5, is_anomaly, anomaly_type)

        assert "stages" in item
        assert len(item["stages"]) == 5
        assert item["stages"][0] is s1
        assert item["stages"][4] is s5
        assert item["is_anomaly"] is False
        assert item["anomaly_type"] == "none"
        assert s5["causal_chain"] == {"chain": "ok"}

    def test_anomaly_marks(self, monkeypatch):
        """异常标记正确传递"""
        monkeypatch.setattr(
            "app.api.chat.build_causal_chain",
            lambda *a, **k: {},
        )

        s1, s2, s3, s4, s5 = {}, {}, {}, {}, {}
        item = _build_audit_item(s1, s2, s3, s4, s5, True, "tool_error")

        assert item["is_anomaly"] is True
        assert item["anomaly_type"] == "tool_error"

    def test_stage_execution_mutated_with_causal_chain(self, monkeypatch):
        """s5 被原地写入 causal_chain 键"""
        monkeypatch.setattr(
            "app.api.chat.build_causal_chain",
            lambda s1, s2, s3, s4, s5: {"injected": True},
        )

        s5 = {"action_taken": "test"}
        _build_audit_item({}, {}, {}, {}, s5, False, "none")

        assert s5["causal_chain"] == {"injected": True}
        assert s5["action_taken"] == "test"  # 原有键保留


# ── _derive_risk_level 测试 ──

class TestDeriveRiskLevel:
    """_derive_risk_level: 从事件流推断风险等级"""

    def test_read_only_default(self):
        """无风险事件 → read_only"""
        events = [
            {"event": "token", "data": {"text": "你好"}},
            {"event": "done", "data": {}},
        ]
        assert _derive_risk_level(events) == "read_only"

    def test_dangerous_from_tool_risk(self):
        """tool_call 含 risk_level=dangerous → dangerous"""
        events = [
            {"event": "tool_call", "data": {"risk_level": "dangerous"}},
        ]
        assert _derive_risk_level(events) == "dangerous"

    def test_restricted_from_tool_risk(self):
        """tool_call 含 risk_level=restricted → restricted"""
        events = [
            {"event": "tool_call", "data": {"risk_level": "restricted"}},
        ]
        assert _derive_risk_level(events) == "restricted"

    def test_error_event_means_dangerous(self):
        """error 事件 → dangerous"""
        events = [
            {"event": "error", "data": {"message": "something"}},
        ]
        assert _derive_risk_level(events) == "dangerous"

    def test_first_risk_level_wins(self):
        """_derive_risk_level 返回第一个命中的 risk_level, 不扫描全部"""
        events = [
            {"event": "security_check", "data": {"risk_level": "restricted"}},
            {"event": "tool_call", "data": {"risk_level": "dangerous"}},
        ]
        assert _derive_risk_level(events) == "restricted"

    def test_risk_level_wins_over_error_when_first(self):
        """risk_level 在 error 之前出现 → 返回 risk_level"""
        events = [
            {"event": "security_check", "data": {"risk_level": "restricted"}},
            {"event": "error", "data": {}},
        ]
        assert _derive_risk_level(events) == "restricted"
    
    def test_error_wins_when_no_risk_level(self):
        """无 risk_level 字段时, error 事件 → dangerous"""
        events = [
            {"event": "tool_call", "data": {"tool_name": "x"}},
            {"event": "error", "data": {"message": "fail"}},
        ]
        assert _derive_risk_level(events) == "dangerous"

    def test_no_risk_field_defaults_read_only(self):
        """data 中无 risk_level → read_only"""
        events = [
            {"event": "tool_call", "data": {"tool_name": "disk_inspect"}},
        ]
        assert _derive_risk_level(events) == "read_only"

    def test_empty_events(self):
        """空列表 → read_only"""
        assert _derive_risk_level([]) == "read_only"
