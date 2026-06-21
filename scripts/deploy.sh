#!/usr/bin/env bash
# ============================================================
# SRE-agent 一键部署 v1.0.0
# 用法: bash scripts/deploy.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'
log_ok()   { echo -e "  ${GREEN}[OK]${NC}    $*"; }
log_info() { echo -e "  ${BLUE}[INFO]${NC}  $*"; }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC}  $*"; }
log_err()  { echo -e "  ${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "\n  ${CYAN}[···]${NC}  $*"; }

# 定义脚本全局变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
OFFLINE_DIR="$PROJECT_DIR/offline-packages"
ACTUAL_USER="${SUDO_USER:-$(whoami)}"

echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   SRE-agent 一键部署 v1.0.0          ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Step 1: 环境检测
# ============================================================
echo -e "\n${BOLD}▶ Step 1/5: 环境检测${NC}"

ARCH="$(uname -m)"
IS_LOONGARCH=false
[[ "$ARCH" == "loongarch64" ]] && IS_LOONGARCH=true

OS_ID="unknown"
[ -f /etc/os-release ] && . /etc/os-release && OS_ID="${ID:-unknown}"

PKG_MGR=""
command -v dnf &>/dev/null && PKG_MGR="dnf"
command -v apt &>/dev/null && PKG_MGR="apt"
[ -z "$PKG_MGR" ] && { log_err "未检测到 dnf/apt"; exit 1; }

_HAS_RPM=false; _HAS_WHEELS=false
[ -f "$OFFLINE_DIR/rpms.tar.gz" ] && _HAS_RPM=true
[ -f "$OFFLINE_DIR/wheels.tar.gz" ] && _HAS_WHEELS=true

echo "  OS: $OS_ID | 架构: $ARCH | 包管理: $PKG_MGR"
echo "  离线 RPM: $_HAS_RPM | 离线 Wheel: $_HAS_WHEELS"

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
echo -e "\n${BOLD}▶ Step 2/5: 系统依赖${NC}"

#离线 RPM
if [ "$_HAS_RPM" = true ]; then
  _TMP="$(mktemp -d)"
  tar xzf "$OFFLINE_DIR/rpms.tar.gz" -C "$_TMP" 2>/dev/null || true
  _CNT=$(find "$_TMP" -name "*.rpm" 2>/dev/null | wc -l)
  [ "$_CNT" -gt 0 ] && log_info "安装 $_CNT 个 RPM..." && find "$_TMP" -name "*.rpm" -print0 | xargs -0 sudo rpm -ivh --nodeps 2>/dev/null || true
  rm -rf "$_TMP"
fi

#Python 3.11
PYTHON_BIN=""
for py in python3.11 python3.10 python3; do
  command -v "$py" &>/dev/null && { PYTHON_BIN="$py"; break; }
done
[ -z "$PYTHON_BIN" ] && { install_pkg python3.11 || install_pkg python3; PYTHON_BIN="python3.11"; }
log_ok "Python: $($PYTHON_BIN --version)"

#Node.js (仅前端未构建时需要)
if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
  command -v node &>/dev/null || { install_pkg nodejs 2>/dev/null || true; install_pkg npm 2>/dev/null || true; }
  command -v node &>/dev/null && log_ok "Node: $(node --version)" || log_warn "Node 未安装, 前端构建将跳过"
fi

#LoongArch: 编译工具链 (pip 在线回退时需要)
if [ "$IS_LOONGARCH" = true ]; then
  for pkg in gcc gcc-c++ make git cmake python3-devel; do
    install_pkg "$pkg" 2>/dev/null || true
  done
  log_ok "编译工具链就绪"
fi

# ============================================================
# Step 3: 后端依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 3/5: 后端依赖${NC}"
cd "$BACKEND_DIR"

VENV_DIR="$BACKEND_DIR/.venv"
VENDOR_DIR="$BACKEND_DIR/vendor"

#创建 venv (LoongArch 用 --system-site-packages 复用系统 numpy/scipy)
if [ ! -d "$VENV_DIR" ]; then
  if [ "$IS_LOONGARCH" = true ]; then
    $PYTHON_BIN -m venv "$VENV_DIR" --system-site-packages
  else
    $PYTHON_BIN -m venv "$VENV_DIR"
  fi
  log_ok "venv 已创建"
else
  log_info "venv 已存在"
fi

VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"
"$VENV_PIP" install --upgrade pip -q 2>/dev/null || true

#解压离线 wheel
if [ "$_HAS_WHEELS" = true ]; then
  log_info "解压离线 wheel..."
  rm -rf "$VENDOR_DIR" && mkdir -p "$VENDOR_DIR"
  _TMP="$(mktemp -d)"
  tar xzf "$OFFLINE_DIR/wheels.tar.gz" -C "$_TMP" 2>/dev/null || true
  find "$_TMP" -name '*.whl' -exec mv {} "$VENDOR_DIR/" \; 2>/dev/null || true
  rm -rf "$_TMP"
  _CNT=$(find "$VENDOR_DIR" -maxdepth 1 -name '*.whl' 2>/dev/null | wc -l)
  if [ "$_CNT" -gt 0 ]; then
    log_ok "vendor/ 就绪: $_CNT 个 wheel"
  else
    log_warn "wheels.tar.gz 解压失败, 将在线安装"
    _HAS_WHEELS=false
  fi
fi

#安装依赖
if [ "$_HAS_WHEELS" = true ]; then
  log_info "离线安装..."

  #逐个装所有 wheel, --no-deps 完全跳过依赖解析
  _TOTAL=$(find "$VENDOR_DIR" -name '*.whl' 2>/dev/null | wc -l)
  _DONE=0
  for _whl in "$VENDOR_DIR"/*.whl; do
    "$VENV_PIP" install --no-deps "$_whl" 2>&1 | tail -1
    _DONE=$((_DONE + 1))
  done
  log_ok "已安装 $_DONE / $_TOTAL 个包"

  #修复 pydantic 版本检查 + METADATA
  _CORE_VER=$("$VENV_PIP" show pydantic-core 2>/dev/null | awk '/Version/ {print $2}')
  if [ -n "$_CORE_VER" ]; then
    _VER_FILE=$(find "$VENV_DIR" -path '*/pydantic/version.py' 2>/dev/null | head -1)
    _META_FILE=$(find "$VENV_DIR" -path '*/pydantic-*.dist-info/METADATA' 2>/dev/null | head -1)
    #直接把 version.py 里 '2.46.4' 这样的硬编码版本号替换掉
    [ -f "$_VER_FILE" ] && sed -i "s/'2\.[0-9]\+\.[0-9]\+'/'$_CORE_VER'/g" "$_VER_FILE" 2>/dev/null || true
    [ -f "$_META_FILE" ] && sed -i "s/pydantic-core==[0-9.]*/pydantic-core>=$_CORE_VER/" "$_META_FILE" 2>/dev/null || true
    log_info "pydantic 版本检查已适配 ($_CORE_VER)"
  fi
else
  log_info "在线安装..."
  "$VENV_PIP" install -r requirements.txt 2>&1 | tail -5
fi

#校验
for pkg in fastapi uvicorn pydantic pydantic-core greenlet sqlalchemy; do
  "$VENV_PIP" show "$pkg" &>/dev/null || { log_err "$pkg 未安装"; exit 1; }
done
log_ok "后端依赖就绪 ($("$VENV_PIP" list 2>/dev/null | wc -l) 个包)"

# ============================================================
# Step 4: 前端
# ============================================================
echo -e "\n${BOLD}▶ Step 4/5: 前端${NC}"

if [ -f "$FRONTEND_DIR/dist/index.html" ]; then
  log_ok "前端已预构建 (dist/), 跳过"
elif [ -f "$FRONTEND_DIR/package.json" ] && command -v npm &>/dev/null; then
  cd "$FRONTEND_DIR"
  log_info "npm install + build..."
  npm install --silent 2>&1 | tail -3
  npm run build 2>&1 | tail -3
  [ -f "dist/index.html" ] && log_ok "前端构建完成" || log_warn "前端构建失败"
else
  log_warn "前端不可用 (缺 dist/ 且无法构建)"
fi

# ============================================================
# Step 5: 配置
# ============================================================
echo -e "\n${BOLD}▶ Step 5/5: 配置${NC}"
cd "$BACKEND_DIR"

#.env (支持环境变量预设: SRE_LLM_PROVIDER / SRE_LLM_MODEL / SRE_LLM_API_KEY)
if [ ! -f .env ]; then
  if [ -n "${SRE_LLM_PROVIDER:-}" ]; then
    #非交互模式: 从环境变量读取
    _PROVIDER="${SRE_LLM_PROVIDER}"; _URL="${SRE_LLM_BASE_URL:-https://api.deepseek.com}"
    _MODEL="${SRE_LLM_MODEL:-deepseek-v4-flash}"; _KEY="${SRE_LLM_API_KEY:-}"
    log_info "LLM 配置来自环境变量: $_PROVIDER / $_MODEL"
  else
    #交互模式: 默认 DeepSeek 云端
    echo ""
    echo "  配置 LLM (默认 DeepSeek 云端):"
    _PROVIDER="deepseek"; _URL="https://api.deepseek.com"
    echo -n "  模型 (默认 deepseek-v4-flash): "; read -r _M; _MODEL="${_M:-deepseek-v4-flash}"
    echo -n "  API Key: "; read -rs _KEY; echo ""
  fi

  cat > .env << EOF
LLM_PROVIDER=$_PROVIDER
LLM_BASE_URL=$_URL
LLM_MODEL=$_MODEL
LLM_API_KEY=$_KEY
MAX_RISK_LEVEL=restricted
REQUIRE_CONFIRMATION=true
AUDIT_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///$BACKEND_DIR/data/sre_agent.db
EOF
  log_ok ".env 已生成"
else
  log_info ".env 已存在, 跳过配置"
  _PROVIDER=$(grep -oP 'LLM_PROVIDER=\K.*' .env 2>/dev/null || echo "?")
  _MODEL=$(grep -oP 'LLM_MODEL=\K.*' .env 2>/dev/null || echo "?")
fi

#数据库
mkdir -p data
"$VENV_PYTHON" -c "
from app.db import init_db
import asyncio
asyncio.run(init_db())
print('数据库就绪')
" 2>&1 | tail -1
log_ok "数据库就绪"

#验证
echo ""
_TOOLS=$("$VENV_PYTHON" -c "from app.mcp_plugins.base import registry; print(registry.count)" 2>/dev/null || echo "0")
echo -e "  MCP Tool: ${GREEN}$_TOOLS${NC} 个  |  LLM: ${GREEN}$_PROVIDER / $_MODEL${NC}"
echo ""
echo -e "  ${BOLD}${GREEN}✅ 部署完成${NC}"
echo -e "  启动: ${BOLD}bash scripts/start.sh${NC}"
echo -e "  访问: ${BOLD}http://localhost:8001${NC}"
echo ""
