#!/usr/bin/env bash
# ============================================================
# SRE-agent 一键启动脚本 v1.0
#
# 同时启动后端 (FastAPI) 和前端 (Vite dev server)
# 用法: bash scripts/start.sh
# 停止: Ctrl+C 自动清理两个进程
#
# 适配: 麒麟 V10/V11 (x86_64 / LoongArch64) + Ubuntu/Debian
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_PORT=8001
FRONTEND_PORT=5173

PID_BACKEND=""
PID_FRONTEND=""

# 端口检查: 避免重复启动同一服务导致误触发清理
check_port_free() {
  local port="$1"
  local label="$2"
  local info=""
  if ! command -v ss >/dev/null 2>&1; then
    return 0
  fi
  info="$(ss -ltnp "( sport = :$port )" 2>/dev/null | tail -n +2 || true)"
  if [ -n "$info" ]; then
    echo -e "  ${RED}[✗]${NC}     ${label} 端口 $port 已被占用:"
    echo "$info" | sed 's/^/  │ /'
    echo -e "  ${YELLOW}请先停止已有的 ${label} 服务后再执行脚本${NC}"
    exit 1
  fi
}

# ============================================================
# 清理函数: Ctrl+C 或脚本退出时终止两个子进程
# ============================================================
cleanup() {
  local reason="${1:-manual}"
  echo ""
  if [ "$reason" = "manual" ]; then
    echo -e "\n  ${YELLOW}[STOP]${NC}  正在停止所有服务..."
  else
    echo -e "\n  ${RED}[ERROR]${NC}  服务异常退出, 正在停止所有服务..."
  fi
  if [ -n "$PID_BACKEND" ] && kill -0 "$PID_BACKEND" 2>/dev/null; then
    kill "$PID_BACKEND" 2>/dev/null || true
    wait "$PID_BACKEND" 2>/dev/null || true
    echo -e "  ${GREEN}[✓]${NC}     后端已停止"
  fi
  if [ -n "$PID_FRONTEND" ] && kill -0 "$PID_FRONTEND" 2>/dev/null; then
    kill "$PID_FRONTEND" 2>/dev/null || true
    wait "$PID_FRONTEND" 2>/dev/null || true
    echo -e "  ${GREEN}[✓]${NC}     前端已停止"
  fi
  echo -e "  ${BLUE}再见!${NC}"
  exit 0
}
trap 'cleanup manual' INT TERM

echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║     SRE-agent 一键启动                             ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# 1. 环境检测
# ============================================================
echo -e "  ${CYAN}[1/4]${NC} 检测运行环境..."

IS_LOONGARCH=false
ARCH="$(uname -m)"
[[ "$ARCH" == "loongarch64" ]] && IS_LOONGARCH=true
echo "        架构: $ARCH ($([ "$IS_LOONGARCH" = true ] && echo 'LoongArch' || echo 'x86_64/ARM'))"

# 读取 .env 获取 LLM 配置
if [ -f "$BACKEND_DIR/.env" ]; then
  LLM_PROVIDER=$(grep '^LLM_PROVIDER=' "$BACKEND_DIR/.env" | cut -d= -f2 || echo "unknown")
  LLM_MODEL=$(grep '^LLM_MODEL=' "$BACKEND_DIR/.env" | cut -d= -f2 || echo "unknown")
  echo "        LLM : $LLM_PROVIDER / $LLM_MODEL"
else
  echo -e "  ${RED}[✗]${NC}     .env 不存在, 请先运行: bash scripts/deploy.sh"
  exit 1
fi

# ============================================================
# 2. 后端预检
# ============================================================
echo -e "  ${CYAN}[2/4]${NC} 后端预检..."

cd "$BACKEND_DIR"

# 虚拟环境
if [ ! -d ".venv" ]; then
  echo -e "  ${RED}[✗]${NC}     虚拟环境 .venv 不存在, 请先运行: bash scripts/deploy.sh"
  exit 1
fi
source .venv/bin/activate
echo -e "  ${GREEN}[✓]${NC}     虚拟环境已激活"

# 关键包
for pkg in fastapi uvicorn; do
  if ! pip show "$pkg" &>/dev/null; then
    echo -e "  ${RED}[✗]${NC}     $pkg 未安装, 请先运行: bash scripts/deploy.sh"
    exit 1
  fi
done
echo -e "  ${GREEN}[✓]${NC}     依赖包完整"

# Tool 注册验证 (快速自检)
TOOLS=$(python -c "from app.mcp_plugins.base import registry; print(registry.count)" 2>/dev/null || echo "0")
echo -e "  ${GREEN}[✓]${NC}     MCP Tool: $TOOLS 个已注册"

# ============================================================
# 3. 前端预检
# ============================================================
echo -e "  ${CYAN}[3/4]${NC} 前端预检..."

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  echo -e "  ${RED}[✗]${NC}     node_modules 不存在, 请先运行: bash scripts/deploy.sh"
  exit 1
fi
echo -e "  ${GREEN}[✓]${NC}     前端依赖已安装"

# 可选: 检查 dist 是否已有构建产物
if [ -f "dist/index.html" ]; then
  echo -e "  ${GREEN}[✓]${NC}     前端构建产物已存在"
else
  echo -e "  ${YELLOW}[!]${NC}     前端未构建 (dev 模式仍可运行, 但建议 npm run build)"
fi

# ============================================================
# 4. 启动服务
# ============================================================
echo -e "\n  ${CYAN}[4/4]${NC} 启动服务..."
echo ""

check_port_free "$BACKEND_PORT" "后端"
check_port_free "$FRONTEND_PORT" "前端"

# 启动后端 (后台)
cd "$BACKEND_DIR"
source .venv/bin/activate
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --log-level info 2>&1 | sed -u 's/^/  [backend]  /' &
PID_BACKEND=$!
echo -e "  ${GREEN}[✓]${NC}     后端已启动 (PID: $PID_BACKEND, 端口: $BACKEND_PORT)"

# 启动前端 (后台)
cd "$FRONTEND_DIR"
npm run dev 2>&1 | sed -u 's/^/  [frontend] /' &
PID_FRONTEND=$!
echo -e "  ${GREEN}[✓]${NC}     前端已启动 (PID: $PID_FRONTEND, 端口: $FRONTEND_PORT)"

# ============================================================
# 等待服务就绪
# ============================================================
echo ""
echo -e "  ${CYAN}[···]${NC}   等待服务就绪..."

#等后端启动
for i in $(seq 1 30); do
  if curl -s "http://localhost:$BACKEND_PORT/health" &>/dev/null; then
    echo -e "  ${GREEN}[✓]${NC}     后端就绪 (尝试 $i 次)"
    break
  fi
  sleep 1
done

# 等前端启动
for i in $(seq 1 20); do
  if curl -s "http://localhost:$FRONTEND_PORT" &>/dev/null; then
    echo -e "  ${GREEN}[✓]${NC}     前端就绪 (尝试 $i 次)"
    break
  fi
  sleep 1
done

# ============================================================
# 输出访问信息
# ============================================================
echo ""
echo -e "  ${BOLD}${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "  ${BOLD}${GREEN}  ✅ SRE-agent 已就绪${NC}"
echo -e "  ${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  前端页面: ${BOLD}http://localhost:$FRONTEND_PORT${NC}"
echo -e "  API 文档: ${BOLD}http://localhost:$BACKEND_PORT/docs${NC}"
echo -e "  健康检查: ${BOLD}http://localhost:$BACKEND_PORT/health${NC}"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 阻塞等待: 任一子进程退出则脚本退出
wait -n "$PID_BACKEND" "$PID_FRONTEND" 2>/dev/null || true
cleanup exit
