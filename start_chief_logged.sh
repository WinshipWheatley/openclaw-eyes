#!/usr/bin/env bash

LOGFILE=/mnt/c/OpenClaw/logs/start_chief_debug.log

mkdir -p /mnt/c/OpenClaw/logs

{
  echo "===== $(date) ====="
  echo "start_chief_logged.sh starting"

  source ~/chief_env/bin/activate
  echo "venv activated"

  pkill -f chief_listener.py
  pkill -f chief_worker.py
  pkill -f chief_memory_worker.py
  pkill -f chief_state_worker.py
  echo "old processes cleared"

  nohup python ~/chief_listener.py >> /mnt/c/OpenClaw/logs/listener.out 2>&1 &
  echo "listener launch attempted"

  nohup python ~/chief_worker.py >> /mnt/c/OpenClaw/logs/worker.out 2>&1 &
  echo "worker launch attempted"

  nohup python ~/chief_memory_worker.py >> /mnt/c/OpenClaw/logs/memory_worker.out 2>&1 &
  echo "memory worker launch attempted"

  nohup python ~/chief_state_worker.py >> /mnt/c/OpenClaw/logs/state_worker.out 2>&1 &
  echo "state worker launch attempted"

  sleep 2
  ps -ef | grep chief_ | grep -v grep || true

  echo "start_chief_logged.sh done"
} >> "$LOGFILE" 2>&1
