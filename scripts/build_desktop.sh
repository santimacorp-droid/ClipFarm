#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="python3"

if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "ERROR: python3 or python required"
        exit 1
    fi
fi

exec "$PYTHON_CMD" "$SCRIPT_DIR/build_desktop.py" "$@"
