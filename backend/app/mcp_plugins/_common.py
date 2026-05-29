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

# 允许执行的命令白名单 (只有这些命令可通过 run_command 执行)
_ALLOWED_COMMANDS={
    "ss", "ip", "who", "find", "lsmod", "systemctl",
    "journalctl", "dmesg", "cat", "crontab", "sysctl",
    "docker", "podman", "which", "dnf", "yum", "apt",
}

# 高危参数模式 (即使命令在白名单内, 参数包含这些也拒绝)
_DANGEROUS_PARAMS = {
    "rm", "-rf", "-r", "-f", "mkfs", "dd", "shutdown", "reboot",
    "poweroff", "halt", "chmod", "chown", ">", ">>", "|", ";", "&&",
}

#方法: 在 run_command 前校验命令安全性
def _is_safe_command(cmd):
    #命令本身不在白名单
    if not cmd:
        return False, "空命令"
    base=cmd[0]
    if base not in _ALLOWED_COMMANDS:
        return False, "命令 '{}' 不在白名单内".format(base)

    #参数中检测高危模式
    for arg in cmd[1:]:
        for pattern in _DANGEROUS_PARAMS:
            if pattern in arg:
                return False, "参数 '{}' 包含高危模式 '{}'".format(arg[:50], pattern)

    return True, ""

"""
方法: run_command(), 安全执行固定参数命令, 返回 stdout, 超时或失败返回空字符串
"""
def run_command(cmd, timeout=10):
    #安全校验
    safe, reason=_is_safe_command(cmd)
    if not safe:
        print("[run_command] 拦截: {} — {}".format(" ".join(cmd[:3]), reason))
        return ""

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
        
"""
方法: alert_if(), 告警句式生产辅助
"""
#方法: 告警句式辅助
def alert_if(condition, template, *args):
    return template.format(*args) if condition else ""