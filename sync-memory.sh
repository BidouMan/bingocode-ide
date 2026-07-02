#!/bin/bash
# 同步 MiMoCode 记忆到项目目录
# 在家电脑：编辑完代码后运行此脚本，然后 git commit && git push
# 在公司电脑：git pull 后运行此脚本

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIMOCODE_DIR="$HOME/.local/share/mimocode/memory/projects/0689edf3-9b93-43af-9d9e-fd43b8a3b46d"

echo "=== MiMoCode Memory Sync ==="

# 从 MiMoCode 同步到项目目录
if [ -d "$MIMOCODE_DIR" ]; then
    echo "Syncing from MiMoCode to project..."
    mkdir -p "$PROJECT_DIR/.mimocode/memory"
    cp -r "$MIMOCODE_DIR"/* "$PROJECT_DIR/.mimocode/memory/"
    echo "✓ Memory synced to .mimocode/memory/"
else
    echo "✗ MiMoCode directory not found: $MIMOCODE_DIR"
fi

# 从项目目录同步到 MiMoCode
if [ -d "$PROJECT_DIR/.mimocode/memory" ]; then
    echo "Syncing from project to MiMoCode..."
    mkdir -p "$MIMOCODE_DIR"
    cp -r "$PROJECT_DIR/.mimocode/memory"/* "$MIMOCODE_DIR/"
    echo "✓ Memory synced to MiMoCode"
fi

echo "=== Done ==="
