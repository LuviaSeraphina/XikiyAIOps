"""
MCP 配置管理工具 — 配置对比/备份/恢复/内核参数

功能:
- config_diff: 当前配置 vs 包默认配置/备份的差异对比
- config_backup: 备份文件到 /var/backups/xikiy/{timestamp}/
- config_restore: 从备份恢复 (恢复前自动再备份)
- sysctl_set: 设置内核参数 (仅白名单 key)

"""
import os
import time
import shutil
from datetime import datetime
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)


#备份根目录
_BACKUP_ROOT="/var/backups/xikiy"

#sysctl 白名单 — 仅允许设置这些内核参数
_SYSCTL_WHITELIST={
    "vm.swappiness",
    "vm.dirty_ratio",
    "vm.dirty_background_ratio",
    "vm.overcommit_memory",
    "vm.overcommit_ratio",
    "vm.min_free_kbytes",
    "fs.file-max",
    "fs.inotify.max_user_watches",
    "fs.inotify.max_user_instances",
    "net.core.somaxconn",
    "net.core.netdev_max_backlog",
    "net.core.rmem_max",
    "net.core.wmem_max",
    "net.ipv4.tcp_max_syn_backlog",
    "net.ipv4.tcp_fin_timeout",
    "net.ipv4.tcp_keepalive_time",
    "net.ipv4.tcp_keepalive_intvl",
    "net.ipv4.tcp_keepalive_probes",
    "net.ipv4.tcp_tw_reuse",
    "net.ipv4.ip_local_port_range",
    "net.ipv4.ip_forward",
    "net.ipv4.conf.all.rp_filter",
    "net.ipv4.conf.all.accept_redirects",
    "net.ipv4.conf.all.accept_source_route",
    "net.ipv6.conf.all.accept_redirects",
    "kernel.shmmax",
    "kernel.shmall",
    "kernel.panic",
    "kernel.pid_max",
}

def _ensure_backup_dir():
    """确保备份目录存在"""
    os.makedirs(_BACKUP_ROOT, exist_ok=True)


# ── 1. config_diff ──

"""
方法: config_diff(), 对比配置文件与包默认配置或备份的差异

"""
def config_diff(path="", compare_to=""):
    try:
        if not path:
            return _error_response("config_diff", ValueError("参数 path 不能为空"))

        real_path=os.path.realpath(path)
        if not os.path.isfile(real_path):
            return _error_response("config_diff", FileNotFoundError(f"文件不存在: {real_path}"))

        diff_target=""
        diff_source=""

        if compare_to:
            #用户指定了对比目标
            compare_real=os.path.realpath(compare_to)
            if not os.path.isfile(compare_real):
                return _error_response("config_diff", FileNotFoundError(f"对比文件不存在: {compare_real}"))
            diff_target=compare_real
            diff_source="user_specified"
        else:
            #自动查找包默认配置 (rpm -V 或 dpkg -V)
            #尝试 rpm
            r=_run_command(["rpm","-Vf",real_path], timeout=10)
            if _cmd_ok(r) and r["stdout"]:
                diff_target=""
                diff_source="rpm_verify"
                #rpm -V 输出格式: SM5DLUGTP c /path
                lines=[l.strip() for l in r["stdout"].split("\n") if l.strip()]
                changed_lines=[l for l in lines if not l.startswith(".")]
                if changed_lines:
                    return _make_response("config_diff",
                        data={
                            "path":real_path,
                            "source":"rpm_verify",
                            "has_changes":True,
                            "changes":changed_lines[:20],
                            "change_count":len(changed_lines),
                        },
                        summary={
                            "path":real_path,
                            "has_changes":True,
                            "change_count":len(changed_lines),
                        },
                        risk_level="read_only",
                    )
                else:
                    return _make_response("config_diff",
                        data={"path":real_path,"source":"rpm_verify","has_changes":False,"changes":[]},
                        summary={"path":real_path,"has_changes":False},
                        risk_level="read_only",
                    )

            #尝试 dpkg
            #先查找文件所属包
            r_pkg=_run_command(["dpkg","-S",real_path], timeout=10)
            if _cmd_ok(r_pkg) and r_pkg["stdout"]:
                #提取包名 (格式: package: /path/to/file)
                pkg_name=r_pkg["stdout"].split(":")[0].strip()
                #验证包文件完整性
                r=_run_command(["dpkg","--verify",pkg_name], timeout=15)
                diff_source="dpkg_verify"
                if r["stdout"]:
                    lines=[l.strip() for l in r["stdout"].split("\n") if real_path in l]
                    if lines:
                        return _make_response("config_diff",
                            data={
                                "path":real_path,
                                "source":"dpkg_verify",
                                "package":pkg_name,
                                "has_changes":True,
                                "changes":lines[:20],
                                "change_count":len(lines),
                            },
                            summary={
                                "path":real_path,
                                "package":pkg_name,
                                "has_changes":True,
                                "change_count":len(lines),
                            },
                            risk_level="read_only",
                        )

            #尝试查找最新备份
            if os.path.isdir(_BACKUP_ROOT):
                backups=sorted(os.listdir(_BACKUP_ROOT), reverse=True)
                for ts_dir in backups[:5]:
                    backup_path=os.path.join(_BACKUP_ROOT, ts_dir, os.path.basename(real_path))
                    if os.path.isfile(backup_path):
                        diff_target=backup_path
                        diff_source="latest_backup"
                        break

        if diff_target:
            #执行 diff
            r=_run_command(["diff","-u",diff_target,real_path], timeout=10)
            if r["exit_code"]==0:
                return _make_response("config_diff",
                    data={"path":real_path,"compare_to":diff_target,"source":diff_source,"has_changes":False,"diff":""},
                    summary={"path":real_path,"has_changes":False,"source":diff_source},
                    risk_level="read_only",
                )
            elif r["exit_code"]==1:
                #diff 输出
                diff_output=r["stdout"]
                lines=diff_output.split("\n")
                return _make_response("config_diff",
                    data={
                        "path":real_path,
                        "compare_to":diff_target,
                        "source":diff_source,
                        "has_changes":True,
                        "diff_lines":lines[:50],
                        "diff_line_count":len(lines),
                    },
                    summary={
                        "path":real_path,
                        "has_changes":True,
                        "diff_line_count":len(lines),
                        "source":diff_source,
                    },
                    risk_level="read_only",
                )
            else:
                return _error_response("config_diff", RuntimeError(r["stderr"] or "diff 执行失败"))

        #无对比目标
        return _make_response("config_diff",
            data={"path":real_path,"source":"none","has_changes":None,"reason":"未找到包默认配置或备份"},
            summary={"path":real_path,"has_changes":None,"info":"请使用 compare_to 参数指定对比文件"},
            risk_level="read_only",
        )
    except Exception as e:
        return _error_response("config_diff", e)


# ── 2. config_backup ──

"""
方法: config_backup(), 备份文件到 /var/backups/xikiy/{timestamp}/

"""
def config_backup(path="", tag=""):
    try:
        if not path:
            return _error_response("config_backup", ValueError("参数 path 不能为空"))

        real_path=os.path.realpath(path)
        if not os.path.isfile(real_path):
            return _error_response("config_backup", FileNotFoundError(f"文件不存在: {real_path}"))

        _ensure_backup_dir()

        #生成时间戳目录
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        tag_suffix=f"_{tag}" if tag else ""
        backup_dir=os.path.join(_BACKUP_ROOT, f"{timestamp}{tag_suffix}")
        os.makedirs(backup_dir, exist_ok=True)

        #复制文件
        backup_file=os.path.join(backup_dir, os.path.basename(real_path))
        shutil.copy2(real_path, backup_file)

        #记录原始路径
        meta_path=os.path.join(backup_dir, ".metadata")
        with open(meta_path,"w") as f:
            f.write(f"original={real_path}\n")
            f.write(f"size={os.path.getsize(real_path)}\n")
            f.write(f"mtime={os.path.getmtime(real_path)}\n")
            f.write(f"backup_time={datetime.now().isoformat()}\n")

        return _make_response("config_backup",
            data={
                "original_path":real_path,
                "backup_path":backup_file,
                "backup_dir":backup_dir,
                "size_bytes":os.path.getsize(backup_file),
                "success":True,
            },
            summary={
                "original":real_path,
                "backup":backup_file,
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("config_backup", e)


# ── 3. config_restore ──

"""
方法: config_restore(), 从备份恢复配置 (恢复前自动再备份当前版本)

"""
def config_restore(backup_path=""):
    try:
        if not backup_path:
            return _error_response("config_restore", ValueError("参数 backup_path 不能为空"))

        real_backup=os.path.realpath(backup_path)
        if not os.path.isfile(real_backup):
            return _error_response("config_restore", FileNotFoundError(f"备份文件不存在: {real_backup}"))

        #读取 metadata 获取原始路径
        backup_dir=os.path.dirname(real_backup)
        meta_path=os.path.join(backup_dir, ".metadata")
        original_path=""
        if os.path.isfile(meta_path):
            with open(meta_path,"r") as f:
                for line in f:
                    if line.startswith("original="):
                        original_path=line.strip().split("=",1)[1]
                        break

        if not original_path:
            #尝试从文件名推断
            basename=os.path.basename(real_backup)
            #常见配置目录
            for prefix in ["/etc/", "/etc/nginx/", "/etc/ssh/", "/etc/systemd/"]:
                candidate=os.path.join(prefix, basename)
                if os.path.isfile(candidate):
                    original_path=candidate
                    break

        if not original_path:
            return _error_response("config_restore", ValueError(f"无法确定原始路径, 请在 backup_path 同目录的 .metadata 中指定"))

        if not os.path.isfile(original_path):
            return _error_response("config_restore", FileNotFoundError(f"原始文件不存在: {original_path}"))

        #恢复前先备份当前版本
        pre_restore_result=config_backup(original_path, tag="pre_restore")
        if pre_restore_result.get("summary",{}).get("error"):
            return _error_response("config_restore", RuntimeError(f"恢复前备份失败: {pre_restore_result['summary']['error']}"))

        #执行恢复
        shutil.copy2(real_backup, original_path)

        return _make_response("config_restore",
            data={
                "backup_path":real_backup,
                "original_path":original_path,
                "pre_restore_backup":pre_restore_result["data"]["backup_path"],
                "size_restored":os.path.getsize(original_path),
                "success":True,
            },
            summary={
                "restored":original_path,
                "from_backup":real_backup,
                "pre_restore_backup":pre_restore_result["data"]["backup_path"],
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("config_restore", e)


# ── 4. sysctl_set ──

"""
方法: sysctl_set(), 设置内核参数 (仅白名单 key)

"""
def sysctl_set(key="", value=""):
    try:
        if not key:
            return _error_response("sysctl_set", ValueError("参数 key 不能为空"))
        if not value and value!=0:
            return _error_response("sysctl_set", ValueError("参数 value 不能为空"))

        #安全检查: 仅允许白名单参数
        if key not in _SYSCTL_WHITELIST:
            return _make_response("sysctl_set",
                data={"key":key,"value":value,"blocked":True},
                summary={"error":f"安全拦截: 参数 {key} 不在允许设置的内核参数白名单内"},
                risk_level="restricted",
            )

        #获取当前值
        r=_run_command(["sysctl","-n",key], timeout=5)
        old_value=r["stdout"].strip() if _cmd_ok(r) else "unknown"

        #设置新值
        r=_run_command(["sysctl","-w",f"{key}={value}"], timeout=5)
        if r.get("blocked"):
            return _make_response("sysctl_set",
                data={"key":key,"value":value,"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {r['stderr']}"},
                risk_level="restricted",
            )

        if r["exit_code"]!=0:
            return _make_response("sysctl_set",
                data={"key":key,"value":value,"failed":True},
                summary={"error":r["stderr"] or "sysctl -w 执行失败"},
                risk_level="restricted",
            )

        #验证设置结果
        r=_run_command(["sysctl","-n",key], timeout=5)
        new_value=r["stdout"].strip() if _cmd_ok(r) else "unknown"

        return _make_response("sysctl_set",
            data={
                "key":key,
                "old_value":old_value,
                "new_value":new_value,
                "success":True,
            },
            summary={
                "key":key,
                "old_value":old_value,
                "new_value":new_value,
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("sysctl_set", e)
