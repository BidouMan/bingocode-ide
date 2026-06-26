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

echo "📦 Installing dependencies..."
"$VENV_DIR/bin/pip" install -r "$ENGINE_DIR/requirements.txt"

echo "✅ Setup complete!"
echo "   Python: $VENV_DIR/bin/python3"
