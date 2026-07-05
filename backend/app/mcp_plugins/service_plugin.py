"""
MCP 服务管理工具 — systemctl 操作封装

功能:
- service_control: 启停/重启/重载/启用/禁用 systemd 服务

安全护栏:
- 禁止操作关键系统服务 (sshd/auditd/systemd-journald/systemd-logind/init)
- 操作前自动记录服务当前状态
- 仅允许白名单内的 action

"""
import os
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)


#禁止操作的系统关键服务 — 停止这些服务会导致系统不可用
_PROTECTED_SERVICES={
    "sshd","ssh","openssh-server",
    "auditd",
    "systemd-journald",
    "systemd-logind",
    "dbus",
    "systemd-udevd",
    "networkd-dispatcher",
    "systemd-resolved",
    "systemd-timesyncd",
    "NetworkManager",
    "polkit",
    "init",
}

#允许的 systemctl action
_ALLOWED_ACTIONS={"start","stop","restart","reload","enable","disable","status"}

"""
方法: _get_service_status(), 获取服务当前状态

"""
def _get_service_status(service):
    r=_run_command(["systemctl","is-active",service], timeout=5)
    active=r["stdout"].strip() if _cmd_ok(r) else "unknown"
    r2=_run_command(["systemctl","is-enabled",service], timeout=5)
    enabled=r2["stdout"].strip() if _cmd_ok(r2) else "unknown"
    return {"active":active,"enabled":enabled}


# ── service_control ──

"""
方法: service_control(), 控制系统服务 (start/stop/restart/reload/enable/disable)

"""
def service_control(service="", action=""):
    try:
        if not service:
            return _error_response("service_control", ValueError("参数 service 不能为空"))
        if not action:
            return _error_response("service_control", ValueError("参数 action 不能为空"))

        #参数校验
        if action not in _ALLOWED_ACTIONS:
            return _make_response("service_control",
                data={"service":service,"action":action,"blocked":True},
                summary={"error":f"不支持的操作: {action}, 仅允许: {', '.join(sorted(_ALLOWED_ACTIONS))}"},
                risk_level="restricted",
            )

        #安全检查: 禁止操作关键服务
        if service in _PROTECTED_SERVICES:
            return _make_response("service_control",
                data={"service":service,"action":action,"blocked":True},
                summary={"error":f"安全拦截: {service} 是系统关键服务, 禁止 {action}"},
                risk_level="restricted",
            )

        #操作前记录当前状态
        pre_status=_get_service_status(service)

        #执行操作
        result=_run_command(["systemctl",action,service], timeout=15)

        if result.get("blocked"):
            return _make_response("service_control",
                data={
                    "service":service,
                    "action":action,
                    "blocked":True,
                    "pre_status":pre_status,
                },
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="restricted",
            )

        #操作后状态
        post_status=_get_service_status(service)
        success=result["exit_code"]==0

        return _make_response("service_control",
            data={
                "service":service,
                "action":action,
                "success":success,
                "pre_status":pre_status,
                "post_status":post_status,
                "stdout":result["stdout"][:500] if result["stdout"] else "",
                "stderr":result["stderr"][:500] if result["stderr"] else "",
            },
            summary={
                "service":service,
                "action":action,
                "success":success,
                "active_before":pre_status["active"],
                "active_after":post_status["active"],
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("service_control", e)
