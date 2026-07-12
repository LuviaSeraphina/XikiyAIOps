"""
MCP 安全态势感知插件

提供九项安全检查能力：

1. security_auth_failures      — 多源认证失败统计(SSH/su/sudo/PAM)
2. security_active_sessions    — 活跃登录会话 & SSH 连接枚举
3. security_suid_scan          — SUID/SGID 后门文件扫描
4. security_crontab_audit      — 用户定时任务审计(持久化检测)
5. security_kernel_modules     — 内核模块审计(Rootkit 检测)
6. security_pending_updates    — 安全更新检测(dnf/apt)
7. security_user_audit         — 用户与权限审计(空密码/UID=0/NOPASSWD)
8. security_sysctl_audit       — 内核安全参数审计(ASLR/ptrace/转发)
9. user_list                   — 用户与组查询(只读)

数据源优先级: journalctl > /var/log/auth.log(自动降级)
所有操作均为只读(risk_level: read_only)，适合 MCP Agent 安全巡检调用。
返回统一 JSON 结构：{tool, timestamp, risk_level, data, summary}

"""

import os
import re
import pwd
import psutil
from datetime import datetime
from collections import Counter
from app.mcp_plugins._common import (
    make_response as _make_response,
    run_command as _run_command,
    _cmd_ok,
    journalctl_available as _journalctl_available,
    read_log_file as _read_log_file,
    error_response as _error_response,
    alert_if as _alert_if,
    _kysdk_available,
    _kysdk_import,
)

_AUTH_FAILURE_PATTERNS=[
    (re.compile(r"sshd\[\d+\]:\s*(Failed password|Authentication failure).*?(?:for|user)\s+(\S+)\s+from\s+(\S+)"), "ssh", "user", "ip"),
    (re.compile(r"sshd\[\d+\]:\s*(Connection closed by authenticating user|Connection reset by).*?(\d+\.\d+\.\d+\.\d+)"), "ssh_abort", "unknown", "ip"),
    (re.compile(r"su\[\d+\]:\s*pam_unix\(su.*?\):\s*authentication failure.*?ruser=(\S+).*?user=(\S+)"), "su_pam", "ruser", "target_user"),
    (re.compile(r"su\[?\d*\]?:\s*FAILED SU\s*\(to\s+(\S+)\)\s+(\S+)\s+on"), "su", "target_user", "who"),
    (re.compile(r"su:\s*FAILED SU.*?for\s+(\S+)\s+by\s+(\S+)"), "su", "target_user", "who"),
    (re.compile(r"sudo\[?\d*\]?:\s*(\S+)\s*:\s*(.*?)\s*;\s*.*?incorrect password"), "sudo", "who", "message"),
    (re.compile(r"sudo:\s*pam_unix\(sudo:auth\):\s*authentication failure.*?user=(\S+)"), "sudo_pam", "user", "source"),
    (re.compile(r"(login|gdm-password|lightdm|polkit)\[\d+\]:.*?(?:authentication failure|FAILED LOGIN).*?(?:user|for user)\s+(\S+)"), "pam", "user", "service"),
    (re.compile(r"(?:fail2ban\.\w+|pam_tally2?|pam_faillock)\[?\d*\]?:\s*(?:Ban|block|deny|lock).*?(?:\d+\.\d+\.\d+\.\d+|\S+)"), "ban", "raw", "ip"),
    (re.compile(r"FAILED.*?(?:user[= ]?(\S+))?"), "generic", "user", "raw"),
]

#方法: 从 journalctl 提取认证失败记录
def _parse_journalctl_auth(hours=24):
    since=f"{hours}h ago"
    result=_run_command([
        "journalctl","--no-pager","-o","cat",
        "-t","sshd","-t","sudo","-t","su","-t","login",
        "-t","systemd-logind","-t","polkit",
        "-t","fail2ban","-t","pam_tally2","-t","pam_faillock",
        "--since",since,
    ], timeout=15)
    if not _cmd_ok(result):
        return None
    output=result["stdout"]
    if not output:
        return []
    return _match_auth_lines(output.split("\n"))

#方法: 从传统 /var/log/auth.log 和 /var/log/secure 提取认证失败记录
def _parse_auth_log(hours=24):
    log_paths=["/var/log/auth.log","/var/log/secure"]
    all_lines=[]
    for p in log_paths:
        lines=_read_log_file(p, max_lines=3000)
        all_lines.extend(lines)
    if not all_lines:
        return []
    return _match_auth_lines(all_lines)

#方法: 对日志行列表进行多模式正则匹配, 返回结构化失败记录
def _match_auth_lines(lines):
    records=[]
    for line in lines:
        if not line:
            continue
        for pattern, fail_type, user_field, extra_field in _AUTH_FAILURE_PATTERNS:
            m=pattern.search(line)
            if m:
                groups=m.groupdict()
                user=groups.get(user_field, m.group(2) if m.lastindex and m.lastindex>=2 else "unknown")
                ip_or_source=groups.get(extra_field, m.group(3) if m.lastindex and m.lastindex>=3 else "local")
                records.append({
                    "type": fail_type,
                    "user": user if user else "unknown",
                    "source": ip_or_source if ip_or_source else "local",
                    "raw": line[:200],
                })
                break
    return records

"""
方法: security_auth_failures(), 多源登录失败检测

v2: KYSDK AuditLog 优先 (麒麟原生, 零 shell 注入), 回落 journalctl/auth.log
统计近 hours 小时内的登录失败事件, 返回按 IP/用户聚合的计数和细分类别"
"""
def security_auth_failures(hours=24):
    try:
        #优先 KYSDK AuditLog (麒麟原生)
        AuditLog=_kysdk_import("AuditLog")
        if AuditLog:
            try:
                audit=AuditLog()
                failed_attempts=audit.get_failed_attempts()
                user_logins=audit.get_user_logins("*")
                if failed_attempts is not None:
                    return _make_response("security_auth_failures",
                        data={
                            "failed_attempts": failed_attempts if isinstance(failed_attempts, list) else [failed_attempts],
                            "recent_logins": user_logins if isinstance(user_logins, list) else [user_logins],
                            "source": "kysdk.AuditLog",
                        },
                        summary={
                            "total_failures": len(failed_attempts) if isinstance(failed_attempts, list) else 0,
                            "source": "kysdk.AuditLog",
                            "hours": hours,
                        },
                    )
            except Exception:
                pass  #KYSDK 失败, 回落 shell

        #回落 journalctl / auth.log
        if _journalctl_available():
            records=_parse_journalctl_auth(hours)
            source="journalctl"
            if records is None:
                records=_parse_auth_log(hours)
                source="auth.log"
        else:
            records=_parse_auth_log(hours)
            source="auth.log"

        if not records:
            return _make_response("security_auth_failures",
                data={"failed_ips":{},"failed_users":{},"by_type":{}},
                summary={"total_failures":0,"source":source},
            )

        ip_counter=Counter(r["source"] for r in records if r["source"]!="local" and re.match(r"\d+\.\d+",r["source"]))
        user_counter=Counter(r["user"] for r in records if r["user"]!="unknown")
        type_counter=Counter(r["type"] for r in records)

        return _make_response("security_auth_failures",
            data={
                "failed_ips":dict(ip_counter.most_common(20)),
                "failed_users":dict(user_counter.most_common(20)),
                "by_type":dict(type_counter),
            },
            summary={
                "total_failures":len(records),
                "unique_ips":len(ip_counter),
                "unique_users":len(user_counter),
                "source":source,
                "hours":hours,
            },
        )
    except Exception as e:
        return _error_response("security_auth_failures", e)

"""
方法: security_active_sessions(), 活跃会话枚举, 解析 who -u 输出, 返回登录会话列表

"""
def _parse_who_output():
    result=_run_command(["who", "-u"], timeout=5)
    if not _cmd_ok(result):
        return None
    output=result["stdout"]
    if not output:
        return []

    sessions=[]
    for line in output.split("\n"):
        parts=line.split()
        if len(parts)>=5:
            sessions.append({
                "user": parts[0],
                "terminal": parts[1],
                "login_time": f"{parts[2]} {parts[3]}",
                "pid": parts[4].replace(".", ""),
                "from_ip": parts[5].strip("()") if len(parts)>=6 else "local",
            })
    return sessions

#方法: 从 ss 获取 ESTABLISHED 的 SSH 连接
def _parse_ssh_connections():
    result=_run_command(["ss", "-tnp", "state", "established", "dport", "=", ":22"], timeout=5)
    if not _cmd_ok(result):
        return None
    output=result["stdout"]
    if not output:
        return []
    connections=[]
    for line in output.split("\n")[1:]:
        parts=line.split()
        if len(parts)>=5:
            remote=parts[4] if ":" in parts[4] else parts[3]
            connections.append({"remote": remote, "state": "ESTABLISHED"})
    return connections

"""
方法: security_active_sessions(), 返回当前所有活跃登录会话和 SSH 连接

"""
def security_active_sessions():
    try:
        sessions=_parse_who_output()
        if sessions is None:
            return _error_response("security_active_sessions","who -u 执行失败")
        ssh_conns=_parse_ssh_connections()
        if ssh_conns is None:
            return _error_response("security_active_sessions","ss -tnp state established dport=:22 执行失败")
        return _make_response("security_active_sessions",
            data={
                "sessions":sessions,
                "ssh_connections":ssh_conns,
            },
            summary={
                "active_sessions":len(sessions),
                "active_ssh":len(ssh_conns),
                "alert":len(sessions)>10 or len(ssh_conns)>20,
            },
        )
    except Exception as e:
        return _error_response("security_active_sessions", e)

_KNOWN_SUID_BINARIES={
    "passwd", "sudo", "su", "ping", "mount", "umount", "newgrp",
    "chsh", "chfn", "gpasswd", "pkexec", "polkit-agent-helper-1",
    "fusermount", "fusermount3", "unix_chkpwd", "ssh-keysign",
    "Xorg", "Xorg.wrap", "dbus-daemon-launch-helper", "pam_extrausers_chkpwd",
    "wall", "write", "chage", "expiry", "bsd-write",
}

#方法: 扫描指定目录下的 SUID/SGID 文件, 标记非白名单文件
def _scan_suid(paths):
    results=[]
    failed_paths=[]
    for scan_path in paths:
        if not os.path.isdir(scan_path):
            continue
        result=_run_command([
            "find", scan_path, "-maxdepth", "3",
            "-type", "f", "(", "-perm", "-4000", "-o", "-perm", "-2000", ")",
            "-ls",
        ], timeout=30)
        if not _cmd_ok(result):
            failed_paths.append(scan_path)
            continue
        output=result["stdout"]
        if not output:
            continue
        for line in output.split("\n"):
            parts=line.split()
            if len(parts)<11:
                continue
            try:
                perms=parts[2]
                owner=parts[4]
                filepath=parts[10]
                basename=os.path.basename(filepath)
                is_suid="s" in perms[3] or "s" in perms[2]
                is_sgid="s" in perms[6] or "s" in perms[5]
                suspicious=basename not in _KNOWN_SUID_BINARIES
                results.append({
                    "path": filepath,
                    "permissions": perms,
                    "owner": owner,
                    "group": parts[5],
                    "size_bytes": int(parts[6]),
                    "suid": is_suid,
                    "sgid": is_sgid,
                    "suspicious": suspicious,
                })
            except (IndexError, ValueError):
                continue
    return results,failed_paths

"""
方法: security_suid_scan(), SUID/SGID 后门扫描, 识别非白名单的提权文件

"""
def security_suid_scan(paths=None):
    try:
        if paths is None:
            paths=["/usr/bin", "/usr/sbin", "/bin", "/sbin", "/usr/local/bin", "/usr/local/sbin"]
        files, failed_paths=_scan_suid(paths)
        suspicious=[f for f in files if f["suspicious"]]
        if not files and failed_paths:
            return _error_response("security_suid_scan",f"find 扫描失败: {', '.join(failed_paths)}")
        return _make_response("security_suid_scan",
            data={
                "files": files,
                "suspicious_files":suspicious,
            },
            summary={
                "total_suid_sgid":len(files),
                "suspicious_count":len(suspicious),
                "scanned_paths":paths,
                "alert":len(suspicious)>0,
            },
        )
    except Exception as e:
        return _error_response("security_suid_scan", e)


#方法: 获取系统中所有有home目录的普通用户
def _get_all_users():
    users=[]
    try:
        for entry in pwd.getpwall():
            if entry.pw_uid>=1000 and entry.pw_uid<65534:
                users.append(entry.pw_name)
    except (KeyError, OSError):
        pass
    if "root" not in users:
        users.insert(0, "root")
    return users

#方法: 获取指定用户的 crontab 有效行
def _parse_crontab(user):
    result=_run_command(["crontab", "-u", user, "-l"], timeout=5)
    if not _cmd_ok(result):
        return None
    output=result["stdout"]
    if not output or "no crontab" in output.lower():
        return []
    lines=[]
    for line in output.split("\n"):
        stripped=line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines

"""
方法: security_crontab_audit(), 审计所有用户的 crontab, 检测可疑定时任务

"""
def security_crontab_audit():
    try:
        users=_get_all_users()
        all_entries=[]
        suspicious_keywords=["curl", "wget", "nc ", "netcat", "bash -i", "/dev/tcp", "/tmp/", "/var/tmp/", ".onion"]

        for user in users:
            lines=_parse_crontab(user)
            if lines is None:
                return _error_response("security_crontab_audit",f"crontab -u {user} -l 执行失败")
            for line in lines:
                suspicious=False
                matched_keywords=[]
                for kw in suspicious_keywords:
                    if kw in line.lower():
                        suspicious=True
                        matched_keywords.append(kw)
                all_entries.append({
                    "user": user,
                    "entry": line,
                    "suspicious": suspicious,
                    "matched_keywords": matched_keywords,
                })

        suspicious_entries=[e for e in all_entries if e["suspicious"]]
        return _make_response("security_crontab_audit",
            data={
                "entries": all_entries,
                "suspicious_entries": suspicious_entries,
            },
            summary={
                "total_users_checked": len(users),
                "total_entries": len(all_entries),
                "suspicious_count": len(suspicious_entries),
                "alert": len(suspicious_entries)>0,
            },
        )
    except Exception as e:
        return _error_response("security_crontab_audit", e)

_KNOWN_MODULE_PREFIXES={
    "ext", "xfs", "btrfs", "vfat", "ntfs", "nfs", "cifs", "fuse",
    "nf_", "iptable_", "ip6table_", "ebtable_", "arptable_",
    "bridge", "vxlan", "bonding", "tun", "tap", "macvlan", "ipvlan",
    "overlay", "br_netfilter", "dm_", "raid", "md_", "lvm",
    "kvm", "vfio", "vhost",
    "usb", "hid", "pci", "acpi", "ahci", "sata", "nvme",
    "sound", "snd_", "video", "drm",
    "sch_", "cls_", "act_",
    "binfmt", "loop", "sr_", "cdrom", "sg",
    "crc", "lz", "zstd", "xz_",
    "bpfilter", "vsock",
    "loongson", "loongarch", "ls_", "gsgpu",
}

#方法: 解析 lsmod 输出，识别可疑的内核模块
def _parse_lsmod():
    result=_run_command(["lsmod"],timeout=5)
    if not _cmd_ok(result):
        return None
    output=result["stdout"]
    if not output:
        return []
    modules=[]
    for line in output.split("\n")[1:]:
        parts=line.split()
        if len(parts)>=3:
            name=parts[0]
            used_by=int(parts[2]) if parts[2].isdigit() else -1
            known=any(name.startswith(p) for p in _KNOWN_MODULE_PREFIXES)
            modules.append({
                "name": name,
                "size_bytes": parts[1],
                "used_by_count": used_by,
                "known": known,
                "suspicious": not known,
            })
    return modules

"""
方法: security_kernel_modules(), 审计已加载内核模块, 识别非标准/可疑模块

"""
def security_kernel_modules():
    try:
        modules=_parse_lsmod()
        if modules is None:
            return _error_response("security_kernel_modules","lsmod 执行失败")
        suspicious=[m for m in modules if m["suspicious"]]
        return _make_response("security_kernel_modules",
            data={
                "modules":modules,
                "suspicious_modules":suspicious,
            },
            summary={
                "total_modules":len(modules),
                "suspicious_count":len(suspicious),
                "alert":len(suspicious)>3,
            },
        )
    except Exception as e:
        return _error_response("security_kernel_modules", e)


"""
方法: security_pending_updates(), 检测系统待安装的安全更新数量 (dnf/apt 自动适配)

"""
def security_pending_updates():
    try:
        #优先 dnf (麒麟/红帽系), 回退 apt (Debian 系)
        if os.path.exists("/usr/bin/dnf"):
            result=_run_command(["dnf","check-update","--security","-q"],timeout=30)
            pkg_mgr="dnf"
        elif os.path.exists("/usr/bin/apt"):
            result=_run_command(["apt","list","--upgradable","-qq"],timeout=30)
            pkg_mgr="apt"
        else:
            return _make_response("security_pending_updates",
                data={"packages": [], "pkg_manager": "unknown"},
                summary={"total": 0, "alert": False},
            )

        if not _cmd_ok(result):
            return _error_response("security_pending_updates",f"{pkg_mgr} 更新检查执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("security_pending_updates",
                data={"packages":[],"pkg_manager":pkg_mgr},
                summary={"total":0,"alert":False},
            )

        #解析更新列表, 只取包名
        packages=[]
        for line in output.split("\n"):
            line=line.strip()
            if line and not line.startswith("Last ") and not line.startswith("Listing"):
                packages.append(line.split()[0] if line.split() else line)

        alert=len(packages)>20
        return _make_response("security_pending_updates",
            data={
                "packages":packages[:50],
                "pkg_manager":pkg_mgr,
            },
            summary={
                "total":len(packages),
                "alert":alert,
                "alert_reason":_alert_if(alert,"{} 个待安装更新, 建议尽快升级",len(packages)),
            },
        )
    except Exception as e:
        return _error_response("security_pending_updates", e)

"""
方法: security_sysctl_audit(), 内核安全参数审计: ASLR/ptrace_scope/ip_forward 等

"""
def security_sysctl_audit():
    try:
        checks={
            #参数名: (期望值, 安全说明, 实际值)
            "kernel.randomize_va_space":("2","ASLR 应开启"),
            "kernel.kptr_restrict":("2","内核指针泄漏保护"),
            "kernel.dmesg_restrict":("1","非 root 禁止读 dmesg"),
            "kernel.yama.ptrace_scope":("1","限制 ptrace"),
            "net.ipv4.ip_forward":("0","IP 转发应关闭"),
            "net.ipv4.conf.all.send_redirects":("0","ICMP 重定向应关闭"),
            "net.ipv4.conf.all.accept_source_route":("0","源路由应关闭"),
            "net.ipv4.tcp_syncookies":("1","SYN Cookie 防护"),
            "net.ipv6.conf.all.disable_ipv6":("1","IPv6 如未使用应关闭"),
            "fs.protected_symlinks":("1","符号链接保护"),
            "fs.protected_hardlinks":("1","硬链接保护"),
            "fs.suid_dumpable":("0","SUID 程序 core dump"),
        }

        violations=[]
        passed=[]
        skipped=[]
        for param, (expected, description) in checks.items():
            result=_run_command(["sysctl", "-n", param], timeout=3)
            if not _cmd_ok(result):
                #单个参数读取失败不中断整个审计, 记录后继续
                skipped.append({"param":param,"reason":result.get("stderr","权限不足或参数不存在")})
                continue
            actual=result["stdout"].strip() if result["stdout"] else ""
            if actual!=expected:
                violations.append({
                    "param":param,
                    "expected":expected,
                    "actual":actual,
                    "description":description,
                })
            else:
                passed.append(param)

        return _make_response("security_sysctl_audit",
            data={
                "violations":violations,
                "passed_count":len(passed),
                "skipped":skipped,
            },
            summary={
                "total_checked":len(checks),
                "violations":len(violations),
                "passed":len(passed),
                "skipped":len(skipped),
                "alert":len(violations)>0,
                "alert_reason": _alert_if(len(violations)>0,
                "{} 个内核安全参数不符合基线",len(violations)),
            },
        )
    except Exception as e:
        return _error_response("security_sysctl_audit", e)


"""
方法: security_user_audit(), 用户与权限审计: 空密码账户 / UID=0 非 root / 无密码 sudo

"""
def security_user_audit():
    try:
        issues=[]

        #检查空密码账户 (从 /etc/shadow 第二字段)
        if os.path.exists("/etc/shadow"):
            shadow=_read_log_file("/etc/shadow", max_lines=200)
            for line in shadow:
                parts=line.split(":")
                if len(parts)>=2:
                    user=parts[0]
                    pwd_field=parts[1]
                    if pwd_field=="" and user not in ("","root"):
                        issues.append({
                            "user":user,
                            "type":"empty_password",
                            "detail":f"账户 {user} 密码字段为空, 可无密码登录",
                        })

        #检查 UID=0 的非 root 账户
        for entry in pwd.getpwall():
            if entry.pw_uid==0 and entry.pw_name!="root":
                issues.append({
                    "user":entry.pw_name,
                    "type":"uid_zero",
                    "detail":f"账户 {entry.pw_name} 的 UID=0, 具有 root 等效权限",
                })

        #检查 sudoers 中无密码 sudo 配置
        if os.path.exists("/etc/sudoers"):
            sudoers=_read_log_file("/etc/sudoers",max_lines=200)
            for line in sudoers:
                if "NOPASSWD" in line and not line.strip().startswith("#"):
                    issues.append({
                        "type":"sudo_nopasswd",
                        "detail":line.strip()[:200],
                    })

        return _make_response("security_user_audit",
        data={"issues":issues},
            summary={
            "total_issues":len(issues),
            "alert":len(issues)>0,
            "alert_reason":_alert_if(len(issues)>0,"发现 {} 个用户安全风险",len(issues)),
            },
        )
    except Exception as e:
        return _error_response("security_user_audit", e)

"""
方法: user_list(), 用户与组查询 (只读)

"""
def user_list():
    try:
        users=[]
        for entry in pwd.getpwall():
            #只列出 UID>=1000 的普通用户 + root + 系统服务账户 (如 mysql/nginx)
            if entry.pw_uid>=1000 or entry.pw_name in ("root", "mysql", "nginx", "www-data", "postgres"):
                users.append({
                    "name": entry.pw_name,
                    "uid": entry.pw_uid,
                    "gid": entry.pw_gid,
                    "home": entry.pw_dir,
                    "shell": entry.pw_shell,
                    "is_system": entry.pw_uid<1000,
                })

        #读取 /etc/group 获取组信息
        groups=[]
        if os.path.exists("/etc/group"):
            group_lines=_read_log_file("/etc/group", max_lines=100)
            for line in group_lines:
                parts=line.split(":")
                if len(parts)>=4:
                    groups.append({
                        "name": parts[0],
                        "gid": parts[2],
                        "members": parts[3].split(",") if parts[3] else [],
                    })

        return _make_response("user_list",
            data={
                "users": users,
                "groups": groups,
            },
            summary={
                "total_users": len(users),
                "total_groups": len(groups),
            },
        )
    except Exception as e:
        return _error_response("user_list", e)


"""
方法: security_open_files(top_n=10), 打开文件数 Top N — 句柄泄漏检测, FD>1000 告警

"""
def security_open_files(top_n=10):
    try:
        top_n=max(1, min(int(top_n), 50))
        procs=[]
        total_fds=0
        max_fds=0
        top_proc=None

        for proc in psutil.process_iter(['pid','name']):
            try:
                pinfo=proc.info
                nfd=proc.num_fds()
                total_fds+=nfd
                procs.append({"pid": pinfo['pid'], "name": pinfo['name'], "num_fds": nfd})
                if nfd>max_fds:
                    max_fds=nfd
                    top_proc=pinfo['name']
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

        procs.sort(key=lambda p: p['num_fds'], reverse=True)

        return _make_response("security_open_files",
            data={"processes": procs[:top_n]},
            summary={
                "total_fds": total_fds,
                "top_process": top_proc if top_proc else "N/A",
                "max_fds": max_fds,
                "alert": max_fds>1000,
                "alert_reason": _alert_if(max_fds>1000, "进程 {} FD 数 {} > 1000, 可能存在句柄泄漏", top_proc, max_fds),
            },
        )
    except Exception as e:
        return _error_response("security_open_files", e)


"""
方法: security_selinux_status(), SELinux/AppArmor 运行模式检测

v2: KYSDK Selinux 优先, 回落 /sys/fs/selinux + getenforce + aa-status
"""
def security_selinux_status():
    try:
        #优先 KYSDK Selinux (麒麟原生)
        Selinux=_kysdk_import("Selinux")
        if Selinux:
            try:
                sel=Selinux()
                se_mode=sel.get_status()
                if se_mode in ("enforcing", "permissive", "disabled"):
                    se_enabled=se_mode!="disabled"
                    return _make_response("security_selinux_status",
                        data={
                            "selinux": {"enabled": se_enabled, "mode": se_mode, "source": "kysdk.Selinux"},
                            "apparmor": {"enabled": None, "active": None},
                        },
                        summary={
                            "mac_type": "selinux" if se_enabled else "none",
                            "mode": se_mode,
                            "alert": not se_enabled,
                            "alert_reason": _alert_if(not se_enabled, "SELinux 未启用, 缺少强制访问控制 (MAC) 保护"),
                        },
                    )
            except Exception:
                pass  #KYSDK 失败, 回落 shell

        #回落 shell 检测
        se_enabled=False
        se_mode="disabled"
        se_mount=os.path.exists("/sys/fs/selinux")

        if se_mount:
            enforce="/sys/fs/selinux/enforce"
            if os.path.exists(enforce):
                try:
                    with open(enforce, "r") as fh:
                        val=fh.read().strip()
                    if val=="1":
                        se_enabled=True
                        se_mode="enforcing"
                    elif val=="0":
                        se_enabled=True
                        se_mode="permissive"
                except Exception:
                    pass

            #getenforce 补充 — 可能未安装, 失败时静默跳过
            try:
                out=_run_command(["getenforce"], timeout=5)
                if _cmd_ok(out) and out.get("stdout"):
                    ms=out["stdout"].strip().lower()
                    if ms in ("enforcing", "permissive", "disabled"):
                        se_enabled=True
                        se_mode=ms
            except Exception:
                pass

        aa_enabled=False
        aa_active=False

        #AppArmor 内核参数
        aa_param="/sys/module/apparmor/parameters/enabled"
        if os.path.exists(aa_param):
            try:
                with open(aa_param, "r") as fh:
                    if fh.read().strip()=="Y":
                        aa_enabled=True
            except Exception:
                pass

        #aa-status 命令 — 可能未安装, 失败时静默跳过
        try:
            aa_out=_run_command(["aa-status", "--enabled"], timeout=5)
            if _cmd_ok(aa_out):
                aa_active=True
                aa_enabled=True
        except Exception:
            pass

        #判断 MAC 类型
        if se_enabled and se_mode!="disabled":
            mac_type="selinux"
            mac_mode=se_mode
        elif aa_enabled or aa_active:
            mac_type="apparmor"
            mac_mode="enforcing" if aa_active else "disabled"
        else:
            mac_type="none"
            mac_mode="disabled"

        is_alert=(mac_type=="none")

        return _make_response("security_selinux_status",
            data={
                "selinux": {"enabled": se_enabled and se_mode!="disabled", "mode": se_mode, "mount_exists": se_mount},
                "apparmor": {"enabled": aa_enabled, "active": aa_active},
            },
            summary={
                "mac_type": mac_type,
                "mode": mac_mode,
                "alert": is_alert,
                "alert_reason": _alert_if(is_alert, "系统未启用 SELinux 或 AppArmor, 缺少强制访问控制 (MAC) 保护"),
            },
        )
    except Exception as e:
        return _error_response("security_selinux_status", e)


# ── KYSDK 原生工具 (麒麟 SDK 优先, 非麒麟回落 shell) ────────

"""
方法: security_password_policy(), 系统密码复杂度策略检查

KYSDK 优先 (UserAuth.get_password_policy), 回落 /etc/pam.d/* 解析
"""
def security_password_policy():
    try:
        #优先 KYSDK
        UserAuth=_kysdk_import("UserAuth")
        if UserAuth:
            try:
                auth=UserAuth()
                policy=auth.get_password_policy()
                if policy:
                    return _make_response("security_password_policy",
                        data={"policy": policy, "source": "kysdk.UserAuth"},
                        summary={"source": "kysdk.UserAuth", "alert": False},
                    )
            except Exception:
                pass

        #回落: 解析 PAM 配置
        policy={}
        for pam_file in ["/etc/pam.d/common-password", "/etc/pam.d/system-auth"]:
            if os.path.exists(pam_file):
                lines=_read_log_file(pam_file, max_lines=50)
                for line in lines:
                    stripped=line.strip()
                    if stripped and not stripped.startswith("#"):
                        policy.setdefault("raw_rules", []).append(stripped)
                        #检测关键配置
                        if "minlen" in stripped:
                            policy["min_length"]=stripped
                        if "remember" in stripped:
                            policy["history"]=stripped
                        if "retry" in stripped:
                            policy["retry"]=stripped

        if not policy:
            return _make_response("security_password_policy",
                data={"policy": {}, "source": "unavailable"},
                summary={"alert": True, "alert_reason": "未检测到密码策略配置"},
            )

        return _make_response("security_password_policy",
            data={"policy": policy, "source": "pam"},
            summary={"source": "pam", "alert": len(policy.get("raw_rules", []))==0},
        )
    except Exception as e:
        return _error_response("security_password_policy", e)


"""
方法: security_user_privilege(), 指定用户权限审计

KYSDK UserAuth 优先 (check_sudo + check_home_permission), 回落 shell
"""
def security_user_privilege(username=None):
    try:
        if not username:
            return _make_response("security_user_privilege",
                data={"users": []},
                summary={"alert": False},
                parameters={"username": "必填, 要审计的用户名"},
            )
        #输入校验: 防止路径遍历/命令注入
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9._-]{0,31}$', username):
            return _make_response("security_user_privilege",
                data={"username": username, "error": "非法用户名格式"},
                summary={"alert": False, "alert_reason": f"用户名 '{username}' 包含非法字符"},
            )

        #优先 KYSDK
        UserAuth=_kysdk_import("UserAuth")
        if UserAuth:
            try:
                auth=UserAuth()
                sudo_status=auth.check_sudo(username)
                home_status=auth.check_home_permission(username)
                if sudo_status is not None:
                    return _make_response("security_user_privilege",
                        data={
                            "username": username,
                            "sudo_access": sudo_status,
                            "home_permission": home_status,
                            "source": "kysdk.UserAuth",
                        },
                        summary={
                            "has_sudo": bool(sudo_status),
                            "source": "kysdk.UserAuth",
                            "alert": bool(sudo_status),
                            "alert_reason": _alert_if(bool(sudo_status), f"用户 {username} 具有 sudo 权限"),
                        },
                    )
            except Exception:
                pass

        #回落: root 直接返回 (root 始终有 sudo)
        if username=="root":
            return _make_response("security_user_privilege",
                data={
                    "username": "root",
                    "sudo_access": True,
                    "home_permission": "root",
                    "source": "builtin",
                },
                summary={
                    "has_sudo": True,
                    "source": "builtin",
                    "alert": True,
                    "alert_reason": "root 用户具有完全系统权限",
                },
            )

        #方法1: groups 命令
        grp_result=_run_command(["groups", username], timeout=5)
        in_sudo_group=False
        if _cmd_ok(grp_result) and grp_result.get("stdout"):
            in_sudo_group="sudo" in grp_result["stdout"] or "wheel" in grp_result["stdout"]

        #方法2: 检查 sudoers 文件
        in_sudoers=False
        if os.path.exists("/etc/sudoers"):
            sudoers_lines=_read_log_file("/etc/sudoers", max_lines=200)
            for line in sudoers_lines:
                if line.startswith(username) and not line.strip().startswith("#"):
                    in_sudoers=True
                    break

        has_sudo=in_sudo_group or in_sudoers

        return _make_response("security_user_privilege",
            data={
                "username": username,
                "sudo_access": has_sudo,
                "source": "shell",
            },
            summary={
                "has_sudo": has_sudo,
                "source": "shell",
                "alert": has_sudo,
                "alert_reason": _alert_if(has_sudo, f"用户 {username} 具有 sudo 权限"),
            },
        )
    except Exception as e:
        return _error_response("security_user_privilege", e)