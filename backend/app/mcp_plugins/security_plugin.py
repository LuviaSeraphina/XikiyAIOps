"""
MCP 安全态势感知插件

"""

import os
import re
import pwd
from datetime import datetime
from collections import Counter
from app.mcp_plugins._common import (
    make_response as _make_response,
    run_command as _run_command,
    journalctl_available as _journalctl_available,
    read_log_file as _read_log_file,
    error_response as _error_response,
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
    re.compile(r"(?:fail2ban\.\w+|pam_tally2?|pam_faillock)\[?\d*\]?:\s*(?:Ban|block|deny|lock).*?(?:\d+\.\d+\.\d+\.\d+|\S+)"),
    (re.compile(r"FAILED.*?(?:user[= ]?(\S+))?"), "generic", "user", "raw"),
]

#方法: 从 journalctl 提取认证失败记录
def _parse_journalctl_auth(hours=24):
    since=f"{hours}h ago"
    output=_run_command([
        "journalctl", "--no-pager", "-o", "cat",
        "-t", "sshd", "-t", "sudo", "-t", "su", "-t", "login",
        "-t", "systemd-logind", "-t", "polkit",
        "-t", "fail2ban", "-t", "pam_tally2", "-t", "pam_faillock",
        "--since", since,
    ], timeout=15)
    if not output:
        return []
    return _match_auth_lines(output.split("\n"))

#方法: 从传统 /var/log/auth.log 和 /var/log/secure 提取认证失败记录
def _parse_auth_log(hours=24):
    log_paths=["/var/log/auth.log", "/var/log/secure"]
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
方法: security_auth_failures(), 多源登录失败检测, 统计近 hours 小时内的登录失败事件, 返回按 IP/用户聚合的计数和细分类别"
"""
def security_auth_failures(hours=24):
    try:
        if _journalctl_available():
            records=_parse_journalctl_auth(hours)
            source="journalctl"
        else:
            records=_parse_auth_log(hours)
            source="auth.log"

        if not records:
            return _make_response("security_auth_failures",
                data={"failed_ips": {}, "failed_users": {}, "by_type": {}},
                summary={"total_failures": 0, "source": source},
            )

        ip_counter=Counter(r["source"] for r in records if r["source"]!="local" and re.match(r"\d+\.\d+", r["source"]))
        user_counter=Counter(r["user"] for r in records if r["user"]!="unknown")
        type_counter=Counter(r["type"] for r in records)

        return _make_response("security_auth_failures",
            data={
                "failed_ips": dict(ip_counter.most_common(20)),
                "failed_users": dict(user_counter.most_common(20)),
                "by_type": dict(type_counter),
            },
            summary={
                "total_failures": len(records),
                "unique_ips": len(ip_counter),
                "unique_users": len(user_counter),
                "source": source,
                "hours": hours,
            },
        )
    except Exception as e:
        return _error_response("security_auth_failures", e)

"""
方法: security_active_sessions(), 活跃会话枚举, 解析 who -u 输出, 返回登录会话列表
"""
def _parse_who_output():
    output=_run_command(["who", "-u"], timeout=5)
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
    output=_run_command(["ss", "-tnp", "state", "established", "dport", "=", ":22"], timeout=5)
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
        ssh_conns=_parse_ssh_connections()
        return _make_response("security_active_sessions",
            data={
                "sessions": sessions,
                "ssh_connections": ssh_conns,
            },
            summary={
                "active_sessions": len(sessions),
                "active_ssh": len(ssh_conns),
                "alert": len(sessions)>10 or len(ssh_conns)>20,
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
    for scan_path in paths:
        if not os.path.isdir(scan_path):
            continue
        output=_run_command([
            "find", scan_path, "-maxdepth", "3",
            "-type", "f", "(", "-perm", "-4000", "-o", "-perm", "-2000", ")",
            "-ls",
        ], timeout=30)
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
    return results

"""
方法: security_suid_scan(), SUID/SGID 后门扫描, 识别非白名单的提权文件
"""
def security_suid_scan(paths=None):
    try:
        if paths is None:
            paths=["/usr/bin", "/usr/sbin", "/bin", "/sbin", "/usr/local/bin", "/usr/local/sbin"]
        files=_scan_suid(paths)
        suspicious=[f for f in files if f["suspicious"]]
        return _make_response("security_suid_scan",
            data={
                "files": files,
                "suspicious_files": suspicious,
            },
            summary={
                "total_suid_sgid": len(files),
                "suspicious_count": len(suspicious),
                "scanned_paths": paths,
                "alert": len(suspicious)>0,
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
    output=_run_command(["crontab", "-u", user, "-l"], timeout=5)
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
    output=_run_command(["lsmod"], timeout=5)
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
        suspicious=[m for m in modules if m["suspicious"]]
        return _make_response("security_kernel_modules",
            data={
                "modules": modules,
                "suspicious_modules": suspicious,
            },
            summary={
                "total_modules": len(modules),
                "suspicious_count": len(suspicious),
                "alert": len(suspicious)>3,
            },
        )
    except Exception as e:
        return _error_response("security_kernel_modules", e)