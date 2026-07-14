#!/bin/bash
set -e

ENGINE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ENGINE_DIR/venv"

echo "🐍 Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "✅ Virtual environment already exists at $VENV_DIR"
else
    python3 -m venv "$VENV_DIR"
    echo "✅ Created virtual environment at $VENV_DIR"
fi

# Detect platform: Windows uses Scripts/, Unix uses bin/
if [ -d "$VENV_DIR/Scripts" ]; then
    PIP="$VENV_DIR/Scripts/pip"
    PYTHON="$VENV_DIR/Scripts/python"
else
    PIP="$VENV_DIR/bin/pip"
    PYTHON="$VENV_DIR/bin/python3"
fi

echo "📦 Installing dependencies..."
"$PIP" install -r "$ENGINE_DIR/requirements.txt"

echo "✅ Setup complete!"
echo "   Python: $PYTHON"
