"""
MCP 磁盘巡检工具

"""

import psutil
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response


disk_inspect_schema={
    "name": "disk_inspect",
    "description": "获取磁盘信息,可定义具体路径",
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {"type": "string","default": "/","description": "要检查的挂载点路径，例如 '/' 或 '/var/log'"}
        }
    }
}

"""
方法: disk_inspect_handler(), 获取磁盘信息
"""
def disk_inspect_handler(path="/"):
    try:
        GB=1024**3
        disk_info=psutil.disk_usage(path)
        return _make_response("disk_inspect_handler",
            data={
                "total_gb": round(disk_info.total / GB, 2),
                "used_gb": round(disk_info.used / GB, 2),
                "free_gb": round(disk_info.free / GB, 2),
                "usage_percent": disk_info.percent,
            },
            summary={
                "path": path,
                "usage_percent": disk_info.percent,
                "alert": disk_info.percent > 90,
            },
        )
    except Exception as e:
        return _error_response("disk_inspect_handler", e)