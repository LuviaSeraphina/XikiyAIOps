#!/usr/bin/env bash
# SRE-agent 安装包生成 (直接 tar, 无中间复制)
set -euo pipefail
GREEN='\033[0;32m'; BOLD='\033[1m'; NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
VERSION="v1.0.0"
PKG="sre-agent-${VERSION}"

cd "$PROJECT_DIR"
mkdir -p "$DIST_DIR"
rm -f "$DIST_DIR/${PKG}.tar.gz"

echo -e "${BOLD}${GREEN}▶ 生成安装包: $PKG${NC}"

tar czf "$DIST_DIR/${PKG}.tar.gz" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='*.db' \
    --exclude='.venv' --exclude='.pytest_cache' --exclude='.vite' \
    --exclude='node_modules' --exclude='dist' --exclude='.git' \
    --exclude='.env' --exclude='package-lock.json' \
    --exclude='*.egg-info' --exclude='.vscode' \
    --exclude='data/state_store.db' \
    --transform="s,^,${PKG}/," \
    backend/ frontend/ docs/ scripts/ README.md

FILES=$(tar tzf "$DIST_DIR/${PKG}.tar.gz" | wc -l)
SIZE=$(du -h "$DIST_DIR/${PKG}.tar.gz" | cut -f1)

echo ""
echo -e "  ${GREEN}安装包: dist/${PKG}.tar.gz${NC}"
echo -e "  ${GREEN}大小:   $SIZE ($FILES 文件)${NC}"
