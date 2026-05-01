#!/usr/bin/env bash
set -euo pipefail

# Rebuild ChatGPT Project ingest folders from the Mac audit/build mirror.
# The ingest folders are curated copies only; the PC/WSL repo remains canonical.

SSH_HOST="${SSH_HOST:-mac}"
MAC_MIRROR_REL="${MAC_MIRROR_REL:-OpenClaw_Watch/openclaw_audit_build_readiness}"
INGEST_DIR_NAME="CHATGPT_PROJECT_INGEST_OPENCLAW_AUDIT_BUILD"

FOLDER_1="01_CURRENT_CONTROL_MCP_HASH_READINESS"
FOLDER_2="02_EXPERT_EVIDENCE_OVERNIGHT_INTEGRATION"
FOLDER_3="03_RUNTIME_SERVICE_MODEL_BACKLOG_CONTEXT"
EXPECTED_FILES_PER_FOLDER=24

usage() {
  cat <<'EOF'
Usage:
  refresh_openclaw_audit_build_ingest.sh

Rebuilds exactly three ChatGPT Project ingest upload folders from files already
present in ~/OpenClaw_Watch/openclaw_audit_build_readiness on the Mac.
It deletes/recreates only those three upload folders and writes one
README_DO_NOT_UPLOAD.md outside them. Each numbered upload folder is curated
to 24 files so one ChatGPT Project slot remains open for an ad-hoc note.
EOF
}

case "${1:-}" in
  "") ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

command -v ssh >/dev/null 2>&1 || { echo 'ERROR: ssh is required' >&2; exit 127; }

FOLDER_1_FILES=(
  '00_current_handoff_checkpoint/OPENCLAW_RUNTIME.md|OPENCLAW_RUNTIME.md'
  '00_current_handoff_checkpoint/USER.md|USER.md'
  '00_current_handoff_checkpoint/AGENTS.md|AGENTS.md'
  '00_current_handoff_checkpoint/docs_INDEX.md|docs_INDEX.md'
  '00_current_handoff_checkpoint/AI_WORKING_CONTEXT.md|AI_WORKING_CONTEXT.md'
  '00_current_handoff_checkpoint/BUILD_INTENT.md|BUILD_INTENT.md'
  '00_current_handoff_checkpoint/OPENCLAW_INTENT_AND_CONTROL_MAP.md|OPENCLAW_INTENT_AND_CONTROL_MAP.md'
  '02_architecture_contracts/CORE_ARCHITECTURE_PRINCIPLES.md|CORE_ARCHITECTURE_PRINCIPLES.md'
  '02_architecture_contracts/agent_boundary_resource_audit.md|agent_boundary_resource_audit.md'
  '06_mcp_progressive_discovery/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md|MCP_PROGRESSIVE_DISCOVERY_PROFILES.md'
  '06_mcp_progressive_discovery/mcp_json_default_profile.json|mcp_json_default_profile.json'
  '06_mcp_progressive_discovery/test_mcp_progressive_discovery_profiles.py|test_mcp_progressive_discovery_profiles.py'
  '01_operational_docs/OPENROUTER_KEY_STORAGE.md|OPENROUTER_KEY_STORAGE.md'
  '05_model_router_policy/OPENCLAW_MODEL_FALLBACK_POLICY.md|OPENCLAW_MODEL_FALLBACK_POLICY.md'
  '05_model_router_policy/chief_llm.py|chief_llm.py'
  '05_model_router_policy/test_chief_llm_router.py|test_chief_llm_router.py'
  '08_expert_lane_contracts/expert_escalation_job_manifest.py|expert_escalation_job_manifest.py'
  '08_expert_lane_contracts/expert_provider_policy.py|expert_provider_policy.py'
  '08_expert_lane_contracts/test_expert_escalation_job_manifest.py|test_expert_escalation_job_manifest.py'
  '08_expert_lane_contracts/test_expert_provider_policy.py|test_expert_provider_policy.py'
  '03_harness_test_proof/VALIDATION_POLICY.md|VALIDATION_POLICY.md'
  '03_harness_test_proof/VALIDATION_MAP.md|VALIDATION_MAP.md'
  '03_harness_test_proof/TESTING_SYSTEM.md|TESTING_SYSTEM.md'
  '01_operational_docs/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md|OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md'
)

FOLDER_2_FILES=(
  '08_expert_lane_contracts/expert_escalation_packet.py|expert_escalation_packet.py'
  '08_expert_lane_contracts/test_expert_escalation_packet.py|test_expert_escalation_packet.py'
  '08_expert_lane_contracts/expert_escalation_lane_policy.py|expert_escalation_lane_policy.py'
  '08_expert_lane_contracts/test_expert_escalation_lane_policy.py|test_expert_escalation_lane_policy.py'
  '08_expert_lane_contracts/expert_escalation_queue.py|expert_escalation_queue.py'
  '08_expert_lane_contracts/test_expert_escalation_queue.py|test_expert_escalation_queue.py'
  '08_expert_lane_contracts/expert_escalation_job_manifest.py|expert_escalation_job_manifest.py'
  '08_expert_lane_contracts/test_expert_escalation_job_manifest.py|test_expert_escalation_job_manifest.py'
  '08_expert_lane_contracts/expert_provider_policy.py|expert_provider_policy.py'
  '08_expert_lane_contracts/test_expert_provider_policy.py|test_expert_provider_policy.py'
  '08_expert_lane_contracts/expert_execution_approval_receipt.py|expert_execution_approval_receipt.py'
  '08_expert_lane_contracts/test_expert_execution_approval_receipt.py|test_expert_execution_approval_receipt.py'
  '08_expert_lane_contracts/expert_result_schema.py|expert_result_schema.py'
  '08_expert_lane_contracts/test_expert_result_schema.py|test_expert_result_schema.py'
  '07_dashboard_evidence_reporting/dashboard_evidence_adapter.py|dashboard_evidence_adapter.py'
  '07_dashboard_evidence_reporting/test_dashboard_evidence_adapter.py|test_dashboard_evidence_adapter.py'
  '09_eod_overnight_lane/overnight_run_manifest.py|overnight_run_manifest.py'
  '09_eod_overnight_lane/test_overnight_run_manifest.py|test_overnight_run_manifest.py'
  '09_eod_overnight_lane/chief_eod_harness.py|chief_eod_harness.py'
  '03_harness_test_proof/test_chief_end_of_day_review.py|test_chief_end_of_day_review.py'
  '03_harness_test_proof/chief_acceptance_gate.py|chief_acceptance_gate.py'
  '03_harness_test_proof/test_chief_acceptance_gate.py|test_chief_acceptance_gate.py'
  '09_eod_overnight_lane/morning_brief_harness.py|morning_brief_harness.py'
  '00_current_handoff_checkpoint/OPENCLAW_INTENT_AND_CONTROL_MAP.md|OPENCLAW_INTENT_AND_CONTROL_MAP.md'
)

FOLDER_3_FILES=(
  '01_operational_docs/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md|OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md'
  '04_service_runtime_control/install_hermes_gateway_service.sh|install_hermes_gateway_service.sh'
  '04_service_runtime_control/hermes-gateway.service.in|hermes-gateway.service.in'
  '04_service_runtime_control/chief-listener.service.in|chief-listener.service.in'
  '04_service_runtime_control/chief-worker.service.in|chief-worker.service.in'
  '04_service_runtime_control/chief-memory-worker.service.in|chief-memory-worker.service.in'
  '04_service_runtime_control/chief-state-worker.service.in|chief-state-worker.service.in'
  '04_service_runtime_control/chief-watcher-brain.service.in|chief-watcher-brain.service.in'
  '04_service_runtime_control/chief-guardian-listener.service.in|chief-guardian-listener.service.in'
  '04_service_runtime_control/cassandra-listener.service.in|cassandra-listener.service.in'
  '04_service_runtime_control/cassandra-watcher.service.in|cassandra-watcher.service.in'
  '04_service_runtime_control/cassandra-briefing-scheduler.service.in|cassandra-briefing-scheduler.service.in'
  '05_model_router_policy/OPENCLAW_MODEL_FALLBACK_POLICY.md|OPENCLAW_MODEL_FALLBACK_POLICY.md'
  '05_model_router_policy/chief_llm.py|chief_llm.py'
  '05_model_router_policy/test_chief_llm_router.py|test_chief_llm_router.py'
  '02_architecture_contracts/agent_boundary_resource_audit.md|agent_boundary_resource_audit.md'
  '01_operational_docs/OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md|OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md'
  '03_harness_test_proof/HARNESS_INDEX.md|HARNESS_INDEX.md'
  '03_harness_test_proof/VALIDATION_POLICY.md|VALIDATION_POLICY.md'
  '03_harness_test_proof/VALIDATION_MAP.md|VALIDATION_MAP.md'
  '03_harness_test_proof/TESTING_SYSTEM.md|TESTING_SYSTEM.md'
  '00_current_handoff_checkpoint/OPENCLAW_RUNTIME.md|OPENCLAW_RUNTIME.md'
  '00_current_handoff_checkpoint/USER.md|USER.md'
  '02_architecture_contracts/CORE_ARCHITECTURE_PRINCIPLES.md|CORE_ARCHITECTURE_PRINCIPLES.md'
)

prepare_ingest() {
  ssh "$SSH_HOST" "set -euo pipefail
root=\"\$HOME/$MAC_MIRROR_REL\"
ingest=\"\$root/$INGEST_DIR_NAME\"
case \"\$ingest\" in
  \"\$root\"/*) ;;
  *) echo 'ERROR: unsafe ingest path' >&2; exit 1 ;;
esac
test -d \"\$root\"
mkdir -p \"\$ingest\"
rm -rf \"\$ingest/$FOLDER_1\" \"\$ingest/$FOLDER_2\" \"\$ingest/$FOLDER_3\"
mkdir -p \"\$ingest/$FOLDER_1\" \"\$ingest/$FOLDER_2\" \"\$ingest/$FOLDER_3\"
"

  ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/README_DO_NOT_UPLOAD.md\"" <<'EOF'
# README_DO_NOT_UPLOAD

These folders are curated ChatGPT Project upload sets for OpenClaw audit/build continuity.

- PC/WSL `/home/openclaw` remains the source of truth.
- This Mac mirror and the ingest folders are readable copies only.
- Upload one numbered workflow folder at a time, in order.
- Each numbered workflow folder intentionally contains 24 curated files, leaving one ChatGPT Project slot open for an ad-hoc current prompt, handoff note, error log, screenshot note, or working note.
- Do not upload this README as part of the numbered workflow batches.
- Do not treat copied files as permission to run providers, services, Gmail, Telegram, Legal matter workflows, or Hermes runtime expansion.
EOF
}

copy_to_workflow() {
  local source_rel="$1"
  local folder="$2"
  local dest_name="$3"

  ssh "$SSH_HOST" "set -euo pipefail
source_path=\"\$HOME/$MAC_MIRROR_REL/$source_rel\"
dest_path=\"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/$folder/$dest_name\"
test -f \"\$source_path\"
cp \"\$source_path\" \"\$dest_path\"
"
}

populate_folder() {
  local folder="$1"
  local expected="$2"
  shift 2
  local copied=0
  local entry source_rel dest_name count

  for entry in "$@"; do
    IFS='|' read -r source_rel dest_name <<< "$entry"
    copy_to_workflow "$source_rel" "$folder" "$dest_name"
    copied=$((copied + 1))
  done

  count=$(ssh "$SSH_HOST" "find \"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/$folder\" -maxdepth 1 -type f | wc -l")
  count="${count//[[:space:]]/}"
  printf '%s: copied=%s count=%s expected=%s\n' "$folder" "$copied" "$count" "$expected"

  if [[ "$copied" != "$expected" || "$count" != "$expected" ]]; then
    printf 'ERROR: %s expected %s files, copied %s, found %s\n' "$folder" "$expected" "$copied" "$count" >&2
    exit 1
  fi
}

printf 'openclaw-audit-build-ingest: mirror=%s:%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL"
printf 'openclaw-audit-build-ingest: ingest=%s:%s/%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL" "$INGEST_DIR_NAME"

prepare_ingest
populate_folder "$FOLDER_1" "$EXPECTED_FILES_PER_FOLDER" "${FOLDER_1_FILES[@]}"
populate_folder "$FOLDER_2" "$EXPECTED_FILES_PER_FOLDER" "${FOLDER_2_FILES[@]}"
populate_folder "$FOLDER_3" "$EXPECTED_FILES_PER_FOLDER" "${FOLDER_3_FILES[@]}"

printf 'openclaw-audit-build-ingest: refreshed 3 folders under %s/%s\n' "~/$MAC_MIRROR_REL" "$INGEST_DIR_NAME"