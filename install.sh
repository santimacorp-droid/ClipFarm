#!/usr/bin/env bash
# ==============================================================================
# ClipFarm Studio - Setup & Installation Script
# ==============================================================================
set -e

# Resolve real script location if called via symlink
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python interpreter (priority: explicit env var, bundled venv, user venv, project venv, system python)
if [ -n "$CLIPFARM_PYTHON" ] && [ -x "$CLIPFARM_PYTHON" ]; then
    PYTHON_BIN="$CLIPFARM_PYTHON"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [ -x "$HOME/.local/share/clipfarm/venv/bin/python" ]; then
    PYTHON_BIN="$HOME/.local/share/clipfarm/venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ Error: Python 3 could not be found. Please ensure Python is installed."
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/installer_wizard.py" "$@"
