"""
MCP 平台信息采集工具

"""

import platform
import os

#方法: 获取系统内核信息
def _get_platform_info():
    return {
        "arch": platform.machine(),         # "loongarch64" / "x86_64"
        "os": platform.system(),            # "Linux"
        "distro": _get_linux_distro(),       # "Kylin" / "Ubuntu" / ...
        "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
        "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
        "has_selinux": os.path.exists("/sys/fs/selinux"),
    }

#方法: 检查Linux发行版本    
def _get_linux_distro() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=")[1].strip().strip('"')
    except FileNotFoundError:
        pass
    
    # fallback: 检查常见发行版标志文件
    if os.path.exists("/etc/kylin-release"):
        return "kylin"
    
    return "unknown"