#!/usr/bin/env bash
# ============================================================
# XikiyAIOps 一键部署 v1.2.0 (amd64)
# 用法: sudo bash scripts/deploy.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'
log_ok()   { echo -e "  ${GREEN}[OK]${NC}    $*"; }
log_info() { echo -e "  ${BLUE}[INFO]${NC}  $*"; }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC}  $*"; }
log_err()  { echo -e "  ${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
ACTUAL_USER="${SUDO_USER:-$(whoami)}"
_PROD_DIR="/opt/xikiy-aiops"

echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   XikiyAIOps 一键部署 v1.2.0          ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Step 1: 环境检测
# ============================================================
echo -e "\n${BOLD}▶ Step 1/6: 环境检测${NC}"

ARCH="$(uname -m)"
OS_ID="unknown"
[ -f /etc/os-release ] && . /etc/os-release && OS_ID="${ID:-unknown}"

PKG_MGR=""
command -v dnf &>/dev/null && PKG_MGR="dnf"
command -v apt &>/dev/null && PKG_MGR="apt"
[ -z "$PKG_MGR" ] && { log_err "未检测到 dnf/apt"; exit 1; }

echo "  OS: $OS_ID | 架构: $ARCH | 包管理: $PKG_MGR"

install_pkg() {
  if [ "$PKG_MGR" = "dnf" ]; then
    sudo dnf install -y "$1" 2>/dev/null && return 0 || return 1
  else
    sudo apt install -y "$1" 2>/dev/null && return 0 || return 1
  fi
}

# ============================================================
# Step 2: 系统依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 2/6: 系统依赖${NC}"

PYTHON_BIN=""
for py in python3.11 python3.10 python3; do
  command -v "$py" &>/dev/null && { PYTHON_BIN="$py"; break; }
done
[ -z "$PYTHON_BIN" ] && { install_pkg python3.11 || install_pkg python3; PYTHON_BIN="python3.11"; }
log_ok "Python: $($PYTHON_BIN --version)"

if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
  command -v node &>/dev/null || { install_pkg nodejs 2>/dev/null || true; install_pkg npm 2>/dev/null || true; }
  command -v node &>/dev/null && log_ok "Node: $(node --version)" || log_warn "Node 未安装"
fi

log_info "安装编译工具链..."
for pkg in gcc gcc-c++ make python3-devel; do
  install_pkg "$pkg" 2>/dev/null || true
done
log_ok "编译工具链就绪"

# ============================================================
# Step 3: 后端依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 3/6: 后端依赖${NC}"
cd "$BACKEND_DIR"

VENV_DIR="$BACKEND_DIR/.venv"
VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -d "$VENV_DIR" ]; then
  $PYTHON_BIN -m venv "$VENV_DIR"
  log_ok "venv 已创建"
else
  log_info "venv 已存在"
fi
"$VENV_PIP" install --upgrade pip -q 2>/dev/null || true

log_info "安装 Python 依赖..."
"$VENV_PIP" install -r requirements.txt -q 2>/dev/null || true
log_ok "Python 依赖已安装"

# ============================================================
# Step 4: 前端
# ============================================================
echo -e "\n${BOLD}▶ Step 4/6: 前端${NC}"
if [ -f "$FRONTEND_DIR/dist/index.html" ]; then
  log_ok "前端已预构建 (dist/), 跳过"
else
  log_info "构建前端..."
  cd "$FRONTEND_DIR"
  command -v npm &>/dev/null && npm install --silent --legacy-peer-deps && npm run build 2>&1 | tail -1
  cd "$PROJECT_DIR"
  log_ok "前端构建完成"
fi

# ============================================================
# Step 5: 配置 + 数据库 + RAG
# ============================================================
echo -e "\n${BOLD}▶ Step 5/6: 配置${NC}"
cd "$BACKEND_DIR"

if [ ! -f .env ]; then
  tee .env > /dev/null << ENVEOF
MAX_RISK_LEVEL=restricted
REQUIRE_CONFIRMATION=true
AUDIT_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///data/xikiy_aiops.db
ENVEOF
  log_ok ".env 已生成"
else
  log_info ".env 已存在, 跳过"
fi

mkdir -p data/rag_db data/sre_kb
"$VENV_PYTHON" -c "
from app.db import init_db
import asyncio
asyncio.run(init_db())
print('数据库就绪')
" 2>&1 | tail -1
log_ok "数据库就绪"

log_info "构建 RAG 知识库索引..."
"$VENV_PYTHON" -c "
from app.rag.ingestion import build_knowledge_base
build_knowledge_base(force=True)
print('RAG 就绪')
" 2>&1 | tail -3
log_ok "RAG 知识库已索引"

echo ""
_TOOLS=$("$VENV_PYTHON" -c "from app.mcp_plugins.base import registry; print(registry.count)" 2>/dev/null || echo "0")
echo -e "  MCP Tool: ${GREEN}$_TOOLS${NC} 个  |  LLM: ${YELLOW}请在前端配置${NC}"

# ============================================================
# Step 6: 最小权限代理
# ============================================================
echo -e "\n${BOLD}▶ Step 6/6: 最小权限代理${NC}"
_DEPLOY_USER="$(whoami)"

if ! getent group xikiy &>/dev/null; then
  sudo groupadd -r xikiy && log_ok "组 xikiy 已创建"
fi
if ! id xikiy &>/dev/null; then
  sudo useradd -r -g xikiy -d "$_PROD_DIR" -s /sbin/nologin xikiy
  log_ok "用户 xikiy 已创建"
else
  log_info "用户 xikiy 已存在"
fi

if [ "$PROJECT_DIR" != "$_PROD_DIR" ]; then
  log_info "安装到 $_PROD_DIR ..."
  sudo mkdir -p "$_PROD_DIR"
  sudo cp -r "$PROJECT_DIR"/* "$_PROD_DIR/" 2>/dev/null || true
  log_ok "项目已复制到 $_PROD_DIR"
fi
sudo chown -R xikiy:xikiy "$_PROD_DIR"

log_info "创建 venv (xikiy) ..."
sudo rm -rf "$_PROD_DIR/backend/.venv"
sudo -u xikiy python3 -m venv "$_PROD_DIR/backend/.venv"
sudo -u xikiy "$_PROD_DIR/backend/.venv/bin/pip" install --upgrade pip -q 2>/dev/null || true

log_info "安装 Python 依赖..."
sudo -u xikiy "$_PROD_DIR/backend/.venv/bin/pip" install -r "$_PROD_DIR/backend/requirements.txt" -q 2>/dev/null || true
log_ok "Python 依赖已安装"

sudo -u xikiy mkdir -p "$_PROD_DIR/backend/data"
sudo -u xikiy tee "$_PROD_DIR/backend/.env" > /dev/null << ENVEOF
MAX_RISK_LEVEL=restricted
REQUIRE_CONFIRMATION=true
AUDIT_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///$_PROD_DIR/backend/data/xikiy_aiops.db
ENVEOF
log_ok ".env 已生成"

sudo -u xikiy rm -f "$_PROD_DIR/backend/data/xikiy_aiops.db" 2>/dev/null || true
sudo -u xikiy bash -c "cd '$_PROD_DIR/backend' && '$_PROD_DIR/backend/.venv/bin/python' -c \"
from app.db import init_db
import asyncio
asyncio.run(init_db())
\"" 2>&1 | tail -1
log_ok "数据库已初始化"

log_info "构建 RAG 知识库索引..."
sudo -u xikiy bash -c "cd '$_PROD_DIR/backend' && PYTHONPATH='$_PROD_DIR/backend' '$_PROD_DIR/backend/.venv/bin/python' -c \"
from app.rag.ingestion import build_knowledge_base
build_knowledge_base(force=True)
print('RAG 就绪')
\"" 2>&1 | tail -3
log_ok "RAG 知识库已索引"

_SUDOERS_SRC="$PROJECT_DIR/scripts/sudoers.d/xikiy-aiops"
if [ -f "$_SUDOERS_SRC" ]; then
  sudo install -m 440 "$_SUDOERS_SRC" /etc/sudoers.d/xikiy-aiops
  log_ok "sudoers 已配置 (%xikiy 组免密)"
fi

_SVC_FILE="/etc/systemd/system/xikiy-aiops.service"
sudo tee "$_SVC_FILE" > /dev/null << SVCEOF
[Unit]
Description=XikiyAIOps — 麒麟安全智能运维 Agent
After=network-online.target
Wants=network-online.target

[Service]
User=xikiy
WorkingDirectory=$_PROD_DIR/backend
ExecStart=$_PROD_DIR/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONPATH=$_PROD_DIR/backend
Environment=DATABASE_URL=sqlite+aiosqlite:///$_PROD_DIR/backend/data/xikiy_aiops.db

[Install]
WantedBy=multi-user.target
SVCEOF
sudo systemctl daemon-reload
sudo systemctl enable xikiy-aiops 2>/dev/null || true
log_ok "systemd 服务已注册"

if getent group sudo >/dev/null 2>&1; then
  sudo usermod -aG sudo xikiy 2>/dev/null || true
elif getent group wheel >/dev/null 2>&1; then
  sudo usermod -aG wheel xikiy 2>/dev/null || true
fi
if getent group systemd-journal >/dev/null 2>&1; then
  sudo usermod -aG systemd-journal xikiy 2>/dev/null || true
fi
if getent group adm >/dev/null 2>&1; then
  sudo usermod -aG adm xikiy 2>/dev/null || true
fi
if [ "$_DEPLOY_USER" != "root" ]; then
  sudo usermod -aG xikiy "$_DEPLOY_USER" 2>/dev/null || true
fi

echo ""
echo -e "  ${BOLD}${GREEN}✅ 部署完成${NC}"
echo -e "  启动服务: ${BOLD}bash $_PROD_DIR/scripts/start.sh${NC}"
