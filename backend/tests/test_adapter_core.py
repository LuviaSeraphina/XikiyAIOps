"""
适配器核心函数测试 — _process_tool_call + _extract_metrics

覆盖本次重构引入的所有新增/修改逻辑:
- _process_tool_call(skip_prefix=False): 完整事件流
- _process_tool_call(skip_prefix=True):  跳过前缀事件
- _process_tool_call 工具不存在: 返回 error 事件
- _extract_metrics: 数据驱动映射 + 边界条件
"""
import json
import pytest
from unittest.mock import MagicMock

from app.mcp_plugins.base import RiskLevel
from app.llm.adapter import _process_tool_call, _extract_metrics, _METRIC_EXTRACTORS, _safe_div


# ── helpers ──

class _FakeTool:
    """模拟 MCPTool, 仅暴露 risk_level.value 属性"""
    def __init__(self, risk_level):
        self.risk_level = MagicMock()
        self.risk_level.value = risk_level


def _make_tc(tool_name, args=None):
    """构建标准 tool_call 字典"""
    return {
        "id": "call_001",
        "function": {"name": tool_name, "arguments": args or {}},
    }


SUCCESS_RESULT = {
    "tool": "test_tool", "risk_level": "read_only",
    "data": {"usage_percent": 42}, "summary": {"alert": False},
}
ERROR_RESULT = {
    "tool": "test_tool", "risk_level": "error",
    "data": {}, "summary": {"error": "something broke"},
}


# ── _process_tool_call 测试 ──

class TestProcessToolCall:
    """_process_tool_call 事件流验证"""

    def test_read_only_tool_emits_no_security_check(self, monkeypatch):
        """read_only 工具: 有 tool_call + tool_result, 无 security_check"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: _FakeTool("read_only"),
        )
        monkeypatch.setattr(
            "app.llm.adapter.execute_tool",
            lambda name, args: SUCCESS_RESULT,
        )
        tc = _make_tc("disk_inspect")

        tool_msg, events = _process_tool_call(tc)

        event_types = [e["event"] for e in events]
        assert event_types == ["tool_call", "tool_result"], event_types
        assert events[0]["data"]["risk_level"] == "read_only"
        assert tool_msg["role"] == "tool"
        assert "tool_call_id" in tool_msg

    def test_restricted_tool_emits_security_check(self, monkeypatch):
        """restricted 工具: tool_call + security_check + tool_result"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: _FakeTool("restricted"),
        )
        monkeypatch.setattr(
            "app.llm.adapter.execute_tool",
            lambda name, args: SUCCESS_RESULT,
        )
        tc = _make_tc("process_kill", {"pid": 9999})

        tool_msg, events = _process_tool_call(tc)

        event_types = [e["event"] for e in events]
        assert event_types == ["tool_call", "security_check", "tool_result"], event_types
        assert events[1]["event"] == "security_check"

    def test_skip_prefix_disables_tool_call_and_security_check(self, monkeypatch):
        """skip_prefix=True: 只产出 tool_result, 无 tool_call/security_check"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: _FakeTool("restricted"),
        )
        monkeypatch.setattr(
            "app.llm.adapter.execute_tool",
            lambda name, args: SUCCESS_RESULT,
        )
        tc = _make_tc("process_kill", {"pid": 9999})

        tool_msg, events = _process_tool_call(tc, skip_prefix=True)

        event_types = [e["event"] for e in events]
        assert event_types == ["tool_result"], event_types
        assert tool_msg["role"] == "tool"

    def test_skip_prefix_still_emits_tool_result_even_on_error(self, monkeypatch):
        """skip_prefix=True + 执行错误: 仍然产出 tool_result, status=error"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: _FakeTool("read_only"),
        )
        monkeypatch.setattr(
            "app.llm.adapter.execute_tool",
            lambda name, args: ERROR_RESULT,
        )
        tc = _make_tc("disk_inspect")

        tool_msg, events = _process_tool_call(tc, skip_prefix=True)

        assert len(events) == 1
        assert events[0]["event"] == "tool_result"
        assert events[0]["data"]["status"] == "error"

    def test_nonexistent_tool_returns_error_regardless_of_skip_prefix(self, monkeypatch):
        """不存在的工具: skip_prefix 不影响, 直接返回 error"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: None,
        )
        tc = _make_tc("nonexistent_tool")

        # skip_prefix=False
        tool_msg1, events1 = _process_tool_call(tc, skip_prefix=False)
        assert events1[0]["event"] == "tool_result"
        assert events1[0]["data"]["status"] == "error"
        assert "Tool not found" in events1[0]["data"]["result"]["summary"]["error"]

        # skip_prefix=True
        tool_msg2, events2 = _process_tool_call(tc, skip_prefix=True)
        assert events2[0]["event"] == "tool_result"
        assert events2[0]["data"]["status"] == "error"

    def test_tool_result_contains_execution_data(self, monkeypatch):
        """tool_result 事件包含 result 和 status"""
        monkeypatch.setattr(
            "app.llm.adapter.registry.get_tool",
            lambda name: _FakeTool("read_only"),
        )
        monkeypatch.setattr(
            "app.llm.adapter.execute_tool",
            lambda name, args: SUCCESS_RESULT,
        )
        tc = _make_tc("memory_info")

        tool_msg, events = _process_tool_call(tc)

        result_event = events[-1]  # tool_result is last
        assert result_event["data"]["tool_name"] == "memory_info"
        assert result_event["data"]["status"] == "done"
        assert result_event["data"]["result"]["data"]["usage_percent"] == 42


# ── _extract_metrics 测试 ──

class TestExtractMetrics:
    """_extract_metrics 数据驱动映射 + 边界"""

    def test_all_four_dimensions(self):
        """四个维度全部提取"""
        m = _extract_metrics([
            {"tool": "system_load", "data": {"load_1min": 3.0, "cpu_cores": 4}},
            {"tool": "memory_info", "data": {"usage_percent": 72}},
            {"tool": "disk_inspect_handler", "data": {"usage_percent": 55}},
            {"tool": "swap_info", "data": {"swap_percent": 10}},
        ])
        assert abs(m["load_ratio"] - 0.75) < 0.01, m
        assert m["memory_percent"] == 72
        assert m["disk_percent"] == 55
        assert m["swap_percent"] == 10
        assert m["cpu_percent"] == 75.0

    def test_empty_input(self):
        """空列表返回仅含近似 cpu_percent 的 dict"""
        m = _extract_metrics([])
        assert m == {"cpu_percent": 0.0}, m

    def test_unknown_tool_ignored(self):
        """不认识的工具名被忽略"""
        m = _extract_metrics([
            {"tool": "unknown_tool", "data": {"something": 99}},
            {"tool": "memory_info", "data": {"usage_percent": 33}},
        ])
        assert m["memory_percent"] == 33
        assert m["cpu_percent"] == 0.0  # no system_load → load_ratio absent → 0.0

    def test_zero_cores_does_not_divide_by_zero(self):
        """cpu_cores=0 时被 max(cores,1) 提升到 1, 不除零"""
        m = _extract_metrics([
            {"tool": "system_load", "data": {"load_1min": 5.0, "cpu_cores": 0}},
        ])
        assert m["load_ratio"] == 5.0, m

    def test_missing_load_1min_defaults_to_zero(self):
        """load_1min 缺失时默认 0"""
        m = _extract_metrics([
            {"tool": "system_load", "data": {"cpu_cores": 2}},
        ])
        assert m["load_ratio"] == 0.0

    def test_cpu_percent_approximated_from_load_ratio(self):
        """cpu_percent 由 load_ratio * 100 近似"""
        m = _extract_metrics([
            {"tool": "system_load", "data": {"load_1min": 6.0, "cpu_cores": 8}},
        ])
        assert abs(m["load_ratio"] - 0.75) < 0.01
        assert m["cpu_percent"] == 75.0


# ── _METRIC_EXTRACTORS 结构验证 ──

class TestMetricExtractorsTable:
    """验证 _METRIC_EXTRACTORS 映射表的完整性"""

    def test_all_keys_are_valid_tool_names(self):
        assert set(_METRIC_EXTRACTORS.keys()) == {
            "system_load", "memory_info", "disk_inspect_handler", "swap_info",
        }

    def test_each_extractor_returns_dict(self):
        for name, extractor in _METRIC_EXTRACTORS.items():
            result = extractor({})
            assert isinstance(result, dict), "{} returned {}".format(name, type(result))


# ── _safe_div 测试 ──

class TestSafeDiv:
    def test_normal_division(self):
        assert _safe_div(6, 3) == 2.0

    def test_zero_divisor(self):
        assert _safe_div(5, 0) == 0

    def test_zero_numerator(self):
        assert _safe_div(0, 5) == 0.0
