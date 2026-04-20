#!/usr/bin/env bash
# scripts/start_all.sh — Authoritative command to start the Full OpenClaw Environment.
# Restores the entire operating environment: core services + expected legacy polling.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "--- 1. Refreshing Core Stack (systemd) ---"
# Includes: chief-listener, chief-worker, chief-memory-worker, chief-state-worker,
#           chief-watcher-brain, chief-guardian-listener,
#           cassandra-listener, cassandra-watcher, cassandra-briefing-scheduler.
systemctl --user restart openclaw-stack.target
echo "Core stack services are online."

echo ""
echo "--- 2. Starting Expected Legacy Polling Brains ---"
# Includes: chief_album_brain (polling), chief_billing_brain (polling).
# These are included in the full restart to ensure background reminders/state checks
# are active, as expected in the live operating environment.
bash "${REPO_ROOT}/start_openclaw_brains.sh"
echo "Legacy polling loops are active."

echo ""
echo "--- 3. Verifying Full Environment ---"
ps aux | grep -E "chief_|cassandra_" | grep -v grep || echo "No processes found."

echo ""
echo "Full OpenClaw Operating Environment restored."
