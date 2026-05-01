#!/usr/bin/env bash
set -euo pipefail

# One-way curated mirror: PC/WSL canonical audit/build files -> Mac review copy.
# This helper copies only the explicit manifest below. It never uses --delete.

SSH_HOST="${SSH_HOST:-mac}"
REPO_ROOT="${REPO_ROOT:-/home/openclaw}"
MAC_MIRROR_REL="${MAC_MIRROR_REL:-OpenClaw_Watch/openclaw_audit_build_readiness}"

usage() {
  cat <<'EOF'
Usage:
  sync_openclaw_audit_build_to_mac.sh          # copy manifest to Mac mirror
  sync_openclaw_audit_build_to_mac.sh --dry-run
  sync_openclaw_audit_build_to_mac.sh --list

Copies only the explicit audit/build readiness manifest from /home/openclaw
to ~/OpenClaw_Watch/openclaw_audit_build_readiness on the Mac SSH host.
No secrets, runtime vaults, logs, generated artifacts, or broad repo folders
are copied. This script never deletes Mac files.
EOF
}

mode="apply"
case "${1:-}" in
  "") ;;
  --dry-run) mode="dry-run" ;;
  --list) mode="list" ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

MANIFEST=(
  'AGENTS.md|00_current_handoff_checkpoint/AGENTS.md'
  'OPENCLAW_RUNTIME.md|00_current_handoff_checkpoint/OPENCLAW_RUNTIME.md'
  'USER.md|00_current_handoff_checkpoint/USER.md'
  'docs/INDEX.md|00_current_handoff_checkpoint/docs_INDEX.md'
  'docs/_ai/AI_WORKING_CONTEXT.md|00_current_handoff_checkpoint/AI_WORKING_CONTEXT.md'
  'docs/_ai/BUILD_INTENT.md|00_current_handoff_checkpoint/BUILD_INTENT.md'
  'docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md|00_current_handoff_checkpoint/OPENCLAW_INTENT_AND_CONTROL_MAP.md'
  'docs/operations/OPENROUTER_KEY_STORAGE.md|01_operational_docs/OPENROUTER_KEY_STORAGE.md'
  'docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md|01_operational_docs/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md'
  'docs/operations/OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md|01_operational_docs/OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md'
  'CORE_ARCHITECTURE_PRINCIPLES.md|02_architecture_contracts/CORE_ARCHITECTURE_PRINCIPLES.md'
  'docs/planning/agent_boundary_resource_audit.md|02_architecture_contracts/agent_boundary_resource_audit.md'
  'docs/testing/HARNESS_INDEX.md|03_harness_test_proof/HARNESS_INDEX.md'
  'docs/testing/TESTING_SYSTEM.md|03_harness_test_proof/TESTING_SYSTEM.md'
  'docs/testing/VALIDATION_MAP.md|03_harness_test_proof/VALIDATION_MAP.md'
  'docs/testing/VALIDATION_POLICY.md|03_harness_test_proof/VALIDATION_POLICY.md'
  'chief_acceptance_gate.py|03_harness_test_proof/chief_acceptance_gate.py'
  'tests/test_chief_acceptance_gate.py|03_harness_test_proof/test_chief_acceptance_gate.py'
  'tests/test_chief_end_of_day_review.py|03_harness_test_proof/test_chief_end_of_day_review.py'
  'scripts/install_hermes_gateway_service.sh|04_service_runtime_control/install_hermes_gateway_service.sh'
  'systemd/user/cassandra-briefing-scheduler.service.in|04_service_runtime_control/cassandra-briefing-scheduler.service.in'
  'systemd/user/cassandra-listener.service.in|04_service_runtime_control/cassandra-listener.service.in'
  'systemd/user/cassandra-watcher.service.in|04_service_runtime_control/cassandra-watcher.service.in'
  'systemd/user/chief-guardian-listener.service.in|04_service_runtime_control/chief-guardian-listener.service.in'
  'systemd/user/chief-listener.service.in|04_service_runtime_control/chief-listener.service.in'
  'systemd/user/chief-memory-worker.service.in|04_service_runtime_control/chief-memory-worker.service.in'
  'systemd/user/chief-state-worker.service.in|04_service_runtime_control/chief-state-worker.service.in'
  'systemd/user/chief-watcher-brain.service.in|04_service_runtime_control/chief-watcher-brain.service.in'
  'systemd/user/chief-worker.service.in|04_service_runtime_control/chief-worker.service.in'
  'systemd/user/hermes-gateway.service.in|04_service_runtime_control/hermes-gateway.service.in'
  'docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md|05_model_router_policy/OPENCLAW_MODEL_FALLBACK_POLICY.md'
  'chief_llm.py|05_model_router_policy/chief_llm.py'
  'tests/test_chief_llm_router.py|05_model_router_policy/test_chief_llm_router.py'
  '.mcp.json|06_mcp_progressive_discovery/mcp_json_default_profile.json'
  'docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md|06_mcp_progressive_discovery/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md'
  'tests/test_mcp_progressive_discovery_profiles.py|06_mcp_progressive_discovery/test_mcp_progressive_discovery_profiles.py'
  'dashboard_evidence_adapter.py|07_dashboard_evidence_reporting/dashboard_evidence_adapter.py'
  'tests/test_dashboard_evidence_adapter.py|07_dashboard_evidence_reporting/test_dashboard_evidence_adapter.py'
  'dashboard_report_snapshot.py|07_dashboard_evidence_reporting/dashboard_report_snapshot.py'
  'tests/test_dashboard_report_snapshot.py|07_dashboard_evidence_reporting/test_dashboard_report_snapshot.py'
  'expert_escalation_packet.py|08_expert_lane_contracts/expert_escalation_packet.py'
  'tests/test_expert_escalation_packet.py|08_expert_lane_contracts/test_expert_escalation_packet.py'
  'expert_escalation_lane_policy.py|08_expert_lane_contracts/expert_escalation_lane_policy.py'
  'tests/test_expert_escalation_lane_policy.py|08_expert_lane_contracts/test_expert_escalation_lane_policy.py'
  'expert_escalation_queue.py|08_expert_lane_contracts/expert_escalation_queue.py'
  'tests/test_expert_escalation_queue.py|08_expert_lane_contracts/test_expert_escalation_queue.py'
  'expert_escalation_job_manifest.py|08_expert_lane_contracts/expert_escalation_job_manifest.py'
  'tests/test_expert_escalation_job_manifest.py|08_expert_lane_contracts/test_expert_escalation_job_manifest.py'
  'expert_provider_policy.py|08_expert_lane_contracts/expert_provider_policy.py'
  'tests/test_expert_provider_policy.py|08_expert_lane_contracts/test_expert_provider_policy.py'
  'expert_execution_approval_receipt.py|08_expert_lane_contracts/expert_execution_approval_receipt.py'
  'tests/test_expert_execution_approval_receipt.py|08_expert_lane_contracts/test_expert_execution_approval_receipt.py'
  'expert_result_schema.py|08_expert_lane_contracts/expert_result_schema.py'
  'tests/test_expert_result_schema.py|08_expert_lane_contracts/test_expert_result_schema.py'
  'expert_staged_packet_flow.py|08_expert_lane_contracts/expert_staged_packet_flow.py'
  'tests/test_expert_staged_packet_flow.py|08_expert_lane_contracts/test_expert_staged_packet_flow.py'
  'expert_approval_packet.py|08_expert_lane_contracts/expert_approval_packet.py'
  'tests/test_expert_approval_packet.py|08_expert_lane_contracts/test_expert_approval_packet.py'
  'overnight_run_manifest.py|09_eod_overnight_lane/overnight_run_manifest.py'
  'tests/test_overnight_run_manifest.py|09_eod_overnight_lane/test_overnight_run_manifest.py'
  'chief_eod_harness.py|09_eod_overnight_lane/chief_eod_harness.py'
  'morning_brief_harness.py|09_eod_overnight_lane/morning_brief_harness.py'
  'guardian_schema_harness.py|09_eod_overnight_lane/guardian_schema_harness.py'
  'docs/planning/OPENCLAW_LANE_A_OPENROUTER_SCOUT_BACKLOG.md|10_future_work_backlog/OPENCLAW_LANE_A_OPENROUTER_SCOUT_BACKLOG.md'
  'mac_eyes/Launchers/sync_openclaw_audit_build_to_mac.sh|helpers/sync_openclaw_audit_build_to_mac.sh'
  'mac_eyes/Launchers/refresh_openclaw_audit_build_ingest.sh|helpers/refresh_openclaw_audit_build_ingest.sh'
)

if [[ "$mode" == "list" ]]; then
  for entry in "${MANIFEST[@]}"; do
    printf '%s\n' "$entry"
  done
  exit 0
fi

if [[ ! -d "$REPO_ROOT" ]]; then
  printf 'ERROR: repository root is missing: %s\n' "$REPO_ROOT" >&2
  exit 1
fi

if [[ "$mode" == "apply" ]]; then
  command -v ssh >/dev/null 2>&1 || { echo 'ERROR: ssh is required' >&2; exit 127; }
  command -v rsync >/dev/null 2>&1 || { echo 'ERROR: rsync is required' >&2; exit 127; }
fi

printf 'openclaw-audit-build-sync: mode=%s\n' "$mode"
printf 'openclaw-audit-build-sync: source=%s\n' "$REPO_ROOT"
printf 'openclaw-audit-build-sync: destination=%s:%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL"
printf 'openclaw-audit-build-sync: manifest_entries=%s\n' "${#MANIFEST[@]}"

missing=0
copied=0
skipped=0
verified=0

for entry in "${MANIFEST[@]}"; do
  IFS='|' read -r source_rel dest_rel <<< "$entry"
  source_path="$REPO_ROOT/$source_rel"

  if [[ ! -f "$source_path" ]]; then
    printf 'ERROR: required source missing: %s\n' "$source_rel" >&2
    missing=$((missing + 1))
    continue
  fi

  if [[ "$mode" == "dry-run" ]]; then
    printf 'would copy: %s -> %s:%s/%s\n' "$source_rel" "$SSH_HOST" "~/$MAC_MIRROR_REL" "$dest_rel"
    skipped=$((skipped + 1))
    continue
  fi

  dest_dir="${dest_rel%/*}"
  ssh "$SSH_HOST" "mkdir -p \"\$HOME/$MAC_MIRROR_REL/$dest_dir\""
  rsync -az --timeout=10 "$source_path" "$SSH_HOST:$MAC_MIRROR_REL/$dest_rel"
  ssh "$SSH_HOST" "test -f \"\$HOME/$MAC_MIRROR_REL/$dest_rel\""
  copied=$((copied + 1))
  verified=$((verified + 1))
done

if (( missing > 0 )); then
  printf 'openclaw-audit-build-sync: FAILED missing=%s copied=%s skipped=%s verified=%s\n' "$missing" "$copied" "$skipped" "$verified" >&2
  exit 1
fi

printf 'openclaw-audit-build-sync: copied=%s skipped=%s verified=%s missing=%s\n' "$copied" "$skipped" "$verified" "$missing"