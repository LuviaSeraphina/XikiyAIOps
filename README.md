# XikiyAIOps — linux系统智能运维 Agent

---

## 一句话

用自然语言管理 Linux 服务器。AI 不接触 Shell，全部走 82 个安全封装的 MCP 运维工具。

## 核心亮点

| 亮点 | 说明 |
|------|------|
| 🗣️ 自然语言运维 | "看看系统状态" → Agent 动态规划 4 步 → 执行 → 报告，零命令行 |
| 🔒 纵深安全护栏 | 意图过滤 + 注入检测 + 三级权限代理 + xikiy 降权 + 命令白名单 |
| 🔧 82 个 MCP Tool | 进程/磁盘/网络/内存/安全/系统/容器/运维/配置/知识库，15 插件 |
| 🧠 动态规划 | 不依赖预设场景，LLM 根据意图自主选择工具组合 |
| 🛡️ 反幻觉机制 | Summarizer 6 条铁律 + Executor 如实汇报 + status 字段 |
| 🖥️ 麒麟原生适配 | dnf/nftables/LoongArch 自动检测，离线 CDN 拉取依赖 |
| 🎨 Vue 3 前端 | 对话 / 仪表盘 / 审计 / 模型配置，SSE 流式 |

## 架构

```
用户 (Web UI) ──→ FastAPI ──→ Security Agent (安全审查)
                      │
                 Planner Agent (意图分析 → 动态规划)
                      │
                 Executor Agent (按步执行 MCP Tool)
                      │
                 Summarizer Agent (反幻觉报告)
                      │
              ┌───────┴────────┐
              │  MCP 注册中心   │
              │  82 Tools (15) │
              └───────┬────────┘
                 LLM (自定义Provider)
```

## 快速部署

```bash
# 1. 解压
tar xzf XikiyAIOps_v1.2.0.tar.gz
cd XikiyAIOps_v1.2.0

sudo bash scripts/deploy.sh

# 3. 启动
bash /opt/xikiy-aiops/scripts/start.sh

# 4. 浏览器打开 → 模型配置 → 输入 API Key → 对话
#    http://localhost:8001
```

## MCP 工具 (82 Tools)

| 插件 | 数量 | 说明 |
|------|:--:|------|
| process | 12 | inspect, detail, tree, zombie, top_cpu, top_mem, smaps, io_top, kill🔴, renice🟡, ionice🟡, zombie_cleanup🟡 |
| disk | 5 | inspect, inode, io_stats, mount_audit, large_files |
| network | 8 | ports, connections, interfaces, firewall, tcp_retrans, dns, ping, http |
| memory | 5 | info, swap, oom_history, hugepages, slab |
| security | 12 | auth_failures, sessions, suid, crontab, kernel_mods, updates, user_audit, sysctl, open_files, selinux, password, privilege |
| system | 10 | info, load, failed_svcs, boot, packages, entropy, cpu, bios, journal_query, journal_tail |
| container | 3 | list, stats, inspect |
| ops | 5 | file_identify, file_read, file_truncate🟡, disk_cleanup🟡, logrotate🟡 |
| service | 1 | service_control🟡 |
| config | 4 | diff, backup🟡, restore🟡, sysctl_set🟡 |
| network_sec | 3 | fw_add🔴, fw_del🔴, dns_flush🟡 |
| user_pkg | 6 | user_create🔴, user_lock🔴, user_pass🔴, pkg_install🔴, pkg_remove🔴, pkg_update🟡 |
| health | 2 | get, set🟡 |
| rag | 2 | search, stats |
| threat_hunt | 1 | hunt |

> 🔴 dangerous · 🟡 restricted · 其余 read_only

## 安全模型

```
用户输入 → intent_filter → injection_detector → permission_agent
  → _SUDO_COMMANDS (15 命令白名单) → run_command (高危参数拦截)
  → registry.call (统一执行 + 脱敏)
```

Agent 以专用 `xikiy` 用户运行，sudo 白名单精确到 15 个命令，systemd-journal/adm 组读日志。
