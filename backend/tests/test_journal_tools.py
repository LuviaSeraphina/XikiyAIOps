"""
系统日志工具测试 — system_journal_query + system_journal_tail

覆盖:
- _parse_journal_entries: 六种日志行格式 + 关键词过滤 + 空输入
- system_journal_query: journalctl 不可用时的错误路径
- system_journal_tail: journalctl 不可用时的错误路径
"""
import pytest
from app.mcp_plugins.system_plugin import (
    _parse_journal_entries,
    system_journal_query,
    system_journal_tail,
    journalctl_available as _journalctl_available,
)


# ── _parse_journal_entries 测试 ──

class TestParseJournalEntries:
    """_parse_journal_entries: 四种日志行格式 + 关键词过滤 + 边界"""

    def test_standard_syslog_line(self):
        """标准短日志行: timestamp hostname service[pid]: message"""
        lines = [
            "2024-06-15T10:30:00+0800 myserver sshd[1234]: Failed password for root",
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries) == 1
        assert entries[0]["timestamp"] == "2024-06-15T10:30:00+0800"
        assert entries[0]["hostname"] == "myserver"
        assert entries[0]["service"] == "sshd"
        assert entries[0]["pid"] == "1234"
        assert "Failed password" in entries[0]["message"]

    def test_service_with_dash(self):
        """服务名含连接符: systemd-journald"""
        lines = [
            "2024-06-15T11:00:00+0000 host systemd-journald[999]: Journal started",
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries) == 1
        assert entries[0]["service"] == "systemd-journald"
        assert entries[0]["pid"] == "999"

    def test_no_pid_line(self):
        """无 PID 的日志行: program: message"""
        lines = [
            "2024-06-15T12:00:00+0800 server CROND: (root) CMD (echo test)",
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries) == 1
        assert entries[0]["service"] == "CROND"
        assert entries[0]["pid"] == ""

    def test_kernel_message(self):
        """内核日志: kernel: message (无 PID)"""
        lines = [
            "2024-06-15T13:00:00+0800 kernel kernel: CPU soft lockup",
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries) == 1
        assert entries[0]["service"] == "kernel"
        assert entries[0]["message"] == "CPU soft lockup"

    def test_keyword_filters_messages(self):
        """关键词过滤: 只保留 message 包含 keyword 的条目"""
        lines = [
            "2024-06-15T10:00:00+0800 host sshd[1]: Failed password",
            "2024-06-15T10:01:00+0800 host sshd[2]: Accepted password",
            "2024-06-15T10:02:00+0800 host systemd[1]: Started service",
        ]
        entries = _parse_journal_entries(lines, keyword="fail")
        assert len(entries) == 1
        assert entries[0]["pid"] == "1"

    def test_empty_lines_skipped(self):
        """空行或非标准格式行被跳过"""
        lines = [
            "",
            "2024-06-15T10:00:00+0800 host sshd[1]: test",
            "   ",
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries) == 1

    def test_keyword_case_insensitive(self):
        """关键词忽略大小写"""
        lines = [
            "2024-06-15T10:00:00+0800 host sshd[1]: FAILED password",
        ]
        entries = _parse_journal_entries(lines, keyword="Failed")
        assert len(entries) == 1

    def test_message_truncated(self):
        """message 超过 200 字符被截断"""
        lines = [
            "2024-06-15T10:00:00+0800 host app[1]: " + "x" * 300,
        ]
        entries = _parse_journal_entries(lines)
        assert len(entries[0]["message"]) <= 200


# ── system_journal_query 错误路径测试 ──

class TestJournalQueryErrorPath:
    """system_journal_query: journalctl 不可用时的降级路径"""

    def test_returns_error_when_journalctl_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "app.mcp_plugins.system_plugin.journalctl_available",
            lambda: False,
        )
        result = system_journal_query()
        assert result["risk_level"] == "error"
        assert "journalctl 不可用" in result["summary"].get("error", "")

    def test_query_without_keyword_still_works_on_error(self, monkeypatch):
        """带参数的调用在 journalctl 不可用时同样返回 error"""
        monkeypatch.setattr(
            "app.mcp_plugins.system_plugin.journalctl_available",
            lambda: False,
        )
        result = system_journal_query(service="sshd", hours=2, priority="warning")
        assert result["risk_level"] == "error"


# ── system_journal_tail 错误路径测试 ──

class TestJournalTailErrorPath:
    """system_journal_tail: journalctl 不可用时的降级路径"""

    def test_returns_error_when_journalctl_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "app.mcp_plugins.system_plugin.journalctl_available",
            lambda: False,
        )
        result = system_journal_tail()
        assert result["risk_level"] == "error"

    def test_custom_lines_param(self, monkeypatch):
        monkeypatch.setattr(
            "app.mcp_plugins.system_plugin.journalctl_available",
            lambda: False,
        )
        result = system_journal_tail(lines=50, priority="crit")
        assert result["risk_level"] == "error"
