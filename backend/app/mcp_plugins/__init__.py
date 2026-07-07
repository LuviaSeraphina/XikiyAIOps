"""
MCP 运维插件集 — 15 个插件 82 个 Tool (v4.0 三阶段流水线)

插件分组:
  process_plugin         — 进程巡检/控制 (12 个)
  disk_plugin            — 磁盘/IO/大文件 (4 个)
  memory_plugin          — 内存画像 (5 个)
  network_plugin         — 网络诊断 (8 个)
  security_plugin        — 安全审计 (12 个)
  system_plugin          — 系统概览/日志 (10 个)
  container_plugin       — Docker/Podman (3 个)
  health_config_plugin   — 健康评分配置 (2 个)
  rag_plugin             — RAG 知识库 (2 个)
  threat_hunt_plugin     — 威胁狩猎 (1 个)
  ops_plugin             — 运维写操作 (6 个)
  service_plugin         — 服务管理 (1 个)
  config_plugin          — 配置管理 (4 个)
  network_security_ops   — 防火墙/网络操作 (4 个)
  user_pkg_plugin        — 用户/包管理 (8 个)

风险分布:
  read_only  — 61 个 (只读感知，自动放行)
  restricted — 13 个 (受限操作，需 sudo 组成员)
  dangerous  — 8 个  (危险操作，需用户二次确认)

导出:
  registry   — MCPToolRegistry 全局注册中心
  MCPTool    — Tool 定义类
  RiskLevel  — 风险等级枚举
"""
from app.mcp_plugins.base import registry, MCPTool, RiskLevel

__all__ = ["registry", "MCPTool", "RiskLevel"]