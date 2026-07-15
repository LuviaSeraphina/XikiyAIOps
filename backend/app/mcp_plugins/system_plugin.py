"""
MCP 系统健康感知

v3: psutil psutil + shell
"""
import os
import re
import platform
import psutil
from datetime import datetime
from app.mcp_plugins._common import(
    run_command as _run_command,
    _cmd_ok,
    make_response as _make_response,
    error_response as _error_response,
    journalctl_available,
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

v3: psutil psutil + /etc/os-release
"""
def system_info():
    try:
        plat=_detect_platform()
        hostname=platform.node()
        kernel=platform.release()
        kernel_version=platform.version()
        uptime_seconds=int(psutil.boot_time())
        boot_time=datetime.fromtimestamp(uptime_seconds).strftime("%Y-%m-%d %H:%M:%S")
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


# ── 硬件检测 ──

"""
方法: system_cpu_detail(), CPU 详细信息: 厂商/型号/频率/缓存/虚拟化/线程数

psutil + /proc/cpuinfo 解析
"""
def system_cpu_detail():
    try:
        result=_run_command(["cat", "/proc/cpuinfo"], timeout=5)
        if not _cmd_ok(result):
            return _error_response("system_cpu_detail", "读取 /proc/cpuinfo 失败")
        cpuinfo=result["stdout"]
        info={}
        for line in cpuinfo.split("\n"):
            if ":" in line:
                k,v=line.split(":",1)
                k=k.strip(); v=v.strip()
                if k in ("vendor_id","model name","cpu cores","siblings","cpu MHz","cache size"):
                    info[k]=v
                if k=="flags":
                    info["flags"]=v.split()[:15]

        return _make_response("system_cpu_detail",
            data={
                "vendor": info.get("vendor_id","unknown"),
                "model": info.get("model name","unknown"),
                "cores": int(info.get("cpu cores",0)),
                "threads": int(info.get("siblings",0)),
                "freq_mhz": info.get("cpu MHz","0"),
                "cache": info.get("cache size","unknown"),
                "flags_sample": info.get("flags",[]),
                "source": "/proc/cpuinfo",
            },
            summary={
                "model": info.get("model name","unknown")[:50],
                "cores": int(info.get("cpu cores",0)),
                "source": "/proc/cpuinfo",
            },
        )
    except Exception as e:
        return _error_response("system_cpu_detail", e)


"""
方法: system_bios_info(), BIOS 信息: 厂商/版本/日期/类型

 dmidecode (需 root)
"""
def system_bios_info():
    try:
        result=_run_command(["dmidecode", "-t", "bios"], timeout=5)
        if not _cmd_ok(result):
            return _make_response("system_bios_info",
                data={"source": "unavailable"},
                summary={"alert": False, "alert_reason": "dmidecode 不可用 (需 root), 无法获取 BIOS 信息"},
            )
        output=result["stdout"]
        info={}
        for line in output.split("\n"):
            if ":" in line:
                k,v=line.split(":",1)
                k=k.strip(); v=v.strip()
                if k in ("Vendor","Version","Release Date"):
                    info[k.lower().replace(" ","_")]=v

        return _make_response("system_bios_info",
            data={**info, "source": "dmidecode"},
            summary={"vendor": info.get("vendor","unknown"), "source": "dmidecode"},
        )
    except Exception as e:
        return _error_response("system_bios_info", e)


# ── 日志查询工具 (v0.3) ──────────────────────────────

# 日志行格式: 2024-06-15T10:30:00+0800 hostname program[pid]: message
_JOURNAL_LINE_RE=re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)$"
)


"""
方法: _parse_journal_entries(lines, keyword), 解析 journalctl -o short-iso 输出行, 可选关键词过滤

"""
def _parse_journal_entries(lines, keyword=""):
    entries=[]
    for line in lines:
        if not line.strip():
            continue
        m=_JOURNAL_LINE_RE.match(line)
        if not m:
            continue
        msg=m.group(5)
        if keyword and keyword.lower() not in msg.lower():
            continue

        entries.append({
            "timestamp": m.group(1),
            "hostname": m.group(2),
            "service": m.group(3),
            "pid": m.group(4) or "",
            "message": msg[:200],
        })
    return entries


"""
方法: system_journal_query(), 日志查询 — 按服务/时间/级别/关键词过滤

v0.3 新增: 补上感知层的最大缺口, 支持 LLM 应答"查一下系统日志"。
底层 journalctl
"""
def system_journal_query(service="", hours=1, priority="err", keyword="", max_lines=50):
    try:
        if not journalctl_available():
            return _error_response("system_journal_query", "journalctl 不可用")

        max_lines=max(1, min(max_lines, 200))
        cmd=["journalctl", "--no-pager", "-o", "short-iso", "-p", priority,
             "--since", "{}h ago".format(hours)]
        if service:
            cmd.extend(["-u", service])
        cmd.extend(["-n", str(max_lines)])

        result=_run_command(cmd, timeout=15)
        if not _cmd_ok(result):
            return _error_response("system_journal_query", "journalctl 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("system_journal_query",
                data={"entries":[], "total":0},
                summary={"total":0, "filter":{"priority":priority,"hours":hours,"service":service or "all"}},
            )

        entries=_parse_journal_entries(output.split("\n"), keyword)

        return _make_response("system_journal_query",
            data={
                "entries": entries[:max_lines],
                "total": len(entries),
                "filter": {"service": service or "all", "hours": hours, "priority": priority, "keyword": keyword or ""},
            },
            summary={
                "total": min(len(entries), max_lines),
                "total_matched": len(entries),
                "service": service or "all",
                "priority": priority,
                "hours": hours,
            },
        )
    except Exception as e:
        return _error_response("system_journal_query", e)


"""
方法: system_journal_tail(), 实时日志快照 — 最新 N 条日志

与 query 的区别: 不按时间范围过滤, 直接取最新 N 条。
适合 LLM 快速应答"现在系统在报什么"。
"""
def system_journal_tail(lines=20, priority="err"):
    try:
        if not journalctl_available():
            return _error_response("system_journal_tail", "journalctl 不可用")

        n=max(1, min(lines, 100))
        cmd=["journalctl", "--no-pager", "-o", "short-iso", "-p", priority, "-n", str(n)]

        result=_run_command(cmd, timeout=10)
        if not _cmd_ok(result):
            return _error_response("system_journal_tail", "journalctl 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("system_journal_tail",
                data={"entries":[], "lines_requested":n},
                summary={"total":0, "priority":priority, "lines":n},
            )

        entries=_parse_journal_entries(output.split("\n"))

        return _make_response("system_journal_tail",
            data={"entries":entries, "priority":priority, "lines_requested":n},
            summary={"total":len(entries), "priority":priority, "lines":n},
        )
    except Exception as e:
        return _error_response("system_journal_tail", e)


# ── vmstat_stats: 虚拟内存/IO/上下文切换/进程统计 ──
"""
方法: vmstat_stats(intervals=1,count=3), 虚拟内存统计 (vmstat): CPU/IO/swap/上下文切换/中断采样

"""
def vmstat_stats(intervals=1,count=3):
    try:
        intervals=int(max(1,min(intervals,5)))
        count=int(max(1,min(count,10)))
        timeout_s=intervals*count+5
        result=_run_command(["vmstat",str(intervals),str(count)],timeout=timeout_s)
        if not _cmd_ok(result):
            return _error_response("vmstat_stats","vmstat 执行失败")
        stdout=result.get("stdout","")
        lines=[l for l in stdout.strip().split("\n") if l.strip()]
        #vmstat 输出: 第1行=header, 第2行=平均, 第3行起=采样
        #字段: r b swpd free buff cache si so bi bo in cs us sy id wa st
        samples=[]
        for line in lines[2:]:
            parts=line.split()
            if len(parts)>=17:
                samples.append({
                    "procs_r":int(parts[0]),"procs_b":int(parts[1]),
                    "swpd_kb":int(parts[2]),"free_kb":int(parts[3]),
                    "buff_kb":int(parts[4]),"cache_kb":int(parts[5]),
                    "si":int(parts[6]),"so":int(parts[7]),
                    "bi":int(parts[8]),"bo":int(parts[9]),
                    "in":int(parts[10]),"cs":int(parts[11]),
                    "us":int(parts[12]),"sy":int(parts[13]),
                    "id":int(parts[14]),"wa":int(parts[15]),
                    "st":int(parts[16]) if len(parts)>16 else 0,
                })
        alerts=[]
        if samples:
            last=samples[-1]
            if last["wa"]>10:
                alerts.append(f"IO等待偏高: wa={last['wa']}%")
            if last["so"]>0:
                alerts.append(f"Swap写出活跃: so={last['so']} KB/s")
            if last["cs"]>50000:
                alerts.append(f"上下文切换频繁: cs={last['cs']}/s")
            if last["procs_b"]>5:
                alerts.append(f"阻塞进程多: b={last['procs_b']}")
            if last["id"]<10:
                alerts.append(f"CPU空闲率低: id={last['id']}%")
        return _make_response("vmstat_stats",
            data={"samples":samples,"sample_count":len(samples),"interval":intervals},
            summary={
                "samples":len(samples),
                "cpu_idle":samples[-1]["id"] if samples else -1,
                "iowait":samples[-1]["wa"] if samples else -1,
                "context_switch":samples[-1]["cs"] if samples else 0,
                "swap_in":samples[-1]["si"] if samples else 0,
                "swap_out":samples[-1]["so"] if samples else 0,
                "alerts":alerts,
            },
        )
    except Exception as e:
        return _error_response("vmstat_stats",e)


# ── system_timers: systemd 定时器列表 ──
"""
方法: system_timers(), 列出 systemd 定时器: 名称/下次触发/上次触发/关联服务

"""
def system_timers():
    try:
        result=_run_command(["systemctl","list-timers","--all","--no-pager","--no-legend"],timeout=10)
        if not _cmd_ok(result):
            return _error_response("system_timers","systemctl list-timers 执行失败")
        stdout=result.get("stdout","")
        timers=[]
        for line in stdout.strip().split("\n"):
            line=line.strip()
            if not line or line.startswith("-"):
                continue
            #用正则提取 .timer 和 .service unit 名
            unit_match=re.search(r'(\S+\.timer)\s+(\S+\.service)',line)
            if unit_match:
                timers.append({"unit":unit_match.group(1),"activates":unit_match.group(2)})
            else:
                if line.endswith(".service"):
                    continue
                unit_match2=re.search(r'(\S+\.timer)',line)
                if unit_match2:
                    timers.append({"unit":unit_match2.group(1),"activates":""})
        return _make_response("system_timers",
            data={"timers":timers},
            summary={"total":len(timers),"units":[t["unit"] for t in timers[:10]]},
        )
    except Exception as e:
        return _error_response("system_timers",e)
