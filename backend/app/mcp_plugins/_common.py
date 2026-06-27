"""
MCP 插件共享工具 — 所有插件复用
"""
import logging
import os
import re
import subprocess
import time
from datetime import datetime

""" 
方法: make_response(), 统一构建 MCP Tool 返回结构
"""
def make_response(tool, data, summary, risk_level="read_only"):
    return {
        "tool": tool,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_level": risk_level,
        "data": data,
        "summary": summary,
    }
""" 
方法: error_response(), 异常时返回统一错误结构, 保证所有 Tool 不会因未捕获异常而崩溃
"""
def error_response(tool, error):
    return {
        "tool": tool,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_level": "error",
        "data": {},
        "summary": {"error": str(error)},
    }


"""
方法: sanitize_response(), 响应脱敏 — 仅过滤真正敏感且 Agent 决策不需要的字段

原则:
  Agent 需要: 进程名/PID/路径/用户/端口/命令/日志 → 全部放行用于感知和判断
  前端脱敏: uid/gid数字/home路径/MAC地址/shell路径 → 删除(无需展示)
"""
_SANITIZE_RULES = {
    # ── 用户/权限类 ──
    "user_list": {
        "keep_data": ["users"],
        "strip_fields": ["uid","gid","home","shell"],  # uid/gid数字无意义, home/shell是隐私
    },
    "security_user_audit": {
        "keep_data": ["issues_count","issues"],  # 保留完整 issues 列表供Agent分析
    },
    "security_user_privilege": {
        "keep_data": ["username","sudo_access","home_permission","source"],  # 放行 username
    },
    # ── 会话/认证类 ── Agent需要追踪入侵来源
    "security_auth_failures": {
        "keep_data": ["total_failures","by_type_summary","sources_count","failed_ips","failed_users"],
        "mask_ips": True,  #保留IP但脱敏后两段
        #保留IP和用户列表 — Agent需要判断是否被暴力破解
    },
    "security_active_sessions": {
        "keep_data": ["session_count","ssh_connection_count","sessions","ssh_connections"],
        "mask_ips": True,  #from_ip保留前两段
        #保留完整会话信息 — Agent需要检测未授权登录
    },
    # ── 进程类 ── Agent需要 exe/username 判断进程合法性
    "process_detail": {
        "keep_data": ["process"],
        "strip_fields": ["num_fds","memory_info_rss_mb"],  # fd数量和RSS细节非决策关键
    },
    "process_detail_handler": {
        "keep_data": ["process"],
        "strip_fields": ["num_fds","memory_info_rss_mb"],
    },
    # ── 网络类 ── Agent需要进程名判断谁在监听
    "network_listening_ports": {
        "keep_data": ["port_count","ports"],
        "strip_fields": [],  #保留 bind/process/pid — Agent需要知道谁在监听什么端口
    },
    "network_interface_stats": {
        "keep_data": ["interface_count","interfaces"],
        "strip_fields": ["mac","driver"],  #MAC地址是硬件标识, 删除
    },
    "network_dns_check": {
        "keep_data": ["domain","dns_server","count","source"],
        #不保留 resolved_ips (解析出的IP列表过长且非决策关键)
    },
    # ── 文件/磁盘类 ── Agent需要路径定位威胁
    "disk_mount_audit": {
        "keep_data": ["mounts","mount_count","suspicious"],
        "strip_fields": ["device"],  #设备路径保留(mountpoint), 裸设备名删除
    },
    "disk_large_files": {
        "keep_data": ["file_count","scan_path","files"],
        "mask_paths": True,  #大文件路径脱敏 /home/ 部分
        #保留完整文件路径 — Agent需要定位大文件
    },
    "security_suid_scan": {
        "keep_data": ["total_files","suspicious_count","suspicious_files","files"],
        "mask_paths": True,  #系统路径/usr/bin保留, /home/脱敏
        #保留文件路径和权限 — Agent需要判断SUID风险
    },
    # ── 定时任务/启动类 ── Agent需要完整命令检测持久化
    "security_crontab_audit": {
        "keep_data": ["total_entries","suspicious_count","suspicious_entries","entries"],
        "mask_paths": True,  #命令关键词保留, /home/路径脱敏
        #保留完整 crontab 条目 — Agent需要识别恶意定时任务
    },
    "system_boot_params": {
        "keep_data": ["security_checks","missing_security_params"],
        #不保留 raw (完整cmdline太长)
    },
    # ── 日志类 ── Agent需要 message 正文调查事件
    "system_journal_query": {
        "keep_data": ["total","filter","entries"],
        "strip_fields": [],
        "mask_ips": True, "mask_paths": True,  #日志中的IP和路径脱敏  #保留 message — Agent需要日志内容分析问题
    },
    "system_journal_tail": {
        "keep_data": ["priority","lines_requested","entries"],
        "strip_fields": [],
        "mask_ips": True, "mask_paths": True,
    },
    # ── 容器类 ── Agent需要完整容器信息做安全审计
    "container_inspect": {
        "keep_data": ["id","name","image","env_count","privileged","state","mounts_count"],
        #保留特权标志和挂载数 — Agent需要判断容器逃逸风险
    },
    "container_list": {
        "keep_data": ["containers","count","runtime"],
        "strip_fields": [],  #保留 ports — Agent需要知道暴露的端口
    },
    # ── 系统信息 ── hostname对多机运维有意义
    "system_info": {
        "keep_data": ["hostname","os","distro","kernel","arch","boot_time","cpu_cores_logical","cpu_cores_physical","pkg_manager","firewall","is_kylin","display_name"],
    },
}

def sanitize_response(tool_name, response):
    """根据工具名对响应数据脱敏 — 仅过滤 strip_fields + IP脱敏 + 路径脱敏"""
    if tool_name is None:
        return response
    rules=_SANITIZE_RULES.get(tool_name)
    if rules is None:
        return response  #无规则, 原样返回

    data=response.get("data",{})
    if not isinstance(data,dict):
        return response

    keep_data=rules.get("keep_data",[])
    strip_fields=rules.get("strip_fields",[])
    mask_ips=rules.get("mask_ips",False)
    mask_paths=rules.get("mask_paths",False)

    #构建顶层白名单
    if keep_data:
        cleaned={k:data[k] for k in keep_data if k in data}
    else:
        cleaned=dict(data)

    #对列表字段递归 strip 敏感子字段
    if strip_fields:
        for key in list(cleaned.keys()):
            val=cleaned[key]
            if isinstance(val,list):
                cleaned[key]=[_strip_dict_fields(item,strip_fields) if isinstance(item,dict) else item for item in val]
            elif isinstance(val,dict):
                cleaned[key]=_strip_dict_fields(val,strip_fields)

    #IP脱敏: 递归扫描所有字符串值, 保留前两段
    if mask_ips:
        cleaned=_walk_and_mask(cleaned, _mask_ip)

    #路径脱敏: 递归扫描所有字符串值, 隐藏用户目录
    if mask_paths:
        cleaned=_walk_and_mask(cleaned, _mask_home_path)

    response["data"]=cleaned
    return response


def _strip_dict_fields(d:dict, fields:list)->dict:
    """从 dict 中删除指定字段"""
    return {k:v for k,v in d.items() if k not in fields}


def _walk_and_mask(obj, mask_fn):
    """递归遍历 dict/list, 对所有字符串值应用 mask_fn"""
    if isinstance(obj,dict):
        return {k:_walk_and_mask(v,mask_fn) for k,v in obj.items()}
    elif isinstance(obj,list):
        return [_walk_and_mask(v,mask_fn) for v in obj]
    elif isinstance(obj,str):
        return mask_fn(obj)
    return obj


def _mask_ip(text:str)->str:
    """IP地址脱敏: 保留前两段, 后两段替换为 ***, 仅匹配合法IPv4"""
    import re
    _octet=r'(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
    _ip=rf'\b({_octet}\.{_octet}\.{_octet}\.{_octet})\b'
    def _replace(m):
        parts=m.group(0).split('.')
        return f"{parts[0]}.{parts[1]}.***.***"
    return re.sub(_ip, _replace, text)


def _mask_home_path(text:str)->str:
    """用户目录路径脱敏: /home/username → /home/***, /root → /root (保留)"""
    import re
    #匹配 /home/ 后跟用户名 (非空白/非斜杠)
    return re.sub(r'/home/[^/\s"]+', '/home/***', text)

# 允许执行的命令白名单 (只有这些命令可通过 run_command 执行)
_ALLOWED_COMMANDS={
    "ss","ip","who","find","lsmod","systemctl",
    "journalctl","dmesg","cat","crontab","sysctl",
    "docker","podman","which","dnf","yum","apt",
    "iptables","nft","getenforce","aa-status","dig","getent",
    "dmidecode","groups",
}

# 高危参数模式 — 分三类匹配, 避免子串误伤 (如 rm 匹配 format)
#   词边界: alphabetic 模式使用 \b 边界, 只匹配独立单词
#   精确:   flag 模式匹配完整参数
#   子串:   操作符匹配任意位置
_DANGEROUS_WORD={"rm","mkfs","dd","shutdown","reboot","poweroff","halt","chmod","chown"}
_DANGEROUS_FLAG={"-rf","-r"}
_DANGEROUS_SUBSTR={">",">>","&&",";","|","`","$(","${"}

#方法: 在 run_command 前校验命令安全性
def _is_safe_command(cmd):
    #命令本身不在白名单
    if not cmd:
        return False, "空命令"
    base=cmd[0]
    if base not in _ALLOWED_COMMANDS:
        return False,f"命令 '{base}' 不在白名单内"

    #参数中检测高危模式
    for arg in cmd[1:]:
        #词边界匹配 (防子串误伤: format/perform/confirm/-perm)
        for pattern in _DANGEROUS_WORD:
            if re.search(r'\b' + re.escape(pattern) + r'\b', arg):
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"
        #精确匹配 flag
        for pattern in _DANGEROUS_FLAG:
            if arg==pattern:
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"
        #子串匹配 shell 操作符
        for pattern in _DANGEROUS_SUBSTR:
            if pattern in arg:
                return False,f"参数 '{arg[:50]}' 包含高危模式 '{pattern}'"

    return True, ""

_logger=logging.getLogger("xikiy_aiops.mcp")

"""
方法: run_command(), 安全执行固定参数命令

v2: 返回结构化 dict {stdout, stderr, exit_code, duration_ms}
    而非原始字符串, 以便上层采集真实执行数据用于异常回溯。

成功时 stdout 为命令输出, stderr 可能为空或有 warning。
执行失败时 stdout 为空字符串, stderr 包含错误信息。
"""
def run_command(cmd, timeout=10):
    #安全校验
    safe,reason=_is_safe_command(cmd)
    if not safe:
        _logger.warning(f"命令拦截: {' '.join(cmd[:3])} — {reason}")
        return {"stdout":"","stderr":reason,"exit_code":-1,"duration_ms":0,"blocked":True}

    start=time.monotonic()
    try:
        result=subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed_ms=int((time.monotonic() - start) * 1000)
        stdout=result.stdout.strip()
        stderr=(result.stderr or "").strip()
        exit_code=result.returncode

        if exit_code!=0 and not stdout:
            _logger.warning(f"命令执行失败: {' '.join(cmd)} (rc={exit_code}){f' stderr={stderr}' if stderr else ''}")
        elif exit_code!=0 and stderr:
            _logger.warning(f"命令返回非 0: {' '.join(cmd)} (rc={exit_code}){f' stderr={stderr}' if stderr else ''}")

        return {
            "stdout":stdout,
            "stderr":stderr,
            "exit_code":exit_code,
            "duration_ms":elapsed_ms,
            "blocked":False,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms=int((time.monotonic() - start) * 1000)
        _logger.warning(f"命令超时: {' '.join(cmd)} (>{timeout}s)")
        return {"stdout":"","stderr":f"命令超时 (>{timeout}s)","exit_code":-1,"duration_ms":elapsed_ms,"blocked":False}
    except (FileNotFoundError, OSError) as e:
        elapsed_ms=int((time.monotonic() - start) * 1000)
        _logger.warning(f"命令执行异常: {' '.join(cmd)} — {e}")
        return {"stdout":"","stderr":str(e),"exit_code":-1,"duration_ms":elapsed_ms,"blocked":False}

"""
方法: journalctl_available(), 检测 journalctl 是否可用
"""
def journalctl_available():
    return os.path.exists("/usr/bin/journalctl") or os.path.exists("/bin/journalctl")

"""
方法: _cmd_ok(), 检查 run_command() 返回的 dict 是否表示命令成功执行

插件层统一使用此函数判断, 替代旧版 `if result is None` 模式。
- blocked → False
- exit_code≠0 且 stdout 为空 → False  
- 其他情况 → True (含 exit_code==0 无输出, exit_code≠0 但有 stdout)
"""
def _cmd_ok(result):
    if result["blocked"]:
        return False
    if result["exit_code"]!=0 and not result["stdout"]:
        return False
    return True

"""
方法: read_log_file(), 安全读取日志文件最后 max_lines 行
"""
def read_log_file(path, max_lines=2000):
    if not os.path.exists(path) or not os.access(path, os.R_OK):
        return []
    try:
        with open(path, "r", errors="ignore") as f:
            lines=f.readlines()
            return [line.strip() for line in lines[-max_lines:]]
    except (PermissionError, OSError):
        return []
        
"""
方法: alert_if(), 告警句式生产辅助
"""
#方法: 告警句式辅助
def alert_if(condition, template, *args):
    return template.format(*args) if condition else ""

# ── KYSDK 麒麟原生 SDK 支持 ──────────────────────────────
#KYSDK 是麒麟操作系统的原生 Python SDK, 提供系统信息/硬件/安全/网络等 API,
#替代 shell 命令采集, 零注入风险, 精度更高。非麒麟环境自动降级为 shell 方案。

#模块级惰性导入标记: True=可用, False=不可用, None=未检测
_KYSDK_AVAILABLE=None

"""
方法: _kysdk_available(), 检测 KYSDK Python SDK 是否可导入

一次检测, 结果缓存于模块变量 _KYSDK_AVAILABLE。
非麒麟系统返回 False, 调用方应回落 shell 方案。
"""
def _kysdk_available():
    global _KYSDK_AVAILABLE
    if _KYSDK_AVAILABLE is not None:
        return _KYSDK_AVAILABLE
    try:
        import kysdk
        _KYSDK_AVAILABLE=True
    except ImportError:
        _KYSDK_AVAILABLE=False
    return _KYSDK_AVAILABLE

"""
方法: _kysdk_import(module_name), 安全按需导入 KYSDK 子模块

成功返回模块对象, 失败返回 None (调用方自行处理降级)。
用法: sdk=_kysdk_import("SystemInfo"); if sdk: sdk.get_cpu_usage()
"""
def _kysdk_import(name):
    if not _kysdk_available():
        return None
    try:
        mod=__import__("kysdk", fromlist=[name])
        return getattr(mod, name, None)
    except (ImportError, AttributeError):
        return None

"""
方法: _sdk_call(), 安全调用 KYSDK 对象方法, 失败返回 None

与 platform_detect._safe_call 合并, 统一入口避免重复实现。
用法: _sdk_call(hw, "get_cpu_arch") or "unknown"
"""
def _sdk_call(obj, method_name, *args):
    try:
        method=getattr(obj, method_name, None)
        if method is None:
            return None
        return method(*args)
    except Exception:
        return None
