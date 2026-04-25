#!/usr/bin/env bash
set -euo pipefail

# One-way legal planning mirror: PC/WSL canonical docs -> Mac review copy.
# Default mode is dry-run. Use --apply to update the Mac mirror.

SRC="/home/openclaw/docs/planning/openclaw_legal/law_program"
DEST="mac:~/OpenClaw_Watch/law_program"

usage() {
  cat <<EOF
Usage:
  $0             # dry-run only
  $0 --apply     # apply one-way PC -> Mac sync

Warning:
  Apply mode uses rsync --delete. Mac-only files inside
  ~/OpenClaw_Watch/law_program will be removed because the PC source is
  authoritative for this mirror.
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
  echo "ERROR: source directory is missing: $SRC" >&2
  exit 1
fi

echo "legal-planning-sync: mode=$mode"
echo "legal-planning-sync: source=$SRC/"
echo "legal-planning-sync: destination=$DEST/"
echo "legal-planning-sync: WARNING apply mode deletes Mac-only files under ~/OpenClaw_Watch/law_program"

if [[ "$mode" == "apply" ]]; then
  ssh mac "mkdir -p ~/OpenClaw_Watch/law_program"
fi

echo "legal-planning-sync: sync started"
rsync -az --itemize-changes --timeout=10 --delete "${rsync_mode[@]}" "$SRC/" "$DEST/"
echo "legal-planning-sync: sync finished"
