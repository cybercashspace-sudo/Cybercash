#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$PROJECT_DIR/buildozer_build.log"
PID_FILE="$PROJECT_DIR/buildozer_build.pid"

echo "Starting Buildozer Android debug build..."
echo "Log: $LOG_FILE"

# Run the staged WSL build helper in the background so the log stays in the repo root.
nohup bash "$PROJECT_DIR/build_android_wsl.sh" >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

echo "PID: $(cat "$PID_FILE")"
