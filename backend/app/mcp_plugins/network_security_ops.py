"""
MCP 网络安全操作工具 — 防火墙规则管理/DNS 缓存刷新

功能:
- firewall_rule_add: 添加 iptables/nft 规则
- firewall_rule_del: 删除 iptables/nft 规则
- dns_flush: 刷新 DNS 缓存

安全护栏:
- 禁止 -F (清空)/-X (删除链)/-P ACCEPT (默认放行)
- 操作前自动备份当前规则
- 参数严格校验

"""
import os
import time
import re
from datetime import datetime
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)


#禁止的 iptables 参数模式
_BLOCKED_PATTERNS=[
    re.compile(r"-F\b"),          #清空规则
    re.compile(r"--flush\b"),
    re.compile(r"-X\b"),          #删除链
    re.compile(r"--delete-chain\b"),
    re.compile(r"-Z\b"),          #清零计数器
    re.compile(r"--zero\b"),
    re.compile(r"-P\s+ACCEPT"),   #默认策略设为放行
    re.compile(r"--policy\s+ACCEPT"),
]

_BACKUP_DIR="/tmp/xikiy_fw_backup"

def _ensure_backup_dir():
    os.makedirs(_BACKUP_DIR, exist_ok=True)

def _backup_firewall_rules():
    """备份当前防火墙规则"""
    _ensure_backup_dir()
    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")

    #尝试 iptables-save
    r=_run_command(["iptables-save"], timeout=10)
    if _cmd_ok(r) and r["stdout"]:
        backup_file=os.path.join(_BACKUP_DIR, f"iptables_{timestamp}.rules")
        try:
            with open(backup_file,"w") as f:
                f.write(r["stdout"])
            return backup_file
        except (PermissionError, OSError):
            pass

    #尝试 nft list
    r=_run_command(["nft","list","ruleset"], timeout=10)
    if _cmd_ok(r) and r["stdout"]:
        backup_file=os.path.join(_BACKUP_DIR, f"nft_{timestamp}.rules")
        try:
            with open(backup_file,"w") as f:
                f.write(r["stdout"])
            return backup_file
        except (PermissionError, OSError):
            pass

    return ""

def _detect_firewall_type():
    """检测防火墙类型: iptables/nft/none"""
    #检查 nft
    r=_run_command(["nft","list","ruleset"], timeout=5)
    if _cmd_ok(r):
        return "nft"
    #检查 iptables
    r=_run_command(["iptables","-L","-n","--line-numbers"], timeout=5)
    if _cmd_ok(r):
        return "iptables"
    return "none"

def _validate_rule_params(rule_args):
    """校验规则参数, 检测是否包含禁止模式"""
    rule_str=" ".join(rule_args) if isinstance(rule_args, list) else str(rule_args)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(rule_str):
            return False, f"参数包含禁止模式: {pattern.pattern}"
    return True, ""


# ── 1. firewall_rule_add ──

"""
方法: firewall_rule_add(), 添加防火墙规则 (iptables/nft 自动适配)

"""
def firewall_rule_add(chain="", protocol="", port=0, source="", destination="", action="ACCEPT"):
    try:
        if not chain:
            return _error_response("firewall_rule_add", ValueError("参数 chain 不能为空 (如 INPUT/OUTPUT/FORWARD)"))
        if not protocol:
            return _error_response("firewall_rule_add", ValueError("参数 protocol 不能为空 (tcp/udp/icmp)"))
        if not port and protocol!="icmp":
            return _error_response("firewall_rule_add", ValueError("参数 port 不能为空 (除非 icmp)"))
        if action not in ("ACCEPT","DROP","REJECT","LOG"):
            return _error_response("firewall_rule_add", ValueError(f"不支持的 action: {action}, 仅允许: ACCEPT/DROP/REJECT/LOG"))

        fw_type=_detect_firewall_type()
        if fw_type=="none":
            return _error_response("firewall_rule_add", RuntimeError("未检测到可用的防火墙工具"))

        #备份当前规则
        backup_file=_backup_firewall_rules()

        if fw_type=="iptables":
            #构建 iptables 命令
            cmd=["iptables","-A",chain,"-p",protocol]
            if port:
                cmd.extend(["--dport",str(port)])
            if source:
                cmd.extend(["-s",source])
            if destination:
                cmd.extend(["-d",destination])
            cmd.extend(["-j",action])

            #安全校验
            safe, reason=_validate_rule_params(cmd)
            if not safe:
                return _make_response("firewall_rule_add",
                    data={"blocked":True,"reason":reason,"cmd":cmd},
                    summary={"error":f"安全拦截: {reason}"},
                    risk_level="dangerous",
                )

            result=_run_command(cmd, timeout=10)
        else:
            #nft 格式
            cmd=["nft","add","rule","ip","filter",chain.lower()]
            if protocol!="icmp":
                cmd.append(protocol)
            if port:
                cmd.extend(["dport",str(port)])
            cmd.append(action.lower())

            safe, reason=_validate_rule_params(cmd)
            if not safe:
                return _make_response("firewall_rule_add",
                    data={"blocked":True,"reason":reason,"cmd":cmd},
                    summary={"error":f"安全拦截: {reason}"},
                    risk_level="dangerous",
                )

            result=_run_command(cmd, timeout=10)

        if result.get("blocked"):
            return _make_response("firewall_rule_add",
                data={"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        success=result["exit_code"]==0
        return _make_response("firewall_rule_add",
            data={
                "firewall_type":fw_type,
                "chain":chain,
                "protocol":protocol,
                "port":port,
                "source":source,
                "destination":destination,
                "action":action,
                "success":success,
                "backup_file":backup_file,
                "stderr":result["stderr"][:300] if result["stderr"] else "",
            },
            summary={
                "firewall_type":fw_type,
                "chain":chain,
                "action":action,
                "port":port,
                "success":success,
                "backup":backup_file,
            },
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("firewall_rule_add", e)


# ── 2. firewall_rule_del ──

"""
方法: firewall_rule_del(), 删除防火墙规则 (iptables/nft 自动适配)

"""
def firewall_rule_del(chain="", protocol="", port=0, source="", destination="", action="ACCEPT"):
    try:
        if not chain:
            return _error_response("firewall_rule_del", ValueError("参数 chain 不能为空"))
        if not protocol:
            return _error_response("firewall_rule_del", ValueError("参数 protocol 不能为空"))

        fw_type=_detect_firewall_type()
        if fw_type=="none":
            return _error_response("firewall_rule_del", RuntimeError("未检测到可用的防火墙工具"))

        #备份当前规则
        backup_file=_backup_firewall_rules()

        if fw_type=="iptables":
            cmd=["iptables","-D",chain,"-p",protocol]
            if port:
                cmd.extend(["--dport",str(port)])
            if source:
                cmd.extend(["-s",source])
            if destination:
                cmd.extend(["-d",destination])
            cmd.extend(["-j",action])

            safe, reason=_validate_rule_params(cmd)
            if not safe:
                return _make_response("firewall_rule_del",
                    data={"blocked":True,"reason":reason},
                    summary={"error":f"安全拦截: {reason}"},
                    risk_level="dangerous",
                )

            result=_run_command(cmd, timeout=10)
        else:
            #nft: 需要 rule handle, 简化为按参数删除
            cmd=["nft","delete","rule","ip","filter",chain.lower()]
            if protocol!="icmp":
                cmd.append(protocol)
            if port:
                cmd.extend(["dport",str(port)])

            safe, reason=_validate_rule_params(cmd)
            if not safe:
                return _make_response("firewall_rule_del",
                    data={"blocked":True,"reason":reason},
                    summary={"error":f"安全拦截: {reason}"},
                    risk_level="dangerous",
                )

            result=_run_command(cmd, timeout=10)

        if result.get("blocked"):
            return _make_response("firewall_rule_del",
                data={"blocked":True},
                summary={"error":f"命令被安全护栏拦截: {result['stderr']}"},
                risk_level="dangerous",
            )

        success=result["exit_code"]==0
        return _make_response("firewall_rule_del",
            data={
                "firewall_type":fw_type,
                "chain":chain,
                "protocol":protocol,
                "port":port,
                "source":source,
                "destination":destination,
                "action":action,
                "success":success,
                "backup_file":backup_file,
                "stderr":result["stderr"][:300] if result["stderr"] else "",
            },
            summary={
                "firewall_type":fw_type,
                "chain":chain,
                "success":success,
                "backup":backup_file,
            },
            risk_level="dangerous",
        )
    except Exception as e:
        return _error_response("firewall_rule_del", e)


# ── 3. dns_flush ──

"""
方法: dns_flush(), 刷新 DNS 缓存

"""
def dns_flush():
    try:
        #尝试 systemd-resolved
        r=_run_command(["systemd-resolve","--flush-caches"], timeout=5)
        if _cmd_ok(r):
            return _make_response("dns_flush",
                data={"method":"systemd-resolve","success":True},
                summary={"method":"systemd-resolve","success":True},
                risk_level="restricted",
            )

        #尝试 resolvectl
        r=_run_command(["resolvectl","flush-caches"], timeout=5)
        if _cmd_ok(r):
            return _make_response("dns_flush",
                data={"method":"resolvectl","success":True},
                summary={"method":"resolvectl","success":True},
                risk_level="restricted",
            )

        #尝试 nscd
        r=_run_command(["systemctl","restart","nscd"], timeout=10)
        if _cmd_ok(r):
            return _make_response("dns_flush",
                data={"method":"nscd restart","success":True},
                summary={"method":"nscd restart","success":True},
                risk_level="restricted",
            )

        return _make_response("dns_flush",
            data={"method":"none","success":False,"reason":"未找到可用的 DNS 缓存刷新工具"},
            summary={"success":False,"info":"无 DNS 缓存服务运行"},
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("dns_flush", e)
