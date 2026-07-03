"""
MCP 插件注册中心 — 统一管理所有 Tool 的注册、发现与调用

设计原则:
1. 每个 Tool 封装原子运维操作, LLM 只能调用 Tool, 不直接接触 Shell
2. 参数通过 JSON Schema 校验, 类型/范围/枚举可控
3. 每个 Tool 声明 risk_level, 调用前自动权限预检
4. 所有 Tool 返回统一结构: {tool, timestamp, risk_level, data, summary}
"""
from enum import Enum
import importlib
from app.core.permission_agent import check_permission
from app.mcp_plugins._common import sanitize_response


class RiskLevel(str, Enum):
    READ_ONLY="read_only"
    RESTRICTED="restricted"
    DANGEROUS="dangerous"


class MCPTool:
    """MCP 工具定义"""
    def __init__(self, name, description, handler, risk_level=RiskLevel.READ_ONLY, parameters=None):
        self.name=name
        self.description=description
        self.handler=handler
        self.risk_level=RiskLevel(risk_level)
        self.parameters=parameters or {}

    def to_schema(self):
    # 转为 MCP 协议的 Tool Schema
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters,
            },
            "risk_level": self.risk_level.value,
        }

    def execute(self, **kwargs):
    # 执行 Tool, 返回统一结构 (handler 内部已有异常保护)
        return self.handler(**kwargs)


class MCPPluginRegistry:
    """MCP 插件注册中心 — 单例, 管理所有 Tool"""

    _instance=None
    _tools={}

    def __new__(cls):
        if cls._instance is None:
            cls._instance=super().__new__(cls)
        return cls._instance

    def register(self, tool):
    # 注册一个 MCP Tool
        self._tools[tool.name]=tool

    def get_tool(self, name):
    # 按名称获取 Tool
        return self._tools.get(name)

    def list_all(self):
    # 列出所有已注册 Tool 的 Schema
        return [t.to_schema() for t in self._tools.values()]

    def list_by_risk(self, max_risk):
    # 按风险等级过滤 Tool
        risk_order={RiskLevel.READ_ONLY: 0, RiskLevel.RESTRICTED: 1, RiskLevel.DANGEROUS: 2}
        max_level=risk_order[RiskLevel(max_risk)]
        return [t for t in self._tools.values() if risk_order[t.risk_level]<=max_level]

    def call(self, name, _raw=False, **kwargs):
    # 统一调用入口, 自动校验 risk_level + 权限预检         _raw=True: 跳过脱敏 (供 Agent 内部感知用, 前端展示仍需单独脱
        tool=self._tools.get(name)
        if not tool:
            return {"tool": name, "risk_level": "error", "data": {}, "summary": {"error": "Tool not found: {}".format(name)}}

        #安全护栏: 权限预检
        allowed, reason,_=check_permission(tool.risk_level.value)
        if not allowed:
            return {"tool": name, "risk_level": "blocked", "data": {}, "summary": {"error": reason}}

        result = tool.execute(**kwargs)
        return result if _raw else sanitize_response(name, result)

    @property
    def count(self):
        return len(self._tools)


#方法: 自动扫描所有插件, 注册 Tool handler
def _auto_register_all(reg):
    reg.register(MCPTool(
        name="process_inspect",
        description="获取系统进程信息, 支持按状态过滤、按 CPU/内存排序",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_inspect_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="process_detail",
        description="获取单个进程的详细信息: PID/名称/状态/CPU/内存/线程数/FD/运行时间/工作目录/可执行文件/用户/nice",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_detail_handler"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "pid": {"type": "integer", "description": "进程 PID"},
        },
    ))
    reg.register(MCPTool(
        name="process_tree",
        description="构建进程树, 以 PID 1 为根展示父子关系, 每节点含 pid/name/ppid/status/children",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_tree_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="process_zombie_scan",
        description="扫描系统僵尸进程, 返回僵尸进程列表及父进程名, 发现僵尸进程时告警",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_zombie_scan_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="process_top_cpu",
        description="获取 CPU 占用最高的 Top N 进程 (默认 5, 最大 20)",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_top_cpu_handler"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "top_n": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20, "description": "返回进程数量"},
        },
    ))
    reg.register(MCPTool(
        name="process_top_memory",
        description="获取内存占用最高的 Top N 进程 (默认 5, 最大 20), 含 RSS 物理内存",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_top_memory_handler"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "top_n": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20, "description": "返回进程数量"},
        },
    ))
    reg.register(MCPTool(
        name="process_kill",
        description="终止指定进程 (SIGTERM/SIGKILL), 多级安全护栏阻止终止 init/自身/关键系统进程",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_kill_handler"),
        risk_level=RiskLevel.DANGEROUS,
        parameters={
            "pid": {"type": "integer", "description": "目标进程 PID"},
            "signal_name": {"type": "string", "default": "SIGTERM", "description": "信号名称: SIGTERM (优雅终止) 或 SIGKILL (强制终止)"},
        },
    ))
    reg.register(MCPTool(
        name="disk_inspect",
        description="获取磁盘空间使用情况, 支持指定挂载点路径",
        handler=_safe_import("app.mcp_plugins.disk_plugin", "disk_inspect_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_listening_ports",
        description="枚举所有 TCP/UDP 监听端口, 含进程名和 PID",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_listening_ports"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_connections_summary",
        description="TCP 连接状态统计, CLOSE_WAIT/SYN_SENT 异常告警",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_connections_summary"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_interface_stats",
        description="网卡流量与错误统计, 丢包/错误检测",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_interface_stats"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="memory_info",
        description="物理内存画像: 总量/已用/可用/使用率",
        handler=_safe_import("app.mcp_plugins.memory_plugin", "memory_info"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="swap_info",
        description="Swap 交换分区画像, 使用率>50% 预警",
        handler=_safe_import("app.mcp_plugins.memory_plugin", "swap_info"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="memory_oom_history",
        description="OOM Killer 历史事件提取 (journalctl/dmesg)",
        handler=_safe_import("app.mcp_plugins.memory_plugin", "memory_oom_history"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="memory_hugepages",
        description="大页内存状态: 总量/空闲/预留/盈余/使用率/页面大小",
        handler=_safe_import("app.mcp_plugins.memory_plugin", "memory_hugepages"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="memory_slab_info",
        description="内核 Slab 缓存用量: 总量/可回收/不可回收 (kB/MB)",
        handler=_safe_import("app.mcp_plugins.memory_plugin", "memory_slab_info"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_auth_failures",
        description="多源认证失败统计 (SSH/su/sudo/PAM), 含 fail2ban 封禁",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_auth_failures"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_active_sessions",
        description="活跃登录会话和 SSH 连接枚举",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_active_sessions"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_suid_scan",
        description="SUID/SGID 后门文件扫描, 标记非白名单文件",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_suid_scan"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_crontab_audit",
        description="审计所有用户 crontab, 检测可疑定时任务 (curl/wget 下载脚本等)",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_crontab_audit"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_kernel_modules",
        description="审计已加载内核模块, 识别非标准/可疑模块",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_kernel_modules"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_pending_updates",
        description="检测待安装安全更新数量 (dnf/apt 自动适配)",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_pending_updates"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_user_audit",
        description="用户与权限审计: 空密码/UOD=0/无密码 sudo",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_user_audit"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_sysctl_audit",
        description="内核安全参数审计 (ASLR/ptrace/IP转发等 12 项基线)",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_sysctl_audit"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="user_list",
        description="用户与组查询 (只读): 列出所有用户及其 UID/GID/家目录/Shell",
        handler=_safe_import("app.mcp_plugins.security_plugin", "user_list"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_open_files",
        description="打开文件数 Top N (句柄泄漏检测): 遍历所有进程统计 FD 数量, 降序返回 top N, FD>1000 时告警",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_open_files"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "top_n": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50, "description": "返回进程数量"},
        },
    ))
    reg.register(MCPTool(
        name="security_selinux_status",
        description="SELinux/AppArmor 运行模式检测: KYSDK Selinux 优先, 回落 getenforce + aa-status",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_selinux_status"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    #KYSDK 新增: 密码策略 + 用户权限审计
    reg.register(MCPTool(
        name="security_password_policy",
        description="系统密码复杂度策略检查: KYSDK UserAuth 优先, 回落 PAM 配置解析",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_password_policy"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="security_user_privilege",
        description="指定用户权限审计: KYSDK UserAuth 优先 (sudo权限+home目录), 回落 sudo -l",
        handler=_safe_import("app.mcp_plugins.security_plugin", "security_user_privilege"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "username": {"type": "string", "pattern": "^[a-zA-Z_][a-zA-Z0-9._-]{0,31}$", "description": "要审计的用户名 (仅字母数字._-, 最长32字符)"},
        },
    ))
    reg.register(MCPTool(
        name="system_info",
        description="系统概览: 主机名/内核/发行版/架构/运行时间 (含麒麟检测)",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_info"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="system_load",
        description="系统负载 (1/5/15分钟), 含过载判断",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_load"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="system_failed_services",
        description="列出失败的系统服务 (systemctl --failed)",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_failed_services"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="system_boot_params",
        description="内核启动参数审计, 检查关键安全参数",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_boot_params"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="health_config_get",
        description="获取当前健康评分权重和阈值配置, 返回完整 JSON",
        handler=_safe_import("app.mcp_plugins.health_config_plugin", "health_config_get_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="health_config_set",
        description="修改健康评分配置中的一项阈值或权重, 传入 dot-path (如 thresholds.cpu.1.max) 和新值",
        handler=_safe_import("app.mcp_plugins.health_config_plugin", "health_config_set_handler"),
        risk_level=RiskLevel.RESTRICTED,
        parameters={
            "key_path": {"type": "string", "description": "配置路径, 用 . 分隔, 如 'thresholds.cpu.1.max' 或 'weights.cpu'"},
            "value": {"type": "number", "description": "新值, 如 80 或 0.3"},
        },
    ))

    #---- Phase 2: 新增工具 (v0.2) ----
    reg.register(MCPTool(
        name="disk_inode_usage",
        description="磁盘 inode 使用率检测 — 生产故障高频根因 (inode 耗尽但磁盘有空间)",
        handler=_safe_import("app.mcp_plugins.disk_plugin", "disk_inode_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="disk_io_stats",
        description="磁盘 I/O 统计: 读写次数、吞吐量 (MB)、读写耗时",
        handler=_safe_import("app.mcp_plugins.disk_plugin", "disk_io_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="disk_mount_audit",
        description="挂载点审计: 列出所有挂载点及其安全属性 (noexec/nosuid/ro), 标记可疑配置",
        handler=_safe_import("app.mcp_plugins.disk_plugin", "disk_mount_audit"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="disk_large_files",
        description="大文件扫描: 扫描指定路径下超过阈值的大文件, 按大小降序返回 top N",
        handler=_safe_import("app.mcp_plugins.disk_plugin", "disk_large_files"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_firewall_audit",
        description="防火墙规则审计: 检测 nftables/iptables 类型并统计规则数量",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_firewall_audit"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_tcp_retrans",
        description="TCP 重传率检测 — 从 ss -ti 解析 retrans 计数, >2% 告警",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_tcp_retrans"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="network_dns_check",
        description="DNS 解析测试 — dig 查询指定域名的解析 IP, getent 兜底",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_dns_check"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "domain": {"type": "string", "description": "要解析的域名"},
            "dns_server": {"type": "string", "default": "", "description": "指定 DNS 服务器地址, 为空则使用系统默认"},
        },
    ))
    reg.register(MCPTool(
        name="system_package_updates",
        description="检测待安装安全更新数量 (dnf/apt 自动适配)",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_package_updates"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="system_entropy",
        description="内核熵池可用量 — 读取 /proc/sys/kernel/random/entropy_avail, 低熵(<500)影响 TLS/SSH 等加密服务",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_entropy"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    #KYSDK 新增: CPU 详情 + BIOS 信息
    reg.register(MCPTool(
        name="system_cpu_detail",
        description="CPU 详细信息: 厂商/型号/频率/核心/线程/缓存(L1/L2/L3)/虚拟化 — KYSDK libkycpu 优先",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_cpu_detail"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="system_bios_info",
        description="BIOS 信息: 厂商/版本/日期/类型 — KYSDK libkybios 优先, 回落 dmidecode",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_bios_info"),
        risk_level=RiskLevel.READ_ONLY,
    ))

    #---- 日志查询工具 (v0.3) ----
    reg.register(MCPTool(
        name="system_journal_query",
        description="日志查询 — 按服务/时间/级别/关键词过滤 (journalctl)",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_journal_query"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "service": {"type": "string", "default": "", "description": "按 systemd 单元过滤, 如 sshd"},  # noqa: E501
            "hours": {"type": "integer", "default": 1, "minimum": 1, "maximum": 168, "description": "回溯小时数"},  # noqa: E501
            "priority": {"type": "string", "default": "err", "enum": ["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"], "description": "最低优先级"},  # noqa: E501
            "keyword": {"type": "string", "default": "", "description": "消息内容关键词过滤"},  # noqa: E501
            "max_lines": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200, "description": "返回条目上限"},  # noqa: E501
        },
    ))
    reg.register(MCPTool(
        name="system_journal_tail",
        description='最新日志快照 — 快速查看系统当前日志, 适合回答「现在系统在报什么」',
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_journal_tail"),
        risk_level=RiskLevel.READ_ONLY,
    ))

    #---- 容器感知 (v0.2) ----
    reg.register(MCPTool(
        name="container_list",
        description="Docker/Podman 容器列表: 名称/镜像/状态/端口映射/运行时长",
        handler=_safe_import("app.mcp_plugins.container_plugin", "container_list"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="container_stats",
        description="容器资源用量: CPU%/内存/网络 I/O (docker/podman stats)",
        handler=_safe_import("app.mcp_plugins.container_plugin", "container_stats"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="container_inspect",
        description="单容器安全审计: privileged/Capabilities/挂载卷/环境变量数量",
        handler=_safe_import("app.mcp_plugins.container_plugin", "container_inspect"),
        risk_level=RiskLevel.READ_ONLY,
    ))

    #---- RAG 知识库 (v0.4) ----
    reg.register(MCPTool(
        name="rag_search",
        description="RAG 运维知识库检索 — 从赛题文档/MCP Tool说明/SRE最佳实践中搜索相关知识。当用户询问「怎么排查」「如何配置」「文档要求」等知识性问题时调用",
        handler=_safe_import("app.mcp_plugins.rag_plugin", "rag_search_handler"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "query": {"type": "string", "description": "检索查询, 用中文关键词描述你想了解的问题"},
            "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10, "description": "返回结果数"},
        },
    ))
    reg.register(MCPTool(
        name="rag_stats",
        description="查看 RAG 知识库统计信息: 总条目数/集合状态",
        handler=_safe_import("app.mcp_plugins.rag_plugin", "rag_stats_handler"),
        risk_level=RiskLevel.READ_ONLY,
    ))

    #---- Phase 3: 新增工具 (v0.3) ----
    reg.register(MCPTool(
        name="network_ping",
        description="ICMP 连通性检查 (ping): 返回丢包率、RTT 最小/平均/最大/抖动",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_ping"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "target": {"type": "string", "description": "目标 IP 或域名"},
            "count": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10, "description": "ping 次数"},
        },
    ))
    reg.register(MCPTool(
        name="network_http_check",
        description="HTTP 端点健康检查: 返回状态码、响应时间、是否可达",
        handler=_safe_import("app.mcp_plugins.network_plugin", "network_http_check"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "url": {"type": "string", "description": "目标 URL (http:// 或 https://)"},
            "timeout": {"type": "integer", "default": 5, "minimum": 1, "maximum": 30, "description": "超时秒数"},
        },
    ))
    reg.register(MCPTool(
        name="vmstat_stats",
        description="虚拟内存统计 (vmstat): CPU/IO/swap/上下文切换/中断的实时采样数据",
        handler=_safe_import("app.mcp_plugins.system_plugin", "vmstat_stats"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "intervals": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5, "description": "采样间隔秒数"},
            "count": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10, "description": "采样次数"},
        },
    ))
    reg.register(MCPTool(
        name="system_timers",
        description="列出 systemd 定时器: 名称/下次触发时间/上次触发时间/关联服务",
        handler=_safe_import("app.mcp_plugins.system_plugin", "system_timers"),
        risk_level=RiskLevel.READ_ONLY,
    ))
    reg.register(MCPTool(
        name="process_smaps",
        description="进程内存映射分析: RSS/PSS/共享/私有/匿名/脏页/Swap 使用量",
        handler=_safe_import("app.mcp_plugins.process_plugin", "process_smaps_handler"),
        risk_level=RiskLevel.READ_ONLY,
        parameters={
            "pid": {"type": "integer", "description": "进程 PID"},
        },
    ))


#方法: 安全导入插件模块和函数, 失败返回占位函数
def _safe_import(module_path, func_name):
    try:
        mod=importlib.import_module(module_path)
        return getattr(mod, func_name)
    except Exception as e:
        print("[base] 插件加载失败: {}.{} — {}".format(module_path, func_name, e))
        def _placeholder(**kwargs):
            return {"tool": func_name, "risk_level": "error", "data": {}, "summary": {"error": "插件未加载: {}".format(str(e))}}
        return _placeholder


# 全局注册中心实例
registry=MCPPluginRegistry()
_auto_register_all(registry)

