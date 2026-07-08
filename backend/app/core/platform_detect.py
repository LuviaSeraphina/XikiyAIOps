"""
MCP 平台信息采集工具

v2: 支持 KYSDK 原生检测, 非麒麟环境回落 /etc/os-release
"""
import platform
from app.mcp_plugins._common import _sdk_call
import os
import logging

_logger=logging.getLogger("xikiy_aiops.platform")

#方法: 获取系统内核信息
def _get_platform_info():
    #优先用 KYSDK (麒麟原生, 精度最高)
    kylin_info=_get_kylin_sdk_info()
    if kylin_info:
        return kylin_info

    #回落标准检测
    distro = _get_linux_distro()
    result = {
        "arch": platform.machine(),
        "os": platform.system(),
        "distro": distro,
        "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
        "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
        "has_selinux": os.path.exists("/sys/fs/selinux"),
    }
    #麒麟环境: 从 /etc/kylin-release 提取版本信息
    if distro == "kylin":
        try:
            result["kernel"] = os.uname().release
            with open("/etc/kylin-release") as f:
                content = f.read().strip()
                result["kylin_version"] = content
                if "V11" in content:
                    result["kylin_major_version"] = "11"
                elif "V10" in content:
                    result["kylin_major_version"] = "10"
        except Exception:
            pass
    return result

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
            "arch": _sdk_call(sysinfo, "get_architecture") or platform.machine(),
            "os": "Linux",
            "distro": "kylin",
            "kernel": _sdk_call(sysinfo, "get_kernel_version"),
            "hostname": _sdk_call(sysinfo, "get_hostname"),
            "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
            "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
            "has_selinux": os.path.exists("/sys/fs/selinux"),
            #麒麟特有字段
            "kylin_version": _sdk_call(sysinfo, "get_version", 0),
            "kylin_version_detail": _sdk_call(sysinfo, "get_version", 1),
            "kylin_production_line": _sdk_call(sysinfo, "get_production_line"),
            "kylin_major_version": _sdk_call(sysinfo, "get_major_version"),
            "kylin_minor_version": _sdk_call(sysinfo, "get_minor_version"),
            "kylin_alias": _sdk_call(sysinfo, "get_version_alias"),
        }
        return {k:v for k,v in info.items() if v is not None}
    except Exception as e:
        _logger.debug(f"KYSDK 平台检测失败: {e}")
        return None


#方法: 检查Linux发行版本
def _get_linux_distro():
    #优先检测麒麟标识
    if os.path.exists("/etc/kylin-release"):
        try:
            with open("/etc/kylin-release") as f:
                content = f.read().strip()
                if "V11" in content:
                    return "kylin"
                if "V10" in content:
                    return "kylin"
                if "麒麟" in content or "Kylin" in content:
                    return "kylin"
        except Exception:
            pass
    
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro = line.split("=")[1].strip().strip('"')
                    if "kylin" in distro.lower():
                        return "kylin"
                    return distro
    except FileNotFoundError:
        pass

    return "unknown"