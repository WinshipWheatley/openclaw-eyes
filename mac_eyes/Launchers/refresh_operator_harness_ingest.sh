#!/usr/bin/env bash
set -euo pipefail

# Rebuild ChatGPT Project ingest folders from the Mac Operator Harness mirror.
# The ingest folders are curated copies only; the PC/WSL repo remains canonical.

SSH_HOST="${SSH_HOST:-mac}"
REPO_ROOT="${REPO_ROOT:-/home/openclaw}"
MAC_MIRROR_REL="${MAC_MIRROR_REL:-OpenClaw_Watch/operator_harness_readiness}"
INGEST_DIR_NAME="CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS"
DELTA_BRIDGE_NAME="CHAT_STAY_UP_TO_DATE.md"

FOLDER_1="01_CURRENT_PRODUCT_SPEC"
FOLDER_2="02_MAC_IOS_APP_BUILD"
FOLDER_3="03_MAC_APP_KNOWLEDGE_SUBSTRATE"
FOLDER_4="04_BACKEND_DATA_CONTRACT_READINESS"
CONTENT_FILES_PER_FOLDER=23
EXPECTED_FILES_PER_FOLDER=24

usage() {
  cat <<'EOF'
Usage:
  refresh_operator_harness_ingest.sh            # rebuild Mac ingest folders
  refresh_operator_harness_ingest.sh --dry-run  # local folder/count design only
  refresh_operator_harness_ingest.sh --list     # print folder source manifests

Rebuilds exactly four ChatGPT Project ingest upload folders from files already
present in ~/OpenClaw_Watch/operator_harness_readiness on the Mac.
It deletes/recreates only those three upload folders and writes one
README_DO_NOT_UPLOAD.md outside them. Each numbered upload folder is curated
to 24 files total: 23 content files plus MANIFEST.md.
The adjacent CHAT_STAY_UP_TO_DATE.md bridge stays at the readiness root, outside
the numbered folders, and is not counted in the 24 files.

No secrets, runtime vaults, logs, generated artifacts, installed units,
provider/model calls, Gmail bodies, LegalPrivate, or broad repo folders are
included.
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

FOLDER_1_PURPOSE="Current Operator Harness product/spec review: Launch Ladder model, authority, readiness, route compression, evidence/freshness, productization posture, and source-set rules."
FOLDER_2_PURPOSE="Mac/iOS app build planning: read-only app brief, cross-platform architecture, UX, security, evidence/freshness, routing, and v1 architecture constraints."
FOLDER_4_PURPOSE="Backend data-contract readiness planning: records, contract boundaries, synthetic fixture intent, and validation expectations before actual backend/schema/SQLite work starts."
FOLDER_3_PURPOSE="Combined Mac desktop Mission Control and Compiled Knowledge Substrate planning: read-only app fixture contracts, first-screen composition, taste/atmosphere, quiet feedback, SQLite-backed local memory doctrine, evidence/freshness, authority, validation, and no-implementation/no-ingestion boundaries."

FOLDER_1_FILES=(
  'docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md|00_launch_ladder/LAUNCH_LADDER_INDEX.md|LAUNCH_LADDER_INDEX.md'
  'docs/planning/launch_ladder/00_NORTH_STAR.md|00_launch_ladder/00_NORTH_STAR.md|00_NORTH_STAR.md'
  'docs/planning/launch_ladder/01_RUNTIME_MAP.md|00_launch_ladder/01_RUNTIME_MAP.md|01_RUNTIME_MAP.md'
  'docs/planning/launch_ladder/02_CAPABILITY_AUTHORITY_AND_READINESS.md|00_launch_ladder/02_CAPABILITY_AUTHORITY_AND_READINESS.md|02_CAPABILITY_AUTHORITY_AND_READINESS.md'
  'docs/planning/launch_ladder/03_GOAL_HORIZONS.md|00_launch_ladder/03_GOAL_HORIZONS.md|03_GOAL_HORIZONS.md'
  'docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md|00_launch_ladder/04_LAUNCH_LADDER_MODEL.md|04_LAUNCH_LADDER_MODEL.md'
  'docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|00_launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|05_EVIDENCE_AND_FRESHNESS.md'
  'docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md|00_launch_ladder/06_ROUTING_AND_WORKSPACES.md|06_ROUTING_AND_WORKSPACES.md'
  'docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md|00_launch_ladder/07_SECURITY_AND_AUTHORITY.md|07_SECURITY_AND_AUTHORITY.md'
  'docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|00_launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|08_SOURCE_SET_REFRESH_SYSTEM.md'
  'docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md|00_launch_ladder/10_PRODUCTIZATION_PROFILES.md|10_PRODUCTIZATION_PROFILES.md'
  'docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|00_launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|11_NEXT_IMPLEMENTATION_SEQUENCE.md'
  'docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md|02_planning_context/OPENCLAW_MODULAR_READINESS_LEDGER.md|OPENCLAW_MODULAR_READINESS_LEDGER.md'
  'docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md|02_planning_context/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md|OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md'
  'docs/planning/launch_ladder/operator_harness_research/FEYNMAN_RESEARCH_INDEX.md|01_operator_harness_research/FEYNMAN_RESEARCH_INDEX.md|FEYNMAN_RESEARCH_INDEX.md'
  'docs/planning/launch_ladder/operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md|01_operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md|OPERATOR_HARNESS_FIRST_PRINCIPLES.md'
  'docs/planning/launch_ladder/operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md|01_operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md|LAUNCH_LADDER_BEST_PRACTICES.md'
  'docs/planning/launch_ladder/operator_harness_research/PRODUCTIZATION_NOTES.md|01_operator_harness_research/PRODUCTIZATION_NOTES.md|PRODUCTIZATION_NOTES.md'
  'docs/planning/launch_ladder/operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md|01_operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md|RECOMMENDED_V1_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md|01_operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md|SECURITY_AND_APPROVAL_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md|01_operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md|EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md'
  'docs/planning/launch_ladder/operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md|01_operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md|MULTI_DEPLOYMENT_CONTROL_PLANE.md'
  'docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md|03_hermes_advisory/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md|HERMES_FIRST_ADVISORY_TRIAL_PLAN.md'
)

FOLDER_2_FILES=(
  'docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|00_launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|09_MAC_IOS_APP_BUILD_BRIEF.md'
  'docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md|00_launch_ladder/06_ROUTING_AND_WORKSPACES.md|06_ROUTING_AND_WORKSPACES.md'
  'docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|00_launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|08_SOURCE_SET_REFRESH_SYSTEM.md'
  'docs/planning/launch_ladder/operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md|01_operator_harness_research/RECOMMENDED_V1_ARCHITECTURE.md|RECOMMENDED_V1_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/CROSS_PLATFORM_ARCHITECTURE.md|01_operator_harness_research/CROSS_PLATFORM_ARCHITECTURE.md|CROSS_PLATFORM_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/HUMAN_OPERATOR_UX_PATTERNS.md|01_operator_harness_research/HUMAN_OPERATOR_UX_PATTERNS.md|HUMAN_OPERATOR_UX_PATTERNS.md'
  'docs/planning/launch_ladder/operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md|01_operator_harness_research/SECURITY_AND_APPROVAL_ARCHITECTURE.md|SECURITY_AND_APPROVAL_ARCHITECTURE.md'
  'docs/planning/launch_ladder/operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md|01_operator_harness_research/EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md|EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md'
  'docs/planning/launch_ladder/operator_harness_research/PRODUCTIZATION_NOTES.md|01_operator_harness_research/PRODUCTIZATION_NOTES.md|PRODUCTIZATION_NOTES.md'
  'docs/planning/launch_ladder/operator_harness_research/FEYNMAN_RESEARCH_INDEX.md|01_operator_harness_research/FEYNMAN_RESEARCH_INDEX.md|FEYNMAN_RESEARCH_INDEX.md'
  'docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md|00_launch_ladder/LAUNCH_LADDER_INDEX.md|LAUNCH_LADDER_INDEX.md'
  'docs/planning/launch_ladder/00_NORTH_STAR.md|00_launch_ladder/00_NORTH_STAR.md|00_NORTH_STAR.md'
  'docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md|00_launch_ladder/04_LAUNCH_LADDER_MODEL.md|04_LAUNCH_LADDER_MODEL.md'
  'docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|00_launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|05_EVIDENCE_AND_FRESHNESS.md'
  'docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md|00_launch_ladder/07_SECURITY_AND_AUTHORITY.md|07_SECURITY_AND_AUTHORITY.md'
  'docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md|00_launch_ladder/10_PRODUCTIZATION_PROFILES.md|10_PRODUCTIZATION_PROFILES.md'
  'docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|00_launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|11_NEXT_IMPLEMENTATION_SEQUENCE.md'
  'docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md|02_planning_context/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md|OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md'
  'docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md|02_planning_context/OPENCLAW_MODULAR_READINESS_LEDGER.md|OPENCLAW_MODULAR_READINESS_LEDGER.md'
  'docs/planning/launch_ladder/operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md|01_operator_harness_research/OPERATOR_HARNESS_FIRST_PRINCIPLES.md|OPERATOR_HARNESS_FIRST_PRINCIPLES.md'
  'docs/planning/launch_ladder/operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md|01_operator_harness_research/LAUNCH_LADDER_BEST_PRACTICES.md|LAUNCH_LADDER_BEST_PRACTICES.md'
  'docs/planning/launch_ladder/operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md|01_operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md|MULTI_DEPLOYMENT_CONTROL_PLANE.md'
  'docs/planning/launch_ladder/operator_harness_research/PARALLEL_WORK_ORCHESTRATION.md|01_operator_harness_research/PARALLEL_WORK_ORCHESTRATION.md|PARALLEL_WORK_ORCHESTRATION.md'
)

FOLDER_3_FILES=(
  'docs/planning/launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md|00_launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md|16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md'
  'docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|00_launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|09_MAC_IOS_APP_BUILD_BRIEF.md'
  'docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md|00_launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md|12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md'
  'docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md|00_launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md|13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md'
  'docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md|00_launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md|14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md'
  'docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md|00_launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md|15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md'
  'docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md|00_launch_ladder/04_LAUNCH_LADDER_MODEL.md|04_LAUNCH_LADDER_MODEL.md'
  'docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|00_launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|05_EVIDENCE_AND_FRESHNESS.md'
  'docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md|00_launch_ladder/06_ROUTING_AND_WORKSPACES.md|06_ROUTING_AND_WORKSPACES.md'
  'docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md|00_launch_ladder/07_SECURITY_AND_AUTHORITY.md|07_SECURITY_AND_AUTHORITY.md'
  'docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|00_launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|08_SOURCE_SET_REFRESH_SYSTEM.md'
  'docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|00_launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|11_NEXT_IMPLEMENTATION_SEQUENCE.md'
  'docs/planning/launch_ladder/knowledge_substrate/README.md|04_knowledge_substrate/README.md|KNOWLEDGE_SUBSTRATE_README.md'
  'docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md|04_knowledge_substrate/01_NORTH_STAR.md|KNOWLEDGE_SUBSTRATE_01_NORTH_STAR.md'
  'docs/planning/launch_ladder/knowledge_substrate/02_SQLITE_LAYER_MODEL.md|04_knowledge_substrate/02_SQLITE_LAYER_MODEL.md|KNOWLEDGE_SUBSTRATE_02_SQLITE_LAYER_MODEL.md'
  'docs/planning/launch_ladder/knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md|04_knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md|KNOWLEDGE_SUBSTRATE_03_SAFETY_AND_SENSITIVITY_LEVELS.md'
  'docs/planning/launch_ladder/knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md|04_knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md|KNOWLEDGE_SUBSTRATE_04_APP_CARDS_AND_UI_STATES.md'
  'docs/planning/launch_ladder/knowledge_substrate/05_FIXTURE_PLAN.md|04_knowledge_substrate/05_FIXTURE_PLAN.md|KNOWLEDGE_SUBSTRATE_05_FIXTURE_PLAN.md'
  'docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md|04_knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md|KNOWLEDGE_SUBSTRATE_06_STATIC_VALIDATION_EXPECTATIONS.md'
  'docs/planning/launch_ladder/knowledge_substrate/INDEX.md|04_knowledge_substrate/INDEX.md|KNOWLEDGE_SUBSTRATE_INDEX.md'
  'docs/testing/VALIDATION_MAP.md|05_static_validation/VALIDATION_MAP.md|VALIDATION_MAP.md'
  'launch_ladder_contract_check.py|05_static_validation/launch_ladder_contract_check.py|launch_ladder_contract_check.py'
  'tests/test_launch_ladder_static_contract.py|05_static_validation/test_launch_ladder_static_contract.py|test_launch_ladder_static_contract.py'
)

print_folder_design() {
  local folder="$1"
  local purpose="$2"
  shift 2
  local entry source_rel mirror_rel dest_name

  printf '%s: purpose=%s\n' "$folder" "$purpose"
  printf '%s: content_files=%s manifest_files=1 total_files=%s\n' "$folder" "$#" "$EXPECTED_FILES_PER_FOLDER"
  for entry in "$@"; do
    IFS='|' read -r source_rel mirror_rel dest_name <<< "$entry"
    printf '%s: %s <- %s (%s)\n' "$folder" "$dest_name" "$source_rel" "$mirror_rel"
  done
}

validate_folder_design() {
  local folder="$1"
  shift
  if [[ "$#" != "$CONTENT_FILES_PER_FOLDER" ]]; then
    printf 'ERROR: %s expected %s content files, found %s\n' "$folder" "$CONTENT_FILES_PER_FOLDER" "$#" >&2
    exit 1
  fi
}

validate_folder_design "$FOLDER_1" "${FOLDER_1_FILES[@]}"
validate_folder_design "$FOLDER_2" "${FOLDER_2_FILES[@]}"
validate_folder_design "$FOLDER_3" "${FOLDER_3_FILES[@]}"

FOLDER_4_FILES=(
  'docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md|00_launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md|17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md'
  'docs/planning/launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md|00_launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md|16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md'
  'docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|00_launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md|11_NEXT_IMPLEMENTATION_SEQUENCE.md'
  'docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md|00_launch_ladder/04_LAUNCH_LADDER_MODEL.md|04_LAUNCH_LADDER_MODEL.md'
  'docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|00_launch_ladder/05_EVIDENCE_AND_FRESHNESS.md|05_EVIDENCE_AND_FRESHNESS.md'
  'docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md|00_launch_ladder/06_ROUTING_AND_WORKSPACES.md|06_ROUTING_AND_WORKSPACES.md'
  'docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md|00_launch_ladder/07_SECURITY_AND_AUTHORITY.md|07_SECURITY_AND_AUTHORITY.md'
  'docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|00_launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md|08_SOURCE_SET_REFRESH_SYSTEM.md'
  'docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|00_launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md|09_MAC_IOS_APP_BUILD_BRIEF.md'
  'docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md|00_launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md|12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md'
  'docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md|00_launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md|13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md'
  'docs/planning/launch_ladder/knowledge_substrate/README.md|04_knowledge_substrate/README.md|KNOWLEDGE_SUBSTRATE_README.md'
  'docs/planning/launch_ladder/knowledge_substrate/INDEX.md|04_knowledge_substrate/INDEX.md|KNOWLEDGE_SUBSTRATE_INDEX.md'
  'docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md|04_knowledge_substrate/01_NORTH_STAR.md|KNOWLEDGE_SUBSTRATE_01_NORTH_STAR.md'
  'docs/planning/launch_ladder/knowledge_substrate/02_SQLITE_LAYER_MODEL.md|04_knowledge_substrate/02_SQLITE_LAYER_MODEL.md|KNOWLEDGE_SUBSTRATE_02_SQLITE_LAYER_MODEL.md'
  'docs/planning/launch_ladder/knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md|04_knowledge_substrate/03_SAFETY_AND_SENSITIVITY_LEVELS.md|KNOWLEDGE_SUBSTRATE_03_SAFETY_AND_SENSITIVITY_LEVELS.md'
  'docs/planning/launch_ladder/knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md|04_knowledge_substrate/04_APP_CARDS_AND_UI_STATES.md|KNOWLEDGE_SUBSTRATE_04_APP_CARDS_AND_UI_STATES.md'
  'docs/planning/launch_ladder/knowledge_substrate/05_FIXTURE_PLAN.md|04_knowledge_substrate/05_FIXTURE_PLAN.md|KNOWLEDGE_SUBSTRATE_05_FIXTURE_PLAN.md'
  'docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md|04_knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md|KNOWLEDGE_SUBSTRATE_06_STATIC_VALIDATION_EXPECTATIONS.md'
  'docs/testing/VALIDATION_MAP.md|05_static_validation/VALIDATION_MAP.md|VALIDATION_MAP.md'
  'launch_ladder_contract_check.py|05_static_validation/launch_ladder_contract_check.py|launch_ladder_contract_check.py'
  'tests/test_launch_ladder_static_contract.py|05_static_validation/test_launch_ladder_static_contract.py|test_launch_ladder_static_contract.py'
  'docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md|02_planning_context/OPENCLAW_MODULAR_READINESS_LEDGER.md|OPENCLAW_MODULAR_READINESS_LEDGER.md'
)

validate_folder_design "$FOLDER_4" "${FOLDER_4_FILES[@]}"

if [[ "$mode" == "list" || "$mode" == "dry-run" ]]; then
  printf 'operator-harness-ingest: mode=%s\n' "$mode"
  if [[ "$mode" == "dry-run" ]]; then
    DRY_RUN_SOURCE_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf 'UNKNOWN')"
    printf 'operator-harness-ingest: source_commit=%s dry_run_basis=local_HEAD apply_basis=mirror_metadata_from_latest_sync\n' "$DRY_RUN_SOURCE_COMMIT"
  fi
  printf 'operator-harness-ingest: mirror=%s:%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL"
  printf 'operator-harness-ingest: ingest=%s:%s/%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL" "$INGEST_DIR_NAME"
  printf 'operator-harness-ingest: delta_bridge=%s:%s/%s adjacent_to_ingest=true counted_in_24=false\n' "$SSH_HOST" "~/$MAC_MIRROR_REL" "$DELTA_BRIDGE_NAME"
  printf 'operator-harness-ingest: bridge_check=apply_requires_regular_file_at_readiness_root\n'
  print_folder_design "$FOLDER_1" "$FOLDER_1_PURPOSE" "${FOLDER_1_FILES[@]}"
  print_folder_design "$FOLDER_2" "$FOLDER_2_PURPOSE" "${FOLDER_2_FILES[@]}"
  print_folder_design "$FOLDER_3" "$FOLDER_3_PURPOSE" "${FOLDER_3_FILES[@]}"
  print_folder_design "$FOLDER_4" "$FOLDER_4_PURPOSE" "${FOLDER_4_FILES[@]}"
  printf 'operator-harness-ingest: dry_run_mutates_mac=false\n'
  exit 0
fi

command -v ssh >/dev/null 2>&1 || { echo 'ERROR: ssh is required' >&2; exit 127; }

validate_mirror_ready() {
  ssh "$SSH_HOST" "set -euo pipefail
root=\"\$HOME/$MAC_MIRROR_REL\"
bridge=\"\$root/$DELTA_BRIDGE_NAME\"
test -d \"\$root\"
if [ -d \"\$bridge\" ]; then
  echo 'ERROR: adjacent delta bridge path is a directory, not a file. Re-run the fixed sync_operator_harness_to_mac.sh to repair the generated mirror bridge.' >&2
  exit 1
fi
test -f \"\$bridge\" || { echo 'ERROR: missing adjacent delta bridge at readiness root' >&2; exit 1; }
test -f \"\$root/.operator_harness_source_repo_path\" || { echo 'ERROR: missing Operator Harness mirror metadata: .operator_harness_source_repo_path' >&2; exit 1; }
test -f \"\$root/.operator_harness_source_commit\" || { echo 'ERROR: missing Operator Harness mirror metadata: .operator_harness_source_commit' >&2; exit 1; }
test -f \"\$root/.operator_harness_generated_at\" || { echo 'ERROR: missing Operator Harness mirror metadata: .operator_harness_generated_at' >&2; exit 1; }
"
}

validate_mirror_ready
SOURCE_REPO_PATH="$(ssh "$SSH_HOST" "cat \"\$HOME/$MAC_MIRROR_REL/.operator_harness_source_repo_path\"")"
SOURCE_COMMIT="$(ssh "$SSH_HOST" "cat \"\$HOME/$MAC_MIRROR_REL/.operator_harness_source_commit\"")"
SOURCE_SYNCED_AT="$(ssh "$SSH_HOST" "cat \"\$HOME/$MAC_MIRROR_REL/.operator_harness_generated_at\"")"
GENERATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

prepare_ingest() {
  ssh "$SSH_HOST" "set -euo pipefail
root=\"\$HOME/$MAC_MIRROR_REL\"
ingest=\"\$root/$INGEST_DIR_NAME\"
case \"\$ingest\" in
  \"\$root\"/*) ;;
  *) echo 'ERROR: unsafe ingest path' >&2; exit 1 ;;
esac
test -d \"\$root\"
test -f \"\$root/$DELTA_BRIDGE_NAME\" || { echo 'ERROR: missing adjacent delta bridge at readiness root' >&2; exit 1; }
mkdir -p \"\$ingest\"
rm -rf \"\$ingest/$FOLDER_1\" \"\$ingest/$FOLDER_2\" \"\$ingest/$FOLDER_3\" \"\$ingest/$FOLDER_4\"
mkdir -p \"\$ingest/$FOLDER_1\" \"\$ingest/$FOLDER_2\" \"\$ingest/$FOLDER_3\" \"\$ingest/$FOLDER_4\"
"

  ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/README_DO_NOT_UPLOAD.md\"" <<EOF
# README_DO_NOT_UPLOAD

These folders are curated ChatGPT Project upload sets for OpenClaw Operator Harness readiness.

- PC/WSL \`$SOURCE_REPO_PATH\` remains the source of truth.
- Source commit mirrored: \`$SOURCE_COMMIT\`.
- Mirror generated at: \`$SOURCE_SYNCED_AT\`.
- Ingest generated at: \`$GENERATED_AT\`.
- This Mac mirror and the ingest folders are readable derived copies only.
- Upload one numbered workflow folder at a time, in order.
- Each numbered workflow folder intentionally contains exactly 24 files total: 23 curated content files plus \`MANIFEST.md\`.
- \`$DELTA_BRIDGE_NAME\` is adjacent to this ingest root. Upload it alongside the active numbered folder only when a bridge-only delta is enough.
- \`$DELTA_BRIDGE_NAME\` is not counted inside the numbered folder's 24 files.
- Do not upload this README as part of the numbered workflow batches.
- Do not treat copied files as permission to run providers, services, Gmail, Legal matter workflows, Hermes runtime expansion, or runtime mutation.
EOF
}

copy_to_workflow() {
  local mirror_rel="$1"
  local folder="$2"
  local dest_name="$3"

  ssh "$SSH_HOST" "set -euo pipefail
source_path=\"\$HOME/$MAC_MIRROR_REL/$mirror_rel\"
dest_path=\"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/$folder/$dest_name\"
test -f \"\$source_path\"
cp \"\$source_path\" \"\$dest_path\"
"
}

write_manifest() {
  local folder="$1"
  local purpose="$2"
  shift 2
  local entry source_rel mirror_rel dest_name

  {
    cat <<EOF
# MANIFEST

## Source

- Source repo path: \`$SOURCE_REPO_PATH\`
- Source commit hash: \`$SOURCE_COMMIT\`
- Mirror generated timestamp: \`$SOURCE_SYNCED_AT\`
- Ingest generated timestamp: \`$GENERATED_AT\`
- Folder purpose: $purpose
- File count assertion: 23 content files + \`MANIFEST.md\` = 24 total upload files

## Included Files

EOF

    for entry in "$@"; do
      IFS='|' read -r source_rel mirror_rel dest_name <<< "$entry"
      printf -- '- `%s` from `%s/%s` via mirror `%s`\n' "$dest_name" "$SOURCE_REPO_PATH" "$source_rel" "$mirror_rel"
    done

    cat <<'EOF'

## Omitted And Withheld Surfaces

- LegalPrivate and private legal matter data.
- Vaults, secrets, tokens, passphrases, credential files, SSH keys, and keychain contents.
- Logs, Gmail bodies, inbox/private message bodies, and private runtime state.
- Installed units, service runtime state, systemd mutation paths, and live service control.
- Provider/model calls, billing actions, external sends, and Hermes runtime expansion.
- Broad repository folders and generated artifacts outside this derived ingest root.

## Stale Conditions

- Any included source file changes after the listed source commit.
- The source commit hash differs from current repo HEAD without a refreshed manifest.
- The mirror is regenerated after this ingest folder is created.
- The folder contains anything other than 24 files total.
- Upload rules, withheld-surface policy, Launch Ladder authority, or source-set rules change.
- A task needs private data, logs, vaults, secrets, installed units, runtime state, provider/model calls, or service mutation.

## Upload Instructions

1. Upload this numbered folder as one ChatGPT Project batch.
2. Upload all 24 files in this folder, including this `MANIFEST.md`.
3. Do not upload the parent `README_DO_NOT_UPLOAD.md`.
4. If the adjacent `../CHAT_STAY_UP_TO_DATE.md` bridge is provided, upload it alongside this folder only as a delta note; it is not part of the 24-file count.
5. Treat model output as advisory until promoted back into the canonical repo.
6. Refresh the mirror and ingest folder if any stale condition is true.

## Derived/Non-Canonical Warning

This generated ingest folder is derived and non-canonical. It is a bounded source-set refresh surface for operator review. It does not authorize runtime mutation, provider/model calls, secret handling, private-data inspection, service control, or autonomous execution.
EOF
  } | ssh "$SSH_HOST" "cat > \"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/$folder/MANIFEST.md\""
}

populate_folder() {
  local folder="$1"
  local purpose="$2"
  shift 2
  local copied=0
  local entry source_rel mirror_rel dest_name count

  for entry in "$@"; do
    IFS='|' read -r source_rel mirror_rel dest_name <<< "$entry"
    copy_to_workflow "$mirror_rel" "$folder" "$dest_name"
    copied=$((copied + 1))
  done

  write_manifest "$folder" "$purpose" "$@"

  count=$(ssh "$SSH_HOST" "find \"\$HOME/$MAC_MIRROR_REL/$INGEST_DIR_NAME/$folder\" -maxdepth 1 -type f | wc -l")
  count="${count//[[:space:]]/}"
  printf '%s: content_copied=%s count=%s expected=%s\n' "$folder" "$copied" "$count" "$EXPECTED_FILES_PER_FOLDER"

  if [[ "$copied" != "$CONTENT_FILES_PER_FOLDER" || "$count" != "$EXPECTED_FILES_PER_FOLDER" ]]; then
    printf 'ERROR: %s expected %s content files and %s total files, copied %s, found %s\n' "$folder" "$CONTENT_FILES_PER_FOLDER" "$EXPECTED_FILES_PER_FOLDER" "$copied" "$count" >&2
    exit 1
  fi
}

printf 'operator-harness-ingest: mirror=%s:%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL"
printf 'operator-harness-ingest: ingest=%s:%s/%s\n' "$SSH_HOST" "~/$MAC_MIRROR_REL" "$INGEST_DIR_NAME"
printf 'operator-harness-ingest: source_commit=%s\n' "$SOURCE_COMMIT"
printf 'operator-harness-ingest: generated_at=%s\n' "$GENERATED_AT"

prepare_ingest
populate_folder "$FOLDER_1" "$FOLDER_1_PURPOSE" "${FOLDER_1_FILES[@]}"
populate_folder "$FOLDER_2" "$FOLDER_2_PURPOSE" "${FOLDER_2_FILES[@]}"
populate_folder "$FOLDER_3" "$FOLDER_3_PURPOSE" "${FOLDER_3_FILES[@]}"
populate_folder "$FOLDER_4" "$FOLDER_4_PURPOSE" "${FOLDER_4_FILES[@]}"

printf 'operator-harness-ingest: refreshed 4 folders under %s/%s\n' "~/$MAC_MIRROR_REL" "$INGEST_DIR_NAME"
