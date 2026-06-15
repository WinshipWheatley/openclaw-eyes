#!/usr/bin/env bash
# OpenClaw GREEN GATE — run the FULL suite on a FRESH, CLEAN CHECKOUT of a ref.
#
# THE LESSON (2026-06-14): a stateful worktree's "green" LIES. The Codex got
# lastfailed={} in its own worktree (full of session-generated fixtures) and pushed
# main — but a clean checkout had 33 failures. This gate ALWAYS clean-rooms: it checks
# out the exact commit into a throwaway worktree with ONLY committed files, so
# "works on my box" can never reach main again.
#
# Usage: green_gate.sh [ref]   (default: HEAD)
# Exit 0 = clean-checkout suite passed; non-zero = NOT green (caller should block).
set -uo pipefail
REF="${1:-HEAD}"
REPO="${OPENCLAW_REPO:-/home/openclaw}"
VENV="${OPENCLAW_VENV:-/home/openclaw/.venv/bin/python}"
TS="$(date +%s)-$$"
WT="$REPO/worktrees/greengate-$TS"
LOG="/tmp/greengate-$TS.log"

# Git hooks export repo-local environment such as GIT_DIR and GIT_WORK_TREE.
# If those leak into pytest, tests that create temporary git repositories can
# accidentally operate on the caller repo instead of their tmp checkout.
for var in GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES; do
  unset "$var" || true
done

cleanup(){ git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "[green-gate] clean-room checkout of $REF ..."
if ! git -C "$REPO" worktree add --detach "$WT" "$REF" >/dev/null 2>&1; then
  echo "[green-gate] FAIL: could not create clean worktree for $REF"; exit 2
fi
cd "$WT" || { echo "[green-gate] FAIL: cwd"; exit 2; }
SHA="$(git rev-parse --short HEAD)"
echo "[green-gate] running FULL suite on clean checkout $SHA (this takes ~25 min) ..."
OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 "$VENV" -m pytest -q > "$LOG" 2>&1
code=$?
echo "[green-gate] --- result ---"; tail -3 "$LOG"
if [ "$code" -eq 0 ]; then
  echo "[green-gate] PASS — clean checkout of $SHA is green."
else
  echo "[green-gate] FAIL ($code) — clean checkout of $SHA is NOT green. (log: $LOG)"
fi
exit "$code"
