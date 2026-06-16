"""
MCP 容器与虚拟化感知插件

提供三项容器巡检能力:

1. container_list       — Docker/Podman 容器列表 (名称/镜像/状态/端口)
2. container_stats      — 容器资源用量 (CPU%/内存/网络 I/O)
3. container_inspect    — 单容器安全审计 (privileged/capabilities/mounts)

底层命令: docker / podman (自动检测可用性, 优雅降级)
所有操作均为只读 (risk_level: read_only)
"""
import json
from app.mcp_plugins._common import (
    run_command as _run_command,
    _cmd_ok,
    make_response as _make_response,
    error_response as _error_response,
)


"""
方法: _detect_container_runtime(), 检测可用容器运行时 — docker > podman > none
"""
def _detect_container_runtime():
    for cmd in ["docker", "podman"]:
        result=_run_command(["which", cmd], timeout=3)
        if _cmd_ok(result) and cmd in result["stdout"]:
            return cmd
    return ""


"""
方法: container_list(), 列出所有容器 (名称/镜像/状态/端口映射/运行时长)

"""
def container_list():
    try:
        runtime=_detect_container_runtime()
        if not runtime:
            return _make_response("container_list",
                data={"containers":[]},
                summary={"total":0,"runtime":"none","alert":False},
            )

        result=_run_command([runtime,"ps","--format","{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"], timeout=10)
        if not _cmd_ok(result):
            return _error_response("container_list",f"{runtime} ps 执行失败")
        containers=[]
        output=result["stdout"]
        if output:
            for line in output.split("\n"):
                parts=line.split("\t")
                if len(parts)>=4:
                    containers.append({
                        "id":parts[0][:12] if parts[0] else "",
                        "name":parts[1] if len(parts)>1 else "",
                        "image":parts[2] if len(parts)>2 else "",
                        "status":parts[3] if len(parts)>3 else "",
                        "ports":parts[4] if len(parts)>4 else "",
                    })

        return _make_response("container_list",
            data={"containers":containers,"runtime":runtime},
            summary={"total":len(containers),"runtime":runtime,"alert":False},
        )
    except Exception as e:
        return _error_response("container_list", e)


"""
方法: container_stats(), 容器资源用量 — CPU%/内存/网络 I/O
"""
def container_stats():
    try:
        runtime=_detect_container_runtime()
        if not runtime:
            return _make_response("container_stats",data={"stats":[]},summary={"total":0,"runtime":"none"})

        result=_run_command([runtime,"stats","--no-stream","--format","{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}\t{{.NetIO}}"], timeout=10)
        if not _cmd_ok(result):
            return _error_response("container_stats",f"{runtime} stats 执行失败")
        stats=[]
        output=result["stdout"]
        if output:
            for line in output.split("\n"):
                parts=line.split("\t")
                if len(parts)>=5:
                    stats.append({
                        "name":parts[0],
                        "cpu_percent":parts[1].replace("%","") if parts[1] else "0",
                        "mem_percent":parts[2].replace("%","") if parts[2] else "0",
                        "mem_usage":parts[3] if parts[3] else "",
                        "net_io":parts[4] if parts[4] else "",
                    })

        return _make_response("container_stats",
            data={"stats":stats,"runtime":runtime},
            summary={"total":len(stats),"runtime":runtime},
        )
    except Exception as e:
        return _error_response("container_stats", e)


"""
方法: container_inspect(), 单容器详情 — 环境变量/挂载卷/privileged/Capabilities (安全审计)
"""
def container_inspect(container_name=""):
    try:
        runtime=_detect_container_runtime()
        if not runtime:
            return _make_response("container_inspect",data={},summary={"error":"无容器运行时"})

        if not container_name:
            return _make_response("container_inspect",data={},summary={"error":"未指定容器名称"})

        result=_run_command([runtime,"inspect",container_name], timeout=10)
        if not _cmd_ok(result):
            return _error_response("container_inspect",f"{runtime} inspect 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("container_inspect",data={},summary={"error":f"容器不存在: {container_name}"})

        data=json.loads(output)
        if not data:
            return _make_response("container_inspect", data={}, summary={"error": "无数据"})

        config=data[0].get("Config", {})
        host_config=data[0].get("HostConfig", {})

        return _make_response("container_inspect",
            data={
                "id": data[0].get("Id", "")[:12],
                "name": data[0].get("Name", "").lstrip("/"),
                "image": config.get("Image", ""),
                "env_count": len(config.get("Env", [])),
                "privileged": host_config.get("Privileged", False),
                "capabilities": host_config.get("CapAdd", []),
                "mounts": [m.get("Source", "") + " → " + m.get("Destination", "") for m in data[0].get("Mounts", [])],
            },
            summary={
                "name": data[0].get("Name", "").lstrip("/"),
                "privileged": host_config.get("Privileged", False),
                "alert": host_config.get("Privileged", False),
                "alert_reason": "容器以 privileged 模式运行 — 安全风险" if host_config.get("Privileged") else "",
            },
        )
    except Exception as e:
        return _error_response("container_inspect", e)
