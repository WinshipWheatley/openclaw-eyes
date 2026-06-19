#!/usr/bin/env bash
# start_orchestrator.sh
# Runs one Phase-C orchestrator event and exits quiescently.
# Safe to run from any directory. Does not create a daemon or PID file.
# Logs to /mnt/c/OpenClaw/logs/orchestrator.log (same file orchestrator.py writes to).

set -euo pipefail

LOOP_DIR="/home/openclaw/polish_loop"
VENV="/home/openclaw/chief_env/bin/activate"
LOG_FILE="/mnt/c/OpenClaw/logs/orchestrator.log"

source "$VENV"
python3 "$LOOP_DIR/orchestrator.py" --once >> "$LOG_FILE" 2>&1
echo "[start_orchestrator] One Phase-C orchestrator event completed. Log: $LOG_FILE"
