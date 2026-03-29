#!/usr/bin/env bash

source ~/chief_env/bin/activate
source /home/openclaw/.chief.env
mkdir -p /mnt/c/OpenClaw/logs

pkill -f chief_listener.py
pkill -f cassandra_listener.py
pkill -f chief_worker.py
pkill -f chief_memory_worker.py
pkill -f chief_state_worker.py
pkill -f cassandra_watcher.py
pkill -f cassandra_briefing_scheduler.py
pkill -f chief_watcher_brain.py
pkill -f chief_guardian_listener.py

nohup python -u ~/chief_listener.py > /mnt/c/OpenClaw/logs/listener.out 2>&1 &
nohup python -u ~/cassandra_listener.py > /mnt/c/OpenClaw/logs/cassandra_listener.out 2>&1 &
nohup python -u ~/chief_worker.py > /mnt/c/OpenClaw/logs/worker.out 2>&1 &
nohup python -u ~/chief_memory_worker.py > /mnt/c/OpenClaw/logs/memory_worker.out 2>&1 &
nohup python -u ~/chief_state_worker.py > /mnt/c/OpenClaw/logs/state_worker.out 2>&1 &
nohup python -u ~/cassandra_watcher.py > /mnt/c/OpenClaw/logs/cassandra_watcher.out 2>&1 &
nohup python -u ~/cassandra_briefing_scheduler.py > /mnt/c/OpenClaw/logs/cassandra_briefing_scheduler.out 2>&1 &
nohup python -u ~/chief_watcher_brain.py > /mnt/c/OpenClaw/logs/chief_watcher.out 2>&1 &

# Guardian approval listener — only starts if a dedicated bot token is configured.
# If GUARDIAN_BOT_TOKEN is empty, Chief listener handles approval responses (existing behavior).
if [ -n "$GUARDIAN_BOT_TOKEN" ]; then
    nohup python -u ~/chief_guardian_listener.py > /mnt/c/OpenClaw/logs/guardian_listener.out 2>&1 &
    echo "Guardian approval listener started."
fi

echo "Chief stack started."
