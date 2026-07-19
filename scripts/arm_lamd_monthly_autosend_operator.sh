#!/usr/bin/env bash
set -euo pipefail

apply=0
if [[ "${1:-}" == "--apply" ]]; then
  apply=1
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--apply]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scope_path=/var/lib/openclaw-authority/lamd-autosend-scope.json
state_path=/var/lib/openclaw-authority/lamd-autosend-brake.json
brake_unit=openclaw-lamd-autosend-brake.service
timer_unit=openclaw-lamd-monthly-autosend.timer
expected_generation=5
not_before_service_month=2026-08
monthly_sha256=09d0dd4b10565791e39baf2f51e95350591a123a956b839a7f13f25ce9e1e12f
runner_sha256=7c1799c507688a51095d43b743a2df0062728b396370d047584632167553daf4
live_adapter_sha256=fb91b7ea96697b0b187a627cde2bec1abc65f0c8c7fb20df4a2d3d95b2aec186

pass_gate() {
  printf 'GATE %s PASS\n' "$1"
}

fail_gate() {
  printf 'GATE %s FAIL: %s\n' "$1" "$2" >&2
  exit 1
}

print_plan() {
  cat <<EOF
PLAN ONLY preview:
  1. Verify tested LAMD runtime hashes and the active brake broker.
  2. Require the live brake state to be PLANNED generation ${expected_generation}.
  3. Atomically arm the standing LAMD scope with operator_stop=false and not_before_service_month=${not_before_service_month}.
  4. Enable the monthly timer and verify the brake still reports PLANNED.
  5. Write a root-owned ARM receipt with the armed scope hash and timer state.
No Gmail call, provider call, production ledger write, money movement, delete, or brake trip is performed by this wrapper.
EOF
}

check_sha() {
  local relpath="$1"
  local expected="$2"
  local observed
  observed="$(sha256sum "$repo_root/$relpath")"
  observed="${observed%% *}"
  if [[ "$observed" != "$expected" ]]; then
    fail_gate "1 SOURCE_AND_BRAKE_PRESENT" "$relpath hash changed"
  fi
}

print_plan
if [[ $apply -ne 1 ]]; then
  echo "No files, services, brake state, sends, money, or ledgers were changed."
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  fail_gate "1 SOURCE_AND_BRAKE_PRESENT" "--apply requires an operator-authenticated root shell"
fi

check_sha "lamd_monthly_autosend.py" "$monthly_sha256"
check_sha "lamd_monthly_autosend_runner.py" "$runner_sha256"
check_sha "lamd_autosend_live_adapter.py" "$live_adapter_sha256"
if ! systemctl is-active --quiet "$brake_unit"; then
  fail_gate "1 SOURCE_AND_BRAKE_PRESENT" "brake broker is not active"
fi
if [[ ! -S /run/openclaw-authority/lamd-autosend-brake.sock ]]; then
  fail_gate "1 SOURCE_AND_BRAKE_PRESENT" "brake broker socket is unavailable"
fi
pass_gate "1 SOURCE_AND_BRAKE_PRESENT"

status_receipt="$(mktemp /run/openclaw-authority/lamd-arm-status.XXXXXX.json)" || \
  fail_gate "2 BRAKE_CLEAR_GENERATION" "could not create bounded status receipt"
trap 'rm -f -- "$status_receipt"' EXIT
if ! /usr/bin/python3 "$repo_root/lamd_autosend_brake.py" status >"$status_receipt"; then
  fail_gate "2 BRAKE_CLEAR_GENERATION" "brake status call failed"
fi
if ! /usr/bin/python3 - "$status_receipt" "$expected_generation" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
expected_generation = int(sys.argv[2])
state = payload.get("state") if payload.get("ok") is True else {}
assert state.get("schema_version") == "fleet_freeze_state_v1"
assert state.get("state") == "PLANNED"
assert int(state.get("generation") or 0) == expected_generation
assert state.get("set_by") == "operator"
assert state.get("reason") == "clear guardian live-trip test generation 4"
PY
then
  fail_gate "2 BRAKE_CLEAR_GENERATION" "brake is not the proven post-clear generation"
fi
pass_gate "2 BRAKE_CLEAR_GENERATION"

scope_receipt="$(mktemp /run/openclaw-authority/lamd-arm-scope.XXXXXX.json)" || \
  fail_gate "3 SCOPE_ARMED_FUTURE_MONTH" "could not create bounded scope receipt"
if ! /usr/bin/python3 - "$scope_path" "$not_before_service_month" >"$scope_receipt" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

scope_path = Path(sys.argv[1])
not_before = sys.argv[2]
expected = {
    "schema_version": "lamd_autosend_scope_v1",
    "client_ref": "live_arts_md",
    "stream": "speaker_rental",
    "amount_minor_units": 10000,
    "currency": "USD",
    "recipient": "Accountant@liveartsmd.org",
    "cadence_day": 16,
    "standing_authority_ref": "operator-terminal-grant:lamd-monthly-autosend:2026-07-18",
    "authority_source_ref": "/home/openclaw/Operator/to-codex/OPUS-ARM-LAMD-MONTHLY-AUTOSEND-20260718.md",
}
with scope_path.open(encoding="utf-8") as handle:
    current = json.load(handle)
for key, expected_value in expected.items():
    if current.get(key) != expected_value:
        raise SystemExit(f"scope drift: {key}")
desired = dict(current)
desired["armed"] = True
desired["operator_stop"] = False
desired["not_before_service_month"] = not_before
if current != desired:
    temporary = scope_path.with_name(f".{scope_path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(desired, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644, follow_symlinks=False)
        os.replace(temporary, scope_path)
        directory_fd = os.open(scope_path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
with scope_path.open("rb") as handle:
    scope_bytes = handle.read()
after = json.loads(scope_bytes.decode("utf-8"))
assert after["armed"] is True
assert after["operator_stop"] is False
assert after["not_before_service_month"] == not_before
print(json.dumps({"scope_sha256": hashlib.sha256(scope_bytes).hexdigest(), "not_before_service_month": not_before}, sort_keys=True))
PY
then
  fail_gate "3 SCOPE_ARMED_FUTURE_MONTH" "could not arm standing scope with future-month gate"
fi
pass_gate "3 SCOPE_ARMED_FUTURE_MONTH"

systemctl daemon-reload || fail_gate "4 TIMER_ENABLED" "daemon-reload failed"
systemctl enable --now openclaw-lamd-monthly-autosend.timer || \
  fail_gate "4 TIMER_ENABLED" "could not enable monthly timer"
if ! systemctl is-enabled --quiet "$timer_unit"; then
  fail_gate "4 TIMER_ENABLED" "monthly timer is not enabled"
fi
if ! systemctl is-active --quiet "$timer_unit"; then
  fail_gate "4 TIMER_ENABLED" "monthly timer is not active"
fi
pass_gate "4 TIMER_ENABLED"

if ! /usr/bin/python3 "$repo_root/lamd_autosend_brake.py" status >"$status_receipt"; then
  fail_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS" "post-arm brake status call failed"
fi
if ! /usr/bin/python3 - "$status_receipt" "$expected_generation" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
expected_generation = int(sys.argv[2])
state = payload.get("state") if payload.get("ok") is True else {}
assert state.get("state") == "PLANNED"
assert int(state.get("generation") or 0) == expected_generation
PY
then
  fail_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS" "brake did not remain clear after arming"
fi
receipt_path="$(mktemp /var/lib/openclaw-authority/lamd-arm.XXXXXX.json)" || \
  fail_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS" "could not create arm receipt"
chmod 0600 "$receipt_path" || \
  fail_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS" "could not protect arm receipt"
if ! /usr/bin/python3 - "$scope_receipt" "$status_receipt" "$timer_unit" "$receipt_path" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone

scope_receipt = json.load(open(sys.argv[1], encoding="utf-8"))
brake_status = json.load(open(sys.argv[2], encoding="utf-8"))
timer_unit = sys.argv[3]
receipt_path = sys.argv[4]
timer_enabled = subprocess.check_output(["systemctl", "is-enabled", timer_unit], text=True).strip()
timer_active = subprocess.check_output(["systemctl", "is-active", timer_unit], text=True).strip()
payload = {
    "schema_version": "lamd_monthly_autosend_arm_receipt_v1",
    "status": "PASS",
    "armed": True,
    "operator_stop": False,
    "not_before_service_month": scope_receipt["not_before_service_month"],
    "scope_sha256": scope_receipt["scope_sha256"],
    "timer_unit": timer_unit,
    "timer_enabled": timer_enabled,
    "timer_active": timer_active,
    "brake_state": brake_status["state"],
    "provider_called": False,
    "production_ledger_writes": 0,
    "money_moved": False,
    "first_live_fire_before_not_before_service_month": False,
    "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
with open(receipt_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
    handle.write("\n")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
then
  fail_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS" "could not write arm receipt"
fi
pass_gate "5 ARM_RECEIPT_AND_BRAKE_STATUS"
printf 'ARM RECEIPT: %s\n' "$receipt_path"
echo "COMPLETE: LAMD monthly auto-send armed with not_before_service_month=${not_before_service_month}; July is blocked by the runtime scope gate."
