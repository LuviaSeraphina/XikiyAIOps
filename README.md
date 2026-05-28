# SRE-agent — 面向麒麟操作系统的安全智能运维 Agent

> 第十五届中国软件杯大赛 A 组赛题
> 出题企业：麒麟软件有限公司

---

## 项目简介

构建一套部署于操作系统的智能运维 Agent，通过 MCP（Model Context Protocol）协议，赋予大模型感知系统实时状态、采集运维指标及执行管理任务的能力。

### 核心设计原则：AI 不能直接执行 Shell

后端封装底层工具为 MCP Tool，AI 只能调用 Tool，永远不直接接触 Shell。

---

## 架构

```
前端 (Vue 3)  ←→  FastAPI 后端  ←→  MCP Server  ←→  LLM
                      │
              ┌───────┼───────┐
              ▼       ▼       ▼
         安全护栏   审计日志   MCP 插件
```

---

## 项目结构

```
SRE-agent/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API 路由
│   │   ├── core/             # 安全护栏核心引擎
│   │   │   ├── intent_filter.py
│   │   │   ├── injection_detector.py
│   │   │   ├── permission_agent.py
│   │   │   └── audit_logger.py
│   │   ├── mcp_plugins/      # MCP 运维插件
│   │   ├── llm/              # LLM 集成
│   │   └── models/           # 数据模型
│   └── tests/                # 测试
├── frontend/                 # Vue 3 前端
├── docs/                     # 比赛文档
└── scripts/                  # 部署脚本
```

---

## 快速启动

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.13 + FastAPI |
| MCP | mcp (anthropic) |
| 前端 | Vue 3 + Element Plus |
| LLM | DeepSeek / Qwen3 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |

---

## 状态

🚧 项目骨架搭建完成，功能开发进行中
