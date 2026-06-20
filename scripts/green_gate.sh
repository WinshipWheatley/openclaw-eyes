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
TIMEOUT_SECONDS="${OPENCLAW_PYTEST_TIMEOUT_SECONDS:-90}"
TIMEOUT_METHOD="${OPENCLAW_PYTEST_TIMEOUT_METHOD:-thread}"
# Stable trusted-test snapshot. Keep this immutable by default; use
# OPENCLAW_TRUSTED_TEST_REF only for explicit emergency override runs.
PINNED_TRUSTED_TEST_REF="2f6f37e046ef345022bdda4de932fd35631cb756"
TRUSTED_TEST_REF="${OPENCLAW_TRUSTED_TEST_REF:-${OPENCLAW_TRUSTED_ACCEPTANCE_REF:-$PINNED_TRUSTED_TEST_REF}}"
WT_ROOT="${OPENCLAW_GREEN_GATE_WORKTREE_ROOT:-/tmp/openclaw-green-gate}"
TS="$(date +%s)-$$"
WT="$WT_ROOT/greengate-$TS"
LOG="/tmp/greengate-$TS.log"
WORKTREE_CREATED=0
REQUIRED_CLEAN_FIXTURES=(
  "generated/read_models/helm_composer_contract.json"
  "generated/read_models/mac_controller_real_use_smoke_status.json"
  "generated/read_models/mac_dynamic_card_renderer_status.json"
  "generated/read_models/cassandra_human_edge_lab.json"
  "generated/read_models/proof_to_response_runtime_status.json"
  "generated/read_models/proof_to_response_schema_adapter_status.json"
)

fail(){ echo "[green-gate] FAIL: $*" >&2; exit 2; }

existing_parent(){
  local path="$1"
  while [ ! -e "$path" ]; do
    path="$(dirname "$path")"
  done
  printf '%s\n' "$path"
}

canonical_input_path(){
  local path="$1"
  local parent base
  case "$path" in
    /*) ;;
    *) path="$PWD/$path" ;;
  esac
  if [ -d "$path" ] && [ ! -L "$path" ]; then
    (cd "$path" && pwd -P)
    return
  fi
  parent="$(dirname "$path")"
  base="$(basename "$path")"
  while [ ! -d "$parent" ] && [ "$parent" != "/" ]; do
    parent="$(dirname "$parent")"
  done
  printf '%s/%s\n' "$(cd "$parent" && pwd -P)" "$base"
}

assert_local_ext4_path(){
  local label="$1"
  local path="$2"
  local existing resolved fs_type
  existing="$(existing_parent "$path")" || fail "could not resolve $label path: $path"
  resolved="$(canonical_input_path "$path")" || fail "could not canonicalize $label path: $path"
  case "$resolved/" in
    /mnt/e/*|/mnt/c/*)
      fail "$label must be on local ext4 (/tmp or /home/openclaw), never /mnt/e or /mnt/c: $resolved"
      ;;
  esac
  case "$resolved/" in
    /tmp/*|/home/openclaw/*) ;;
    *) fail "$label must be under /tmp or /home/openclaw on local ext4: $resolved" ;;
  esac
  fs_type="$(df -PT "$existing" 2>/dev/null | awk 'NR==2 {print $2}')"
  case "$fs_type" in
    ext2|ext3|ext4) ;;
    *) fail "$label must be on local ext4 (/tmp or /home/openclaw), got filesystem '$fs_type' at $resolved" ;;
  esac
}

check_timeout_plugin(){
  if [ ! -x "$VENV" ]; then
    fail "OPENCLAW_VENV is not executable: $VENV"
  fi
  if ! "$VENV" - <<'PY' >/dev/null 2>&1; then
import pytest
import pytest_timeout
PY
    fail "pytest-timeout is not importable in OPENCLAW_VENV=$VENV; install pytest-timeout in the validated gate venv"
  fi
}

check_required_clean_fixtures(){
  local missing=0
  local path
  for path in "${REQUIRED_CLEAN_FIXTURES[@]}"; do
    if [ ! -s "$path" ]; then
      echo "[green-gate] missing required clean-room fixture: $path" >&2
      missing=1
    fi
  done
  if [ "$missing" -ne 0 ]; then
    fail "clean-room fixture parity check failed; use the validated checkout fixture set before trusting full-gate failures"
  fi
  echo "[green-gate] clean-room fixture parity check passed (${#REQUIRED_CLEAN_FIXTURES[@]} fixtures)."
}

restore_trusted_tests(){
  if ! git rev-parse --verify "$TRUSTED_TEST_REF^{commit}" >/dev/null 2>&1; then
    fail "trusted test ref is not available: $TRUSTED_TEST_REF"
  fi
  echo "[green-gate] restoring trusted tests from $TRUSTED_TEST_REF ..."
  if ! git checkout "$TRUSTED_TEST_REF" -- tests/ >/dev/null 2>&1; then
    fail "could not restore trusted tests from $TRUSTED_TEST_REF"
  fi
}

# Git hooks export repo-local environment such as GIT_DIR and GIT_WORK_TREE.
# If those leak into pytest, tests that create temporary git repositories can
# accidentally operate on the caller repo instead of their tmp checkout.
for var in GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES; do
  unset "$var" || true
done

cleanup(){
  if [ "$WORKTREE_CREATED" -eq 1 ]; then
    git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

assert_local_ext4_path "OPENCLAW_REPO" "$REPO"
assert_local_ext4_path "OPENCLAW_VENV" "$VENV"
mkdir -p "$WT_ROOT" || fail "could not create green-gate worktree root: $WT_ROOT"
assert_local_ext4_path "OPENCLAW_GREEN_GATE_WORKTREE_ROOT" "$WT_ROOT"
check_timeout_plugin

echo "[green-gate] clean-room checkout of $REF ..."
if ! git -C "$REPO" worktree add --detach "$WT" "$REF" >/dev/null 2>&1; then
  fail "could not create clean worktree for $REF"
fi
WORKTREE_CREATED=1
cd "$WT" || fail "cwd"
SHA="$(git rev-parse --short HEAD)"
restore_trusted_tests
check_required_clean_fixtures
echo "[green-gate] python: $("$VENV" -c 'import sys; print(sys.executable)')"
echo "[green-gate] running FULL suite on clean checkout $SHA with trusted tests $TRUSTED_TEST_REF (timeout ${TIMEOUT_SECONDS}s/test, method $TIMEOUT_METHOD; this takes ~25 min) ..."
OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 "$VENV" -m pytest -q -rA --timeout="$TIMEOUT_SECONDS" --timeout-method="$TIMEOUT_METHOD" > "$LOG" 2>&1
code=$?
echo "[green-gate] --- result ---"; tail -3 "$LOG"
if [ "$code" -eq 0 ]; then
  echo "[green-gate] PASS — clean checkout of $SHA is green."
else
  echo "[green-gate] FAIL ($code) — clean checkout of $SHA is NOT green. (log: $LOG)"
fi
exit "$code"
