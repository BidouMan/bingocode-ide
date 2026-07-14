#!/bin/bash
# ════════════════════════════════════════════════════════════════
# 设置便携式 Python（python-build-standalone）
# 用于 CI 构建：下载、解压、安装依赖、剔除无用文件
#
# 环境变量：
#   PYTHON_VERSION  (默认 3.12.13)
#   RELEASE_TAG     (默认 20260623)
#
# 根据不同平台自动选择正确的架构：
#   macOS arm64  → aarch64-apple-darwin
#   macOS x86_64 → x86_64-apple-darwin
#   Windows      → x86_64-pc-windows-msvc
# ════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENGINE_DIR="$PROJECT_ROOT/engine"
OUTPUT_DIR="$ENGINE_DIR/portable-python"

PYTHON_VERSION="${PYTHON_VERSION:-3.12.13}"
RELEASE_TAG="${RELEASE_TAG:-20260623}"

# 检测平台
detect_platform() {
  local os
  os=$(uname -s | tr '[:upper:]' '[:lower:]')
  local arch
  arch=$(uname -m)

  case "$os" in
    darwin)
      case "$arch" in
        arm64) echo "aarch64-apple-darwin" ;;
        x86_64) echo "x86_64-apple-darwin" ;;
        *) echo "Unknown macOS arch: $arch" >&2; exit 1 ;;
      esac
      ;;
    mingw*|msys*|cygwin*)
      echo "x86_64-pc-windows-msvc"
      ;;
    *)
      echo "Unsupported OS: $os" >&2
      exit 1
      ;;
  esac
}

PLATFORM=$(detect_platform)
echo "🔍 平台: $PLATFORM"
echo "🔍 Python: $PYTHON_VERSION (release $RELEASE_TAG)"

FILENAME="cpython-${PYTHON_VERSION}+${RELEASE_TAG}-${PLATFORM}-install_only_stripped.tar.gz"
DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/${FILENAME}"

# 如果已经存在，跳过下载
if [ -f "$OUTPUT_DIR/bin/python3" ] || [ -f "$OUTPUT_DIR/bin/python" ]; then
  echo "✅ 便携 Python 已存在，跳过下载"
  # 但可能缺少依赖，仍然安装
else
  mkdir -p "$OUTPUT_DIR"
  echo "📥 下载 $FILENAME ..."
  curl -L --retry 3 --retry-delay 5 -o "/tmp/${FILENAME}" "$DOWNLOAD_URL"

  echo "📦 解压中..."
  tar -xzf "/tmp/${FILENAME}" -C "$OUTPUT_DIR" --strip-components=1
  rm "/tmp/${FILENAME}"
  echo "✅ 解压完成"
fi

# 找到 Python 可执行文件
if [ -f "$OUTPUT_DIR/bin/python3" ]; then
  PYTHON_BIN="$OUTPUT_DIR/bin/python3"
elif [ -f "$OUTPUT_DIR/bin/python" ]; then
  PYTHON_BIN="$OUTPUT_DIR/bin/python"
else
  echo "❌ 未找到 python 可执行文件" >&2
  ls -la "$OUTPUT_DIR/bin/" 2>/dev/null || echo "bin/ 目录不存在"
  exit 1
fi

echo "🐍 Python: $($PYTHON_BIN --version 2>&1)"

# 升级 pip
echo "📦 升级 pip..."
"$PYTHON_BIN" -m pip install --upgrade pip --quiet

# 安装引擎依赖
echo "📦 安装引擎依赖（Pillow, numpy）..."
if [ -f "$ENGINE_DIR/requirements.txt" ]; then
  "$PYTHON_BIN" -m pip install \
    -r "$ENGINE_DIR/requirements.txt" \
    --no-compile \
    --quiet
  echo "✅ 依赖安装完成"
fi

# 剔除无用文件，减小体积
echo "🧹 清理无用文件..."
# 删除 __pycache__
find "$OUTPUT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
# 删除 .pyc 文件
find "$OUTPUT_DIR" -name "*.pyc" -delete 2>/dev/null || true
# 删除 pip 缓存
rm -rf "$OUTPUT_DIR/var/cache" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/.cache" 2>/dev/null || true
# 删除不必要的 stdlib 模块
rm -rf "$OUTPUT_DIR/lib/python3.12/test" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/idlelib" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/tkinter" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/turtledemo" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/unittest" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/ensurepip" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/lib/python3.12/unittest" 2>/dev/null || true
# 删除 include 目录
rm -rf "$OUTPUT_DIR/include" 2>/dev/null || true
# 删除 .pyi 和 .pxd 文件（typeshed 和 Cython，运行时不需要）
find "$OUTPUT_DIR" -name "*.pyi" -delete 2>/dev/null || true

echo "✅ 便携 Python 设置完成"
echo "   目录: $OUTPUT_DIR"
du -sh "$OUTPUT_DIR"
