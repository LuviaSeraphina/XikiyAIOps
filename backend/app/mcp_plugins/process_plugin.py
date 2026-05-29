"""
MCP 进程巡检工具

"""

import psutil
import time
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response

process_inspect_schema={
    "name": "process_inspect",
    "description": "获取系统进程信息",
    "inputSchema": {
        "type": "object",
        "peism ": {
            "filter_state": {"type": "string","default": "","enum": ["running","sleeping","stopped","zombie","disk-sleep"]},
            "sort_by": {"type": "string","default": "cpu","enum": ["cpu","mem"]},
            "top_n": {"type": "integer","default": 10,"minimum": 1,"maximum": 100}
        }
    },
    "risk_level": "read_only"
}

"""
方法: process_inspect_handler(), 返回进程列表，支持按状态过滤、按 CPU/内存(mem)排序
"""
def process_inspect_handler(filter_state="", sort_by="cpu", top_n=10):
    try:
        # 预热: 触发所有进程的第一次采样
        try:
            for _ in psutil.process_iter(['cpu_percent']):
                _=_.info['cpu_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        time.sleep(0.5)
        
        # 正式采样
        all_process=[]
        for process in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
            try:
                if filter_state and process.info['status']!=filter_state:
                    continue
                
                all_process.append({
                    'pid': process.info.get('pid'),
                    'name': process.info.get('name'),
                    'cpu_percent': process.info.get('cpu_percent') or 0.0,
                    'memory_percent': process.info.get('memory_percent') or 0.0,
                    'status': process.info.get('status')
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 按CPU/内存排序
        if sort_by=="cpu":
            all_process.sort(key=lambda x:x['cpu_percent'],reverse=True)
        elif sort_by=="mem":
            all_process.sort(key=lambda x:x['memory_percent'],reverse=True)

        return _make_response("process_inspect_handler",
            data={"processes": all_process[:top_n]},
            summary={"total": len(all_process), "shown": min(top_n, len(all_process))},
        )
    except Exception as e:
        return _error_response("process_inspect_handler", e)