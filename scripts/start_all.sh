#!/usr/bin/env bash
# scripts/start_all.sh — Unified entry point to start/restart the entire stack.
# Resilient to machine reboots and environment changes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "--- 1. Refreshing Core Stack (systemd) ---"
systemctl --user restart openclaw-stack.target
echo "Core stack services (listeners, workers, scheduler) have been restarted."

echo ""
echo "--- 2. Starting Legacy Polling Brains ---"
bash "${REPO_ROOT}/start_openclaw_brains.sh"

echo ""
echo "--- 3. Verifying Processes ---"
ps aux | grep -E "chief_|cassandra_" | grep -v grep || echo "No processes found."

echo ""
echo "Stack initialization complete."
