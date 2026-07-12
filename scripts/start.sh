#!/usr/bin/env bash
# ============================================================
# XikiyAIOps 启动脚本 v1.2.0
#
# Agent 以 xikiy 最低权限用户运行
# 用法: bash scripts/start.sh
# 停止: sudo systemctl stop xikiy-aiops  (或 Ctrl+C)
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
BACKEND_PORT=8001

#── systemd 模式 ──
if systemctl list-unit-files xikiy-aiops.service &>/dev/null; then
  echo "启动 xikiy-aiops (systemd, User=xikiy)..."
  sudo systemctl start xikiy-aiops
  sleep 2
  if systemctl is-active --quiet xikiy-aiops; then
    echo -e "  ${GREEN}[✓]${NC} 服务已启动 — http://localhost:$BACKEND_PORT"
    echo "  状态: sudo systemctl status xikiy-aiops"
    echo "  日志: sudo journalctl -u xikiy-aiops -f"
    exit 0
  else
    echo -e "  ${RED}[✗]${NC} 启动失败，查看日志: sudo journalctl -u xikiy-aiops -n 20"
    exit 1
  fi
fi

#── 直接模式 ──
echo -e "${BOLD}${GREEN}  XikiyAIOps 启动中 (User=xikiy)${NC}"

if [ ! -f "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
  echo -e "  ${RED}[✗]${NC} .venv 不存在, 请先运行: bash scripts/deploy.sh"
  exit 1
fi

cd "$BACKEND_DIR"
exec sudo -u xikiy "$BACKEND_DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --log-level info
