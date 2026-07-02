#!/bin/bash
# 一键设置 MEMORY 符号链接
# 用法: bash setup.sh
# 自动检测本地 MiMoCode 项目 ID

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

MIMOCODE_BASE="$HOME/.local/share/mimocode/memory/projects"
LOCAL_ID=""
for d in "$MIMOCODE_BASE"/*/; do
  id="$(basename "$d")"
  if [ "$id" != "global" ]; then
    LOCAL_ID="$id"
    break
  fi
done

if [ -z "$LOCAL_ID" ]; then
  echo "✗ 未找到本地 MiMoCode 项目记忆目录"
  exit 1
fi

MEMORY_DIR="$MIMOCODE_BASE/$LOCAL_ID"
mkdir -p "$MEMORY_DIR"
rm -f "$MEMORY_DIR/MEMORY.md"
ln -s "$PROJECT_DIR/.mimocode/memory/MEMORY.md" "$MEMORY_DIR/MEMORY.md"
echo "✓ MEMORY 已链接到项目目录 (ID: $LOCAL_ID)"
