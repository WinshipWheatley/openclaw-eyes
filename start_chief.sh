#!/usr/bin/env bash

source ~/chief_env/bin/activate
source /home/openclaw/.chief.env
mkdir -p /mnt/c/OpenClaw/logs

pkill -f chief_listener.py
pkill -f chief_worker.py
pkill -f chief_memory_worker.py
pkill -f chief_state_worker.py

nohup python ~/chief_listener.py > /mnt/c/OpenClaw/logs/listener.out 2>&1 &
nohup python ~/chief_worker.py > /mnt/c/OpenClaw/logs/worker.out 2>&1 &
nohup python ~/chief_memory_worker.py > /mnt/c/OpenClaw/logs/memory_worker.out 2>&1 &
nohup python ~/chief_state_worker.py > /mnt/c/OpenClaw/logs/state_worker.out 2>&1 &

echo "Chief stack started."
