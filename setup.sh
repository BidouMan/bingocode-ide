#!/bin/bash
set -e

echo "========================================="
echo "  BingoCode IDE - 环境安装脚本"
echo "========================================="
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# ─── 检测操作系统 ───
OS="$(uname -s)"
case "$OS" in
  Darwin*) PLATFORM="macos" ;;
  Linux*)  PLATFORM="linux" ;;
  *)       fail "不支持的操作系统: $OS（仅支持 macOS / Linux）" ;;
esac
echo "📌 检测到系统: $PLATFORM"

# ─── 1. Node.js ───
echo ""
echo "── 检查 Node.js ──"
if command -v node &>/dev/null; then
  NODE_VER=$(node -v)
  ok "Node.js $NODE_VER"
else
  fail "未安装 Node.js，请先安装: https://nodejs.org/"
fi

# ─── 2. pnpm ───
echo ""
echo "── 检查 pnpm ──"
if command -v pnpm &>/dev/null; then
  PNPM_VER=$(pnpm -v)
  ok "pnpm $PNPM_VER"
else
  warn "未安装 pnpm，正在安装..."
  npm install -g pnpm
  ok "pnpm 已安装"
fi

# ─── 3. Python 3 ───
echo ""
echo "── 检查 Python 3 ──"
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  ok "$PY_VER"
else
  fail "未安装 Python 3，请先安装: https://www.python.org/"
fi

# ─── 4. Rust ───
echo ""
echo "── 检查 Rust ──"
if command -v rustc &>/dev/null; then
  RUST_VER=$(rustc --version)
  ok "$RUST_VER"
else
  warn "未安装 Rust，正在安装 rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
  ok "Rust 已安装"
fi

# ─── 5. Tauri CLI ──
echo ""
echo "── 检查 Tauri CLI ──"
if command -v cargo-tauri &>/dev/null || cargo tauri --version &>/dev/null 2>&1; then
  ok "Tauri CLI 已安装"
else
  warn "正在安装 Tauri CLI..."
  cargo install tauri-cli
  ok "Tauri CLI 已安装"
fi

# ─── 6. 前端依赖 ──
echo ""
echo "── 安装前端依赖 ──"
pnpm install
ok "前端依赖已安装"

# ─── 7. Python 引擎环境 ──
echo ""
echo "── 安装 Python 引擎环境 ──"
cd engine && bash setup.sh && cd ..
ok "Python 引擎环境已安装"

# ─── 完成 ──
echo ""
echo "========================================="
echo -e "${GREEN}  ✅ 全部安装完成！${NC}"
echo "========================================="
echo ""
echo "启动开发服务器:"
echo "  pnpm tauri dev"
echo ""
