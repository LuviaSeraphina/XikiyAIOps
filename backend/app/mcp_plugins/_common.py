"""
MCP 插件共享工具 — 所有插件复用
"""
import logging
import os
import re
import subprocess
import time
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
    "ss","ip","who","find","lsmod","systemctl",
    "journalctl","dmesg","cat","crontab","sysctl",
    "docker","podman","which","dnf","yum","apt",
    "iptables","nft","getenforce","aa-status","dig","getent",
    "dmidecode","groups",
}

# 高危参数模式 — 分三类匹配, 避免子串误伤 (如 rm 匹配 format)
#   词边界: alphabetic 模式使用 \b 边界, 只匹配独立单词
#   精确:   flag 模式匹配完整参数
#   子串:   操作符匹配任意位置
_DANGEROUS_WORD={"rm","mkfs","dd","shutdown","reboot","poweroff","halt","chmod","chown"}
_DANGEROUS_FLAG={"-rf","-r"}
_DANGEROUS_SUBSTR={">",">>","&&",";","|","`","$(","${"}

#方法: 在 run_command 前校验命令安全性
def _is_safe_command(cmd):
    #命令本身不在白名单
    if not cmd:
        return False, "空命令"
    base=cmd[0]
    if base not in _ALLOWED_COMMANDS:
        return False,f"命令 '{base}' 不在白名单内"

    #参数中检测高危模式
    for arg in cmd[1:]:
        #词边界匹配 (防子串误伤: format/perform/confirm/-perm)
        for pattern in _DANGEROUS_WORD:
            if re.search(r'\b' + re.escape(pattern) + r'\b', arg):
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"
        #精确匹配 flag
        for pattern in _DANGEROUS_FLAG:
            if arg==pattern:
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"
        #子串匹配 shell 操作符
        for pattern in _DANGEROUS_SUBSTR:
            if pattern in arg:
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"

    return True, ""

_logger=logging.getLogger("sre_agent.mcp")

"""
方法: run_command(), 安全执行固定参数命令

v2: 返回结构化 dict {stdout, stderr, exit_code, duration_ms}
    而非原始字符串, 以便上层采集真实执行数据用于异常回溯。

成功时 stdout 为命令输出, stderr 可能为空或有 warning。
执行失败时 stdout 为空字符串, stderr 包含错误信息。
"""
def run_command(cmd, timeout=10):
    #安全校验
    safe,reason=_is_safe_command(cmd)
    if not safe:
        _logger.warning(f"命令拦截: {' '.join(cmd[:3])} — {reason}")
        return {"stdout":"","stderr":reason,"exit_code":-1,"duration_ms":0,"blocked":True}

    start=time.monotonic()
    try:
        result=subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed_ms=int((time.monotonic() - start) * 1000)
        stdout=result.stdout.strip()
        stderr=(result.stderr or "").strip()
        exit_code=result.returncode

        if exit_code!=0 and not stdout:
            _logger.warning(f"命令执行失败: {' '.join(cmd)} (rc={exit_code}){f' stderr={stderr}' if stderr else ''}")
        elif exit_code!=0 and stderr:
            _logger.warning(f"命令返回非 0: {' '.join(cmd)} (rc={exit_code}){f' stderr={stderr}' if stderr else ''}")

        return {
            "stdout":stdout,
            "stderr":stderr,
            "exit_code":exit_code,
            "duration_ms":elapsed_ms,
            "blocked":False,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms=int((time.monotonic() - start) * 1000)
        _logger.warning(f"命令超时: {' '.join(cmd)} (>{timeout}s)")
        return {"stdout":"","stderr":f"命令超时 (>{timeout}s)","exit_code":-1,"duration_ms":elapsed_ms,"blocked":False}
    except (FileNotFoundError, OSError) as e:
        elapsed_ms=int((time.monotonic() - start) * 1000)
        _logger.warning(f"命令执行异常: {' '.join(cmd)} — {e}")
        return {"stdout":"","stderr":str(e),"exit_code":-1,"duration_ms":elapsed_ms,"blocked":False}

"""
方法: journalctl_available(), 检测 journalctl 是否可用
"""
def journalctl_available():
    return os.path.exists("/usr/bin/journalctl") or os.path.exists("/bin/journalctl")

"""
方法: _cmd_ok(), 检查 run_command() 返回的 dict 是否表示命令成功执行

插件层统一使用此函数判断, 替代旧版 `if result is None` 模式。
- blocked → False
- exit_code≠0 且 stdout 为空 → False  
- 其他情况 → True (含 exit_code==0 无输出, exit_code≠0 但有 stdout)
"""
def _cmd_ok(result):
    if result["blocked"]:
        return False
    if result["exit_code"]!=0 and not result["stdout"]:
        return False
    return True

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

# ── KYSDK 麒麟原生 SDK 支持 ──────────────────────────────
#KYSDK 是麒麟操作系统的原生 Python SDK, 提供系统信息/硬件/安全/网络等 API,
#替代 shell 命令采集, 零注入风险, 精度更高。非麒麟环境自动降级为 shell 方案。

#模块级惰性导入标记: True=可用, False=不可用, None=未检测
_KYSDK_AVAILABLE=None

"""
方法: _kysdk_available(), 检测 KYSDK Python SDK 是否可导入

一次检测, 结果缓存于模块变量 _KYSDK_AVAILABLE。
非麒麟系统返回 False, 调用方应回落 shell 方案。
"""
def _kysdk_available():
    global _KYSDK_AVAILABLE
    if _KYSDK_AVAILABLE is not None:
        return _KYSDK_AVAILABLE
    try:
        import kysdk
        _KYSDK_AVAILABLE=True
    except ImportError:
        _KYSDK_AVAILABLE=False
    return _KYSDK_AVAILABLE

"""
方法: _kysdk_import(module_name), 安全按需导入 KYSDK 子模块

成功返回模块对象, 失败返回 None (调用方自行处理降级)。
用法: sdk=_kysdk_import("SystemInfo"); if sdk: sdk.get_cpu_usage()
"""
def _kysdk_import(name):
    if not _kysdk_available():
        return None
    try:
        mod=__import__("kysdk", fromlist=[name])
        return getattr(mod, name, None)
    except (ImportError, AttributeError):
        return None