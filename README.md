# XikiyAIOps — 面向麒麟操作系统的安全智能运维 Agent

> 第十五届中国软件杯大赛 A 组赛题 | 出题企业：麒麟软件有限公司
> 版本: v1.0.0

---

## 项目简介

基于 MCP 协议构建的智能运维 Agent，作为自然语言与 Linux 操作系统交互的安全桥梁。大模型通过调用封装好的 MCP Tool 感知系统状态、执行运维任务——**AI 永远不直接接触 Shell**。

### 核心亮点

| 亮点 | 说明 |
|------|------|
| 🔒 多层安全护栏 | 4 层意图过滤 + 7 层注入检测 + 3 级权限代理，全链路防护 |
| 🔧 51 个 MCP Tool | 进程/网络/磁盘/内存/安全/系统/容器/健康配置，8 大类全覆盖 |
| 🖥️ 麒麟 OS 适配 | 自动检测 dnf/nftables/龙芯架构，兼容通用 Linux |
| 🧠 多 LLM 支持 | Ollama (qwen3) / DeepSeek / Qwen / OpenAI，工厂模式切换 |
| 🎨 Vue 3 前端 | 对话/仪表盘/审计日志三页面，SSE 流式输出 |
| 📊 智能根因分析 | 4 种异常检测算法 + 5 维度健康评分 (0~100) |

---

## 架构

```
用户 (Web UI) ──→ FastAPI ──→ registry.call() ──→ MCP Tool 执行
                      │               │
                 ┌────┴────┐    ┌─────┴──────┐
                 │ 安全护栏 │    │ 51 Tools   │
                 │ intent   │    │ process(7) │
                 │ injection│    │ disk(5)    │
                 │ permission│   │ network(6) │
                 └─────────┘    │ memory(5)  │
                                │ security(13)│
                                │ system(10) │
                                │ container(3)│
                                │ health(2)  │
                                └───────────┘
                      │
                 LLM (DeepSeek / Qwen)
```

---

## 快速启动

```bash
# 一键部署 (自动适配 x86_64 / LoongArch)
bash scripts/deploy.sh

# 部署后启动前后端
bash scripts/start.sh
```

| 服务 | 地址 | 用途 |
|------|------|------|
| 后端 API | `http://localhost:8001/health` | MCP Tool 调用 + 安全护栏 |
| Swagger | `http://localhost:8001/docs` | API 文档 |
| 前端 | `http://localhost:8001` | 对话/仪表盘/审计 (dev: `http://localhost:5173`) |

---

## 安全护栏体系

```
用户输入
  → ① intent_filter.classify_intent()     四层意图分类 + 威胁评分
  → ② injection_detector.detect_injection() 七层注入检测 (含同形字/零宽/Bidi)
  → ③ injection_detector.validate_llm_output() LLM 输出二次校验
  → ④ permission_agent.check_permission()   三级权限预检 + sudo 降权
  → ⑤ _common.run_command()                23 个命令白名单 + 高危参数拦截
  → ⑥ registry.call()                      统一执行入口
```

---

## MCP 插件 (51 Tools)

| 插件 | Tools | 说明 |
|------|:--:|------|
| **process** | 7 | inspect, detail, tree, zombie_scan, top_cpu, top_memory, kill 🔴 |
| **disk** | 5 | inspect, inode_usage, io_stats, mount_audit, large_files |
| **network** | 6 | listening_ports, connections_summary, interface_stats, firewall_audit, tcp_retrans, dns_check |
| **memory** | 5 | info, swap_info, oom_history, hugepages, slab_info |
| **security** | 13 | auth_failures, active_sessions, suid_scan, crontab_audit, kernel_modules, pending_updates, user_audit, sysctl_audit, user_list, open_files, selinux_status, password_policy, user_privilege |
| **system** | 10 | info, load, failed_services, boot_params, package_updates, entropy, cpu_detail, bios_info, journal_query, journal_tail |
| **container** | 3 | list, stats, inspect |
| **health_config** | 2 | get (read_only), set (restricted 🟡) |

> 🔴 = dangerous, 🟡 = restricted, 其余 49 个均为 read_only

---

## 项目结构

```
XikiyAIOps/
├── backend/app/
│   ├── core/                     # 安全护栏核心引擎
│   │   ├── intent_filter.py      # 意图风险过滤器 v2.0
│   │   ├── injection_detector.py # Prompt 注入检测 v2.0
│   │   ├── permission_agent.py   # 最小权限执行代理 v2.0
│   │   ├── platform_detect.py    # 麒麟 OS 平台检测
│   │   └── rca_analyzer.py       # 根因分析引擎
│   ├── mcp_plugins/             # MCP 插件 (8 大类 51 Tools)
│   │   ├── base.py              # 注册中心 + 风险预检
│   │   ├── _common.py           # 共享工具 + 命令白名单
│   │   ├── process_plugin.py    # 进程感知 (7 Tools)
│   │   ├── disk_plugin.py       # 磁盘感知 (5 Tools)
│   │   ├── network_plugin.py    # 网络感知 (6 Tools)
│   │   ├── memory_plugin.py     # 内存 + OOM (5 Tools)
│   │   ├── security_plugin.py   # 安全态势 (13 Tools)
│   │   ├── system_plugin.py     # 系统健康 (10 Tools)
│   │   └── container_plugin.py  # 容器感知 (3 Tools)
│   ├── api/                     # REST API (chat + audit)
│   ├── llm/                     # LLM 适配层 (4 Provider)
│   └── models/                  # 数据模型 (SQLAlchemy)
├── frontend/                    # Vue 3 + Element Plus + ECharts
│   └── src/
│       ├── views/               # ChatView / DashboardView / AuditLogView
│       ├── components/          # chat / dashboard / audit / common
│       ├── api/                 # SSE 流式 / 仪表盘 / 审计 API
│       ├── stores/              # Pinia (chat / system / audit)
│       └── router/              # Vue Router
├── docs/                        # 赛题文档 (6 份)
├── scripts/                     # deploy.sh + package.sh
└── dist/                        # 安装包 + 源码包
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ + FastAPI |
| MCP | 自研 Plugin 系统 + MCPTool Registry |
| 前端 | Vue 3 + Element Plus + ECharts + Pinia + TypeScript |
| LLM | Ollama (Qwen3) / DeepSeek / Qwen / OpenAI |
| 安全 | 4+7+3 层防护 + 命令白名单 + 高危参数拦截 |
| 数据库 | SQLite (SQLAlchemy AsyncSession) |
| 部署 | 麒麟 V11 (LoongArch) / 通用 Linux (x86_64) — 架构自动适配 |

---

## 赛题交付物

| # | 文件 | 说明 |
|:--:|------|------|
| 1 | `docs/01-需求分析.md` | 软件功能需求分析文档 |
| 2 | `docs/02-系统设计.md` | 软件功能设计文档 |
| 3 | `docs/03-产品说明书.md` | 软件产品说明书 |
| 4 | `docs/04-测试报告.md` | 软件功能测试报告 (68/71 通过) |
| 5 | `docs/05-性能测试报告.md` | 软件性能测试报告 |
| 6 | `dist/xikiy-aiops-v1.0.0.tar.gz` | 软件安装包 |
| 7 | `dist/xikiy-aiops-v1.0.0-src.tar.gz` | 软件源代码压缩包 |
| 6* | `docs/06-部署文档.md` | 部署文档 |
| 8 | (待制作) | 演示 PPT |
| 9 | (待制作) | 演示视频 (≤7min) |

---

## License

MIT
