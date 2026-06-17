"""
MCP 平台信息采集工具

v2: 支持 KYSDK 原生检测, 非麒麟环境回落 /etc/os-release
"""
import platform
import os
import logging

_logger=logging.getLogger("sre_agent.platform")

#方法: 获取系统内核信息
def _get_platform_info():
    #优先用 KYSDK (麒麟原生, 精度最高)
    kylin_info=_get_kylin_sdk_info()
    if kylin_info:
        return kylin_info

    #回落标准检测
    return {
        "arch": platform.machine(),
        "os": platform.system(),
        "distro": _get_linux_distro(),
        "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
        "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
        "has_selinux": os.path.exists("/sys/fs/selinux"),
    }

"""
方法: _get_kylin_sdk_info(), 通过 KYSDK 获取麒麟系统精确版本信息

返回 None 表示 SDK 不可用, 调用方应回落。
"""
def _get_kylin_sdk_info():
    try:
        from app.mcp_plugins._common import _kysdk_import
        sysinfo=_kysdk_import("SystemInfo")
        if not sysinfo:
            return None
        #KYSDK SystemInfo 提供的方法
        info={
            "arch": _safe_call(sysinfo, "get_architecture") or platform.machine(),
            "os": "Linux",
            "distro": "kylin",
            "kernel": _safe_call(sysinfo, "get_kernel_version"),
            "hostname": _safe_call(sysinfo, "get_hostname"),
            "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
            "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
            "has_selinux": os.path.exists("/sys/fs/selinux"),
            #麒麟特有字段
            "kylin_version": _safe_call(sysinfo, "get_version", 0),
            "kylin_version_detail": _safe_call(sysinfo, "get_version", 1),
            "kylin_production_line": _safe_call(sysinfo, "get_production_line"),
            "kylin_major_version": _safe_call(sysinfo, "get_major_version"),
            "kylin_minor_version": _safe_call(sysinfo, "get_minor_version"),
            "kylin_alias": _safe_call(sysinfo, "get_version_alias"),
        }
        return {k:v for k,v in info.items() if v is not None}
    except Exception as e:
        _logger.debug(f"KYSDK 平台检测失败: {e}")
        return None

#方法: 安全调用 SDK 方法, 失败返回 None
def _safe_call(obj, method_name, *args):
    try:
        method=getattr(obj, method_name, None)
        if method is None:
            return None
        return method(*args)
    except Exception:
        return None

#方法: 检查Linux发行版本
def _get_linux_distro():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=")[1].strip().strip('"')
    except FileNotFoundError:
        pass

    if os.path.exists("/etc/kylin-release"):
        return "kylin"

    return "unknown"