#!/usr/bin/env bash
set -euo pipefail

# Watch the canonical legal planning package and mirror it one-way to Mac.
# Requires inotifywait from the inotify-tools package.

SRC="/home/openclaw/docs/planning/openclaw_legal/law_program"
DEST="mac:~/OpenClaw_Watch/law_program"
SYNC_SCRIPT="/home/openclaw/mac_eyes/Launchers/sync_legal_planning_to_mac.sh"
DEBOUNCE_SECONDS="${DEBOUNCE_SECONDS:-2}"

if [[ ! -d "$SRC" ]]; then
  echo "legal-planning-watch: ERROR source directory is missing: $SRC" >&2
  exit 1
fi

if [[ ! -x "$SYNC_SCRIPT" ]]; then
  echo "legal-planning-watch: ERROR sync helper is missing or not executable: $SYNC_SCRIPT" >&2
  exit 1
fi

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "legal-planning-watch: ERROR inotifywait is not installed." >&2
  echo "legal-planning-watch: install with: sudo apt-get update && sudo apt-get install -y inotify-tools" >&2
  exit 127
fi

echo "legal-planning-watch: source=$SRC/"
echo "legal-planning-watch: destination=$DEST/"
echo "legal-planning-watch: debounce=${DEBOUNCE_SECONDS}s"
echo "legal-planning-watch: WARNING apply sync uses --delete; Mac-only files under ~/OpenClaw_Watch/law_program will be removed."

echo "legal-planning-watch: initial sync started"
"$SYNC_SCRIPT" --apply
echo "legal-planning-watch: initial sync finished"

while true; do
  echo "legal-planning-watch: waiting for changes"
  if inotifywait -r -e create,modify,delete,move,close_write "$SRC"; then
    echo "legal-planning-watch: change detected; debouncing for ${DEBOUNCE_SECONDS}s"
    sleep "$DEBOUNCE_SECONDS"
    echo "legal-planning-watch: sync started"
    if "$SYNC_SCRIPT" --apply; then
      echo "legal-planning-watch: sync finished"
    else
      rc=$?
      echo "legal-planning-watch: ERROR sync failed with exit code $rc" >&2
    fi
  else
    rc=$?
    echo "legal-planning-watch: ERROR watcher failed with exit code $rc" >&2
    exit "$rc"
  fi
done
