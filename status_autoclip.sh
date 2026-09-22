#!/bin/bash
# Backward-compatibility alias for ClipFarm
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/status_clipfarm.sh" "$@"
