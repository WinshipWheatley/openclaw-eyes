#!/usr/bin/env bash
# OpenClaw GREEN GATE — run the FULL suite on a FRESH, CLEAN CHECKOUT of a ref.
#
# THE LESSON (2026-06-14): a stateful worktree's "green" LIES. The Codex got
# lastfailed={} in its own worktree (full of session-generated fixtures) and pushed
# main — but a clean checkout had 33 failures. This gate ALWAYS clean-rooms: it checks
# out the exact commit into a throwaway worktree with ONLY committed files, so
# "works on my box" can never reach main again.
#
# Usage:
#   green_gate.sh [ref]                     # FULL gate, serialized by atomic lock
#   green_gate.sh --fast [ref] [pytest ...] # focused pre-gate, no full-gate lock
# Exit 0 = clean-checkout suite passed; non-zero = NOT green (caller should block).
set -uo pipefail
MODE="full"
if [ "${1:-}" = "--fast" ]; then
  MODE="fast"
  shift
fi
REF="${1:-HEAD}"
if [ "$#" -gt 0 ]; then
  shift
fi
PYTEST_ARGS=("$@")
REPO="${OPENCLAW_REPO:-/home/openclaw}"
VENV="${OPENCLAW_VENV:-/home/openclaw/.venv/bin/python}"
TIMEOUT_SECONDS="${OPENCLAW_PYTEST_TIMEOUT_SECONDS:-90}"
TIMEOUT_METHOD="${OPENCLAW_PYTEST_TIMEOUT_METHOD:-thread}"
TRUSTED_TEST_REF="${OPENCLAW_TRUSTED_TEST_REF:-${OPENCLAW_TRUSTED_ACCEPTANCE_REF:-origin/codex/pc4-self-healing}}"
WT_ROOT="${OPENCLAW_GREEN_GATE_WORKTREE_ROOT:-/tmp/openclaw-green-gate}"
TS="$(date +%s)-$$"
WT="$WT_ROOT/greengate-$TS"
RUN_ROOT="${OPENCLAW_GREEN_GATE_RUN_ROOT:-/tmp/openclaw-green-gate-runs}"
RUN_TMP="$RUN_ROOT/greengate-$TS"
LOG="$RUN_TMP/pytest.log"
LOCK_DIR="${OPENCLAW_GREEN_GATE_LOCK_DIR:-/tmp/openclaw-green-gate-full.lock}"
LOCK_STALE_SECONDS="${OPENCLAW_GREEN_GATE_LOCK_STALE_SECONDS:-900}"
LOCK_POLL_SECONDS="${OPENCLAW_GREEN_GATE_LOCK_POLL_SECONDS:-5}"
WORKTREE_CREATED=0
LOCK_HELD=0
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

lock_holder_value(){
  local key="$1"
  awk -F= -v key="$key" '$1 == key {print $2; exit}' "$LOCK_DIR/holder.env" 2>/dev/null || true
}

lock_age_seconds(){
  local now started
  now="$(date +%s)"
  started="$(lock_holder_value started_epoch)"
  case "$started" in
    ""|*[!0-9]*)
      started="$(stat -c %Y "$LOCK_DIR" 2>/dev/null || printf '%s\n' "$now")"
      ;;
  esac
  printf '%s\n' "$(( now - started ))"
}

lock_holder_alive(){
  local pid
  pid="$(lock_holder_value pid)"
  case "$pid" in
    ""|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" >/dev/null 2>&1
}

reap_stale_full_gate_lock(){
  [ -d "$LOCK_DIR" ] || return 0
  if lock_holder_alive; then
    return 0
  fi
  local age
  age="$(lock_age_seconds)"
  if [ "$age" -ge "$LOCK_STALE_SECONDS" ]; then
    echo "[green-gate] reaping stale full gate lock at $LOCK_DIR (age ${age}s, no live holder)."
    rm -rf "$LOCK_DIR"
  fi
}

write_full_gate_lock_metadata(){
  cat > "$LOCK_DIR/holder.env" <<EOF
pid=$$
started_epoch=$(date +%s)
ref=$REF
worktree=$WT
run_tmp=$RUN_TMP
log=$LOG
EOF
}

acquire_full_gate_lock(){
  while true; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      LOCK_HELD=1
      write_full_gate_lock_metadata
      echo "[green-gate] FULL gate lock acquired: $LOCK_DIR"
      return 0
    fi
    reap_stale_full_gate_lock
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      LOCK_HELD=1
      write_full_gate_lock_metadata
      echo "[green-gate] FULL gate lock acquired: $LOCK_DIR"
      return 0
    fi
    echo "[green-gate] waiting for FULL gate lock: $LOCK_DIR"
    sleep "$LOCK_POLL_SECONDS"
  done
}

release_full_gate_lock(){
  if [ "$LOCK_HELD" -eq 1 ]; then
    if [ "$(lock_holder_value pid)" = "$$" ]; then
      rm -rf "$LOCK_DIR"
    fi
    LOCK_HELD=0
    echo "[green-gate] FULL gate lock released: $LOCK_DIR"
  fi
}

prepare_fast_pytest_args(){
  if [ "${#PYTEST_ARGS[@]}" -gt 0 ]; then
    return 0
  fi
  if [ -n "${OPENCLAW_FAST_PYTEST_ARGS:-}" ]; then
    # Intentional shell-style splitting for operator-provided focused pytest args.
    # shellcheck disable=SC2206
    PYTEST_ARGS=($OPENCLAW_FAST_PYTEST_ARGS)
    return 0
  fi
  PYTEST_ARGS=(tests/test_green_gate_script.py)
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
  release_full_gate_lock
}
trap cleanup EXIT

assert_local_ext4_path "OPENCLAW_REPO" "$REPO"
assert_local_ext4_path "OPENCLAW_VENV" "$VENV"
assert_local_ext4_path "OPENCLAW_GREEN_GATE_RUN_ROOT" "$RUN_ROOT"
assert_local_ext4_path "OPENCLAW_GREEN_GATE_LOCK_DIR" "$LOCK_DIR"
mkdir -p "$WT_ROOT" || fail "could not create green-gate worktree root: $WT_ROOT"
mkdir -p "$RUN_TMP/tmp" "$RUN_TMP/sqlite" || fail "could not create green-gate run tmp: $RUN_TMP"
mkdir -p "$(dirname "$LOCK_DIR")" || fail "could not create full-gate lock parent: $(dirname "$LOCK_DIR")"
assert_local_ext4_path "OPENCLAW_GREEN_GATE_WORKTREE_ROOT" "$WT_ROOT"
export TMPDIR="$RUN_TMP/tmp"
export OPENCLAW_PYTEST_REDIRECT_TMP_SQLITE="${OPENCLAW_PYTEST_REDIRECT_TMP_SQLITE:-1}"
export OPENCLAW_PYTEST_TMP_SQLITE_ROOT="${OPENCLAW_PYTEST_TMP_SQLITE_ROOT:-$RUN_TMP/sqlite}"
check_timeout_plugin

if [ "$MODE" = "full" ]; then
  acquire_full_gate_lock
else
  prepare_fast_pytest_args
  echo "[green-gate] FAST pre-gate mode enabled; no full-gate lock will be acquired."
fi

echo "[green-gate] clean-room checkout of $REF ..."
if ! git -C "$REPO" worktree add --detach "$WT" "$REF" >/dev/null 2>&1; then
  fail "could not create clean worktree for $REF"
fi
WORKTREE_CREATED=1
cd "$WT" || fail "cwd"
SHA="$(git rev-parse --short HEAD)"
echo "[green-gate] python: $("$VENV" -c 'import sys; print(sys.executable)')"
if [ "$MODE" = "full" ]; then
  restore_trusted_tests
  check_required_clean_fixtures
  echo "[green-gate] running FULL suite on clean checkout $SHA with trusted tests $TRUSTED_TEST_REF (timeout ${TIMEOUT_SECONDS}s/test, method $TIMEOUT_METHOD; this takes ~25 min) ..."
  OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 "$VENV" -m pytest -q -rA --timeout="$TIMEOUT_SECONDS" --timeout-method="$TIMEOUT_METHOD" > "$LOG" 2>&1
else
  echo "[green-gate] running FAST pre-gate on clean checkout $SHA: ${PYTEST_ARGS[*]}"
  OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 "$VENV" -m pytest -q -rA --timeout="$TIMEOUT_SECONDS" --timeout-method="$TIMEOUT_METHOD" "${PYTEST_ARGS[@]}" > "$LOG" 2>&1
fi
code=$?
echo "[green-gate] --- result ---"; tail -3 "$LOG"
if [ "$code" -eq 0 ]; then
  echo "[green-gate] PASS — clean checkout of $SHA is green."
else
  echo "[green-gate] FAIL ($code) — clean checkout of $SHA is NOT green. (log: $LOG)"
fi
exit "$code"
