#!/usr/bin/env bash
# Pop up a Windows Terminal on WSL that runs the secure-drop slot prompt, so the
# operator can paste a sensitive value into a hidden slot without it ever touching
# a log, the LLM, or shell history. Falls back to running in-place if not on WSL.
#
# Usage: scripts/secure_drop_popup.sh <slot_name>
set -euo pipefail
SLOT="${1:-}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${OPENCLAW_VENV:-/home/openclaw/chief_env/bin/python}"
if [ -z "$SLOT" ]; then
  exec "$PY" "$REPO/secure_drop.py" --list
fi
# WSL → launch a visible Windows Terminal window running the prompt.
if command -v wt.exe >/dev/null 2>&1; then
  wt.exe wsl.exe -e bash -lc "cd '$REPO' && '$PY' secure_drop.py '$SLOT'; echo; read -p 'Done — press Enter to close.'" >/dev/null 2>&1 &
  echo "Opened a secure-paste window for slot '$SLOT'. Paste the value there."
else
  exec "$PY" "$REPO/secure_drop.py" "$SLOT"
fi
