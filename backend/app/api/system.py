"""
系统快照 API — 仪表盘实时数据源

GET /api/system/snapshot  — 返回 CPU/内存/磁盘/网络/系统信息
"""
from fastapi import APIRouter
import psutil
import os
import platform
import time

router=APIRouter()


@router.get("/snapshot")
async def system_snapshot():
    """返回系统实时快照，供仪表盘直接展示"""
    #CPU
    cpu_percent=psutil.cpu_percent(interval=0.3)
    cpu_count=psutil.cpu_count(logical=True)
    cpu_physical=psutil.cpu_count(logical=False)
    load=psutil.getloadavg()

    #内存
    mem=psutil.virtual_memory()
    swap=psutil.swap_memory()

    #磁盘
    disk=psutil.disk_usage("/")

    #网络
    net_io=psutil.net_io_counters()
    connections=len(psutil.net_connections(kind="inet"))

    #启动时间
    boot_time=psutil.boot_time()
    uptime_seconds=int(time.time()-boot_time)

    #进程
    proc_count=len(psutil.pids())

    return {
        "code": 0,
        "data": {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "kernel": platform.version(),
            "architecture": platform.machine(),
            "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_time)),
            "uptime_seconds": uptime_seconds,

            "cpu": {
                "cores_logical": cpu_count,
                "cores_physical": cpu_physical or cpu_count,
                "percent": round(cpu_percent, 1),
                "load_1m": round(load[0], 2),
                "load_5m": round(load[1], 2),
                "load_15m": round(load[2], 2),
            },

            "memory": {
                "total_gb": round(mem.total/(1024**3), 1),
                "used_gb": round(mem.used/(1024**3), 1),
                "available_gb": round(mem.available/(1024**3), 1),
                "percent": mem.percent,
                "swap_total_gb": round(swap.total/(1024**3), 1) if swap.total>0 else 0,
                "swap_used_gb": round(swap.used/(1024**3), 1) if swap.total>0 else 0,
                "swap_percent": swap.percent,
            },

            "disk": {
                "total_gb": round(disk.total/(1024**3), 1),
                "used_gb": round(disk.used/(1024**3), 1),
                "free_gb": round(disk.free/(1024**3), 1),
                "percent": disk.percent,
            },

            "network": {
                "bytes_sent_mb": round(net_io.bytes_sent/(1024**2), 1),
                "bytes_recv_mb": round(net_io.bytes_recv/(1024**2), 1),
                "connections": connections,
            },

            "process_count": proc_count,
        },
        "message": "ok",
    }
