"""
MCP 平台信息采集工具 — psutil + /etc/os-release
"""
import platform
import os
import logging

_logger=logging.getLogger("xikiy_aiops.platform")

def _get_platform_info():
    distro = _get_linux_distro()
    result = {
        "arch": platform.machine(),
        "os": platform.system(),
        "distro": distro,
        "pkg_manager": "dnf" if os.path.exists("/usr/bin/dnf") else "apt",
        "firewall_type": "nftables" if os.path.exists("/usr/sbin/nft") else "iptables",
        "has_selinux": os.path.exists("/sys/fs/selinux"),
    }
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