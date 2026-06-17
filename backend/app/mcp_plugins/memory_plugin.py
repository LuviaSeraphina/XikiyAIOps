"""
MCP 内存与 OOM 监控插件

v2: KYSDK SystemInfo 优先 (麒麟原生), 回落 psutil
"""
import psutil
import re
from app.mcp_plugins._common import(
    run_command as _run_command,
    _cmd_ok,
    make_response as _make_response,
    error_response as _error_response,
    alert_if as _alert_if,
    _kysdk_import,
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

v2: KYSDK SystemInfo 优先 (麒麟原生), 回落 psutil
"""
def memory_info():
    try:
        #优先 KYSDK
        SystemInfo=_kysdk_import("SystemInfo")
        if SystemInfo:
            try:
                si=SystemInfo()
                mem=si.get_memory_info()
                if mem and isinstance(mem, dict):
                    usage_percent=mem.get("used_percent", 0)
                    alert=usage_percent>90
                    return _make_response("memory_info",
                        data={**mem, "source": "kysdk.SystemInfo"},
                        summary={
                            "usage_percent": usage_percent,
                            "alert": alert,
                            "alert_reason": _alert_if(alert, "物理内存({}%)即将耗尽", usage_percent),
                            "source": "kysdk.SystemInfo",
                        },
                    )
            except Exception:
                pass

        #回落 psutil
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
        result=_run_command([
            "journalctl","-k","--no-pager","--since",f"{hours}h ago"
        ], timeout=10)
        if not _cmd_ok(result):
            result=_run_command(["dmesg"],timeout=5)
        if not _cmd_ok(result):
            return _error_response("memory_oom_history","dmesg 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("memory_oom_history",
                data={"events":[]},
                summary={"total_events":0,"hours":hours},
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
                    "process":process,
                    "pid":pid,
                    "raw":line[:300],
                })

        return _make_response("memory_oom_history",
            data={"events": events},
            summary={
                "total_events":len(events),
                "hours":hours,
                "alert":len(events)>0,
                "alert_reason":_alert_if(len(events)>0,"检测到 {} 次 OOM 事件",len(events)),
            },
        )
    except Exception as e:
        return _error_response("memory_oom_history", e)


"""
方法: memory_hugepages(), 大页内存状态 — 从 /proc/meminfo 解析 HugePages 字段

"""
def memory_hugepages():
    try:
        result=_run_command(["cat", "/proc/meminfo"], timeout=5)
        if not _cmd_ok(result):
            return _error_response("memory_hugepages","cat /proc/meminfo 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("memory_hugepages",
                data={"total":0,"free":0,"used":0,"usage_percent":0,"page_size_kb":0},
                summary={"usage_percent":0,"alert":False},
            )

        huge_total=0
        huge_free=0
        huge_rsvd=0
        huge_surp=0
        huge_pagesize=0

        for line in output.split("\n"):
            parts=line.split(":")
            if len(parts)<2:
                continue
            key=parts[0].strip()
            val=parts[1].strip().split()[0]
            val_int=int(val) if val.isdigit() else 0

            if key=="HugePages_Total":
                huge_total=val_int
            elif key=="HugePages_Free":
                huge_free=val_int
            elif key=="HugePages_Rsvd":
                huge_rsvd=val_int
            elif key=="HugePages_Surp":
                huge_surp=val_int
            elif key=="Hugepagesize":
                huge_pagesize=val_int

        used=huge_total-huge_free
        usage_percent=round(used/huge_total*100,1) if huge_total>0 else 0.0

        return _make_response("memory_hugepages",
            data={
                "total":huge_total,
                "free":huge_free,
                "reserved":huge_rsvd,
                "surplus":huge_surp,
                "used":used,
                "usage_percent":usage_percent,
                "page_size_kb":huge_pagesize,
            },
            summary={"usage_percent":usage_percent,"alert":False},
        )
    except Exception as e:
        return _error_response("memory_hugepages", e)


"""
方法: memory_slab_info(), 内核 Slab 缓存用量 — 从 /proc/meminfo 解析 Slab/SReclaimable/SUnreclaim

"""
def memory_slab_info():
    try:
        result=_run_command(["cat", "/proc/meminfo"], timeout=5)
        if not _cmd_ok(result):
            return _error_response("memory_slab_info","cat /proc/meminfo 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("memory_slab_info",
                data={"slab_total_kb":0,"slab_reclaimable_kb":0,"slab_unreclaimable_kb":0,"slab_total_mb":0.0},
                summary={"slab_mb":0.0,"alert":False},
            )

        slab_kb=0
        slab_rec_kb=0
        slab_unrec_kb=0

        for line in output.split("\n"):
            parts=line.split(":")
            if len(parts)<2:
                continue
            key=parts[0].strip()
            val=parts[1].strip().split()[0]
            val_int=int(val) if val.isdigit() else 0

            if key=="Slab":
                slab_kb=val_int
            elif key=="SReclaimable":
                slab_rec_kb=val_int
            elif key=="SUnreclaim":
                slab_unrec_kb=val_int

        slab_mb=round(slab_kb/1024,1)

        return _make_response("memory_slab_info",
            data={
                "slab_total_kb":slab_kb,
                "slab_reclaimable_kb":slab_rec_kb,
                "slab_unreclaimable_kb":slab_unrec_kb,
                "slab_total_mb":slab_mb,
            },
            summary={"slab_mb":slab_mb,"alert":False},
        )
    except Exception as e:
        return _error_response("memory_slab_info", e)