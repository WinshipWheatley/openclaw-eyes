#!/usr/bin/env bash
set -euo pipefail

# One-way curated mirror: PC/WSL canonical Operator Harness files -> Mac review copy.
# This helper copies only the explicit manifest below. It never uses --delete.

SSH_HOST="${SSH_HOST:-mac}"
REPO_ROOT="${REPO_ROOT:-/home/openclaw}"
MAC_MIRROR_REL="${MAC_MIRROR_REL:-OpenClaw_Watch/operator_harness_readiness}"
DELTA_BRIDGE_NAME="CHAT_STAY_UP_TO_DATE.md"

usage() {
  cat <<'EOF'
Usage:
  sync_operator_harness_to_mac.sh            # copy manifest to Mac mirror
  sync_operator_harness_to_mac.sh --dry-run  # local source/count check only
  sync_operator_harness_to_mac.sh --list     # print source|mirror manifest

Copies only the explicit Operator Harness / Launch Ladder readiness source set
from /home/openclaw to ~/OpenClaw_Watch/operator_harness_readiness on the Mac
SSH host. The adjacent CHAT_STAY_UP_TO_DATE.md bridge is copied to the mirror
root, outside the ChatGPT Project ingest folders. No secrets, runtime vaults,
logs, generated artifacts, installed units, provider/model calls, Gmail bodies,
LegalPrivate, or broad repo folders are copied. This script never deletes Mac
files.
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
  'docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md|00_launch_ladder/LAUNCH_LADDER_INDEX.md'
  'docs/planning/launch_ladder/00_NORTH_STAR.md|00_launch_ladder/00_NORTH_STAR.md'
  'docs/planning/launch_ladder/01_RUNTIME_MAP.md|00_launch_ladder/01_RUNTIME_MAP.md'
  'docs/planning/launch_ladder/02_CAPABILITY_AUTHORITY_AND_READINESS.md|00_launch_ladder/02_CAPABILITY_AUTHORITY_AND_READINESS.md'
  'docs/planning/launch_ladder/03_GOAL_HORIZONS.md|00_launch_ladder/03_GOAL_HORIZONS.md'
  'docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md|00_launch_ladder/04_LAUNCH_LADDER_MODEL.md'
  'docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|00_launch_ladder/05_EVIDENCE_AND_FRESHNESS.md'
  'docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md|00_launch_ladder/06_ROUTING_AND_WORKSPACES.md'
  'docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md|00_launch_ladder/07_SECURITY_AND_AUTHORITY.md'
  'docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|00_launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md'
  'docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|00_launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md'
  'docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md|00_launch_ladder/10_PRODUCTIZATION_PROFILES.md'
  'docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|00_launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md'
  'docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md|00_launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md'
  'docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md|00_launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md'
  'docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md|00_launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md'
  'docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md|00_launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md'
  'docs/planning/launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md|00_launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md'
  'docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md|00_launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md'
  'docs/planning/launch_ladder/WATCH_PRIOR_ART_CANONICALIZATION.md|00_launch_ladder/WATCH_PRIOR_ART_CANONICALIZATION.md'
  'docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md|CHAT_STAY_UP_TO_DATE.md'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_fresh_navigation_profile.json|00_launch_ladder/fixtures/mission_control/fixture_fresh_navigation_profile.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_malformed_executable_profile.json|00_launch_ladder/fixtures/mission_control/fixture_malformed_executable_profile.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_packet_available_not_approved.json|00_launch_ladder/fixtures/mission_control/fixture_packet_available_not_approved.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_approval_receipt_valid.json|00_launch_ladder/fixtures/mission_control/fixture_approval_receipt_valid.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_approval_receipt_expired.json|00_launch_ladder/fixtures/mission_control/fixture_approval_receipt_expired.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_stale_evidence_route.json|00_launch_ladder/fixtures/mission_control/fixture_stale_evidence_route.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_blocked_missing_authority.json|00_launch_ladder/fixtures/mission_control/fixture_blocked_missing_authority.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_ui_claim_without_evidence.json|00_launch_ladder/fixtures/mission_control/fixture_ui_claim_without_evidence.json'
  'docs/planning/launch_ladder/fixtures/mission_control/fixture_operator_experience_golden_overview.json|00_launch_ladder/fixtures/mission_control/fixture_operator_experience_golden_overview.json'
  'docs/planning/launch_ladder/fixtures/mission_control/golden_first_screen_default.json|00_launch_ladder/fixtures/mission_control/golden_first_screen_default.json'
  'docs/planning/launch_ladder/fixtures/mission_control/golden_first_screen_local_ahead_of_origin.json|00_launch_ladder/fixtures/mission_control/golden_first_screen_local_ahead_of_origin.json'
  'docs/planning/launch_ladder/fixtures/mission_control/golden_first_screen_knowledge_context_non_ingestive.json|00_launch_ladder/fixtures/mission_control/golden_first_screen_knowledge_context_non_ingestive.json'
  'docs/planning/launch_ladder/fixtures/mission_control/golden_first_screen_unknown_preserved.json|00_launch_ladder/fixtures/mission_control/golden_first_screen_unknown_preserved.json'
  'docs/planning/launch_ladder/fixtures/mission_control/malformed_first_screen_ai_command_center.json|00_launch_ladder/fixtures/mission_control/malformed_first_screen_ai_command_center.json'
  'docs/planning/launch_ladder/fixtures/mission_control/malformed_first_screen_profile_executes_work.json|00_launch_ladder/fixtures/mission_control/malformed_first_screen_profile_executes_work.json'
  'docs/planning/launch_ladder/fixtures/mission_control/malformed_first_screen_synced_after_push_failure.json|00_launch_ladder/fixtures/mission_control/malformed_first_screen_synced_after_push_failure.json'
  'docs/planning/launch_ladder/knowledge_substrate/README.md|04_knowledge_substrate/README.md'
  'docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md|04_knowledge_substrate/01_NORTH_STAR.md'
  'docs/planning/launch_ladder/knowledge_substrate/02_SQLITE_LAYER_MODEL.md|04_knowledge_substrate/02_SQLITE_LAYER_MODEL.md'
  'docs/planning/launch_ladder/knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md|04_knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md'
  'docs/planning/launch_ladder/knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md|04_knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md'
  'docs/planning/launch_ladder/knowledge_substrate/05_FIXTURE_PLAN.md|04_knowledge_substrate/05_FIXTURE_PLAN.md'
  'docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md|04_knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md'
  'docs/planning/launch_ladder/knowledge_substrate/INDEX.md|04_knowledge_substrate/INDEX.md'
  'docs/planning/launch_ladder/operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md|01_operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md'
  'docs/planning/launch_ladder/operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md|01_operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md'
  'docs/planning/launch_ladder/operator_harness_research/HUMAN_OPERATOR_UX_PATTERNS.md|01_operator_harness_research/HUMAN_OPERATOR_UX_PATTERNS.md'
  'docs/planning/launch_ladder/operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md|01_operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md'
  'docs/planning/launch_ladder/operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md|01_operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/CROSS_PLATFORM_ARCHITECTURE.md|01_operator_harness_research/CROSS_PLATFORM_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md|01_operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md'
  'docs/planning/launch_ladder/operator_harness_research/PARALLEL_WORK_ORCHESTRATION.md|01_operator_harness_research/PARALLEL_WORK_ORCHESTRATION.md'
  'docs/planning/launch_ladder/operator_harness_research/PRODUCTIZATION_NOTES.md|01_operator_harness_research/PRODUCTIZATION_NOTES.md'
  'docs/planning/launch_ladder/operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md|01_operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/FEYNMAN_RESEARCH_INDEX.md|01_operator_harness_research/FEYNMAN_RESEARCH_INDEX.md'
  'docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md|02_planning_context/OPENCLAW_MODULAR_READINESS_LEDGER.md'
  'docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md|02_planning_context/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md'
  'docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md|03_hermes_advisory/HERMES_ADVISORY_PACKET_CONTRACT.md'
  'docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md|03_hermes_advisory/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md'
  'hermes_advisory_packet.py|03_hermes_advisory/hermes_advisory_packet.py'
  'tests/test_hermes_advisory_packet_contract.py|03_hermes_advisory/test_hermes_advisory_packet_contract.py'
  'tests/test_hermes_launch_ladder_review_packet.py|03_hermes_advisory/test_hermes_launch_ladder_review_packet.py'
  'tests/fixtures/hermes_launch_ladder_review_packet.json|03_hermes_advisory/hermes_launch_ladder_review_packet.json'
  'tests/fixtures/hermes_launch_ladder_review_expected_memo_shape.json|03_hermes_advisory/hermes_launch_ladder_review_expected_memo_shape.json'
  'docs/testing/VALIDATION_MAP.md|05_static_validation/VALIDATION_MAP.md'
  'launch_ladder_contract_check.py|05_static_validation/launch_ladder_contract_check.py'
  'tests/test_launch_ladder_static_contract.py|05_static_validation/test_launch_ladder_static_contract.py'
  'mac_eyes/Launchers/sync_operator_harness_to_mac.sh|helpers/sync_operator_harness_to_mac.sh'
  'mac_eyes/Launchers/refresh_operator_harness_ingest.sh|helpers/refresh_operator_harness_ingest.sh'
)

FORBIDDEN_PATTERNS=(
  '.chief.env'
  '.google-secrets/'
  'LegalPrivate'
  'vault'
  'logs/'
  'gmail'
  'Gmail'
  'systemd/user/'
  '.service'
  '_token.json'
  '_credentials.json'
)

validate_entry() {
  local source_rel="$1"
  local dest_rel="$2"
  local pattern

  case "$source_rel" in
    /*|../*|*/../*) printf 'ERROR: unsafe source path: %s\n' "$source_rel" >&2; return 1 ;;
  esac

  case "$dest_rel" in
    /*|../*|*/../*) printf 'ERROR: unsafe mirror path: %s\n' "$dest_rel" >&2; return 1 ;;
  esac

  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if [[ "$source_rel" == *"$pattern"* || "$dest_rel" == *"$pattern"* ]]; then
      printf 'ERROR: forbidden surface in manifest: %s -> %s\n' "$source_rel" "$dest_rel" >&2
      return 1
    fi
  done
}

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

SOURCE_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
GENERATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

printf 'operator-harness-sync: mode=%s\n' "$mode"
printf 'operator-harness-sync: source=%s\n' "$REPO_ROOT"
printf 'operator-harness-sync: source_commit=%s\n' "$SOURCE_COMMIT"
printf 'operator-harness-sync: generated_at=%s\n' "$GENERATED_AT"
printf 'operator-harness-sync: destination=%s:%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL"
printf 'operator-harness-sync: delta_bridge=%s:%s/%s adjacent_to_ingest=true counted_in_24=false\n' "$SSH_HOST" "~/$MAC_MIRROR_REL" "$DELTA_BRIDGE_NAME"
printf 'operator-harness-sync: manifest_entries=%s\n' "${#MANIFEST[@]}"

missing=0
for entry in "${MANIFEST[@]}"; do
  IFS='|' read -r source_rel dest_rel <<< "$entry"
  validate_entry "$source_rel" "$dest_rel" || exit 1

  source_path="$REPO_ROOT/$source_rel"
  if [[ ! -f "$source_path" ]]; then
    printf 'ERROR: required source missing: %s\n' "$source_rel" >&2
    missing=$((missing + 1))
  fi
done

if (( missing > 0 )); then
  printf 'operator-harness-sync: FAILED missing=%s\n' "$missing" >&2
  exit 1
fi

if [[ "$mode" == "dry-run" ]]; then
  for entry in "${MANIFEST[@]}"; do
    IFS='|' read -r source_rel dest_rel <<< "$entry"
    printf 'would copy: %s -> %s:%s/%s\n' "$source_rel" "$SSH_HOST" "~/$MAC_MIRROR_REL" "$dest_rel"
  done
  printf 'would write metadata: .operator_harness_source_repo_path .operator_harness_source_commit .operator_harness_generated_at\n'
  printf 'operator-harness-sync: dry_run_entries=%s missing=0\n' "${#MANIFEST[@]}"
  exit 0
fi

command -v ssh >/dev/null 2>&1 || { echo 'ERROR: ssh is required' >&2; exit 127; }
command -v rsync >/dev/null 2>&1 || { echo 'ERROR: rsync is required' >&2; exit 127; }

copied=0
verified=0

prepare_remote_destination() {
  local dest_rel="$1"
  local dest_dir

  if [[ "$dest_rel" == */* ]]; then
    dest_dir="${dest_rel%/*}"
    ssh "$SSH_HOST" "mkdir -p \"\$HOME/$MAC_MIRROR_REL/$dest_dir\""
  else
    ssh "$SSH_HOST" "mkdir -p \"\$HOME/$MAC_MIRROR_REL\""
  fi

  ssh "$SSH_HOST" 'bash -s --' "$MAC_MIRROR_REL" "$dest_rel" "$DELTA_BRIDGE_NAME" <<'EOF'
set -euo pipefail
mirror_rel="$1"
dest_rel="$2"
delta_bridge_name="$3"
target="$HOME/$mirror_rel/$dest_rel"

if [[ -d "$target" ]]; then
  nested="$target/${dest_rel##*/}"
  entry_count="$(find "$target" -maxdepth 1 -mindepth 1 | wc -l | tr -d '[:space:]')"

  if [[ "$dest_rel" == "$delta_bridge_name" && -f "$nested" && "$entry_count" == "1" ]]; then
    tmp="$target.repaired.$$"
    mv "$nested" "$tmp"
    rmdir "$target"
    mv "$tmp" "$target"
  else
    printf 'ERROR: mirror destination is a directory where a file is expected: %s\n' "$dest_rel" >&2
    exit 1
  fi
fi
EOF
}

ssh "$SSH_HOST" "mkdir -p \"\$HOME/$MAC_MIRROR_REL\""

for entry in "${MANIFEST[@]}"; do
  IFS='|' read -r source_rel dest_rel <<< "$entry"
  source_path="$REPO_ROOT/$source_rel"

  prepare_remote_destination "$dest_rel"
  rsync -az --timeout=10 "$source_path" "$SSH_HOST:$MAC_MIRROR_REL/$dest_rel"
  ssh "$SSH_HOST" "test -f \"\$HOME/$MAC_MIRROR_REL/$dest_rel\""
  copied=$((copied + 1))
  verified=$((verified + 1))
done

ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/.operator_harness_source_repo_path\"" <<< "$REPO_ROOT"
ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/.operator_harness_source_commit\"" <<< "$SOURCE_COMMIT"
ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/.operator_harness_generated_at\"" <<< "$GENERATED_AT"

printf 'operator-harness-sync: copied=%s verified=%s missing=0\n' "$copied" "$verified"
