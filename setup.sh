#!/bin/bash
# 一键设置 MEMORY 符号链接
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_DIR="$HOME/.local/share/mimocode/memory/projects/0689edf3-9b93-43af-9d9e-fd43b8a3b46d"

mkdir -p "$MEMORY_DIR"
rm -f "$MEMORY_DIR/MEMORY.md"
ln -s "$PROJECT_DIR/.mimocode/memory/MEMORY.md" "$MEMORY_DIR/MEMORY.md"
echo "✓ MEMORY 已链接到项目目录"
