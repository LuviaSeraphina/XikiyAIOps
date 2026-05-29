"""
MCP 插件共享工具 — 所有插件复用
"""
import subprocess
import os
from datetime import datetime

""" 
方法: make_response(), 统一构建 MCP Tool 返回结构
"""
def make_response(tool, data, summary, risk_level="read_only"):
    return {
        "tool": tool,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_level": risk_level,
        "data": data,
        "summary": summary,
    }
""" 
方法: error_response(), 异常时返回统一错误结构, 保证所有 Tool 不会因未捕获异常而崩溃
"""
def error_response(tool, error):
    return {
        "tool": tool,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_level": "error",
        "data": {},
        "summary": {"error": str(error)},
    }

"""
方法: run_command(), 安全执行固定参数命令, 返回 stdout, 超时或失败返回空字符串
"""
def run_command(cmd, timeout=10):
    try:
        result=subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""

"""
方法: journalctl_available(), 检测 journalctl 是否可用
"""
def journalctl_available():
    return os.path.exists("/usr/bin/journalctl") or os.path.exists("/bin/journalctl")

"""
方法: read_log_file(), 安全读取日志文件最后 max_lines 行
"""
def read_log_file(path, max_lines=2000):
    if not os.path.exists(path) or not os.access(path, os.R_OK):
        return []
    try:
        with open(path, "r", errors="ignore") as f:
            lines=f.readlines()
            return [line.strip() for line in lines[-max_lines:]]
    except (PermissionError, OSError):
        return []
