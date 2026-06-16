"""
MCP 系统健康感知

覆盖系统基本信息、负载、失败服务检测、平台兼容性识别

"""
import os
import platform
import psutil
from datetime import datetime
from app.mcp_plugins._common import(
    run_command as _run_command,
    _cmd_ok,
    make_response as _make_response,
    error_response as _error_response,
)


"""
方法: _detect_platform(), 检测当前 OS 发行版和包管理器, 用于兼容麒麟/通用 Linux

"""
def _detect_platform():
    info={
        "os": platform.system(),
        "arch": platform.machine(),
        "distro": "",
        "pkg_manager": "",
        "is_kylin": False,
    }

    #读取 /etc/os-release 获取发行版信息
    release_files=["/etc/os-release", "/etc/kylin-release", "/etc/lsb-release"]
    for f in release_files:
        if os.path.exists(f):
            try:
                with open(f, "r") as fh:
                    content=fh.read()
                    for line in content.split("\n"):
                        if line.startswith("ID="):
                            info["distro"]=line.split("=")[1].strip('"')
                        elif line.startswith("PRETTY_NAME="):
                            info["display_name"]=line.split("=")[1].strip('"')
            except (PermissionError, OSError):
                pass
            break

    if not info.get("display_name"):
        info["display_name"]=f"{platform.system()} {platform.release()}"

    #检测包管理器
    if os.path.exists("/usr/bin/dnf"):
        info["pkg_manager"]="dnf"
    elif os.path.exists("/usr/bin/yum"):
        info["pkg_manager"]="yum"
    elif os.path.exists("/usr/bin/apt"):
        info["pkg_manager"]="apt"

    #检测防火墙类型
    if os.path.exists("/usr/sbin/nft"):
        info["firewall"]="nftables"
    elif os.path.exists("/usr/sbin/iptables"):
        info["firewall"]="iptables"

    #麒麟特有标记
    info["is_kylin"]=os.path.exists("/etc/kylin-release") or "kylin" in info.get("distro", "").lower()

    return info


"""
方法: system_info(), 系统概览: 主机名/内核/发行版/架构/运行时间

"""
def system_info():
    try:
        plat=_detect_platform()

        #主机名和内核
        hostname=platform.node()
        kernel=platform.release()
        kernel_version=platform.version()

        #运行时间
        uptime_seconds=int(psutil.boot_time())
        boot_time=datetime.fromtimestamp(uptime_seconds).strftime("%Y-%m-%d %H:%M:%S")

        #CPU 信息, 极端情况 cpu_count 可能返回 None
        cpu_count=psutil.cpu_count(logical=True) or 1
        cpu_physical=psutil.cpu_count(logical=False) or 1

        return _make_response("system_info",
            data={
                "hostname": hostname,
                "os": plat["display_name"],
                "distro": plat["distro"],
                "is_kylin": plat["is_kylin"],
                "kernel": kernel,
                "kernel_version": kernel_version,
                "arch": plat["arch"],
                "boot_time": boot_time,
                "cpu_cores_logical": cpu_count,
                "cpu_cores_physical": cpu_physical,
                "pkg_manager": plat["pkg_manager"],
                "firewall": plat["firewall"],
            },
            summary={
                "hostname": hostname,
                "os": plat["display_name"],
                "arch": plat["arch"],
                "is_kylin": plat["is_kylin"],
            },
        )
    except Exception as e:
        return _error_response("system_info", e)


"""
方法: system_load(), 系统负载, 含 CPU 核心数用于判断是否过载

"""
def system_load():
    try:
        load1, load5, load15=os.getloadavg()
        cpu_count=psutil.cpu_count(logical=True) or 1

        #过载判定: 1分钟负载超过 CPU 核心数
        overload=load1>cpu_count
        reason=f"1分钟负载({load1:.2f})超过 CPU 核心数({cpu_count}), 系统过载" if overload else ""

        return _make_response("system_load",
            data={
                "load_1min": round(load1, 2),
                "load_5min": round(load5, 2),
                "load_15min": round(load15, 2),
                "cpu_cores": cpu_count,
            },
            summary={
                "load_1min": round(load1, 2),
                "overload": overload,
                "alert": overload,
                "alert_reason": reason,
            },
        )
    except Exception as e:
        return _error_response("system_load", e)


"""
方法: system_failed_services(), 列出失败的系统服务 (systemctl --failed)

"""
def system_failed_services():
    try:
        result=_run_command(["systemctl", "--failed", "--no-legend", "--no-pager"], timeout=10)
        if not _cmd_ok(result):
            return _error_response("system_failed_services","systemctl --failed 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("system_failed_services",
                data={"services":[]},
                summary={"total_failed":0,"alert":False},
            )

        #解析失败服务列表
        services=[]
        for line in output.split("\n"):
            parts=line.split()
            if len(parts)>=2 and parts[0]:
                services.append({
                    "name":parts[0],
                    "load":parts[1] if len(parts)>1 else "unknown",
                    "active":parts[2] if len(parts)>2 else "unknown",
                    "description":" ".join(parts[4:]) if len(parts)>4 else "",
                })

        return _make_response("system_failed_services",
            data={"services": services},
            summary={
                "total_failed":len(services),
                "alert":len(services)>0,
                "alert_reason":f"{len(services)} 个系统服务处于失败状态" if services else "",
            },
        )
    except Exception as e:
        return _error_response("system_failed_services", e)


"""
方法: system_boot_params(), 内核启动参数审计, 检查关键安全参数

"""
def system_boot_params():
    try:
        result=_run_command(["cat", "/proc/cmdline"], timeout=5)
        params=result["stdout"].strip() if _cmd_ok(result) else ""

        #检查关键安全参数是否缺失
        checks={
            "selinux": "selinux=1" in params or "enforcing=1" in params,
            "audit": "audit=1" in params,
            "nosmt": "nosmt" in params,
            "page_poison": "page_poison=1" in params,
        }
        missing=[k for k, v in checks.items() if not v]

        return _make_response("system_boot_params",
            data={
                "raw": params,
                "security_checks": checks,
                "missing_security_params": missing,
            },
            summary={
                "params_count": len(params.split()),
                "missing_security_params": len(missing),
                "alert": len(missing)>0,
                "alert_reason":f"缺失安全启动参数: {', '.join(missing)}" if missing else "",
            },
        )
    except Exception as e:
        return _error_response("system_boot_params", e)


"""
方法: system_package_updates(), 检查可用安全更新数量 — dnf/apt 自动适配

"""
def system_package_updates():
    try:
        plat=_detect_platform()
        pkg=plat.get("pkg_manager", "")

        if pkg=="dnf":
            result=_run_command(["dnf", "check-update", "--security"], timeout=30)
            if not _cmd_ok(result):
                return _error_response("system_package_updates","dnf check-update 执行失败")
            output=result["stdout"]
            lines=[l for l in output.split("\n") if l.strip() and not l.startswith("Last metadata")]
            #排除空行和标题行
            updates=[l for l in lines if "." in l and " " in l]
            count=len(updates)
        elif pkg=="apt":
            result=_run_command(["apt", "list", "--upgradable"], timeout=15)
            if not _cmd_ok(result):
                return _error_response("system_package_updates","apt list --upgradable 执行失败")
            output=result["stdout"]
            lines=[l for l in output.split("\n") if "/" in l and "upgradable" not in l.lower()]
            count=len(lines)
        else:
            count=-1

        return _make_response("system_package_updates",
            data={
                "updates_count": count,
                "pkg_manager": pkg,
            },
            summary={
                "count": count,
                "alert": count > 10,
                "alert_reason":f"{count} 个安全更新待安装" if count>10 else "",
            },
        )
    except Exception as e:
        return _error_response("system_package_updates", e)


"""
方法: system_entropy(), 内核熵池可用量 — 读取 /proc/sys/kernel/random/entropy_avail, <500 影响 TLS/SSH

"""
def system_entropy():
    try:
        entropy_raw=_run_command(["cat", "/proc/sys/kernel/random/entropy_avail"], timeout=5)
        poolsize_raw=_run_command(["cat", "/proc/sys/kernel/random/poolsize"], timeout=5)

        entropy_avail=int(entropy_raw["stdout"].strip()) if _cmd_ok(entropy_raw) and entropy_raw["stdout"] else 0
        poolsize=int(poolsize_raw["stdout"].strip()) if _cmd_ok(poolsize_raw) and poolsize_raw["stdout"] else 0

        is_critical=entropy_avail<100
        is_low=entropy_avail<500

        if is_critical:
            reason=f"熵池严重不足 ({entropy_avail} < 100), TLS/SSH 可能阻塞"
        elif is_low:
            reason=f"熵池偏低 ({entropy_avail} < 500), 建议安装 haveged/rng-tools"
        else:
            reason=""

        return _make_response("system_entropy",
            data={
                "entropy_avail": entropy_avail,
                "poolsize": poolsize,
                "is_low": is_low,
                "is_critical": is_critical,
            },
            summary={
                "entropy_avail": entropy_avail,
                "alert": entropy_avail<500,
                "alert_reason": reason,
            },
        )
    except Exception as e:
        return _error_response("system_entropy", e)
