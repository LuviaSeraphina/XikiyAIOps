#!/usr/bin/env bash
# ============================================================
# XikiyAIOps 一键部署 v1.2.0
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
echo "  ║   XikiyAIOps 一键部署 v1.2.0          ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Step 1: 环境检测
# ============================================================
echo -e "\n${BOLD}▶ Step 1/6: 环境检测${NC}"

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
[ -f "$OFFLINE_DIR/wheels-loongarch64.tar.gz" ] && _HAS_WHEELS=true

#离线包仅在 LoongArch 上可用 (RPM 为 ky11.loongarch64, wheel 含原生 .so)
if [ "$IS_LOONGARCH" = false ]; then
  [ "$_HAS_RPM" = true ] && log_warn "跳过离线 RPM (当前架构 $ARCH ≠ loongarch64)"
  [ "$_HAS_WHEELS" = true ] && log_warn "跳过离线 Wheel (当前架构 $ARCH ≠ loongarch64)"
  _HAS_RPM=false
  _HAS_WHEELS=false
fi

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
echo -e "\n${BOLD}▶ Step 2/6: 系统依赖${NC}"

#离线 RPM (仅 LoongArch)
if [ "$IS_LOONGARCH" = true ] && [ "$_HAS_RPM" = true ]; then
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

#编译工具链 (pip 在线安装需编译原生扩展: greenlet/httptools/watchfiles 等)
if [ "$IS_LOONGARCH" = true ]; then
  for pkg in gcc gcc-c++ make git cmake python3-devel gcc-gfortran; do
    install_pkg "$pkg" 2>/dev/null || true
  done
  log_ok "编译工具链就绪 (LoongArch)"

  #Rust 离线恢复 (避免 rustup 联网)
  _RUST_OFFLINE="$PROJECT_DIR/offline-packages/rust-loongarch64.tar.gz"
  if [ -f "$_RUST_OFFLINE" ] && ! command -v cargo &>/dev/null; then
    log_info "恢复 Rust 工具链 (离线)..."
    tar xzf "$_RUST_OFFLINE" -C "$HOME" 2>/dev/null
    export PATH="$HOME/.cargo/bin:$PATH"
    log_ok "Cargo: $(cargo --version 2>/dev/null || echo '失败')"
  fi
else
  #x86_64: 区分 dnf/apt 包名
  if [ "$PKG_MGR" = "dnf" ]; then
    for pkg in gcc gcc-c++ make python3-devel; do
      install_pkg "$pkg" 2>/dev/null || true
    done
  else
    for pkg in gcc g++ make python3-dev; do
      install_pkg "$pkg" 2>/dev/null || true
    done
  fi
  log_ok "编译工具链就绪 (x86_64)"
fi

# ============================================================
# Step 2b: Prometheus (可选)
# ============================================================
echo -e "\n${BOLD}▶ Step 2b/6: Prometheus 监控${NC}"

_INSTALL_PROM=false
command -v prometheus &>/dev/null && _INSTALL_PROM=false || _INSTALL_PROM=true

_install_prom_from_bin() {
  #通用二进制安装: 从离线包解压到 / (不含 web UI, 不需要)
  local _src="$1"  # tarball 路径或 URL
  local _tmp="$(mktemp -d)"
  if echo "$_src" | grep -q '^https\?://'; then
    log_info "下载 Prometheus 二进制包..."
    curl -sL "$_src" -o "$_tmp/prometheus.tar.gz" || { log_err "下载失败"; rm -rf "$_tmp"; return 1; }
    _src="$_tmp/prometheus.tar.gz"
  fi
  log_info "解压到 / ..."
  sudo tar xzf "$_src" -C / 2>/dev/null
  #创建数据目录
  sudo mkdir -p /var/lib/prometheus/metrics-data
  #创建 systemd 服务
  _create_svc prometheus \
    "Prometheus monitoring system" \
    "/usr/local/bin/prometheus --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/var/lib/prometheus/metrics-data --web.listen-address=0.0.0.0:9090"
  _create_svc prometheus-alertmanager \
    "Prometheus Alertmanager" \
    "/usr/local/bin/alertmanager --config.file=/etc/prometheus/alertmanager.yml --cluster.listen-address= --web.listen-address=0.0.0.0:9093"
  _create_svc prometheus-node-exporter \
    "Prometheus Node Exporter" \
    "/usr/local/bin/node_exporter --web.listen-address=0.0.0.0:9100"
  sudo mkdir -p /etc/prometheus
  rm -rf "$_tmp"
}

_create_svc() {
  local _name="$1" _desc="$2" _exec="$3"
  cat << SERVICEEOF | sudo tee /etc/systemd/system/$_name.service >/dev/null
[Unit]
Description=$_desc
After=network.target

[Service]
Type=simple
User=root
ExecStart=$_exec
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
}

if [ "$_INSTALL_PROM" = true ]; then
  log_info "安装 Prometheus + Alertmanager + Node Exporter..."
  if [ "$IS_LOONGARCH" = true ]; then
    #LoongArch: 优先用离线包, 没有则从 Debian sid 下载 .deb 提取
    _PROM_OFFLINE="$PROJECT_DIR/offline-packages/prometheus-loongarch64.tar.gz"
    if [ -f "$_PROM_OFFLINE" ]; then
      log_info "使用离线包: $_PROM_OFFLINE"
      _install_prom_from_bin "$_PROM_OFFLINE"
    else
      log_info "下载 Debian sid loong64 二进制..."
      _tmp="$(mktemp -d)"
      for _p_url in \
        "http://ftp.us.debian.org/debian/pool/main/p/prometheus/prometheus_2.53.5+ds1-5_loong64.deb" \
        "http://ftp.us.debian.org/debian/pool/main/p/prometheus-alertmanager/prometheus-alertmanager_0.31.1+ds-2_loong64.deb" \
        "http://ftp.us.debian.org/debian/pool/main/p/prometheus-node-exporter/prometheus-node-exporter_1.11.1-2_loong64.deb"; do
        _f="$(basename "$_p_url")"
        curl -sL "$_p_url" -o "$_tmp/$_f" || true
        [ -f "$_tmp/$_f" ] && cd "$_tmp" && ar x "$_f" 2>/dev/null && tar xJf data.tar.xz 2>/dev/null || true
      done
      #将解压出的二进制打包 (不含 web 资源, 不需要)
      _final_tmp="$(mktemp -d)"
      mkdir -p "$_final_tmp/usr/local/bin"
      find "$_tmp" -name 'prometheus' -type f -executable 2>/dev/null | head -1 | xargs -I{} cp {} "$_final_tmp/usr/local/bin/prometheus" 2>/dev/null || true
      find "$_tmp" -name 'prometheus-alertmanager' -type f -executable 2>/dev/null | head -1 | xargs -I{} cp {} "$_final_tmp/usr/local/bin/alertmanager" 2>/dev/null || true
      find "$_tmp" -name 'amtool' -type f -executable 2>/dev/null | head -1 | xargs -I{} cp {} "$_final_tmp/usr/local/bin/" 2>/dev/null || true
      find "$_tmp" -name 'prometheus-node-exporter' -type f -executable 2>/dev/null | head -1 | xargs -I{} cp {} "$_final_tmp/usr/local/bin/node_exporter" 2>/dev/null || true
      tar czf "$_tmp/prometheus-bin.tar.gz" -C "$_final_tmp" .
      _install_prom_from_bin "$_tmp/prometheus-bin.tar.gz"
      rm -rf "$_tmp" "$_final_tmp"
    fi
  elif [ "$PKG_MGR" = "apt" ]; then
    sudo apt install -y prometheus prometheus-alertmanager prometheus-node-exporter 2>&1 | tail -1 || true
  elif [ "$PKG_MGR" = "dnf" ]; then
    sudo dnf install -y prometheus2 alertmanager prometheus-node-exporter 2>&1 | tail -1 || true
  fi
fi

if command -v prometheus &>/dev/null; then
  log_ok "Prometheus: $(prometheus --version 2>&1 | head -1)"
  #复制项目配置到 /etc/prometheus/
  sudo mkdir -p /etc/prometheus
  for _cfg in prometheus.yml alertmanager.yml xikiy-rules.yml; do
    if [ -f "$PROJECT_DIR/prometheus/$_cfg" ]; then
      sudo cp "$PROJECT_DIR/prometheus/$_cfg" "/etc/prometheus/$_cfg"
      log_ok "配置已部署: /etc/prometheus/$_cfg"
    fi
  done
  #修复 Alertmanager: 单节点禁用 gossip mesh (否则无私网 IP 时启动失败)
  if [ -f /etc/default/prometheus-alertmanager ]; then
    sudo sed -i 's/^ARGS=.*/ARGS="--cluster.listen-address="/' /etc/default/prometheus-alertmanager
  fi
  #重启服务
  sudo systemctl daemon-reload 2>/dev/null || true
  sudo systemctl enable prometheus prometheus-alertmanager prometheus-node-exporter 2>/dev/null || true
  sudo systemctl restart prometheus prometheus-alertmanager prometheus-node-exporter 2>/dev/null || true
  log_ok "Prometheus 服务已启动"
else
  log_warn "Prometheus 未安装或安装失败, 跳过配置"
fi

# ============================================================
# Step 3: 后端依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 3/6: 后端依赖${NC}"
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

#解压离线 wheel (仅 LoongArch — x86_64 已在 Step 1 强制 _HAS_WHEELS=false)
if [ "$_HAS_WHEELS" = true ]; then
  log_info "解压离线 wheel..."
  rm -rf "$VENDOR_DIR" && mkdir -p "$VENDOR_DIR"
  _TMP="$(mktemp -d)"
  tar xzf "$OFFLINE_DIR/wheels-loongarch64.tar.gz" -C "$_TMP" 2>/dev/null || true
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

  #LoongArch: gfortran 刚装, 强制重装 numpy 让其重新链接 Fortran 符号
  if [ "$IS_LOONGARCH" = true ]; then
    log_info "LoongArch: 重新链接 numpy Fortran 符号..."
    "$VENV_PIP" install --force-reinstall --no-deps --no-build-isolation numpy 2>&1 | tail -1 || true
  fi

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
echo -e "\n${BOLD}▶ Step 4/6: 前端${NC}"

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
echo -e "\n${BOLD}▶ Step 5/6: 配置${NC}"
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
DATABASE_URL=sqlite+aiosqlite:///$BACKEND_DIR/data/xikiy_aiops.db
EOF
  log_ok ".env 已生成"
else
  log_info ".env 已存在, 跳过配置"
  _PROVIDER=$(grep -oP 'LLM_PROVIDER=\K.*' .env 2>/dev/null || echo "?")
  _MODEL=$(grep -oP 'LLM_MODEL=\K.*' .env 2>/dev/null || echo "?")
fi

#数据库 + RAG 知识库目录
mkdir -p data/rag_db data/sre_kb
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

# ============================================================
# Step 6: 最小权限代理
# ============================================================
echo -e "\n${BOLD}▶ Step 6/6: 最小权限代理${NC}"

#创建 xikiy 系统用户 (无登录权限)
if ! id xikiy &>/dev/null; then
  sudo useradd -r -d /opt/xikiy-aiops -s /sbin/nologin xikiy
  log_ok "用户 xikiy 已创建"
else
  log_info "用户 xikiy 已存在"
fi

#加入 sudo 组 — restricted 工具需要 sudo 组成员权限
if ! groups xikiy 2>/dev/null | grep -qw sudo; then
  sudo usermod -aG sudo xikiy
  log_ok "xikiy 已加入 sudo 组"
else
  log_info "xikiy 已在 sudo 组"
fi

#配置 sudoers 白名单
_SUDOERS_SRC="$PROJECT_DIR/scripts/sudoers.d/xikiy-aiops"
if [ -f "$_SUDOERS_SRC" ]; then
  sudo install -m 440 "$_SUDOERS_SRC" /etc/sudoers.d/xikiy-aiops
  log_ok "sudoers 已配置 (NOPASSWD 白名单)"
else
  log_warn "未找到 sudoers 配置文件: $_SUDOERS_SRC"
fi

#文件权限: 确保 xikiy 可访问项目文件
_PROD_DIR="/opt/xikiy-aiops"
if [ -d "$_PROD_DIR" ]; then
  sudo chown -R xikiy:xikiy "$_PROD_DIR" 2>/dev/null || true
fi
if [ -d "/var/backups/xikiy" ]; then
  sudo chown -R xikiy:xikiy /var/backups/xikiy 2>/dev/null || true
fi

#systemd service: User=xikiy
_SVC_FILE="/etc/systemd/system/xikiy-aiops.service"
if [ -f "$_SVC_FILE" ]; then
  sudo sed -i 's/^User=.*/User=xikiy/' "$_SVC_FILE"
  sudo systemctl daemon-reload 2>/dev/null || true
  log_ok "systemd service User=xikiy"
fi

echo ""
echo -e "  ${BOLD}${GREEN}✅ 部署完成${NC}"
echo -e "  启动: ${BOLD}bash scripts/start.sh${NC}"
echo -e "  访问: ${BOLD}http://localhost:8001${NC}"
echo ""
