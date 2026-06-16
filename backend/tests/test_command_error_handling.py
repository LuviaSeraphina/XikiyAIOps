import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mcp_plugins import _common
from app.mcp_plugins import disk_plugin


def test_run_command_returns_dict_on_failed_command(monkeypatch):
    """v2.1: run_command() 返回结构化 dict, 失败时 stdout 为空, exit_code≠0"""
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="permission denied")

    monkeypatch.setattr(_common.subprocess, "run", fake_run)
    result=_common.run_command(["find", "/missing"])
    assert isinstance(result, dict)
    assert result["stdout"]==""
    assert result["exit_code"]!=0
    assert result["blocked"]==False


def test_disk_large_files_surfaces_command_failure(monkeypatch):
    """v2.1: 模拟命令执行失败 — 返回不通过 _cmd_ok 的 dict"""
    monkeypatch.setattr(disk_plugin, "_run_command", lambda *args, **kwargs: {
        "stdout":"","stderr":"模拟失败","exit_code":1,"duration_ms":0,"blocked":False
    })
    result=disk_plugin.disk_large_files(path="/tmp", top_n=5, min_size_mb=10)
    assert result["risk_level"]=="error"
    assert result["summary"]["error"]=="find 命令执行失败"
