"""
MCP 插件注册中心 — 统一管理所有 Tool 的注册、发现与调用

设计原则:
1. 每个 Tool 封装原子运维操作, LLM 只能调用 Tool, 不直接接触 Shell
2. 参数通过 JSON Schema 校验, 类型/范围/枚举可控
3. 每个 Tool 声明 risk_level, 调用前自动权限预检
4. 所有 Tool 返回统一结构: {tool, timestamp, risk_level, data, summary}
"""
from enum import Enum
from app.core.permission_agent import check_permission


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
        """转为 MCP 协议的 Tool Schema"""
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
        """执行 Tool, 返回统一结构 (handler 内部已有异常保护)"""
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
        """注册一个 MCP Tool"""
        self._tools[tool.name]=tool

    def get_tool(self, name):
        """按名称获取 Tool"""
        return self._tools.get(name)

    def list_all(self):
        """列出所有已注册 Tool 的 Schema"""
        return [t.to_schema() for t in self._tools.values()]

    def list_by_risk(self, max_risk):
        """按风险等级过滤 Tool"""
        risk_order={RiskLevel.READ_ONLY: 0, RiskLevel.RESTRICTED: 1, RiskLevel.DANGEROUS: 2}
        max_level=risk_order[RiskLevel(max_risk)]
        return [t for t in self._tools.values() if risk_order[t.risk_level]<=max_level]

    def call(self, name, **kwargs):
        """统一调用入口, 自动校验 risk_level + 权限预检"""
        tool=self._tools.get(name)
        if not tool:
            return {"tool": name, "risk_level": "error", "data": {}, "summary": {"error": "Tool not found: {}".format(name)}}

        #安全护栏: 权限预检
        allowed, reason=check_permission(tool.risk_level.value)
        if not allowed:
            return {"tool": name, "risk_level": "blocked", "data": {}, "summary": {"error": reason}}

        return tool.execute(**kwargs)

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


#方法: 安全导入插件模块和函数, 失败返回占位函数
def _safe_import(module_path, func_name):
    try:
        import importlib
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

