#!/bin/bash
# 同步 MiMoCode 记忆到项目目录
# 用法: 先 git pull，再运行此脚本同步 MEMORY
# 在家/公司电脑通用
#
# 家电脑: 编辑完代码后运行 → git commit && git push
# 公司电脑: git pull 后运行

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测本地项目 ID
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

MIMOCODE_DIR="$MIMOCODE_BASE/$LOCAL_ID"

echo "=== MiMoCode Memory Sync (ID: $LOCAL_ID) ==="

# 从本地 MiMoCode 同步到项目目录（编辑完代码后上传记忆）
if [ -d "$MIMOCODE_DIR" ]; then
    echo "Syncing from MiMoCode to project..."
    mkdir -p "$PROJECT_DIR/.mimocode/memory"
    cp -r "$MIMOCODE_DIR"/* "$PROJECT_DIR/.mimocode/memory/"
    echo "✓ Memory synced to .mimocode/memory/"
fi

# 从项目目录同步到本地 MiMoCode（pull 后同步到本地 agent）
if [ -d "$PROJECT_DIR/.mimocode/memory" ]; then
    echo "Syncing from project to MiMoCode..."
    mkdir -p "$MIMOCODE_DIR"
    cp -r "$PROJECT_DIR/.mimocode/memory"/* "$MIMOCODE_DIR/"
    echo "✓ Memory synced to MiMoCode"
fi

echo "=== Done ==="
