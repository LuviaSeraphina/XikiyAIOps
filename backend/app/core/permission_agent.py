"""
最小权限执行代理 — 安全护栏第三道防线

设计原则:
- 1. 操作前权限预检 (当前用户 + Tool 风险等级 → 放行/确认/拦截)
- 2. read_only  → 所有用户可执行
- 3. restricted → 需要用户二次确认
- 4. dangerous  → 管理员授权方可执行, 默认拦截
"""
import os
import pwd


# 风险等级 → 所需权限等级
_RISK_PERMISSION_MAP={
    "read_only":  "ops_basic",
    "restricted": "ops_advanced",
    "dangerous":  "ops_admin",
}

# 受保护的关键进程/路径 (即使管理员也不能操作)
_PROTECTED_PROCESSES={"systemd", "sshd", "kernel", "init"}
_PROTECTED_PATHS={"/etc/shadow", "/etc/passwd", "/boot", "/sys", "/proc"}


#方法: 获取当前执行用户信息
def _current_user():
    uid=os.getuid()
    try:
        return pwd.getpwuid(uid).pw_name
    except (KeyError, OSError):
        return "uid:{}".format(uid)


"""
方法: check_permission(), 操作前权限预检

返回: (allowed: bool, reason: str)
"""
def check_permission(risk_level, user=None, target=None):
    if user is None:
        user=_current_user()
    required=_RISK_PERMISSION_MAP.get(risk_level)

    if not required:
        return False, "未知风险等级: {}".format(risk_level)

    #read_only — 所有用户可执行
    if required=="ops_basic":
        return True, ""

    #restricted — 非 root 需要二次确认 (模拟环境默认放行, 生产环境需确认)
    if required=="ops_advanced":
        if user=="root":
            return True, ""
        return True, "restricted: 需要用户确认 (当前用户: {})".format(user)

    #dangerous — 仅 ops_admin 可执行
    if required=="ops_admin":
        #检查目标是否在保护名单
        if target:
            if target in _PROTECTED_PROCESSES or target in _PROTECTED_PATHS:
                return False, "dangerous: 受保护目标 '{}' 不可操作".format(target)
        if user=="root":
            return True, ""
        return False, "dangerous: 需要管理员授权 (当前用户: {})".format(user)

    return False, "权限不足: 需要 {}, 当前用户 {}".format(required, user)


"""
方法: require_confirmation(), 判断操作是否需要用户确认

"""
def require_confirmation(risk_level):
    return risk_level in ("restricted", "dangerous")


"""
方法: validate_path(), 校验操作路径是否在保护名单内

"""
def validate_path(path):
    if path in _PROTECTED_PATHS:
        return False, "路径 '{}' 在保护名单内, 不可操作".format(path)
    for protected in _PROTECTED_PATHS:
        if path.startswith(protected + "/"):
            return False, "路径 '{}' 在保护目录 '{}' 下, 不可操作".format(path, protected)
    return True, ""


"""
方法: get_permission_level(), 返回当前用户的权限等级

"""
def get_permission_level():
    user=_current_user()
    if user=="root":
        return "ops_admin"
    #检查是否在 sudo 组
    try:
        import grp
        sudo_group=grp.getgrnam("sudo")
        if user in sudo_group.gr_mem:
            return "ops_advanced"
    except (ImportError, KeyError):
        pass
    return "ops_basic"


"""
方法: permission_summary(), 返回当前权限状态摘要 (用于仪表盘展示)

"""
def permission_summary():
    level=get_permission_level()
    user=_current_user()
    return {
        "user": user,
        "uid": os.getuid(),
        "level": level,
        "can_read_only": True,
        "can_restricted": level in ("ops_advanced", "ops_admin"),
        "can_dangerous": level=="ops_admin",
        "protected_targets_count": len(_PROTECTED_PROCESSES) + len(_PROTECTED_PATHS),
    }
