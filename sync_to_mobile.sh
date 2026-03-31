#!/usr/bin/env bash
# sync_to_mobile.sh — Push live system status to the phone vault via Mac SSH
# Runs on PC, writes to Mac iCloud Obsidian vault (or staging dir if iCloud not set up)
set -euo pipefail

MAC_SSH="ssh -i /home/openclaw/.ssh/id_mac mac"
MOBILE_VAULT_ICLOUD="/Users/hwinshipwheatley/Library/Mobile Documents/iCloud~md~obsidian/Documents/OpenClaw-Mobile"
MOBILE_VAULT_STAGING="/Users/hwinshipwheatley/Eyes/mobile-staging/OpenClaw-Mobile"

# Use iCloud path if accessible, otherwise staging
if $MAC_SSH "test -d '$MOBILE_VAULT_ICLOUD'" 2>/dev/null; then
    VAULT_PATH="$MOBILE_VAULT_ICLOUD"
else
    VAULT_PATH="$MOBILE_VAULT_STAGING"
fi

NOW=$(date '+%Y-%m-%d %H:%M')

# --- Gather system status from PC ---

chief_status="unknown"
cassandra_status="unknown"
loop_status="unknown"
watcher_status="unknown"

pgrep -f "chief_listener.py" >/dev/null 2>&1 && chief_status="running" || chief_status="stopped"
pgrep -f "cassandra_listener.py" >/dev/null 2>&1 && cassandra_status="running" || cassandra_status="stopped"
pgrep -f "chief_watcher_brain.py" >/dev/null 2>&1 && watcher_status="running" || watcher_status="stopped"

# Loop status from status.json
if [[ -f /home/openclaw/polish_loop/status.json ]]; then
    loop_state=$(python3 -c "import json; d=json.load(open('/home/openclaw/polish_loop/status.json')); print(d.get('state','unknown'))" 2>/dev/null || echo "unknown")
    loop_task=$(python3 -c "import json; d=json.load(open('/home/openclaw/polish_loop/status.json')); print(d.get('task','—'))" 2>/dev/null || echo "—")
    loop_turn=$(python3 -c "import json; d=json.load(open('/home/openclaw/polish_loop/status.json')); print(d.get('turn','—'))" 2>/dev/null || echo "—")
    loop_status="$loop_state"
else
    loop_state="no status.json"
    loop_task="—"
    loop_turn="—"
    loop_status="no status.json"
fi

# Recent logbook entries (last 3 table rows)
logbook_rows=""
if [[ -f /mnt/c/OpenClawShared/openclaw-vault/Eyes/06_Logbook.md ]]; then
    logbook_rows=$(grep '^|' /mnt/c/OpenClawShared/openclaw-vault/Eyes/06_Logbook.md | grep -v '^| Date' | grep -v '^|---' | tail -3)
fi
[[ -z "$logbook_rows" ]] && logbook_rows="| — | — | — |"

# --- Write Dashboard ---

$MAC_SSH "cat > '$VAULT_PATH/Dashboard.md'" << EOF
# OpenClaw Mobile Dashboard

_Last synced: ${NOW}_

---

## System Status

| Component | Status |
|---|---|
| Chief Bot | $chief_status |
| Cassandra Bot | $cassandra_status |
| Polish Loop | $loop_status |
| Watcher | $watcher_status |

> Auto-updated by PC sync script.

---

## Quick Actions

### Report an Issue
Open **Issues.md** and write your problem under "New Issues".

---

## Recent Loop Activity

_Last 3 entries from Logbook._

| Date | Task | Result |
|---|---|---|
$logbook_rows

---

## Telegram Birds Eye

_Check Telegram directly for live messages. This section shows last known state._

| Bot | Status |
|---|---|
| Chief | $chief_status |
| Cassandra | $cassandra_status |

---

## Polish Loop Detail

- **State:** $loop_state
- **Current task:** $loop_task
- **Turn:** $loop_turn
EOF

# --- Write System Status detail ---

chief_uptime=$(ps -o etime= -p "$(pgrep -f chief_listener.py | head -1)" 2>/dev/null || echo "—")
cassandra_uptime=$(ps -o etime= -p "$(pgrep -f cassandra_listener.py | head -1)" 2>/dev/null || echo "—")

$MAC_SSH "cat > '$VAULT_PATH/System Status.md'" << EOF
# System Status Detail

_Last synced: ${NOW}_

---

## Chief Bot
- **Status:** $chief_status
- **Uptime:** $chief_uptime

## Cassandra Bot
- **Status:** $cassandra_status
- **Uptime:** $cassandra_uptime

## Polish Loop
- **State:** $loop_state
- **Current task:** $loop_task
- **Turn:** $loop_turn

## Watcher
- **Status:** $watcher_status

---

> Updated by sync_to_mobile.sh on PC.
EOF

echo "[sync_to_mobile] Pushed to $VAULT_PATH at $NOW"
