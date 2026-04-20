#!/usr/bin/env bash
# scripts/start_all.sh — Unified entry point to start/restart the core stack.
# Resilient to machine reboots and environment changes.

set -euo pipefail

echo "--- 1. Refreshing Core Stack (systemd) ---"
systemctl --user restart openclaw-stack.target
echo "Core stack services (listeners, workers, scheduler) have been restarted."

echo ""
echo "--- 2. Verifying Core Processes ---"
ps aux | grep -E "chief_|cassandra_" | grep -vE "grep|album_brain|billing_brain" || echo "No core processes found."

echo ""
echo "NOTE: Legacy polling brains (album/billing) are NOT started by default."
echo "Use 'bash start_openclaw_brains.sh' if manual polling is required."
echo ""
echo "Stack initialization complete."
