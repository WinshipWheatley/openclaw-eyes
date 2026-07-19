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
proof_commit=2b5314a57d7107ae1b67a4304e02e3b8d7dfa8ab
scope_path=/var/lib/openclaw-authority/lamd-autosend-scope.json
state_path=/var/lib/openclaw-authority/lamd-autosend-brake.json
installed_root=/usr/local/libexec/openclaw-authority
brake_unit=openclaw-lamd-autosend-brake.service
timer_unit=openclaw-lamd-monthly-autosend.timer

pass_gate() {
  printf 'GATE %s PASS\n' "$1"
}

fail_gate() {
  printf 'GATE %s FAIL: %s\n' "$1" "$2" >&2
  exit 1
}

print_plan() {
  cat <<'EOF'
PLAN ONLY preview:
  1. Verify the exact proven source boundary.
  2. Install/start the root brake broker and verify root-owned clear state.
  3. Force the monthly timer disabled and verify the scope unarmed/operator-stopped.
  4. Run clear-vs-tripped acceptance with a fake provider and temporary fake ledger.
  5. Verify final clear state, zero production sends/ledger writes, and preserve a root receipt.
EOF
}

print_plan
if [[ $apply -ne 1 ]]; then
  echo "No files, services, brake state, sends, money, or ledgers were changed."
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  fail_gate "1 SOURCE_AND_INSTALL" "--apply requires an operator-authenticated root shell"
fi

source_paths=(
  lamd_autosend_brake.py
  lamd_autosend_live_adapter.py
  lamd_monthly_autosend.py
  lamd_monthly_autosend_runner.py
  lamd_monthly_package_publisher.py
  config/lamd_autosend_scope.unarmed.json
  scripts/accept_lamd_autosend_installed.py
  scripts/install_lamd_autosend_brake_linux.sh
  systemd/system/openclaw-lamd-autosend-brake.service.in
  systemd/system/openclaw-lamd-monthly-autosend.service.in
  systemd/system/openclaw-lamd-monthly-autosend.timer
)
if ! git -c safe.directory="$repo_root" -C "$repo_root" merge-base --is-ancestor "$proof_commit" HEAD; then
  fail_gate "1 SOURCE_AND_INSTALL" "proven commit is not present in HEAD"
fi
if ! git -c safe.directory="$repo_root" -C "$repo_root" diff --quiet "$proof_commit" -- "${source_paths[@]}"; then
  fail_gate "1 SOURCE_AND_INSTALL" "proven install/runtime sources differ from $proof_commit"
fi
cd "$repo_root"
if ! scripts/install_lamd_autosend_brake_linux.sh --apply; then
  fail_gate "1 SOURCE_AND_INSTALL" "root installer failed"
fi
if ! cmp -s lamd_autosend_brake.py "$installed_root/lamd_autosend_brake.py"; then
  fail_gate "1 SOURCE_AND_INSTALL" "installed brake bytes differ from source"
fi
if ! cmp -s scripts/accept_lamd_autosend_installed.py "$installed_root/accept_lamd_autosend_installed.py"; then
  fail_gate "1 SOURCE_AND_INSTALL" "installed acceptance bytes differ from source"
fi
pass_gate "1 SOURCE_AND_INSTALL"

if ! systemctl is-active --quiet "$brake_unit"; then
  fail_gate "2 ROOT_BRAKE_CLEAR" "root brake broker is not active"
fi
if [[ "$(stat -c '%U:%G:%a' "$state_path")" != "root:root:644" ]]; then
  fail_gate "2 ROOT_BRAKE_CLEAR" "brake state is not root:root mode 0644"
fi
status_receipt="$(mktemp /run/openclaw-authority/lamd-status.XXXXXX.json)" || \
  fail_gate "2 ROOT_BRAKE_CLEAR" "could not create bounded status receipt"
trap 'rm -f -- "$status_receipt"' EXIT
if ! /usr/bin/python3 "$installed_root/lamd_autosend_brake.py" status >"$status_receipt"; then
  fail_gate "2 ROOT_BRAKE_CLEAR" "installed brake status call failed"
fi
if ! /usr/bin/python3 -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p.get("ok") is True; s=p["state"]; assert s["schema_version"]=="fleet_freeze_state_v1" and s["state"]=="PLANNED"' \
  "$status_receipt"; then
  fail_gate "2 ROOT_BRAKE_CLEAR" "brake was not already clear; it was not overridden"
fi
pass_gate "2 ROOT_BRAKE_CLEAR"

if ! systemctl disable --now openclaw-lamd-monthly-autosend.timer; then
  fail_gate "3 UNARMED_AND_TIMER_DISABLED" "could not disable the monthly timer"
fi
if systemctl is-enabled --quiet "$timer_unit" || systemctl is-active --quiet "$timer_unit"; then
  fail_gate "3 UNARMED_AND_TIMER_DISABLED" "monthly timer remains enabled or active"
fi
if [[ "$(stat -c '%U:%G:%a' "$scope_path")" != "root:root:644" ]]; then
  fail_gate "3 UNARMED_AND_TIMER_DISABLED" "scope is not root:root mode 0644"
fi
if ! /usr/bin/python3 -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["schema_version"]=="lamd_autosend_scope_v1"; assert p["armed"] is False and p["operator_stop"] is True' \
  "$scope_path"; then
  fail_gate "3 UNARMED_AND_TIMER_DISABLED" "scope is not unarmed and operator-stopped"
fi
pass_gate "3 UNARMED_AND_TIMER_DISABLED"

acceptance_receipt="$(mktemp /var/lib/openclaw-authority/lamd-installed-acceptance.XXXXXX.json)" || \
  fail_gate "4 FAKE_PROVIDER_ACCEPTANCE" "could not create the root acceptance receipt"
chmod 0600 "$acceptance_receipt" || \
  fail_gate "4 FAKE_PROVIDER_ACCEPTANCE" "could not protect the root acceptance receipt"
if ! OPENCLAW_REPO_ROOT="$repo_root" /usr/bin/python3 "$installed_root/accept_lamd_autosend_installed.py" --apply >"$acceptance_receipt"; then
  cat "$acceptance_receipt" >&2 || true
  fail_gate "4 FAKE_PROVIDER_ACCEPTANCE" "installed clear-vs-tripped acceptance failed"
fi
cat "$acceptance_receipt"
if ! /usr/bin/python3 -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="PASS"; assert p["clear_result"]["status"]=="LEDGER_POSTED"; assert p["tripped_result"]["status"]=="REFUSED_FLEET_FREEZE"; assert p["queued_for_release"] is False' \
  "$acceptance_receipt"; then
  fail_gate "4 FAKE_PROVIDER_ACCEPTANCE" "acceptance receipt did not prove clear and tripped behavior"
fi
pass_gate "4 FAKE_PROVIDER_ACCEPTANCE"

if ! /usr/bin/python3 -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["fake_provider_total_calls"]==1; assert p["production_provider_calls"]==0; assert p["production_ledger_writes"]==0' \
  "$acceptance_receipt"; then
  fail_gate "5 FINAL_SAFETY_STATE" "acceptance did not prove zero production side effects"
fi
if ! /usr/bin/python3 "$installed_root/lamd_autosend_brake.py" status >"$status_receipt"; then
  fail_gate "5 FINAL_SAFETY_STATE" "final brake status call failed"
fi
if ! /usr/bin/python3 -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p.get("ok") is True and p["state"]["state"]=="PLANNED"' \
  "$status_receipt"; then
  fail_gate "5 FINAL_SAFETY_STATE" "brake did not return to clear state"
fi
if systemctl is-enabled --quiet "$timer_unit" || systemctl is-active --quiet "$timer_unit"; then
  fail_gate "5 FINAL_SAFETY_STATE" "monthly timer changed during acceptance"
fi
pass_gate "5 FINAL_SAFETY_STATE"
printf 'ACCEPTANCE RECEIPT: %s\n' "$acceptance_receipt"
echo "COMPLETE: installed brake proven; auto-send remains unarmed and its timer disabled."
