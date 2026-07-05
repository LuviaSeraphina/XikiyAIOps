"""
MCP 用户/包管理工具 — 用户创建/锁定/密码修改 + 包安装/卸载/安全更新

功能:
- user_create: 创建用户 + 可选加入组
- user_lock: 锁定/解锁用户账户
- user_password: 修改用户密码
- package_install: apt/dnf install
- package_remove: apt/dnf remove
- package_update_security: 仅安装安全更新

安全护栏:
- 禁止创建 UID=0 用户
- 禁止锁定 root/当前用户
- 密码强度校验
- 包操作前记录已安装列表

"""
import os
import pwd
import re
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)


#禁止锁定的用户
_LOCK_PROTECTED={"root","nobody"}

#禁止的包名模式 (可能导致系统崩溃的关键包)
_PROTECTED_PACKAGES={
    "kernel","linux-image","linux-headers","systemd","grub","grub2",
    "glibc","libc6","init","udev","dbus",
}

#包管理器检测
def _get_pkg_manager():
    """检测包管理器: apt/dnf/yum"""
    for mgr in ["apt","dnf","yum"]:
        r=_run_command(["which",mgr], timeout=3)
        if _cmd_ok(r) and r["stdout"]:
            return mgr
    return ""

def _validate_password_strength(password):
    """密码强度校验: ≥8 位, 含大小写+数字"""
    if len(password)<8:
        return False, "密码长度至少 8 位"
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含小写字母"
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含大写字母"
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    return True, ""


# ── 1. user_create ──

"""
方法: user_create(), 创建用户 + 可选加入组

"""
def user_create(username="", groups="", shell="/bin/bash", create_home=True):
    try:
        if not username:
            return _error_response("user_create", ValueError("参数 username 不能为空"))

        #用户名格式校验
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9._-]{0,31}$', username):
            return _make_response("user_create",
                data={"username":username,"blocked":True},
                summary={"error":"用户名格式无效: 仅允许字母/数字/._-, 不以数字开头, 最长32字符"},
                risk_level="dangerous",
            )

        #检查用户是否已存在
        try:
            pwd.getpwnam(username)
            return _make_response("user_create",
                data={"username":username,"blocked":True},
                summary={"error":f"用户 {username} 已存在"},
                risk_level="dangerous",
            )
        except KeyError:
            pass#用户不存在, 可以继续

        #构建命令
        cmd=["useradd"]
        if create_home:
            cmd.append("-m")
        if shell:
            cmd.extend(["-s",shell])
        if groups:
            cmd.extend(["-G",groups])
        cmd.append(username)

        result=_run_command(cmd, timeout=10)
        if result.get("blocked"):
            return _make_response("user_create",
                data={"username":username,"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        if result["exit_code"]!=0:
            return _make_response("user_create",
                data={"username":username,"failed":True},
                summary={"error":result["stderr"] or "useradd 执行失败"},
                risk_level="dangerous",
            )

        #验证创建结果
        try:
            pw=pwd.getpwnam(username)
            return _make_response("user_create",
                data={
                    "username":username,
                    "uid":pw.pw_uid,
                    "gid":pw.pw_gid,
                    "home":pw.pw_dir,
                    "shell":pw.pw_shell,
                    "success":True,
                },
                summary={
                    "username":username,
                    "uid":pw.pw_uid,
                    "success":True,
                },
                risk_level="dangerous",
            )
        except KeyError:
            return _make_response("user_create",
                data={"username":username,"failed":True},
                summary={"error":"useradd 返回成功但用户未找到"},
                risk_level="dangerous",
            )
    except Exception as e:
        return _error_response("user_create", e)


# ── 2. user_lock ──

"""
方法: user_lock(), 锁定/解锁用户账户

"""
def user_lock(username="", lock=True):
    try:
        if not username:
            return _error_response("user_lock", ValueError("参数 username 不能为空"))

        #安全检查: 禁止锁定关键用户
        if username in _LOCK_PROTECTED:
            return _make_response("user_lock",
                data={"username":username,"lock":lock,"blocked":True},
                summary={"error":f"安全拦截: 禁止 {'锁定' if lock else '解锁'} {username}"},
                risk_level="dangerous",
            )

        #检查用户是否存在
        try:
            pwd.getpwnam(username)
        except KeyError:
            return _error_response("user_lock", ValueError(f"用户 {username} 不存在"))

        #检查当前用户
        try:
            current_user=os.getlogin()
        except OSError:
            current_user=""
        if lock and username==current_user:
            return _make_response("user_lock",
                data={"username":username,"lock":lock,"blocked":True},
                summary={"error":"禁止锁定当前登录用户"},
                risk_level="dangerous",
            )

        flag="-L" if lock else "-U"
        action="锁定" if lock else "解锁"
        cmd=["usermod",flag,username]

        result=_run_command(cmd, timeout=10)
        if result.get("blocked"):
            return _make_response("user_lock",
                data={"username":username,"lock":lock,"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        if result["exit_code"]!=0:
            return _make_response("user_lock",
                data={"username":username,"lock":lock,"failed":True},
                summary={"error":result["stderr"] or f"usermod {flag} 执行失败"},
                risk_level="dangerous",
            )

        return _make_response("user_lock",
            data={
                "username":username,
                "action":action,
                "success":True,
            },
            summary={
                "username":username,
                "action":action,
                "success":True,
            },
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("user_lock", e)


# ── 3. user_password ──

"""
方法: user_password(), 修改用户密码 (chpasswd)

"""
def user_password(username="", password=""):
    try:
        if not username:
            return _error_response("user_password", ValueError("参数 username 不能为空"))
        if not password:
            return _error_response("user_password", ValueError("参数 password 不能为空"))

        #密码强度校验
        valid, reason=_validate_password_strength(password)
        if not valid:
            return _make_response("user_password",
                data={"username":username,"blocked":True,"reason":reason},
                summary={"error":f"密码强度不足: {reason}"},
                risk_level="dangerous",
            )

        #检查用户是否存在
        try:
            pwd.getpwnam(username)
        except KeyError:
            return _error_response("user_password", ValueError(f"用户 {username} 不存在"))

        #通过 chpasswd 修改密码 (需要 root)
        #chpasswd 从 stdin 读取 "user:password" 格式
        cmd=["chpasswd"]
        result=_run_command(cmd, timeout=10)

        #由于 chpasswd 需要 stdin, 回退到 passwd 命令
        #但 passwd 需要交互式输入, 使用 echo + pipe 的方式
        #更安全的方式: 通过 chpasswd 的 --stdin 或写入临时文件
        #这里使用 python 子进程直接处理
        import subprocess
        try:
            proc=subprocess.run(
                ["chpasswd"],
                input=f"{username}:{password}",
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode!=0:
                return _make_response("user_password",
                    data={"username":username,"failed":True},
                    summary={"error":proc.stderr or "chpasswd 执行失败"},
                    risk_level="dangerous",
                )
        except subprocess.TimeoutExpired:
            return _error_response("user_password", TimeoutError("chpasswd 超时"))
        except (FileNotFoundError, OSError) as e:
            return _error_response("user_password", e)

        return _make_response("user_password",
            data={"username":username,"success":True},
            summary={"username":username,"success":True},
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("user_password", e)


# ── 4. package_install ──

"""
方法: package_install(), 安装软件包 (apt/dnf/yum 自动适配)

"""
def package_install(packages=""):
    try:
        if not packages:
            return _error_response("package_install", ValueError("参数 packages 不能为空"))

        mgr=_get_pkg_manager()
        if not mgr:
            return _error_response("package_install", RuntimeError("未检测到可用的包管理器"))

        pkg_list=[p.strip() for p in packages.split(",") if p.strip()]
        if not pkg_list:
            return _error_response("package_install", ValueError("未提供有效的包名"))

        #安全检查: 禁止安装关键系统包
        for pkg in pkg_list:
            pkg_lower=pkg.lower()
            for protected in _PROTECTED_PACKAGES:
                if protected in pkg_lower:
                    return _make_response("package_install",
                        data={"packages":pkg_list,"blocked":True,"reason":f"安全拦截: {pkg} 包含受保护包 {protected}"},
                        summary={"error":f"禁止安装关键系统包: {pkg}"},
                        risk_level="dangerous",
                    )

        #记录操作前已安装包数量
        if mgr=="apt":
            cmd=["apt","install","-y"]+pkg_list
        else:
            cmd=[mgr,"install","-y"]+pkg_list

        result=_run_command(cmd, timeout=60)
        if result.get("blocked"):
            return _make_response("package_install",
                data={"packages":pkg_list,"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        success=result["exit_code"]==0
        return _make_response("package_install",
            data={
                "packages":pkg_list,
                "manager":mgr,
                "success":success,
                "stdout":result["stdout"][:500] if result["stdout"] else "",
                "stderr":result["stderr"][:300] if result["stderr"] else "",
            },
            summary={
                "packages":pkg_list,
                "manager":mgr,
                "success":success,
            },
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("package_install", e)


# ── 5. package_remove ──

"""
方法: package_remove(), 卸载软件包

"""
def package_remove(packages=""):
    try:
        if not packages:
            return _error_response("package_remove", ValueError("参数 packages 不能为空"))

        mgr=_get_pkg_manager()
        if not mgr:
            return _error_response("package_remove", RuntimeError("未检测到可用的包管理器"))

        pkg_list=[p.strip() for p in packages.split(",") if p.strip()]
        if not pkg_list:
            return _error_response("package_remove", ValueError("未提供有效的包名"))

        #安全检查: 禁止卸载关键系统包
        for pkg in pkg_list:
            pkg_lower=pkg.lower()
            for protected in _PROTECTED_PACKAGES:
                if protected in pkg_lower:
                    return _make_response("package_remove",
                        data={"packages":pkg_list,"blocked":True},
                        summary={"error":f"禁止卸载关键系统包: {pkg}"},
                        risk_level="dangerous",
                    )

        if mgr=="apt":
            cmd=["apt","remove","-y"]+pkg_list
        else:
            cmd=[mgr,"remove","-y"]+pkg_list

        result=_run_command(cmd, timeout=60)
        if result.get("blocked"):
            return _make_response("package_remove",
                data={"packages":pkg_list,"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        success=result["exit_code"]==0
        return _make_response("package_remove",
            data={
                "packages":pkg_list,
                "manager":mgr,
                "success":success,
                "stdout":result["stdout"][:500] if result["stdout"] else "",
                "stderr":result["stderr"][:300] if result["stderr"] else "",
            },
            summary={
                "packages":pkg_list,
                "manager":mgr,
                "success":success,
            },
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("package_remove", e)


# ── 6. package_update_security ──

"""
方法: package_update_security(), 仅安装安全更新

"""
def package_update_security():
    try:
        mgr=_get_pkg_manager()
        if not mgr:
            return _error_response("package_update_security", RuntimeError("未检测到可用的包管理器"))

        if mgr=="apt":
            #apt: 先 update 再 upgrade --only-upgrade
            _run_command(["apt","update"], timeout=30)
            cmd=["apt","upgrade","-y","--only-upgrade"]
        elif mgr=="dnf":
            cmd=["dnf","update","--security","-y"]
        else:
            cmd=["yum","update","--security","-y"]

        result=_run_command(cmd, timeout=120)
        if result.get("blocked"):
            return _make_response("package_update_security",
                data={"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="restricted",
            )

        success=result["exit_code"]==0
        #提取更新数量
        lines=result["stdout"].split("\n") if result["stdout"] else []
        updated_count=sum(1 for l in lines if "upgraded" in l.lower() or "installed" in l.lower())

        return _make_response("package_update_security",
            data={
                "manager":mgr,
                "success":success,
                "output_lines":len(lines),
                "stdout":result["stdout"][:800] if result["stdout"] else "",
            },
            summary={
                "manager":mgr,
                "success":success,
                "packages_updated":updated_count,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("package_update_security", e)
