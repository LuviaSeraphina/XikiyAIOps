#!/usr/bin/env bash
# ============================================================
# SRE-agent 一键部署脚本 v3.0
#
# 适配: 麒麟 V10/V11 (x86_64 / LoongArch64) + Ubuntu/Debian
# 用法: bash scripts/deploy.sh
# ============================================================
set -euo pipefail

# ── 颜色 & 日志 ──────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'
log_ok()   { echo -e "  ${GREEN}[OK]${NC}    $(date +%H:%M:%S) $*"; }
log_info() { echo -e "  ${BLUE}[INFO]${NC}  $(date +%H:%M:%S) $*"; }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC}  $(date +%H:%M:%S) $*"; }
log_err()  { echo -e "  ${RED}[ERROR]${NC} $(date +%H:%M:%S) $*"; }
log_step() { echo -e "\n  ${CYAN}[···]${NC}  $(date +%H:%M:%S) $*"; }

# ── 路径 ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
ACTUAL_USER="${SUDO_USER:-$(whoami)}"
ACTUAL_HOME="$(eval echo ~"$ACTUAL_USER")"

echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║     SRE-agent 一键部署 v3.0                        ║"
echo "  ║     麒麟 V10/V11 (LoongArch) + 通用 Linux          ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Step 1: 检测系统环境
# ============================================================
echo -e "\n${BOLD}▶ Step 1/8: 检测系统环境${NC}"

ARCH="$(uname -m)"
IS_LOONGARCH=false
[[ "$ARCH" == "loongarch64" ]] && IS_LOONGARCH=true

OS_ID="unknown"; OS_NAME="unknown"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_NAME="${PRETTY_NAME:-$OS_ID}"
elif [ -f /etc/kylin-release ]; then
  OS_ID="kylin"; OS_NAME="Kylin Linux"
fi

PKG_MGR=""
if command -v dnf &>/dev/null; then PKG_MGR="dnf"
elif command -v apt &>/dev/null; then PKG_MGR="apt"
else log_err "未检测到 dnf/apt"; exit 1; fi

echo "  OS       : $OS_NAME"
echo "  架构     : $ARCH (LoongArch: $IS_LOONGARCH)"
echo "  包管理器 : $PKG_MGR"
echo "  用户     : $ACTUAL_USER"

#离线包检测 — 若项目根目录下有 offline-packages/ 则优先使用
OFFLINE_DIR="$PROJECT_DIR/offline-packages"
_HAS_RPM_ZIP=false
_HAS_WHEEL_TAR=false
if [ -d "$OFFLINE_DIR" ]; then
  [ -f "$OFFLINE_DIR/rpms.tar.gz" ] && _HAS_RPM_ZIP=true
  [ -f "$OFFLINE_DIR/wheels.tar.gz" ] && _HAS_WHEEL_TAR=true
  if [ "$_HAS_RPM_ZIP" = true ] || [ "$_HAS_WHEEL_TAR" = true ]; then
    log_ok "检测到 offline-packages/ (RPM: $_HAS_RPM_ZIP, Wheel: $_HAS_WHEEL_TAR)"
  fi
fi

# ── 包安装 helper ────────────────────────────────────────
install_pkg() {
  local pkg="$1"
  if [ "$PKG_MGR" = "dnf" ]; then
    sudo dnf install -y "$pkg" 2>/dev/null && return 0 || return 1
  else
    sudo apt install -y "$pkg" 2>/dev/null && return 0 || return 1
  fi
}

# ============================================================
# Step 2: 安装系统依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 2/8: 安装系统依赖${NC}"

#离线 RPM 优先 — 解压直接安装, 跳过在线源
if [ "$_HAS_RPM_ZIP" = true ]; then
  log_step "离线 RPM 安装..."
  _RPM_TMP="$(mktemp -d)"
  tar xzf "$OFFLINE_DIR/rpms.tar.gz" -C "$_RPM_TMP" 2>/dev/null || true
  _RPM_COUNT=$(find "$_RPM_TMP" -name "*.rpm" 2>/dev/null | wc -l)
  if [ "$_RPM_COUNT" -gt 0 ]; then
    log_info "安装 $_RPM_COUNT 个 RPM 包..."
    find "$_RPM_TMP" -name "*.rpm" -print0 | xargs -0 sudo rpm -ivh --nodeps 2>&1 | sed -u 's/^/  │ /' || log_warn "部分 RPM 安装失败 (已安装的包会跳过)"
  fi
  rm -rf "$_RPM_TMP"
  log_ok "离线 RPM 安装完成 (跳过在线源)"
fi

# ── Python 3 ─────────────────────────────────────────────
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

# ── Node.js + npm ────────────────────────────────────────
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

# ── LoongArch: 编译工具链 + 科学计算系统包 ──────────────────
if [ "$IS_LOONGARCH" = true ]; then
  log_step "安装编译工具链 (C/C++/Rust)..."
  for pkg in gcc gcc-c++ gcc-gfortran make python3-devel libffi-devel openssl-devel rust cargo; do
    install_pkg "$pkg" && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}跳过${NC}"
  done

  #升级 Rust (Cargo>=1.85 才能用新版 maturin, 否则回退 maturin 1.7.1)
  #策略: 版本够→跳过 → 本地离线包 → rustup 多镜像 → Loongnix FTP → maturin 1.7.1 兜底
  _CARGO_VER=$(cargo --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "0.0")
  if [ "$(printf '%s\n' "1.85" "$_CARGO_VER" | sort -V | head -1)" = "1.85" ]; then
    log_info "Cargo $_CARGO_VER >= 1.85, 跳过升级"
  else
    log_step "升级 Rust (当前 $_CARGO_VER, 需要 >=1.85)..."
    _RUST_UPGRADED=false

    #── 策略0: 本地离线包 (offline-packages/rust-*.tar.xz) ──
    _LOCAL_RUST=$(find "$OFFLINE_DIR" -maxdepth 1 -name "rust-*.tar.xz" 2>/dev/null | head -1)
    if [ -n "$_LOCAL_RUST" ] && [ -f "$_LOCAL_RUST" ]; then
      log_info "发现本地离线包: $_LOCAL_RUST"
      _RUST_TMP="$(mktemp -d)"
      if tar xf "$_LOCAL_RUST" -C "$_RUST_TMP" 2>&1 | sed -u 's/^/  │ /'; then
        _RUST_INSTALL_DIR="$ACTUAL_HOME/.rust-loongnix-1.92"
        _RUST_EXTRACTED=$(find "$_RUST_TMP" -maxdepth 1 -type d -name "rust-*" | head -1)
        if [ -n "$_RUST_EXTRACTED" ] && [ -f "$_RUST_EXTRACTED/install.sh" ]; then
          (cd "$_RUST_EXTRACTED" && \
            sh install.sh --prefix="$_RUST_INSTALL_DIR" --disable-ldconfig 2>&1 | sed -u 's/^/  │ /')
          export PATH="$_RUST_INSTALL_DIR/bin:$PATH"
          _RUST_UPGRADED=true
          log_ok "本地 Rust 离线包已安装 ($_RUST_INSTALL_DIR)"
        else
          log_warn "离线包结构异常, 缺少 install.sh"
        fi
      fi
      rm -rf "$_RUST_TMP"
    fi

    #── 策略1: rustup 多镜像回退 (各 30s 超时) ──────────────
    if [ "$_RUST_UPGRADED" = false ]; then
      if command -v rustup &>/dev/null; then
        for _mirror in \
          "https://mirrors.ustc.edu.cn/rustup" \
          "https://mirrors.tuna.tsinghua.edu.cn/rustup" \
          "https://static.rust-lang.org/rustup"; do
          log_info "尝试 rustup 镜像: $_mirror"
          if RUSTUP_DIST_SERVER="$_mirror" timeout 30 rustup update stable 2>&1 | sed -u 's/^/  │ /'; then
            _RUST_UPGRADED=true
            log_ok "rustup 升级成功 ($_mirror)"
            break
          fi
          log_warn "镜像 $_mirror 失败, 尝试下一个..."
        done
      else
        log_info "rustup 未安装, 跳过"
      fi
    fi

    #── 策略2: Loongnix FTP 直下预编译包 (rustup 全部失败时) ──
    if [ "$_RUST_UPGRADED" = false ]; then
      _RUST_TARBALL="rust-1.92.0-loongarch64-unknown-linux-gnu.tar.xz"
      _RUST_URL="https://ftp.loongnix.cn/toolchain/rust/rust-1.92/2025-12-24/abi1.0/$_RUST_TARBALL"
      log_info "Loongnix FTP 直下 (~237MB, 超时 600s): $_RUST_URL"
      _RUST_TMP="$(mktemp -d)"
      if curl --connect-timeout 10 --max-time 600 -L -o "$_RUST_TMP/$_RUST_TARBALL" "$_RUST_URL" 2>&1 | sed -u 's/^/  │ /'; then
        log_info "解压 $_RUST_TARBALL..."
        if tar xf "$_RUST_TMP/$_RUST_TARBALL" -C "$_RUST_TMP" 2>&1 | sed -u 's/^/  │ /'; then
          #官方 Rust tarball 自带 install.sh, 安装到 ~/.cargo
          _RUST_INSTALL_DIR="$ACTUAL_HOME/.rust-loongnix-1.92"
          if [ -f "$_RUST_TMP/rust-1.92.0-loongarch64-unknown-linux-gnu/install.sh" ]; then
            (cd "$_RUST_TMP/rust-1.92.0-loongarch64-unknown-linux-gnu" && \
              sh install.sh --prefix="$_RUST_INSTALL_DIR" --disable-ldconfig 2>&1 | sed -u 's/^/  │ /')
            export PATH="$_RUST_INSTALL_DIR/bin:$PATH"
            #不设 CARGO_HOME, 继续用 ~/.cargo/config.toml 的镜像配置
            _RUST_UPGRADED=true
            log_ok "Loongnix Rust 1.92 已安装 ($_RUST_INSTALL_DIR)"
          else
            log_warn "tarball 结构异常, 缺少 install.sh"
          fi
        else
          log_warn "解压失败"
        fi
      else
        log_warn "Loongnix FTP 下载失败 (网络不通?)"
      fi
      rm -rf "$_RUST_TMP"
    fi

    if [ "$_RUST_UPGRADED" = false ]; then
      log_warn "Rust 升级全部策略失败, 保持 $_CARGO_VER → 将用 maturin 1.7.1"
    fi
  fi
  log_info "Rust: $(rustc --version 2>/dev/null || echo 'N/A')"

  log_step "安装科学计算系统包..."
  #scikit-learn → scipy → numpy; 三个都装系统 RPM, pip 直接跳过
  for pkg in python3-numpy python3-scipy python3-scikit-learn; do
    echo -n "  → $pkg ... "
    if install_pkg "$pkg"; then
      echo -e "${GREEN}✓${NC}"
    else
      echo -e "${YELLOW}不可用 (将回退源码编译)${NC}"
    fi
  done
fi

# ============================================================
# Step 3: Python 虚拟环境 + 后端依赖
# ============================================================
echo -e "\n${BOLD}▶ Step 3/8: 安装后端依赖${NC}"
cd "$BACKEND_DIR"

#加速: 多源回退 (Loongnix 备用 → TUNA → PyPI), 单个源挂了自动切
#pypi.loongnix.cn 主源不稳定(502), 改用龙芯备用源 lpypi.loongnix.cn
log_step "配置 pip 多源回退..."
mkdir -p "$ACTUAL_HOME/.config/pip"
cat > "$ACTUAL_HOME/.config/pip/pip.conf" << 'PIPEOF'
[global]
timeout = 60
index-url = https://lpypi.loongnix.cn/loongson/pypi/+simple/
extra-index-url = https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple https://pypi.org/simple

[install]
trusted-host = lpypi.loongnix.cn mirrors.tuna.tsinghua.edu.cn pypi.org
PIPEOF
log_info "pip: Loongnix 备用(lpypi) → 清华 TUNA → PyPI (自动逐包回退)"
#Cargo 镜像 (Rust 构建 pydantic-core/maturin 需要)
#强制覆盖: 旧 USTC 镜像 URL 已失效 (404), 统一用 TUNA sparse 协议
mkdir -p "$ACTUAL_HOME/.cargo"
#移除旧格式 config (Cargo 优先读 config.toml)
rm -f "$ACTUAL_HOME/.cargo/config"
cat > "$ACTUAL_HOME/.cargo/config.toml" << 'CARGOEOF'
[source.crates-io]
replace-with = 'tuna'

[source.tuna]
registry = "sparse+https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/"

[source.ustc]
registry = "sparse+https://mirrors.ustc.edu.cn/crates.io-index/"
CARGOEOF
log_ok "Cargo 镜像已配置 (TUNA sparse, 旧 USTC 配置已清除)"

# ── 虚拟环境 ─────────────────────────────────────────────
VENV_DIR="$BACKEND_DIR/.venv"
NEED_RECREATE=false

if [ -d "$VENV_DIR" ]; then
  if [ "$IS_LOONGARCH" = true ]; then
    #检查现有 venv 是否启用了 --system-site-packages
    if "$VENV_DIR/bin/python" -c "import sys; exit(0 if sys.prefix!=sys.base_prefix else 1)" 2>/dev/null; then
      #venv 正常, 但需确认能访问系统包
      if ! "$VENV_DIR/bin/python" -c "import numpy" 2>/dev/null; then
        log_warn "现有 venv 无 --system-site-packages, 将重建"
        NEED_RECREATE=true
      else
        log_info "虚拟环境已存在 (含系统包), 跳过"
      fi
    else
      NEED_RECREATE=true
    fi
  else
    log_info "虚拟环境已存在, 跳过"
  fi
fi

if [ ! -d "$VENV_DIR" ] || [ "$NEED_RECREATE" = true ]; then
  [ "$NEED_RECREATE" = true ] && rm -rf "$VENV_DIR"
  if [ "$IS_LOONGARCH" = true ]; then
    $PYTHON_BIN -m venv "$VENV_DIR" --system-site-packages
    log_ok "venv 已创建 (--system-site-packages, 复用系统 numpy/scipy/scikit-learn)"
  else
    $PYTHON_BIN -m venv "$VENV_DIR"
    log_ok "venv 已创建"
  fi
fi

#使用 venv 绝对路径, 避免 source activate 在某些环境下静默失效
VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"
"$VENV_PIP" install --upgrade pip -q
log_ok "pip 已升级"

# ── LoongArch: 构建环境准备 ──────────────────────────────
if [ "$IS_LOONGARCH" = true ]; then
  log_step "预装构建依赖 + 禁用 PEP 517 构建隔离..."
  #greenlet: SQLAlchemy 异步必需, 有 C 扩展
  "$VENV_PIP" install greenlet 2>&1 | sed -u 's/^/  │ /'
  #maturin: pydantic-core 是 Rust 项目, 源码编译需要 maturin
  CARGO_VER=$(cargo --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "0.0")
  if [ "$(printf '%s\n' "1.85" "$CARGO_VER" | sort -V | head -1)" = "1.85" ]; then
    "$VENV_PIP" install maturin 2>&1 | sed -u 's/^/  │ /'
  else
    log_info "Cargo $CARGO_VER < 1.85 (rustup 失败或离线), 安装 maturin==1.7.1"
    "$VENV_PIP" install "maturin==1.7.1" 2>&1 | sed -u 's/^/  │ /'
  fi

  #关键: 禁用构建隔离, scipy/pydantic-core 源码编译时能访问系统包和预装的 maturin
  #(PEP 517 默认隔离环境看不到 --system-site-packages 的系统包和当前环境的 pip 包)
  export PIP_NO_BUILD_ISOLATION=1
fi

# ── 安装 Python 依赖 ─────────────────────────────────────
VENDOR_DIR="$BACKEND_DIR/vendor"
log_step "安装 Python 依赖..."

#离线 wheel 优先 — 解压到 vendor/, 后续安装自动使用
if [ "$_HAS_WHEEL_TAR" = true ]; then
  log_info "解压离线 wheels.tar.gz → vendor/..."
  mkdir -p "$VENDOR_DIR"
  echo -n "  → 解压中... "
  if tar xzf "$OFFLINE_DIR/wheels.tar.gz" -C "$VENDOR_DIR" --strip-components=1 2>/dev/null; then
    echo -e "${GREEN}OK${NC}"
  else
    echo -e "${RED}失败${NC}"
    log_warn "wheels.tar.gz 解压失败, 将在线安装"
  fi
  #用 find 统计 (防 glob 兼容问题, 且 set -e 下 ls 无匹配会静默退出)
  _VENDOR_CNT=$(find "$VENDOR_DIR" -maxdepth 1 \( -name "*.whl" -o -name "*.tar.gz" \) 2>/dev/null | wc -l)
  if [ "$_VENDOR_CNT" -gt 0 ]; then
    log_ok "vendor/ 已就绪 ($_VENDOR_CNT 个包, 来自离线包)"
  else
    log_warn "vendor/ 为空 — 解压失败或目录结构不匹配, 回退在线安装"
  fi
fi

if [ -d "$VENDOR_DIR" ] && [ "$(find "$VENDOR_DIR" -maxdepth 1 -name "*.whl" 2>/dev/null | wc -l)" -gt 0 ]; then
  log_info "从本地 vendor/ 安装 (离线优先)..."
  if "$VENV_PIP" install --no-index --find-links="$VENDOR_DIR" -r requirements.txt --progress-bar on 2>&1 | sed -u 's/^/  │ /'; then
    log_ok "离线安装成功"
  else
    log_warn "vendor/ 架构不匹配, 回退在线安装"
    "$VENV_PIP" install -r requirements.txt --progress-bar on 2>&1 | sed -u 's/^/  │ /'
  fi
else
  log_info "从 PyPI 在线安装..."
  "$VENV_PIP" install -r requirements.txt --progress-bar on 2>&1 | sed -u 's/^/  │ /'
fi

# ── 缓存 wheel (从 venv 本地导出, 架构正确) ──────────────
log_info "从 venv 导出 wheel 到 vendor/ (本地, 不联网)..."
mkdir -p "$VENDOR_DIR"
#清掉旧 x86_64 wheel (避免下次离线安装命中错误架构)
find "$VENDOR_DIR" -name "*.whl" -delete 2>/dev/null || true
#从已安装包逐包导出, --no-build-isolation 复用当前 venv, 零网络
_WHEEL_PKGS=$("$VENV_PIP" freeze 2>/dev/null | grep -v "^pip=\|^setuptools=\|^wheel=\|@ file" | cut -d= -f1 | tr '\n' ' ')
_WHEEL_OK=0; _WHEEL_SKIP=0
for _pkg in $_WHEEL_PKGS; do
  if "$VENV_PIP" wheel --no-deps --no-build-isolation --wheel-dir="$VENDOR_DIR" "$_pkg" 2>&1 | tail -3 | grep -qE "Created wheel|Stored|Successfully built|Filename"; then
    ((_WHEEL_OK+=1))
  else
    ((_WHEEL_SKIP+=1))
  fi
done
log_ok "vendor/ 已刷新: $_WHEEL_OK 个本架构 wheel (${_WHEEL_SKIP} 个跳过)"
echo ""

# ── 校验关键包 ───────────────────────────────────────────
log_step "校验关键包..."
for pkg in fastapi uvicorn sqlalchemy psutil greenlet aiosqlite httpx pydantic; do
  echo -n "  → $pkg ... "
  if "$VENV_PIP" show "$pkg" &>/dev/null; then echo -e "${GREEN}✓${NC}"; else echo -e "${RED}✗ 缺失${NC}"; log_err "$pkg 未安装"; exit 1; fi
done
#LoongArch 额外校验 numpy/scikit-learn
if [ "$IS_LOONGARCH" = true ]; then
  for pkg in numpy scikit-learn; do
    echo -n "  → $pkg ... "
    if "$VENV_PYTHON" -c "import ${pkg//-/_}" 2>/dev/null; then echo -e "${GREEN}✓${NC}"; else echo -e "${RED}✗ 缺失${NC}"; log_err "$pkg 不可导入"; exit 1; fi
  done
fi
log_ok "后端依赖就绪 ($("$VENV_PIP" list 2>/dev/null | wc -l) 个包)"

# ============================================================
# Step 4: 前端构建
# ============================================================
if [ -d "$FRONTEND_DIR/dist" ] && [ -f "$FRONTEND_DIR/dist/index.html" ]; then
  echo -e "\n${BOLD}▶ Step 4/8: 前端 (已构建, 跳过)${NC}"
  log_info "检测到 frontend/dist/ — 安装包自带构建产物"
else
  echo -e "\n${BOLD}▶ Step 4/8: 前端依赖 + 构建${NC}"
  cd "$FRONTEND_DIR"

  #清理旧构建产物 (可能属于 root)
  [ -d "dist" ] && { rm -rf dist 2>/dev/null || sudo rm -rf dist; }
  [ -d "node_modules" ] && { rm -rf node_modules package-lock.json 2>/dev/null || sudo rm -rf node_modules package-lock.json; }

  log_info "npm install..."
  npm install 2>&1 | sed -u 's/^/  │ /'
  echo ""

  #确保 vite/vue-tsc 可执行
  for bin in node_modules/.bin/vite node_modules/.bin/vue-tsc; do
    [ -f "$bin" ] && [ ! -x "$bin" ] && chmod +x "$bin" 2>/dev/null || true
  done

  log_info "npm run build..."
  npm run build 2>&1 | sed -u 's/^/  │ /'
  echo ""

  if [ -f "dist/index.html" ]; then
    log_ok "前端构建完成"
  else
    log_err "前端构建失败: dist/index.html 不存在"
    exit 1
  fi
fi

# ============================================================
# Step 5: 配置 LLM
# ============================================================
echo -e "\n${BOLD}▶ Step 5/8: 配置 LLM${NC}"
cd "$BACKEND_DIR"

echo ""
echo "  请选择 LLM 模式:"
echo "  ┌──────────────────────────────────────────────┐"
echo "  │ [1] DeepSeek 云端 (推荐)                      │"
echo "  │     base_url: https://api.deepseek.com       │"
echo "  │     模型: deepseek-v4-flash                   │"
echo "  │                                               │"
echo "  │ [2] Ollama 本地 (仅 x86_64)                   │"
echo "  │     模型: qwen3:4b, 端口: 11434               │"
[[ "$IS_LOONGARCH" = true ]] && echo "  │     → LoongArch 暂不支持, 请选 [1]            │"
echo "  └──────────────────────────────────────────────┘"
echo ""

if [ "$IS_LOONGARCH" = true ]; then
  LLM_PROVIDER="deepseek"
  echo -n "  选项 [1/2] (默认 1): "
else
  echo -n "  选项 [1/2] (默认 1): "
fi
read -r llm_choice
llm_choice="${llm_choice:-1}"

if [ "$llm_choice" = "2" ] && [ "$IS_LOONGARCH" = false ]; then
  LLM_PROVIDER="ollama"
  LLM_BASE_URL="http://localhost:11434"
  echo -n "  模型名称 [默认 qwen3:4b]: "; read -r llm_model
  LLM_MODEL="${llm_model:-qwen3:4b}"
  LLM_API_KEY=""
  log_info "请手动启动: ollama serve && ollama pull $LLM_MODEL"
else
  LLM_PROVIDER="deepseek"
  LLM_BASE_URL="https://api.deepseek.com"
  echo -n "  模型名称 [默认 deepseek-v4-flash]: "; read -r llm_model
  LLM_MODEL="${llm_model:-deepseek-v4-flash}"
  echo -n "  API Key: "; read -rs LLM_API_KEY; echo ""
fi

# ============================================================
# Step 6: 生成 .env + 初始化数据库
# ============================================================
echo -e "\n${BOLD}▶ Step 6/8: 配置 + 数据库初始化${NC}"
cd "$BACKEND_DIR"

mkdir -p data
sudo chown -R "$ACTUAL_USER:$(id -gn "$ACTUAL_USER")" data/ 2>/dev/null || true
chmod 755 data

cat > .env << EOF
# SRE-agent 配置 (deploy.sh v3.0 自动生成)
LLM_PROVIDER=$LLM_PROVIDER
LLM_BASE_URL=$LLM_BASE_URL
LLM_MODEL=$LLM_MODEL
LLM_API_KEY=$LLM_API_KEY

MAX_RISK_LEVEL=restricted
REQUIRE_CONFIRMATION=true
AUDIT_ENABLED=true

DATABASE_URL=sqlite+aiosqlite:///$BACKEND_DIR/data/sre_agent.db
EOF
log_ok ".env 已生成"

log_step "初始化数据库..."
"$VENV_PYTHON" -c "
from app.db import init_db
import asyncio
asyncio.run(init_db())
print('数据库表初始化完成')
" 2>&1 | sed -u 's/^/  │ /'
log_ok "数据库就绪"

# ============================================================
# Step 7: 部署验证
# ============================================================
echo -e "\n${BOLD}▶ Step 7/8: 部署验证${NC}"
errors=0

#MCP Tool 注册数
echo -n "  [验证] MCP Tool 注册... "
TOOLS=$("$VENV_PYTHON" -c "from app.mcp_plugins.base import registry; print(registry.count)" 2>/dev/null || echo "0")
if [ "$TOOLS" -ge 49 ]; then
  echo -e "${GREEN}✅${NC} $TOOLS 个 Tool"
else
  echo -e "${RED}❌${NC} 仅 $TOOLS 个"; errors=$((errors+1))
fi

#安全护栏
echo -n "  [验证] 安全护栏... "
SAFE=$("$VENV_PYTHON" -c "
from app.core.intent_filter import classify_intent, IntentCategory
cat, _, _ = classify_intent('rm -rf /etc')
print('OK' if cat==IntentCategory.DANGEROUS_ACTION else 'FAIL')
" 2>/dev/null || echo "FAIL")
if [ "$SAFE" = "OK" ]; then echo -e "${GREEN}✅${NC} 意图分类正常"; else echo -e "${RED}❌${NC}"; errors=$((errors+1)); fi

#LLM
echo -n "  [验证] LLM 配置... "
LLM_INFO=$("$VENV_PYTHON" -c "from app.llm.config import LLM_PROVIDER, LLM_MODEL; print(f'\${LLM_PROVIDER}/\${LLM_MODEL}')" 2>/dev/null || echo "ERROR")
echo -e "${GREEN}$LLM_INFO${NC}"

#前端
echo -n "  [验证] 前端构建... "
if [ -f "$FRONTEND_DIR/dist/index.html" ]; then echo -e "${GREEN}✅${NC}"; else echo -e "${RED}❌${NC}"; errors=$((errors+1)); fi

#磁盘
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
# Step 8: 生成安装包 (可选)
# ============================================================
echo -e "\n${BOLD}▶ Step 8/8: 生成安装包 (可选)${NC}"
echo ""
echo -n "  是否生成当前架构安装包？[y/N] "
read -r do_package

if [ "${do_package:-n}" != "y" ] && [ "${do_package:-n}" != "Y" ]; then
  log_info "跳过打包"
else
  cd "$PROJECT_DIR"
  DIST_DIR="$PROJECT_DIR/dist"
  VERSION="v3.0.0"
  PKG_NAME="sre-agent-${VERSION}-${ARCH}-$(date +%Y%m%d)"
  mkdir -p "$DIST_DIR"

  log_info "打包 $PKG_NAME (架构: $ARCH)..."

  #校验 vendor/ 是否包含当前架构的 wheel
  VENDOR_COUNT=0
  if [ -d "backend/vendor" ]; then
    VENDOR_COUNT=$(find backend/vendor -maxdepth 1 -name "*.whl" 2>/dev/null | wc -l)
  fi
  if [ "$VENDOR_COUNT" -gt 0 ]; then
    log_info "vendor/ 含 ${VENDOR_COUNT} 个 ${ARCH} wheel, 一并打包"
    #backend/ 目录已包含 vendor/*.whl, 无需单独追加
  elif [ "$IS_LOONGARCH" = true ]; then
    log_warn "vendor/ 无 wheel — LoongArch 离线安装将回退在线编译"
  fi

  #前端: 有 dist 则只打包 dist, 否则打包整个 frontend/
  if [ -d "$FRONTEND_DIR/dist" ] && [ -f "$FRONTEND_DIR/dist/index.html" ]; then
    FRONTEND_INC="frontend/dist/"
  else
    FRONTEND_INC="frontend/"
  fi

  tar czf "$DIST_DIR/${PKG_NAME}.tar.gz" \
    --exclude='__pycache__'     --exclude='*.pyc'       --exclude='*.db' \
    --exclude='.venv'           --exclude='.pytest_cache' --exclude='.vite' \
    --exclude='node_modules'    --exclude='.git'         --exclude='./dist' \
    --exclude='.env'            --exclude='package-lock.json' \
    --exclude='*.egg-info'      --exclude='.vscode' \
    --exclude='data/*.db'       --exclude='data/state_store.db' \
    --exclude='赛题'            --exclude='TODO'          --exclude='skills-lock.json' \
    --exclude='scripts/package.sh' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/src'    --exclude='frontend/public' \
    --exclude='frontend/index.html' --exclude='frontend/*.json' --exclude='frontend/*.ts' \
    --transform="s,^,${PKG_NAME}/," \
    backend/ "$FRONTEND_INC" docs/ scripts/ README.md LICENSE \
    2>&1 | sed -u 's/^/  │ /'

  SIZE=$(du -h "$DIST_DIR/${PKG_NAME}.tar.gz" | cut -f1)
  FILES=$(tar tzf "$DIST_DIR/${PKG_NAME}.tar.gz" | wc -l)
  VENDOR_TAR=$(tar tzf "$DIST_DIR/${PKG_NAME}.tar.gz" | grep -c 'vendor/.*\.whl' || echo 0)
  log_ok "安装包: dist/${PKG_NAME}.tar.gz ($SIZE, $FILES 文件, 含 ${VENDOR_TAR} wheel)"
fi

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}${GREEN}✅ 部署完成${NC}"
echo -e "  启动方式: bash scripts/start.sh"
echo ""
