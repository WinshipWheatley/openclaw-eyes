#!/usr/bin/env bash
set -euo pipefail

# One-way ChatGPT Project packet mirror: PC/WSL canonical exports -> Mac copy.
# Default mode is dry-run. Use --apply only after the dry run points at the
# expected project_packets destination.

SRC="/home/openclaw/docs/planning/project_packets"
DEST="mac:~/OpenClaw_Watch/project_packets"

usage() {
  cat <<EOF
Usage:
  $0             # dry-run only
  $0 --apply     # apply one-way PC -> Mac sync

Warning:
  Apply mode uses rsync --delete. Mac-only files inside
  ~/OpenClaw_Watch/project_packets will be removed because the PC export
  packet source is authoritative for this mirror destination.
EOF
}

mode="dry-run"
rsync_mode=(--dry-run)

case "${1:-}" in
  "")
    ;;
  --apply)
    mode="apply"
    rsync_mode=()
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if [[ ! -d "$SRC" ]]; then
  echo "project-packet-sync: ERROR source directory is missing: $SRC" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "project-packet-sync: ERROR rsync is not installed or not on PATH." >&2
  exit 127
fi

if ! ssh -G mac >/dev/null 2>&1; then
  echo "project-packet-sync: ERROR SSH alias 'mac' is unavailable." >&2
  echo "project-packet-sync: expected destination: $DEST/" >&2
  exit 1
fi

if ! ssh -o BatchMode=yes -o ConnectTimeout=5 mac "true" >/dev/null 2>&1; then
  echo "project-packet-sync: ERROR SSH alias 'mac' could not be reached in batch mode." >&2
  echo "project-packet-sync: expected destination: $DEST/" >&2
  exit 1
fi

echo "project-packet-sync: mode=$mode"
echo "project-packet-sync: source=$SRC/"
echo "project-packet-sync: destination=$DEST/"
echo "project-packet-sync: scope is limited to docs/planning/project_packets/"
echo "project-packet-sync: WARNING apply mode deletes Mac-only files only under ~/OpenClaw_Watch/project_packets"

if [[ "$mode" == "apply" ]]; then
  ssh mac "mkdir -p ~/OpenClaw_Watch/project_packets"
fi

echo "project-packet-sync: sync started"
rsync -az --itemize-changes --timeout=10 --delete "${rsync_mode[@]}" "$SRC/" "$DEST/"
echo "project-packet-sync: sync finished"
