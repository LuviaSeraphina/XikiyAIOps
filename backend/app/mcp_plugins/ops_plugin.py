"""
MCP 运维操作工具 — 文件识别/读取/截断/清理/日志轮转

功能:
- file_identify: 识别文件类型/被谁打开/是否关键文件
- file_read: 安全读取文件内容 (路径白名单 + 行数限制)
- file_truncate: 安全截断大日志 (排除数据库/WAL)
- disk_cleanup: 一键清理 (journal/缓存/core/tmp)
- logrotate_force: 强制日志轮转

"""
import os
import re
import time
from pathlib import Path
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)


#关键文件后缀 — 禁止截断/删除
_CRITICAL_EXTENSIONS={
    ".db",".sqlite",".sqlite3",".wal",".shm",".journal",
    ".lock",".pid",".sock",
}

#关键文件正则
_CRITICAL_PATTERNS=[
    re.compile(r"mysql-bin\.\d+"),
    re.compile(r"ib_logfile\d+"),
    re.compile(r"ibdata\d*"),
    re.compile(r"pg_wal"),
]

#系统关键文件 — 绝不能截断/删除
_CRITICAL_SYSTEM_FILES={
    "/etc/shadow","/etc/shadow-","/etc/gshadow","/etc/passwd","/etc/group",
    "/etc/sudoers","/etc/sudoers.d","/etc/crontab",
    "/etc/ssh/sshd_config","/etc/ssh/ssh_config",
    "/boot","/boot/grub","/boot/efi",
}

#file_read 允许的路径前缀
_READ_ALLOWED_PREFIXES=["/etc/","/var/log/","/var/cache/","/proc/","/sys/","/tmp/"]

# ── 内部工具 ──

def _is_critical_file(filepath):
    """判断文件是否为关键系统文件 (数据库/WAL/锁文件/系统关键配置)"""
    real=os.path.realpath(filepath)
    #系统关键文件
    if real in _CRITICAL_SYSTEM_FILES:
        return True, f"系统关键路径: {real}"
    for protected in _CRITICAL_SYSTEM_FILES:
        if real.startswith(protected+"/"):
            return True, f"系统关键目录内: {protected}"
    basename=os.path.basename(real).lower()
    ext=os.path.splitext(basename)[1]
    if ext in _CRITICAL_EXTENSIONS:
        return True, f"关键文件扩展名: {ext}"
    for pattern in _CRITICAL_PATTERNS:
        if pattern.search(real):
            return True, f"匹配关键文件模式: {pattern.pattern}"
    return False, ""

def _get_open_by(filepath):
    """获取打开指定文件的进程列表 (lsof)"""
    result=_run_command(["lsof","-t",filepath], timeout=5)
    if result["exit_code"]!=0 or not result["stdout"]:
        return []
    pids=[p.strip() for p in result["stdout"].split("\n") if p.strip()]
    procs=[]
    for pid in pids[:10]:#最多10个
        r=_run_command(["ps","-p",pid,"-o","pid,comm,stat","--no-headers"], timeout=3)
        if r["exit_code"]==0 and r["stdout"]:
            parts=r["stdout"].split(None,2)
            if len(parts)>=2:
                procs.append({"pid":int(parts[0]),"name":parts[1],"stat":parts[2] if len(parts)>2 else ""})
    return procs


# ── 1. file_identify ──

"""
方法: file_identify(), 识别文件类型/MIME/大小/被谁打开/是否关键文件

"""
def file_identify(path=""):
    try:
        if not path:
            return _error_response("file_identify", ValueError("参数 path 不能为空"))

        #安全校验: 路径规范化
        real_path=os.path.realpath(path)
        if not os.path.exists(real_path):
            return _make_response("file_identify",
                data={"path":real_path,"exists":False},
                summary={"error":f"文件不存在: {real_path}"},
                risk_level="read_only",
            )

        st=os.stat(real_path)
        #文件大小
        size_bytes=st.st_size
        size_mb=round(size_bytes / 1048576, 2)

        #文件类型 (file 命令)
        ft=_run_command(["file","--brief","--mime-type",real_path], timeout=5)
        mime=ft["stdout"] if ft["exit_code"]==0 else "unknown"

        #是否关键文件
        is_critical, critical_reason=_is_critical_file(real_path)

        #被谁打开
        open_by=_get_open_by(real_path)

        #修改时间
        mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))

        return _make_response("file_identify",
            data={
                "path":real_path,
                "exists":True,
                "is_file":os.path.isfile(real_path),
                "is_dir":os.path.isdir(real_path),
                "is_symlink":os.path.islink(real_path),
                "size_bytes":size_bytes,
                "size_mb":size_mb,
                "mime_type":mime,
                "mtime":mtime,
                "owner_uid":st.st_uid,
                "owner_gid":st.st_gid,
                "is_critical":is_critical,
                "critical_reason":critical_reason,
                "open_by_processes":open_by,
                "open_by_count":len(open_by),
            },
            summary={
                "path":real_path,
                "size_mb":size_mb,
                "mime_type":mime,
                "is_critical":is_critical,
                "open_by_count":len(open_by),
                "safe_to_truncate":not is_critical and size_bytes>104857600,
            },
            risk_level="read_only",
        )
    except Exception as e:
        return _error_response("file_identify", e)


# ── 2. file_read ──

"""
方法: file_read(), 安全读取文件内容 (路径白名单 + 行数限制)

"""
def file_read(path="", max_lines=200):
    try:
        if not path:
            return _error_response("file_read", ValueError("参数 path 不能为空"))
        if max_lines<1 or max_lines>1000:
            max_lines=200

        real_path=os.path.realpath(path)

        #路径白名单校验
        allowed=False
        for prefix in _READ_ALLOWED_PREFIXES:
            if real_path.startswith(prefix):
                allowed=True
                break
        if not allowed:
            return _make_response("file_read",
                data={"path":real_path,"blocked":True},
                summary={"error":f"路径 {real_path} 不在允许读取的目录白名单内"},
                risk_level="read_only",
            )

        if not os.path.isfile(real_path):
            return _error_response("file_read", FileNotFoundError(f"文件不存在: {real_path}"))

        #读取内容
        lines=[]
        total_lines=0
        with open(real_path, "r", errors="replace") as f:
            for line in f:
                total_lines+=1
                if len(lines)<max_lines:
                    lines.append(line.rstrip("\n"))

        return _make_response("file_read",
            data={
                "path":real_path,
                "content":lines,
                "lines_read":len(lines),
                "total_lines":total_lines,
                "truncated":total_lines>max_lines,
            },
            summary={
                "path":real_path,
                "lines_read":len(lines),
                "total_lines":total_lines,
                "truncated":total_lines>max_lines,
            },
            risk_level="read_only",
        )
    except PermissionError:
        return _make_response("file_read",
            data={"path":path,"blocked":True},
            summary={"error":"权限不足, 无法读取该文件"},
            risk_level="read_only",
        )
    except Exception as e:
        return _error_response("file_read", e)


# ── 3. file_truncate ──

"""
方法: file_truncate(), 安全截断大日志 (保留 inode, 排除数据库/WAL)

"""
def file_truncate(path=""):
    try:
        if not path:
            return _error_response("file_truncate", ValueError("参数 path 不能为空"))

        real_path=os.path.realpath(path)
        if not os.path.isfile(real_path):
            return _error_response("file_truncate", FileNotFoundError(f"文件不存在: {real_path}"))

        #安全检查: 禁止截断关键文件 (必须在尺寸检查之前执行)
        is_critical, critical_reason=_is_critical_file(real_path)
        if is_critical:
            return _make_response("file_truncate",
                data={"path":real_path,"blocked":True,"reason":critical_reason},
                summary={"error":f"安全拦截: 拒绝截断关键文件 — {critical_reason}"},
                risk_level="restricted",
            )

        #文件大小
        old_size=os.path.getsize(real_path)
        if old_size<1048576:    #<1MB 没必要截断
            return _make_response("file_truncate",
                data={"path":real_path,"old_size_bytes":old_size,"truncated":False},
                summary={"info":f"文件大小 {old_size} 字节, 无需截断"},
                risk_level="restricted",
            )

        #执行截断: truncate -s 0 保留 inode
        result=_run_command(["truncate","-s","0",real_path], timeout=5)
        if result.get("blocked"):
            return _make_response("file_truncate",
                data={"path":real_path,"blocked":True},
                summary={"error":result["stderr"]},
                risk_level="restricted",
            )

        if result["exit_code"]!=0:
            return _make_response("file_truncate",
                data={"path":real_path,"blocked":True},
                summary={"error":result["stderr"] or "truncate 命令执行失败"},
                risk_level="restricted",
            )

        new_size=os.path.getsize(real_path)
        freed_mb=round((old_size - new_size) / 1048576, 2)

        return _make_response("file_truncate",
            data={
                "path":real_path,
                "old_size_bytes":old_size,
                "new_size_bytes":new_size,
                "freed_mb":freed_mb,
                "truncated":True,
            },
            summary={
                "path":real_path,
                "freed_mb":freed_mb,
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("file_truncate", e)


# ── 4. disk_cleanup ──

"""
方法: disk_cleanup(), 一键清理: journal vacuum + 包缓存 + /tmp 旧文件 + core dump

"""
def disk_cleanup(cleanup_journal=True, cleanup_pkg_cache=True, cleanup_tmp=True, cleanup_core=True):
    try:
        results=[]
        total_freed=0

        # ── 1. journalctl vacuum ──
        if cleanup_journal:
            r=_run_command(["journalctl","--vacuum-time=3d"], timeout=30)
            if _cmd_ok(r):
                results.append({"target":"journal","status":"ok","detail":r["stdout"][:200]})
                #尝试提取释放量
                m=re.search(r"Freed\s+([\d.]+)\s+(\w+)", r["stdout"], re.IGNORECASE)
                if m:
                    val=float(m.group(1))
                    unit=m.group(2).upper()
                    if "G" in unit:
                        total_freed+=round(val*1024, 1)
                    elif "M" in unit:
                        total_freed+=round(val, 1)
                    elif "K" in unit:
                        total_freed+=round(val/1024, 2)
            else:
                results.append({"target":"journal","status":"fail","detail":r["stderr"][:200]})

        # ── 2. 包管理器缓存清理 ──
        if cleanup_pkg_cache:
            #尝试 apt
            r=_run_command(["apt","clean"], timeout=15)
            if r["exit_code"]==0 and not r.get("blocked"):
                results.append({"target":"apt_cache","status":"ok","detail":"apt clean 完成"})
            else:
                #尝试 dnf/yum
                for mgr in ["dnf","yum"]:
                    r=_run_command([mgr,"clean","all"], timeout=15)
                    if r["exit_code"]==0 and not r.get("blocked"):
                        results.append({"target":f"{mgr}_cache","status":"ok","detail":f"{mgr} clean all 完成"})
                        break
                else:
                    results.append({"target":"pkg_cache","status":"skip","detail":"无可用包管理器"})

        # ── 3. /tmp 旧文件 (>7天) ──
        if cleanup_tmp:
            r=_run_command(["find","/tmp","-type","f","-atime","+7","-delete"], timeout=15)
            if _cmd_ok(r):
                results.append({"target":"/tmp","status":"ok","detail":"已清理 7天以上未访问的临时文件"})
            else:
                results.append({"target":"/tmp","status":"fail","detail":r["stderr"][:200]})

        # ── 4. core dump 清理 ──
        if cleanup_core:
            for core_path in ["/var/crash","/var/lib/systemd/coredump","/core"]:
                if os.path.isdir(core_path):
                    r=_run_command(["find",core_path,"-name","core*","-type","f","-delete"], timeout=10)
                    if _cmd_ok(r):
                        results.append({"target":core_path,"status":"ok","detail":"core dump 已清理"})
                elif os.path.exists(core_path):
                    results.append({"target":core_path,"status":"skip","detail":"路径不存在"})

        return _make_response("disk_cleanup",
            data={
                "results":results,
                "total_freed_mb_approx":total_freed,
            },
            summary={
                "targets_cleaned":len(results),
                "journal_freed_mb":total_freed,
                "results":results,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("disk_cleanup", e)


# ── 5. logrotate_force ──

"""
方法: logrotate_force(), 对指定路径强制日志轮转

"""
def logrotate_force(path=""):
    try:
        if not path:
            return _error_response("logrotate_force", ValueError("参数 path 不能为空"))

        real_path=os.path.realpath(path)

        #安全检查
        is_critical, critical_reason=_is_critical_file(real_path)
        if is_critical:
            return _make_response("logrotate_force",
                data={"path":real_path,"blocked":True,"reason":critical_reason},
                summary={"error":f"安全拦截: 拒绝轮转关键文件 — {critical_reason}"},
                risk_level="restricted",
            )

        if not os.path.isfile(real_path):
            return _error_response("logrotate_force", FileNotFoundError(f"文件不存在: {real_path}"))

        #轮转前文件大小
        old_size=os.path.getsize(real_path)

        #执行 logrotate -f (需要配置文件, 用 /etc/logrotate.d/ 或 --force)
        #先查找是否有对应的 logrotate 配置
        lr_config=""
        config_dir="/etc/logrotate.d"
        if os.path.isdir(config_dir):
            #搜索包含该路径的配置
            r=_run_command(["find",config_dir,"-type","f"], timeout=5)
            if _cmd_ok(r):
                for cfg in r["stdout"].split("\n"):
                    cfg=cfg.strip()
                    if cfg and os.path.isfile(cfg):
                        try:
                            with open(cfg,"r",errors="replace") as f:
                                content=f.read()
                            #简单检查配置是否涉及该路径
                            if real_path in content or os.path.dirname(real_path) in content:
                                lr_config=cfg
                                break
                        except (PermissionError, OSError):
                            pass

        if lr_config:
            #有配置: 执行 logrotate -f 配置文件
            result=_run_command(["logrotate","-f",lr_config], timeout=15)
        else:
            #无配置: 创建临时配置并执行
            tmp_cfg="/tmp/xikiy_logrotate_tmp"
            try:
                with open(tmp_cfg,"w") as f:
                    f.write(f"{real_path} {{\n  rotate 3\n  compress\n  missingok\n  notifempty\n  copytruncate\n}}\n")
                result=_run_command(["logrotate","-f",tmp_cfg], timeout=15)
            finally:
                if os.path.exists(tmp_cfg):
                    try:
                        os.unlink(tmp_cfg)
                    except OSError:
                        pass

        if result.get("blocked"):
            return _make_response("logrotate_force",
                data={"path":real_path,"blocked":True},
                summary={"error":result["stderr"]},
                risk_level="restricted",
            )

        if result["exit_code"]!=0:
            return _make_response("logrotate_force",
                data={"path":real_path,"failed":True},
                summary={"error":result["stderr"] or "logrotate 执行失败"},
                risk_level="restricted",
            )

        new_size=os.path.getsize(real_path) if os.path.exists(real_path) else 0
        freed_mb=round((old_size - new_size) / 1048576, 2)

        return _make_response("logrotate_force",
            data={
                "path":real_path,
                "config_used":lr_config or "auto-generated",
                "old_size_bytes":old_size,
                "new_size_bytes":new_size,
                "freed_mb":freed_mb,
                "success":True,
            },
            summary={
                "path":real_path,
                "freed_mb":freed_mb,
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("logrotate_force", e)
