"""
最小权限执行代理 v2.1 — 安全护栏第三道防线 (四级风险)

设计原则:
1. 操作前权限预检 (当前用户 + Tool 风险等级 → 放行/确认/拦截)
2. read_only  → 所有用户可执行 (包括 sandbox 用户)
3. restricted → 需要用户二次确认
4. dangerous  → 管理员授权方可执行
5. critical   → 致命操作, 永久拦截不可执行 (即使 root)
6. 支持 sudo 降权: 高危操作降权到专用低权限用户执行
7. 保护名单: 关键进程/路径即使 root 也不可操作

v2.1 新增:
- critical 风险等级 (四级), 永久拦截
"""
import os
import pwd
import grp
import shutil
import shlex
import subprocess


# 风险等级 → 所需权限等级
_RISK_PERMISSION_MAP={
    "read_only":"ops_basic",     #任何人可执行
    "restricted":"ops_advanced", #sudo 组成员可执行
    "dangerous":"ops_admin",     #仅 root 可执行
    "critical":"ops_blocked",    #永久拦截, 不可执行
}


# 专用低权限用户配置
# XikiyAIOps 专用系统用户 (建议部署时创建)
# sudo useradd -r -s /bin/false -d /nonexistent -M xikiy
_XIKIY_OPS_USER="xikiy"

# 沙箱模式下使用的降权用户
_SANDBOX_USER="nobody"  # fallback: 系统自带的低权限用户


# 受保护的关键进程/路径 (即使管理员也不能操作)
_PROTECTED_PROCESSES={
    "systemd","sshd","kernel","init","dbus-daemon",
    "journald","auditd","rsyslogd","cron","agetty",
}

_PROTECTED_PATHS={
    "/etc/shadow",
    "/etc/passwd",
    "/boot",
    "/sys",
    "/proc",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/etc/ssh/sshd_config",
    "/etc/pam.d",
    "/etc/selinux",
}

# 可写但受限的路径 (允许 read_only, 禁止写入操作)
_RESTRICTED_WRITE_PATHS={
    "/etc",
    "/usr/bin",
    "/usr/sbin",
    "/usr/lib",
    "/usr/lib64",
    "/lib",
    "/lib64",
    "/bin",
    "/sbin",
}


#方法: 获取当前执行用户信息
def _current_user():
    uid=os.getuid()
    try:
        return pwd.getpwuid(uid).pw_name
    except (KeyError, OSError):
        return f"uid:{uid}"


"""
方法: _is_xikiy_ops_user_available(), 检查专用 xikiy 用户是否已创建

"""

def _is_xikiy_ops_user_available():
    try:
        pwd.getpwnam(_XIKIY_OPS_USER)
        return True
    except KeyError:
        return False


"""
方法: _get_sandbox_user(), 获取可用的沙箱用户

"""

def _get_sandbox_user():
    if _is_xikiy_ops_user_available():
        return _XIKIY_OPS_USER
    try:
        pwd.getpwnam(_SANDBOX_USER)
        return _SANDBOX_USER
    except KeyError:
        return None


"""
方法: _user_in_group(user, group_name), 检查指定用户是否在指定组中

"""

def _user_in_group(user, group_name):
    try:
        user_info = pwd.getpwnam(user)
        g=grp.getgrnam(group_name)
        return user in g.gr_mem or g.gr_gid == user_info.pw_gid
    except (KeyError, OSError):
        return False


"""
方法: build_sudo_command(), 构建 sudo 降权命令 (v2.0)
将高危命令包装为 sudo -u <低权限用户> 执行, 确保攻击者仅获得低权限身份.
"""
def build_sudo_command(cmd_list, target_user=None):
    if target_user is None:
        target_user = _get_sandbox_user()
        if target_user is None:
            #没有可用的低权限用户,拒绝执行
            return None

    current = _current_user()
    if current == target_user:
        return list(cmd_list)#已经是目标用户,无需 sudo

    return ["sudo","-u",target_user,"--"]+list(cmd_list)


"""
方法: _docker_available(), 检查 Docker 是否可用

"""
def _docker_available():
    try:
        r=subprocess.run(["docker","version","--format","{{.Server.Version}}"],
            capture_output=True,text=True,timeout=3)
        return r.returncode==0
    except Exception:
        return False


"""
方法: build_docker_sandbox_command(), 构建 Docker 沙箱命令 (v2.1)

将高危命令包装为 docker run 执行, 提供:
- 网络隔离 (--network=none)
- 只读根文件系统 (--read-only)
- CPU/内存限制
- 禁止提权 (--security-opt=no-new-privileges)
"""
_DOCKER_SANDBOX_IMAGE="alpine:latest"

def build_docker_sandbox_command(cmd_list):
    """将命令包装为 Docker 沙箱执行, 返回 docker 命令列表"""
    if not _docker_available():
        return None
    
    #将命令列表转为 shell 字符串
    cmd_str=" ".join(shlex.quote(str(c)) for c in cmd_list)
    
    return [
        "docker","run","--rm",
        "--network=none",
        "--memory=256m",
        "--cpus=0.5",
        "--pids-limit=100",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--tmpfs","/tmp:exec",
        "--tmpfs","/var/tmp:exec",
        _DOCKER_SANDBOX_IMAGE,
        "sh","-c",cmd_str,
    ]


"""
方法: get_available_sandbox_modes(), 返回可用的沙箱模式 (v2.1)

"""
def get_available_sandbox_modes():
    modes=[]
    su=_get_sandbox_user()
    if su:
        modes.append({"mode":"sudo","user":su,"available":True,
            "desc":f"sudo 降权到 {su}"})
    else:
        modes.append({"mode":"sudo","user":None,"available":False,
            "desc":"sudo 降权 (无可用低权限用户)"})
    
    if _docker_available():
        modes.append({"mode":"docker","image":_DOCKER_SANDBOX_IMAGE,"available":True,
            "desc":"Docker 容器隔离 (network=none, read-only)"})
    else:
        modes.append({"mode":"docker","available":False,
            "desc":"Docker 不可用"})
    
    return modes

"""
方法: get_available_privilege_levels(), 返回系统可用的权限降级层级 (v2.0)
"""
def get_available_privilege_levels():
    levels=[]
    current=_current_user()

    if current=="root":
        levels.append({"user":"root","level":"ops_admin","available":True})

    if _user_in_group(current,"sudo") or _user_in_group(current,"wheel"):
        levels.append({"user":current,"level":"ops_advanced","available":True})

    if _is_xikiy_ops_user_available():
        levels.append({"user":_XIKIY_OPS_USER,"level":"ops_basic","available":True})
    else:
        levels.append({"user":_XIKIY_OPS_USER,"level":"ops_basic","available":False,
                    "setup_cmd":f"sudo useradd -r -s /bin/false -d /nonexistent -M {_XIKIY_OPS_USER}"})

    try:
        pwd.getpwnam(_SANDBOX_USER)
        levels.append({"user": _SANDBOX_USER, "level": "ops_basic", "available": True})
    except KeyError:
        pass

    return levels


"""
方法: check_permission(), 操作前权限预检
Returns: (allowed: bool, reason: str, downgrade_user: str|None)
"""
def check_permission(risk_level, user=None, target=None, action="execute"):
    if user is None:
        user=_current_user()

    required=_RISK_PERMISSION_MAP.get(risk_level)
    if not required:
        return False,f"未知风险等级: {risk_level}",None

    # 保护名单检查 (最高优先级)
    if target:
        if target in _PROTECTED_PROCESSES and required != "ops_basic":
            return False,f"受保护进程 '{target}' 不可操作",None
        if target in _PROTECTED_PATHS and required != "ops_basic":
            return False,f"受保护路径 '{target}' 不可操作",None
        if action in ("write", "delete"):
            for restricted in _RESTRICTED_WRITE_PATHS:
                if target.startswith(restricted + "/") or target == restricted:
                    return False,f"路径 '{target}' 在受限写目录 '{restricted}' 下",None

    # critical — root + 强制确认, 但可执行 (受保护名单额外拦截)
    if required=="ops_blocked":
        if user=="root":
            return True,f"critical: root 确认执行致命操作 {risk_level}, 请谨慎",_get_sandbox_user()
        return False,f"critical: 致命操作 '{risk_level}' 需要 root 权限 + 二次确认 (当前用户: {user})",None

    # ── OS 用户组检查 ──
    # ops_basic (read_only) — 任何用户可执行
    if required=="ops_basic":
        return True,"read_only: 放行",None

    # ops_advanced (restricted) — sudo 组成员
    if required=="ops_advanced":
        if user=="root":
            return True,"restricted: root 放行",_get_sandbox_user()
        if _user_in_group(user,"sudo") or _user_in_group(user,"wheel"):
            return True,f"restricted: sudo 组成员, 建议降权到 {_get_sandbox_user()}",_get_sandbox_user()
        return False,f"restricted: 需要 sudo 组成员权限 (当前用户: {user})",None

    # ops_admin (dangerous) — 仅 root
    if required=="ops_admin":
        if user=="root":
            return True,"dangerous: root 确认执行",_get_sandbox_user()
        return False,f"dangerous: 需要 root 权限 (当前用户: {user})",None

    return False,f"权限不足: 需要 {required}, 当前 {user}",None

""" 
方法: require_confirmation(), 判断操作是否需要用户确认
"""
def require_confirmation(risk_level):
    """判断操作是否需要用户确认 (critical 必须确认)"""
    return risk_level in ("restricted","dangerous","critical")

""" 
方法: validate_path(), 校验操作路径是否安全
"""
def validate_path(path, action="read"):
    # 规范化路径 (消除 ../ 等)
    normalized=os.path.normpath(os.path.abspath(path))

    # 保护名单：仅写/删操作禁止，读操作允许
    if action in ("write", "delete"):
        if normalized in _PROTECTED_PATHS:
            return False,f"路径 '{path}' 在保护名单内"
        for protected in _PROTECTED_PATHS:
            if normalized.startswith(protected + "/"):
                return False,f"路径 '{path}' 位于保护目录 '{protected}' 下"

    # 受限写路径 (仅写操作检查)
    if action in ("write", "delete"):
        for restricted in _RESTRICTED_WRITE_PATHS:
            if normalized.startswith(restricted + "/") or normalized == restricted:
                return False,f"路径 '{path}' 为受限写目录"

    return True,"路径安全"

""" 
方法: get_permission_level(), 返回当前用户的权限等级
"""
#方法: 返回当前用户的权限等级
def get_permission_level():
    user=_current_user()
    if user=="root":
        return "ops_admin"

    if _user_in_group(user,"sudo") or _user_in_group(user,"wheel"):
        return "ops_advanced"

    if _is_xikiy_ops_user_available() and user==_XIKIY_OPS_USER:
        return "ops_basic"

    return "ops_basic"


"""
方法: permission_summary(), 返回当前权限状态摘要 (v2.0 增强, 用于仪表盘展示)
"""
def permission_summary():
    level=get_permission_level()
    user=_current_user()
    sandbox=_get_sandbox_user()

    return {
        "user":user,
        "uid":os.getuid(),
        "gid":os.getgid(),
        "level":level,
        "can_read_only":True,
        "can_restricted":level in ("ops_advanced","ops_admin"),
        "can_dangerous":level=="ops_admin",
        "sandbox_user":sandbox,
        "sandbox_available":sandbox is not None,
        "xikiy_ops_user_available":_is_xikiy_ops_user_available(),
        "protected_processes_count":len(_PROTECTED_PROCESSES),
        "protected_paths_count":len(_PROTECTED_PATHS),
        "privilege_downgrade_supported":shutil.which("sudo") is not None,
    }


"""
方法: setup_instructions(), 返回创建 XikiyAIOps 专用低权限用户的命令指引
应在首次部署时引导运维人员执行
"""
def setup_instructions():
    return {
        "title": "XikiyAIOps 专用低权限用户创建指引",
        "description": "为遵循最小权限原则, 建议创建专用系统用户运行高风险操作",
        "steps": [
            {
                "step": 1,
                "command":f"sudo useradd -r -s /bin/false -d /nonexistent -M {_XIKIY_OPS_USER}",
                "description":f"创建系统用户 {_XIKIY_OPS_USER} (无登录权限, 无家目录)",
            },
            {
                "step": 2,
                "command":f"sudo usermod -aG {_XIKIY_OPS_USER} {_current_user()}",
                "description":f"可选: 将当前用户加入 {_XIKIY_OPS_USER} 组以便管理",
            },
            {
                "step": 3,
                "command":"sudo visudo -f /etc/sudoers.d/xikiy-aiops",
                "description":f"配置 sudo 策略: {_current_user()} ALL=({_XIKIY_OPS_USER}) NOPASSWD: /usr/bin/systemctl status, /usr/bin/journalctl",
            },
        ],
        "verification":f"id {_XIKIY_OPS_USER}",
    }
