"""
MCP 内存与 OOM 监控插件

提供三项内存健康检查能力：

1. memory_info         — 物理内存画像(总量/已用/可用/使用率)
2. swap_info           — Swap 交换分区画像(使用率 > 50% 预警)
3. memory_oom_history  — OOM Killer 历史事件提取(journalctl / dmesg)

数据源: psutil + journalctl(自动降级到 dmesg)
所有操作均为只读(risk_level: read_only)，适合 MCP Agent 内存健康巡检调用。
返回统一 JSON 结构: {tool, timestamp, risk_level, data, summary}

"""
import psutil
import re
from app.mcp_plugins._common import(
    run_command as _run_command,
    make_response as _make_response,
    error_response as _error_response,
    alert_if as _alert_if
)

# GB 单位
_GB=1024**3

# OOM 关键词正则
_OOM_PATTERN=re.compile(
    r"(?:Out of memory|oom.killer|Killed process|invoked oom)",
    re.IGNORECASE
)

# 被杀进程提取正则
_OOM_KILLED_PATTERN=re.compile(r"Killed process (\d+) \((.+?)\)")

"""
方法: memory_info(), 物理内存画像

"""
def memory_info():
    try:
        mem=psutil.virtual_memory()

        #物理内存
        total_gb=round(mem.total / _GB, 2)
        used_gb=round(mem.used / _GB, 2)
        available_gb=round(mem.available / _GB, 2)
        usage_percent=mem.percent

        alert=usage_percent>90

        return _make_response("memory_info",
            data={
                "total_gb": total_gb,
                "used_gb": used_gb,
                "available_gb": available_gb,
                "usage_percent": usage_percent,
            },
            summary={
                "usage_percent": usage_percent,
                "alert": alert,
                "alert_reason": _alert_if(alert, "物理内存({}%)即将耗尽", usage_percent),
            },
        )
    except Exception as e:
        return _error_response("memory_info", e)


"""
方法: swap_info(), Swap 交换分区画像

"""
def swap_info():
    try:
        swap=psutil.swap_memory()

        #Swap
        total_gb=round(swap.total / _GB, 2)
        used_gb=round(swap.used / _GB, 2)
        free_gb=round(swap.free / _GB, 2)
        swap_percent=swap.percent

        alert=swap_percent>50

        return _make_response("swap_info",
            data={
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "swap_percent": swap_percent,
            },
            summary={
                "swap_percent": swap_percent,
                "alert": alert,
                "alert_reason": _alert_if(alert, "Swap 使用({}%)过高, 系统可能已开始颠簸", swap_percent),
            },
        )
    except Exception as e:
        return _error_response("swap_info", e)


"""
方法: memory_oom_history(), 从 journalctl/dmesg 提取 OOM Killer 历史

"""
def memory_oom_history(hours=24):
    try:
        #优先 journalctl, 回退 dmesg
        output=_run_command([
            "journalctl", "-k", "--no-pager", "--since", "{}h ago".format(hours)
        ], timeout=10)
        if not output:
            output=_run_command(["dmesg"], timeout=5)
        if not output:
            return _make_response("memory_oom_history",
                data={"events": []},
                summary={"total_events": 0, "hours": hours},
            )

        #匹配 OOM 相关行
        events=[]
        for line in output.split("\n"):
            if _OOM_PATTERN.search(line):
                #尝试提取被杀进程名和 pid
                killed=_OOM_KILLED_PATTERN.search(line)
                pid=int(killed.group(1)) if killed else 0
                process=killed.group(2) if killed else "unknown"
                events.append({
                    "process": process,
                    "pid": pid,
                    "raw": line[:300],
                })

        return _make_response("memory_oom_history",
            data={"events": events},
            summary={
                "total_events": len(events),
                "hours": hours,
                "alert": len(events)>0,
                "alert_reason": _alert_if(len(events)>0, "检测到 {} 次 OOM 事件", len(events)),
            },
        )
    except Exception as e:
        return _error_response("memory_oom_history", e)