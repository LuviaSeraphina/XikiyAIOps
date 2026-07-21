# XikiyAIOps — Linux 智能运维 Agent

> 用自然语言管理 Linux 服务器。AI 不接触 Shell，全部走 92 个安全封装的 MCP 运维工具。

---

## 核心亮点

| 亮点 | 说明 |
|------|------|
| 🗣️ 自然语言运维 | "看看系统状态" → Agent 规划 → 执行 → 验证 → 报告，零命令行 |
| 🧠 LangChain Agent | ReAct + PlanAndExecute 双模，参数修正重试 + Replan + 后置验证 |
| 🔒 五道安全防线 | 意图过滤 → 注入检测 → 意图审计 → 四级权限代理 → sudo 降权 |
| 🔧 92 个 MCP Tool | 进程/磁盘/网络/内存/安全/系统/容器/Docker沙箱/备份/敏感规则，17 插件 |
| 📊 全链路追踪 | PipelineTrace 记录 规划→执行→重试→验证→总结，含意图审计评分 |
| 🐳 Docker 沙箱 | 高危命令在隔离容器执行 (network=none, read-only, 资源限制) |
| 🎨 Vue 3 前端 | 对话 / 仪表盘 / 审计(四级风险筛选) / 模型配置，SSE 流式 |

## 架构 (v2.1)

```
用户 (Web UI) ──→ FastAPI ──→ LangChain Agent
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
               Plan (规划)    Execute (执行)   Verify (验证)
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                            Summarize (报告)
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       意图审计              权限代理              全链路追踪
    (危险模式检测)     (四级风险+sudu降权)    (PipelineTrace)
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
                          MCP 注册中心 (92 Tools)
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

## MCP 工具 (92 Tools)

| 插件 | 数量 | 说明 |
|------|:--:|------|
| process | 12 | inspect, detail, tree, zombie, top_cpu, top_mem, smaps, io_top, kill🚫, renice🟡, ionice🟡, zombie_cleanup🟡 |
| disk | 5 | inspect, inode, io_stats, mount_audit, large_files |
| network | 8 | ports, connections, interfaces, firewall, tcp_retrans, dns, ping, http |
| memory | 5 | info, swap, oom_history, hugepages, slab |
| security | 12 | auth_failures, sessions, suid, crontab, kernel_mods, updates, user_audit, sysctl, open_files, selinux, password, privilege |
| system | 11 | info, load, failed_svcs, boot, packages, entropy, cpu, bios, journal_query, journal_tail, timers, vmstat |
| container | 3 | list, stats, inspect |
| ops | 5 | file_identify, file_read, file_truncate🟡, disk_cleanup🟡, logrotate🟡 |
| service | 1 | service_control🟡 |
| config | 4 | diff, backup🟡, restore🟡, sysctl_set🟡 |
| network_sec | 3 | fw_add🔴, fw_del🔴, dns_flush🟡 |
| user_pkg | 6 | user_create🔴, user_lock🔴, user_pass🔴, pkg_install🔴, pkg_remove🔴, pkg_update🟡 |
| health | 2 | get, set🟡 |
| rag | 3 | search, stats, doc_sync🟡 |
| threat_hunt | 1 | hunt |
| sandbox | 2 | sandbox_exec🟡, sandbox_status |
| backup | 4 | backup_create🟡, backup_list, backup_restore🔴, backup_cleanup🟡 |
| sensitive_rules | 3 | get, set🔴, reload |

> 🚫 critical · 🔴 dangerous · 🟡 restricted · 其余 read_only

## 四级风险体系

| 等级 | 标签 | 规则 |
|------|------|------|
| `read_only` | 🟢 安全 | 所有用户可执行 |
| `restricted` | 🟡 受限 | sudo 组成员 + 前端确认弹窗 |
| `dangerous` | 🔴 高危 | 仅 root + 确认弹窗 (防火墙/用户管理/包管理) |
| `critical` | 🚫 致命 | root + 强制确认 + 保护名单拦截 (如 process_kill 不可杀 sshd/systemd) |

## 安全模型 (五道防线)

```
用户输入
  → 第一道: intent_filter (越狱/注入签名检测)
  → 第二道: injection_detector (同形字/命令注入)
  → 第三道: intent_auditor (意图危险模式匹配 + 攻击链检测, 自动拦截≥90分)
  → 第四道: permission_agent (四级风险 + 保护名单 + sudo/Docker 降权)
  → 第五道: registry.call (统一执行 + 脱敏)
```

Agent 以专用 `xikiy` 用户运行，sudo 白名单精确管控，Docker 沙箱可选隔离执行。

## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 智能对话 | `/#/chat` | SSE 流式对话，Plan/Execute/Verify 阶段可视化，工具调用卡片 |
| 仪表盘 | `/#/dashboard` | 系统健康概览 |
| 审计日志 | `/#/audit` | 四级风险筛选 + 异常标记(security_blocked等) + 推理链路溯源 |
| 模型配置 | `/#/settings` | LLM Provider/API Key/模型参数配置 |

## 知识库

`backend/data/sre_kb/` 含 24 篇 SRE 运维知识文档，覆盖 CPU/内存/磁盘/网络/进程/systemd/安全/备份/容器/内核调优等场景，通过 RAG 检索辅助 Agent 决策。

