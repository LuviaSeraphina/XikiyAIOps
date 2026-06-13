#!/usr/bin/env bash
# ============================================================
# SRE-agent 一键部署脚本 v1.0
#
# 适配: 麒麟 V10/V11 (x86_64 / LoongArch64) + Ubuntu/Debian
# 用法: bash scripts/deploy.sh
#
# 修复了 v0.2 在麒麟 LoongArch 虚拟机上遇到的所有已知问题:
#   - npm 缺失 / node_modules 权限 / dist 清理失败
#   - numpy/pandas/scikit-learn 源码编译失败 (改用 dnf 系统包)
#   - libffi-devel 缺失导致 cffi 编译失败
#   - greenlet 缺失导致 SQLAlchemy 异步连接失败
#   - uvicorn 不在 PATH
#   - 数据库路径错误 (root vs vmuser) / data 目录只读
#   - Ollama 在 LoongArch 上不可用 (默认 DeepSeek 云端)
#   - pip install -q 看不到过程 (已改为显示进度)
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
log_ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
log_info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
ACTUAL_USER="${SUDO_USER:-$(whoami)}"
ACTUAL_HOME="$(eval echo ~$ACTUAL_USER)"

echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║     SRE-agent 一键部署 v1.0                        ║"
echo "  ║     适配麒麟 V10/V11 (LoongArch) + 通用 Linux       ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Step 1: 检测系统和包管理器
# ============================================================
echo -e "\n${BOLD}▶ Step 1/7: 检测系统环境${NC}"

OS_ID=""; OS_NAME=""; PKG_MGR=""; IS_LOONGARCH=false
ARCH="$(uname -m)"
[[ "$ARCH" == "loongarch64" ]] && IS_LOONGARCH=true

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_NAME="${PRETTY_NAME:-$OS_ID}"
elif [ -f /etc/kylin-release ]; then
    OS_ID="kylin"; OS_NAME="Kylin Linux"
fi

if command -v dnf &>/dev/null; then PKG_MGR="dnf"
elif command -v apt &>/dev/null; then PKG_MGR="apt"
else log_err "未检测到 dnf/apt"; exit 1; fi

echo "  OS       : $OS_NAME"
echo "  架构     : $ARCH (LoongArch: $IS_LOONGARCH)"
echo "  包管理器 : $PKG_MGR"
echo "  用户     : $ACTUAL_USER (home: $ACTUAL_HOME)"

# ============================================================
# Step 2: 安装系统依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 2/7: 安装系统依赖${NC}"

install_pkg() {
    local pkg="$1"
    if [ "$PKG_MGR" = "dnf" ]; then
        sudo dnf install -y "$pkg" 2>/dev/null && return 0 || return 1
    else
        sudo apt install -y "$pkg" 2>/dev/null && return 0 || return 1
    fi
}

# Python 3
PYTHON_BIN=""
for py in python3.11 python3.10 python3; do
    command -v "$py" &>/dev/null && { PYTHON_BIN="$py"; break; }
done
if [ -z "$PYTHON_BIN" ]; then
    log_info "安装 Python 3..."
    install_pkg python3.11 || install_pkg python3 || { log_err "Python 安装失败"; exit 1; }
    PYTHON_BIN="python3.11"
fi
log_ok "Python: $($PYTHON_BIN --version)"

# Node.js + npm
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    log_info "安装 Node.js + npm..."
    if [ "$PKG_MGR" = "dnf" ]; then
        sudo dnf install -y nodejs npm 2>/dev/null || {
            log_warn "dnf 源无 nodejs, 尝试 NodeSource..."
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo dnf install -y nodejs npm
        }
    else
        sudo apt update -qq && sudo apt install -y nodejs npm
    fi
fi
log_ok "Node: $(node --version) / npm: $(npm --version)"

# 编译工具链 (LoongArch 必备 — 大量包无预编译 wheel)
if [ "$IS_LOONGARCH" = true ]; then
    log_info "LoongArch: 安装编译工具链..."
    for pkg in gcc gcc-c++ make python3-devel libffi-devel openssl-devel; do
        install_pkg "$pkg" || log_warn "跳过: $pkg"
    done
    # numpy/pandas/scikit-learn 优先用系统包 (避免源码编译一小时)
    log_info "LoongArch: 安装 Python 系统包 (numpy/pandas/scikit-learn)..."
    for pkg in python3-numpy python3-pandas python3-scikit-learn; do
        install_pkg "$pkg" || log_warn "跳过系统包: $pkg (将尝试 pip 源码编译)"
    done
fi

# ============================================================
# Step 3: Python 虚拟环境 + 后端依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 3/7: 安装后端依赖${NC}"

cd "$BACKEND_DIR"

# 虚拟环境
if [ ! -d ".venv" ]; then
    $PYTHON_BIN -m venv .venv
    log_ok "虚拟环境已创建"
else
    log_info "虚拟环境已存在, 跳过"
fi
source .venv/bin/activate
pip install --upgrade pip -q

# 安装依赖 (显示进度, 不做静默)
log_info "安装 Python 依赖 (可能需要几分钟)..."
if [ "$IS_LOONGARCH" = true ]; then
    # 先装 greenlet (SQLAlchemy 异步必需, 麒麟上经常漏)
    pip install greenlet 2>&1 | tail -3
fi
pip install -r requirements.txt 2>&1 | tail -20

# 明确校验关键包
for pkg in fastapi uvicorn sqlalchemy psutil greenlet aiosqlite httpx pydantic pytest; do
    pip show "$pkg" &>/dev/null || { log_err "$pkg 未安装"; exit 1; }
done
log_ok "后端依赖安装完成 ($(pip list 2>/dev/null | wc -l) 个包)"

# ============================================================
# Step 4: 前端依赖 + 构建
# ============================================================
echo -e "\n${BOLD}▶ Step 4/7: 安装前端依赖并构建${NC}"

cd "$FRONTEND_DIR"

# 清理旧文件 (修复: 上次构建的 dist 可能是 root 所有)
if [ -d "dist" ]; then
    rm -rf dist 2>/dev/null || sudo rm -rf dist
fi

# 安装依赖 (强制重装 node_modules 避免 vue-tsc 权限问题)
if [ -d "node_modules" ]; then
    log_info "清理旧 node_modules (避免权限问题)..."
    rm -rf node_modules package-lock.json 2>/dev/null || sudo rm -rf node_modules package-lock.json
fi

log_info "npm install (可能需要几分钟)..."
npm install 2>&1 | tail -10

# 验证关键 bin
for bin in node_modules/.bin/vite node_modules/.bin/vue-tsc; do
    if [ ! -x "$bin" ]; then
        log_warn "$bin 不可执行, 修复权限"
        chmod +x "$bin" 2>/dev/null || true
    fi
done

log_info "npm run build..."
npm run build 2>&1 | tail -10

if [ -f "dist/index.html" ]; then
    log_ok "前端构建完成 (dist/index.html)"
else
    log_err "前端构建失败: dist/index.html 不存在"
    exit 1
fi

# ============================================================
# Step 5: LLM 配置
# ============================================================
echo -e "\n${BOLD}▶ Step 5/7: 配置 LLM${NC}"

cd "$BACKEND_DIR"

echo ""
echo "  请选择 LLM 模式:"
echo "  ┌──────────────────────────────────────────────┐"
echo "  │ [1] DeepSeek 云端 (推荐)                      │"
echo "  │     base_url: https://api.deepseek.com       │"
echo "  │     模型: deepseek-v4-flash                   │"
echo "  │     需要 API Key                              │"
echo "  │                                               │"
echo "  │ [2] Ollama 本地 (仅 x86_64, 需 8GB+)          │"
echo "  │     模型: qwen3:4b, 端口: 11434               │"
echo "  │     → LoongArch 暂不支持, 请选 [1]            │"
echo "  └──────────────────────────────────────────────┘"
echo ""

if [ "$IS_LOONGARCH" = true ]; then
    LLM_PROVIDER="deepseek"
    echo -n "  请输入选项 [1/2] (LoongArch 建议 1, 默认 1): "
else
    echo -n "  请输入选项 [1/2] (默认 1): "
fi
read -r llm_choice
llm_choice="${llm_choice:-1}"

if [ "$llm_choice" = "2" ] && [ "$IS_LOONGARCH" = false ]; then
    LLM_PROVIDER="ollama"
    LLM_BASE_URL="http://localhost:11434"
    echo -n "  模型名称 [默认: qwen3:4b]: "; read -r llm_model
    LLM_MODEL="${llm_model:-qwen3:4b}"
    LLM_API_KEY=""
    log_info "请手动启动: ollama serve && ollama pull $LLM_MODEL"
else
    LLM_PROVIDER="deepseek"
    LLM_BASE_URL="https://api.deepseek.com"
    echo -n "  模型名称 [默认: deepseek-v4-flash]: "; read -r llm_model
    LLM_MODEL="${llm_model:-deepseek-v4-flash}"
    echo -n "  API Key: "; read -rs LLM_API_KEY; echo ""
fi

# ============================================================
# Step 6: 生成配置 + 数据库初始化
# ============================================================
echo -e "\n${BOLD}▶ Step 6/7: 生成配置 + 初始化数据库${NC}"

cd "$BACKEND_DIR"
mkdir -p data
# 修复: 确保 data 目录属于当前用户 (不是 root)
sudo chown -R "$ACTUAL_USER:$(id -gn "$ACTUAL_USER")" data/ 2>/dev/null || true
chmod 755 data

cat > .env << EOF
# SRE-agent LLM 配置 (由 deploy.sh v1.0 自动生成)
LLM_PROVIDER=$LLM_PROVIDER
LLM_BASE_URL=$LLM_BASE_URL
LLM_MODEL=$LLM_MODEL
LLM_API_KEY=$LLM_API_KEY

# 安全配置
MAX_RISK_LEVEL=restricted
REQUIRE_CONFIRMATION=true
AUDIT_ENABLED=true

# 数据库 (绝对路径, 修复 root vs vmuser 路径问题)
DATABASE_URL=sqlite+aiosqlite:///$BACKEND_DIR/data/state_store.db
EOF

log_ok ".env 已生成"

# 初始化数据库表
source .venv/bin/activate
python -c "
from app.db import init_db
import asyncio
asyncio.run(init_db())
print('数据库表初始化完成')
" 2>&1 | tail -3
log_ok "数据库已就绪"

# ============================================================
# Step 7: 验证
# ============================================================
echo -e "\n${BOLD}▶ Step 7/7: 部署验证${NC}"

source .venv/bin/activate
errors=0

# Tool 注册
echo -n "  [验证] MCP Tool 注册... "
TOOLS=$(python -c "from app.mcp_plugins.base import registry; print(registry.count)" 2>/dev/null || echo "0")
if [ "$TOOLS" -ge 45 ]; then
    echo -e "${GREEN}✅${NC} $TOOLS 个 Tool"
else
    echo -e "${RED}❌${NC} 仅 $TOOLS 个"; errors=$((errors+1))
fi

# 安全护栏
echo -n "  [验证] 安全护栏... "
SAFE=$(python -c "
from app.core.intent_filter import classify_intent, IntentCategory
cat, _, _ = classify_intent('rm -rf /etc')
print('OK' if cat==IntentCategory.DANGEROUS_ACTION else 'FAIL')
" 2>/dev/null || echo "FAIL")
if [ "$SAFE" = "OK" ]; then echo -e "${GREEN}✅${NC} 意图分类正常"; else echo -e "${RED}❌${NC}"; errors=$((errors+1)); fi

# LLM 配置
echo -n "  [验证] LLM 配置... "
LLM_INFO=$(python -c "from app.llm.config import LLM_PROVIDER, LLM_MODEL; print(f'{LLM_PROVIDER}/{LLM_MODEL}')" 2>/dev/null || echo "ERROR")
echo -e "${GREEN}$LLM_INFO${NC}"

# 前端
echo -n "  [验证] 前端构建... "
if [ -f "$FRONTEND_DIR/dist/index.html" ]; then echo -e "${GREEN}✅${NC}"; else echo -e "${RED}❌${NC}"; errors=$((errors+1)); fi

# 磁盘
echo -n "  [验证] 磁盘空间... "
DISK=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK" -lt 90 ]; then echo -e "${GREEN}✅${NC} ${DISK}%"; else echo -e "${YELLOW}⚠️${NC} ${DISK}%"; fi

echo ""
if [ "$errors" -eq 0 ]; then
    echo -e "  ${BOLD}${GREEN}✅ 部署验证全部通过${NC}"
else
    echo -e "  ${RED}❌ 发现 $errors 个问题${NC}"
fi

# ============================================================
# 启动指引
# ============================================================
echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  启动 SRE-agent${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""
echo "  # 终端1: 启动后端"
echo "  cd $BACKEND_DIR"
echo "  source .venv/bin/activate"
echo "  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo ""
echo "  # 终端2: 启动前端 (开发模式)"
echo "  cd $FRONTEND_DIR"
echo "  npm run dev"
echo ""
echo "  访问: http://localhost:5173"
echo "  API:  http://localhost:8001/docs"
echo "  健康: http://localhost:8001/health"
echo ""
if [ "$LLM_PROVIDER" = "deepseek" ]; then
    echo -e "  ${GREEN}LLM: DeepSeek 云端 ($LLM_MODEL) — 无需额外操作${NC}"
else
    echo -e "  ${YELLOW}LLM: Ollama 本地 — 请先启动: ollama serve && ollama pull $LLM_MODEL${NC}"
fi
echo ""
