"""OpenClaw Work Terrain Gap Detector v0.

This read-model defines metadata-only gap records for OpenClaw work terrain.
It compares terrain, relationships, classifications, read-model visibility,
stable-map visibility, receipts, tests, and built-artifact claims as candidate
gap shapes only. It does not inspect raw bodies, run semantic AI review, mutate
files, refresh the stable map, implement missing work, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "openclaw_work_terrain_gap_detector_v0"
READ_MODEL_ID = "openclaw_work_terrain_gap_detector"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

QUERY_CONTRACT_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_query_contract.json"
RELATIONSHIP_INDEX_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_relationship_index.json"
CLASSIFICATION_CANDIDATE_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_classification_candidate.json"

GAP_TYPES = (
    "SOURCE_NOTE_DESCRIBES_BUILT_ARTIFACT",
    "BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
    "MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION",
    "STABLE_MAP_REPRESENTATION_MISSING",
    "SQLITE_RECORD_MISSING",
    "READ_MODEL_MISSING",
    "DUPLICATE_CONCEPT",
    "OVERLAPPING_CONCEPT",
    "STALE_DOC_STILL_VISIBLE",
    "SUPERSEDED_DOC_NOT_MARKED",
    "IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE",
    "DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED",
    "PARTIALLY_BUILT",
    "BUILT_BUT_UNSAFE",
    "UNSAFE_EXECUTION_POSTURE",
    "CONCEPTUALLY_VALID_BUT_PREMATURE",
    "HISTORICAL_RESIDUE_ONLY",
    "GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE",
    "REPO_B_REFERENCE_NOT_PROMOTED",
    "MISSION_CONTROL_SURFACE_MISSING",
    "PROOF_OR_RECEIPT_MISSING",
    "TEST_VALIDATION_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

GAP_PRIORITIES = (
    "CRITICAL_SECURITY_GAP",
    "INCOMPLETE_LINEAGE",
    "OPERATOR_DECISION_NEEDED",
    "HERMES_REVIEW_NEEDED",
    "CHIEF_RECONCILIATION_NEEDED",
    "STABLE_MAP_VISIBILITY_GAP",
    "PROOF_DETAIL_ONLY",
    "MINOR_ORPHAN",
    "PARKED_OR_PREMATURE",
    "QUARANTINE_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

RECOMMENDED_RESOLUTION_TYPES = (
    "PROMOTE_TO_SOURCE_CARD_CANDIDATE",
    "PROMOTE_TO_STABLE_MAP_CANDIDATE",
    "CREATE_READ_MODEL_CANDIDATE",
    "LINK_SOURCE_TO_BUILT_ARTIFACT",
    "LINK_BUILT_ARTIFACT_TO_SOURCE",
    "ADD_TEST_OR_RECEIPT_CANDIDATE",
    "MARK_SUPERSEDED_CANDIDATE",
    "MERGE_CONCEPTS_CANDIDATE",
    "ARCHIVE_CANDIDATE",
    "HERMES_REVIEW",
    "CHIEF_RECONCILIATION",
    "OPERATOR_DECISION",
    "GUARDIAN_REVIEW",
    "SECURITY_DELTA_REVIEW",
    "KEEP_AS_PROOF_DETAIL",
    "KEEP_PARKED",
    "QUARANTINE",
    "UNKNOWN_FAIL_CLOSED",
)

BUILT_STATUSES = (
    "NOT_BUILT",
    "PARTIALLY_BUILT",
    "BUILT_UNVALIDATED",
    "BUILT_WITH_TESTS",
    "BUILT_WITH_RECEIPTS",
    "BUILT_AND_SURFACED",
    "BUILT_BUT_UNSAFE",
    "UNKNOWN_FAIL_CLOSED",
)

GAP_RECORD_FIELDS = (
    "gap_id",
    "display_name",
    "gap_type",
    "gap_priority",
    "terrain_refs",
    "relationship_refs",
    "classification_refs",
    "sqlite_refs",
    "read_model_refs",
    "stable_map_refs",
    "receipt_refs",
    "test_refs",
    "commit_refs",
    "affected_actor",
    "affected_world",
    "affected_lane",
    "current_visibility",
    "missing_visibility",
    "why_it_matters",
    "negative_filter_applied",
    "should_not_build_reason",
    "recommended_resolution_type",
    "requires_chief_reconciliation",
    "requires_hermes_review",
    "requires_operator_decision",
    "requires_guardian_review",
    "requires_security_delta",
    "action_allowed",
    "next_safe_move",
)

NEGATIVE_FILTER_FIELDS = (
    "filter_id",
    "applies_to_classifications",
    "reason",
    "effect",
    "allowed_gap_types_after_filter",
    "blocked_gap_types_after_filter",
    "next_safe_move",
)

BUILT_STATUS_VALIDATION_RULE_FIELDS = (
    "rule_id",
    "artifact_ref",
    "built_claim_source",
    "required_test_refs",
    "required_receipt_refs",
    "required_commit_refs",
    "required_generated_artifacts",
    "built_status",
    "can_claim_built",
    "missing_validation",
    "next_safe_move",
)

GAP_DETECTOR_POLICY_FIELDS = (
    "metadata_only",
    "body_ingestion_allowed",
    "semantic_review_allowed",
    "file_mutation_allowed",
    "auto_archive_allowed",
    "auto_consolidation_allowed",
    "auto_stable_map_promotion_allowed",
    "auto_implementation_allowed",
    "negative_filtering_required",
    "built_status_requires_validation",
    "operator_attention_dedup_required",
    "chief_reconciliation_role",
    "hermes_review_role",
    "guardian_review_role",
    "operator_final_authority",
)

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "body_ingestion_allowed": False,
    "semantic_review_allowed": False,
    "broad_ai_semantic_review_allowed": False,
    "broad_private_root_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "file_archive_allowed": False,
    "auto_archive_allowed": False,
    "auto_consolidation_allowed": False,
    "auto_stable_map_promotion_allowed": False,
    "auto_implementation_allowed": False,
    "stable_map_refresh_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_queue_autonomy_allowed": False,
    "c_drive_scan_or_artifact_write_allowed": False,
    "credential_account_browser_email_coupa_access_allowed": False,
    "authority_escalation_allowed": False,
}


@dataclass(frozen=True)
class WorkTerrainGapRecord:
    gap_id: str
    display_name: str
    gap_type: str
    gap_priority: str
    terrain_refs: tuple[str, ...]
    relationship_refs: tuple[str, ...]
    classification_refs: tuple[str, ...]
    sqlite_refs: tuple[str, ...]
    read_model_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    commit_refs: tuple[str, ...]
    affected_actor: str
    affected_world: str
    affected_lane: str
    current_visibility: tuple[str, ...]
    missing_visibility: tuple[str, ...]
    why_it_matters: str
    negative_filter_applied: bool
    should_not_build_reason: str
    recommended_resolution_type: str
    requires_chief_reconciliation: bool
    requires_hermes_review: bool
    requires_operator_decision: bool
    requires_guardian_review: bool
    requires_security_delta: bool
    action_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainNegativeFilter:
    filter_id: str
    applies_to_classifications: tuple[str, ...]
    reason: str
    effect: str
    allowed_gap_types_after_filter: tuple[str, ...]
    blocked_gap_types_after_filter: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainBuiltStatusValidationRule:
    rule_id: str
    artifact_ref: str
    built_claim_source: str
    required_test_refs: tuple[str, ...]
    required_receipt_refs: tuple[str, ...]
    required_commit_refs: tuple[str, ...]
    required_generated_artifacts: tuple[str, ...]
    built_status: str
    can_claim_built: bool
    missing_validation: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainGapDetectorPolicy:
    metadata_only: bool
    body_ingestion_allowed: bool
    semantic_review_allowed: bool
    file_mutation_allowed: bool
    auto_archive_allowed: bool
    auto_consolidation_allowed: bool
    auto_stable_map_promotion_allowed: bool
    auto_implementation_allowed: bool
    negative_filtering_required: bool
    built_status_requires_validation: bool
    operator_attention_dedup_required: bool
    chief_reconciliation_role: str
    hermes_review_role: str
    guardian_review_role: str
    operator_final_authority: str


@dataclass(frozen=True)
class WorkTerrainGapDetectorExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    gap_count: int
    negative_filter_count: int
    built_validation_rule_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _gap(
    gap_id: str,
    *,
    display_name: str,
    gap_type: str,
    gap_priority: str,
    terrain_refs: tuple[str, ...] = (),
    relationship_refs: tuple[str, ...] = (),
    classification_refs: tuple[str, ...] = (),
    sqlite_refs: tuple[str, ...] = (),
    read_model_refs: tuple[str, ...] = (),
    stable_map_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    test_refs: tuple[str, ...] = (),
    commit_refs: tuple[str, ...] = (),
    affected_actor: str = "UNKNOWN_FAIL_CLOSED",
    affected_world: str = "UNKNOWN_FAIL_CLOSED",
    affected_lane: str = "UNKNOWN_FAIL_CLOSED",
    current_visibility: tuple[str, ...] = (),
    missing_visibility: tuple[str, ...] = (),
    why_it_matters: str,
    negative_filter_applied: bool = False,
    should_not_build_reason: str = "Gap records are review candidates, not implementation authority.",
    recommended_resolution_type: str,
    requires_chief_reconciliation: bool = False,
    requires_hermes_review: bool = False,
    requires_operator_decision: bool = False,
    requires_guardian_review: bool = False,
    requires_security_delta: bool = False,
    next_safe_move: str,
) -> WorkTerrainGapRecord:
    return WorkTerrainGapRecord(
        gap_id=gap_id,
        display_name=display_name,
        gap_type=gap_type,
        gap_priority=gap_priority,
        terrain_refs=terrain_refs,
        relationship_refs=relationship_refs,
        classification_refs=classification_refs,
        sqlite_refs=sqlite_refs,
        read_model_refs=read_model_refs,
        stable_map_refs=stable_map_refs,
        receipt_refs=receipt_refs,
        test_refs=test_refs,
        commit_refs=commit_refs,
        affected_actor=affected_actor,
        affected_world=affected_world,
        affected_lane=affected_lane,
        current_visibility=current_visibility,
        missing_visibility=missing_visibility,
        why_it_matters=why_it_matters,
        negative_filter_applied=negative_filter_applied,
        should_not_build_reason=should_not_build_reason,
        recommended_resolution_type=recommended_resolution_type,
        requires_chief_reconciliation=requires_chief_reconciliation,
        requires_hermes_review=requires_hermes_review,
        requires_operator_decision=requires_operator_decision,
        requires_guardian_review=requires_guardian_review,
        requires_security_delta=requires_security_delta,
        action_allowed=False,
        next_safe_move=next_safe_move,
    )


def default_negative_filters() -> tuple[WorkTerrainNegativeFilter, ...]:
    return (
        WorkTerrainNegativeFilter(
            filter_id="old_prompt_filter",
            applies_to_classifications=("OLD_PROMPT",),
            reason="Old prompts may be historical, candidate doctrine, or residue; they are not current implementation authority.",
            effect="Prevent old prompts from becoming build-now implementation gaps by default.",
            allowed_gap_types_after_filter=("HISTORICAL_RESIDUE_ONLY", "SOURCE_NOTE_DESCRIBES_BUILT_ARTIFACT", "SUPERSEDED_DOC_NOT_MARKED"),
            blocked_gap_types_after_filter=("MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION", "MISSION_CONTROL_SURFACE_MISSING"),
            next_safe_move="Route to Chief/Hermes review only if a receipt, source-card candidate, or stable-map lineage need exists.",
        ),
        WorkTerrainNegativeFilter(
            filter_id="generated_artifact_filter",
            applies_to_classifications=("GENERATED_ARTIFACT",),
            reason="Generated read-models and operator digests are proof/detail, not human-authored doctrine.",
            effect="Prevent generated files from being treated as doctrine or source notes.",
            allowed_gap_types_after_filter=("GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE", "PROOF_OR_RECEIPT_MISSING"),
            blocked_gap_types_after_filter=("MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION", "BUILT_ARTIFACT_LACKS_SOURCE_NOTE"),
            next_safe_move="Keep generated outputs attached to their source contract or receipt lineage.",
        ),
        WorkTerrainNegativeFilter(
            filter_id="reference_only_filter",
            applies_to_classifications=("REFERENCE_ONLY",),
            reason="Repo B and other reference-only material are not active work unless explicitly promoted.",
            effect="Prevent reference terrain from becoming active tasks or activation gaps.",
            allowed_gap_types_after_filter=("REPO_B_REFERENCE_NOT_PROMOTED", "CONCEPTUALLY_VALID_BUT_PREMATURE"),
            blocked_gap_types_after_filter=("MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION", "MISSION_CONTROL_SURFACE_MISSING"),
            next_safe_move="Keep parked/reference-only until Winship approves a bounded promotion lane.",
        ),
        WorkTerrainNegativeFilter(
            filter_id="historical_residue_filter",
            applies_to_classifications=("HISTORICAL_RESIDUE_ONLY",),
            reason="Historical residue preserves traceability without creating work.",
            effect="Keep history visible for reconciliation without treating it as missing implementation.",
            allowed_gap_types_after_filter=("HISTORICAL_RESIDUE_ONLY", "SUPERSEDED_DOC_NOT_MARKED"),
            blocked_gap_types_after_filter=("MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION", "READ_MODEL_MISSING"),
            next_safe_move="Preserve traceability and request operator decision only if visibility causes confusion.",
        ),
        WorkTerrainNegativeFilter(
            filter_id="premature_concept_filter",
            applies_to_classifications=("CONCEPTUALLY_VALID_BUT_PREMATURE",),
            reason="A concept can be coherent while still premature for implementation.",
            effect="Route premature concepts to parked/future terrain instead of build-now gaps.",
            allowed_gap_types_after_filter=("CONCEPTUALLY_VALID_BUT_PREMATURE",),
            blocked_gap_types_after_filter=("MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION", "MISSION_CONTROL_SURFACE_MISSING"),
            next_safe_move="Keep parked and revisit after Chief/Hermes/Operator review.",
        ),
        WorkTerrainNegativeFilter(
            filter_id="unsafe_execution_filter",
            applies_to_classifications=("BUILT_BUT_UNSAFE", "UNSAFE_EXECUTION_POSTURE"),
            reason="Built-but-unsafe terrain needs quarantine or security review, not activation.",
            effect="Route unsafe implementation posture to Guardian/security delta instead of surface or execution.",
            allowed_gap_types_after_filter=("BUILT_BUT_UNSAFE", "UNSAFE_EXECUTION_POSTURE"),
            blocked_gap_types_after_filter=("STABLE_MAP_REPRESENTATION_MISSING", "MISSION_CONTROL_SURFACE_MISSING"),
            next_safe_move="Quarantine candidate and require Guardian/security delta review before any promotion.",
        ),
    )


def default_built_status_validation_rules() -> tuple[WorkTerrainBuiltStatusValidationRule, ...]:
    return (
        WorkTerrainBuiltStatusValidationRule(
            rule_id="file_existence_is_not_built",
            artifact_ref="artifact://candidate_python_contract",
            built_claim_source="FILE_METADATA_ONLY",
            required_test_refs=("test ref required before validated built claim",),
            required_receipt_refs=("export or validation receipt required",),
            required_commit_refs=("commit ref strengthens lineage when available",),
            required_generated_artifacts=("generated read-model ref required where exporter exists",),
            built_status="BUILT_UNVALIDATED",
            can_claim_built=False,
            missing_validation=("test refs", "receipt refs", "generated artifact refs"),
            next_safe_move="Link tests, receipts, generated outputs, and source lineage before claiming built.",
        ),
        WorkTerrainBuiltStatusValidationRule(
            rule_id="validated_by_test_signal",
            artifact_ref="relationship_signal://VALIDATED_BY_TEST",
            built_claim_source="VALIDATED_BY_TEST",
            required_test_refs=("tests/test_<artifact>.py",),
            required_receipt_refs=(),
            required_commit_refs=(),
            required_generated_artifacts=(),
            built_status="BUILT_WITH_TESTS",
            can_claim_built=True,
            missing_validation=(),
            next_safe_move="Use test-linked status as stronger evidence, not final doctrine.",
        ),
        WorkTerrainBuiltStatusValidationRule(
            rule_id="receipt_strengthens_completion_claim",
            artifact_ref="receipt://validation_or_operator_receipt",
            built_claim_source="RECEIPT_LINKED",
            required_test_refs=(),
            required_receipt_refs=("receipt ref required",),
            required_commit_refs=(),
            required_generated_artifacts=(),
            built_status="BUILT_WITH_RECEIPTS",
            can_claim_built=True,
            missing_validation=(),
            next_safe_move="Attach receipt to relationship and classification records for Chief reconciliation.",
        ),
        WorkTerrainBuiltStatusValidationRule(
            rule_id="surface_requires_stable_map_or_ui_receipt",
            artifact_ref="stable_map_or_ui_surface://candidate",
            built_claim_source="STABLE_MAP_OR_UI_SURFACE_REF",
            required_test_refs=("surface or contract test refs",),
            required_receipt_refs=("stable-map import/readback or screenshot validation receipt",),
            required_commit_refs=(),
            required_generated_artifacts=("stable-map section or generated read-model",),
            built_status="BUILT_AND_SURFACED",
            can_claim_built=True,
            missing_validation=(),
            next_safe_move="Keep source lineage attached; screenshots validate UI state but do not become doctrine.",
        ),
        WorkTerrainBuiltStatusValidationRule(
            rule_id="partial_build_requires_reconciliation",
            artifact_ref="artifact://partially_built_lane",
            built_claim_source="MIXED_METADATA",
            required_test_refs=("narrow test refs for built slices",),
            required_receipt_refs=("receipt refs for completed slices",),
            required_commit_refs=("commit refs where available",),
            required_generated_artifacts=("generated read-model refs where exporter exists",),
            built_status="PARTIALLY_BUILT",
            can_claim_built=False,
            missing_validation=("complete source-to-artifact relationship map",),
            next_safe_move="Chief reconciles which slices are built, missing, or stale; no implementation starts here.",
        ),
        WorkTerrainBuiltStatusValidationRule(
            rule_id="built_but_unsafe_requires_quarantine",
            artifact_ref="artifact://unsafe_execution_posture",
            built_claim_source="SECURITY_OR_AUTHORITY_MISMATCH",
            required_test_refs=(),
            required_receipt_refs=("security delta or Guardian receipt required before any promotion",),
            required_commit_refs=(),
            required_generated_artifacts=(),
            built_status="BUILT_BUT_UNSAFE",
            can_claim_built=False,
            missing_validation=("security delta review", "Guardian quarantine decision"),
            next_safe_move="Route to quarantine/security review; never treat unsafe implementation as action-ready.",
        ),
    )


def default_gap_examples() -> tuple[WorkTerrainGapRecord, ...]:
    return (
        _gap(
            "chief_source_notes_vs_built_contracts_gap",
            display_name="Chief Source Notes vs Built Contracts Gap",
            gap_type="SOURCE_NOTE_DESCRIBES_BUILT_ARTIFACT",
            gap_priority="CHIEF_RECONCILIATION_NEEDED",
            terrain_refs=("concept://chief/reconciliation_cross_off_test_harness",),
            relationship_refs=("chief_test_harness_source_to_contract",),
            read_model_refs=("generated/read_models/chief_test_harness_cross_off_receipt_contract.json",),
            test_refs=("tests/test_chief_test_harness_cross_off_receipt_contract.py",),
            affected_actor="Chief",
            affected_world="Build",
            affected_lane="Chief test harness / cross-off",
            current_visibility=("source concepts", "backend contract", "tests"),
            missing_visibility=("complete source-lineage receipt",),
            why_it_matters="Chief concepts may be spread across prompts, Markdown, contracts, and generated digests.",
            recommended_resolution_type="CHIEF_RECONCILIATION",
            requires_chief_reconciliation=True,
            next_safe_move="Build a source-to-contract relationship packet later; do not move or rewrite files.",
        ),
        _gap(
            "markdown_knowledge_atlas_visibility_gap",
            display_name="Markdown Knowledge Atlas Visibility Gap",
            gap_type="STABLE_MAP_REPRESENTATION_MISSING",
            gap_priority="STABLE_MAP_VISIBILITY_GAP",
            terrain_refs=("markdown_knowledge_atlas.py", "markdown_evidence_ingestion.py", "corpus_atlas.py"),
            relationship_refs=("markdown_knowledge_atlas_built_not_prominently_surfaced",),
            affected_actor="Hermes",
            affected_world="Research",
            affected_lane="Markdown Atlas",
            current_visibility=("backend capability metadata",),
            missing_visibility=("compact stable-map or app-facing capability summary",),
            why_it_matters="The backend terrain capability exists but may not be prominent enough in app-facing truth.",
            recommended_resolution_type="PROMOTE_TO_STABLE_MAP_CANDIDATE",
            requires_chief_reconciliation=True,
            requires_hermes_review=True,
            next_safe_move="Review metadata and decide later whether to summarize the capability in stable map.",
        ),
        _gap(
            "capital_hilton_proof_resolution_surface_gap",
            display_name="Capital Hilton Proof Resolution Surface Gap",
            gap_type="MISSION_CONTROL_SURFACE_MISSING",
            gap_priority="INCOMPLETE_LINEAGE",
            terrain_refs=("capital_hilton_proof_resolution_batch_v0",),
            relationship_refs=("capital_hilton_proof_resolution_backend_links",),
            read_model_refs=("generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",),
            affected_actor="Cassandra",
            affected_world="Finance",
            affected_lane="Capital Hilton",
            current_visibility=("backend proof-resolution rails", "stable-map summary candidate"),
            missing_visibility=("Mac UI answer capture surface",),
            why_it_matters="Backend rails exist, but answer capture UI is not implemented by this lane and action remains blocked.",
            recommended_resolution_type="CHIEF_RECONCILIATION",
            requires_chief_reconciliation=True,
            next_safe_move="Leave to a future UI/surface lane; do not infer invoice, account, or send authority.",
        ),
        _gap(
            "repo_b_planner_builder_reference_gap",
            display_name="Repo B Planner/Builder Reference Gap",
            gap_type="REPO_B_REFERENCE_NOT_PROMOTED",
            gap_priority="PARKED_OR_PREMATURE",
            terrain_refs=("repo_b_reference://planner_builder_orchestrator",),
            relationship_refs=("repo_b_planner_builder_reference_only",),
            classification_refs=("repo_b_planner_builder_reference_only",),
            affected_actor="Codex",
            affected_world="Operations",
            affected_lane="Repo B Planner / Builder",
            current_visibility=("reference-only metadata",),
            missing_visibility=(),
            why_it_matters="Repo B concepts may be useful reference terrain but have no active authority.",
            negative_filter_applied=True,
            should_not_build_reason="Reference-only terrain is blocked from becoming active work without explicit approval.",
            recommended_resolution_type="KEEP_PARKED",
            requires_operator_decision=True,
            next_safe_move="Keep reference-only; no Repo B inspection or activation occurs here.",
        ),
        _gap(
            "future_invoicing_audit_parked_gap",
            display_name="Future Invoicing Audit Parked Gap",
            gap_type="CONCEPTUALLY_VALID_BUT_PREMATURE",
            gap_priority="PARKED_OR_PREMATURE",
            terrain_refs=("parked_stress_test://future_invoicing_audit",),
            relationship_refs=("future_invoicing_audit_to_parked_stress_test",),
            stable_map_refs=("stable_map.parked_autonomous_capital_pipeline_experiment",),
            affected_actor="Gemini / Agy",
            affected_world="Finance",
            affected_lane="Parked stress-test",
            current_visibility=("parked stress-test summary",),
            missing_visibility=(),
            why_it_matters="The audit can inform safety but must not be confused with executable invoicing workflow.",
            negative_filter_applied=True,
            should_not_build_reason="Parked stress-test artifacts are not implementation authority.",
            recommended_resolution_type="KEEP_PARKED",
            requires_hermes_review=True,
            next_safe_move="Retain as parked proof/detail for future review; no invoice workflow starts.",
        ),
        _gap(
            "generated_operator_markdown_truth_gap",
            display_name="Generated Operator Markdown Truth Gap",
            gap_type="GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE",
            gap_priority="PROOF_DETAIL_ONLY",
            terrain_refs=("generated/read_models/*_OPERATOR.md",),
            relationship_refs=("generated_operator_markdown_is_proof_detail",),
            classification_refs=("generated_operator_markdown_generated_artifact",),
            read_model_refs=("generated/read_models/*.json",),
            affected_actor="Hermes",
            affected_world="Operations",
            affected_lane="Generated read-models",
            current_visibility=("generated operator digest metadata",),
            missing_visibility=("human-authored source-card lineage where needed",),
            why_it_matters="Generated operator Markdown is useful proof/detail but not doctrine by default.",
            negative_filter_applied=True,
            should_not_build_reason="Generated artifacts cannot create implementation gaps or doctrine by themselves.",
            recommended_resolution_type="KEEP_AS_PROOF_DETAIL",
            requires_hermes_review=True,
            next_safe_move="Keep tied to source contracts and receipts; promote only through reviewed source-card flow.",
        ),
        _gap(
            "stable_map_summary_missing_for_work_terrain",
            display_name="Stable Map Summary Missing for Work Terrain",
            gap_type="STABLE_MAP_REPRESENTATION_MISSING",
            gap_priority="STABLE_MAP_VISIBILITY_GAP",
            terrain_refs=("openclaw_work_terrain_reconciliation_v0",),
            read_model_refs=("generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",),
            affected_actor="Chief",
            affected_world="Operations",
            affected_lane="Work Terrain",
            current_visibility=("backend batch read-models",),
            missing_visibility=("compact stable-map proof section",),
            why_it_matters="Work Terrain should eventually be app-visible as compact proof, not a full file browser.",
            recommended_resolution_type="PROMOTE_TO_STABLE_MAP_CANDIDATE",
            requires_chief_reconciliation=True,
            requires_hermes_review=True,
            next_safe_move="Prompt 5 can add a compact stable-map summary after batch validation.",
        ),
        _gap(
            "old_prompt_not_implementation_gap",
            display_name="Old Prompt Is Not Implementation Gap",
            gap_type="HISTORICAL_RESIDUE_ONLY",
            gap_priority="PROOF_DETAIL_ONLY",
            terrain_refs=("old_prompt://generic_historical_prompt",),
            classification_refs=("OLD_PROMPT",),
            affected_actor="Operator / Winship",
            affected_world="Operations",
            affected_lane="Historical prompts",
            current_visibility=("old prompt metadata",),
            missing_visibility=(),
            why_it_matters="Old prompts preserve context but must not silently become build-now work.",
            negative_filter_applied=True,
            should_not_build_reason="The old prompt filter blocks implementation gaps by default.",
            recommended_resolution_type="KEEP_AS_PROOF_DETAIL",
            requires_operator_decision=True,
            next_safe_move="Preserve traceability and request review only if it conflicts with current doctrine.",
        ),
        _gap(
            "built_artifact_missing_test_receipt_gap",
            display_name="Built Artifact Missing Test/Receipt Gap",
            gap_type="TEST_VALIDATION_MISSING",
            gap_priority="INCOMPLETE_LINEAGE",
            terrain_refs=("python_contract://example_unvalidated_artifact",),
            relationship_refs=("built_artifact_lacks_source_note_example",),
            affected_actor="Chief",
            affected_world="Build",
            affected_lane="Validation lineage",
            current_visibility=("file metadata",),
            missing_visibility=("test refs", "receipt refs"),
            why_it_matters="A file existing is not enough to claim work is built or complete.",
            recommended_resolution_type="ADD_TEST_OR_RECEIPT_CANDIDATE",
            requires_chief_reconciliation=True,
            next_safe_move="Link tests, generated outputs, and receipts before completion claims.",
        ),
        _gap(
            "implementation_exists_but_doctrine_stale_gap",
            display_name="Implementation Exists but Doctrine Is Stale",
            gap_type="IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE",
            gap_priority="HERMES_REVIEW_NEEDED",
            terrain_refs=("concept://implementation_moved_beyond_source_note",),
            classification_refs=("IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE",),
            affected_actor="Hermes",
            affected_world="Operations",
            affected_lane="Doctrine coherence",
            current_visibility=("implementation metadata", "older source note metadata"),
            missing_visibility=("reviewed supersession/source-card receipt",),
            why_it_matters="Implementation can move beyond source notes, leaving doctrine misleading.",
            recommended_resolution_type="HERMES_REVIEW",
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            next_safe_move="Hermes reviews coherence; Chief links source lineage; no rewrite occurs here.",
        ),
        _gap(
            "doctrine_exists_but_implementation_superseded_gap",
            display_name="Doctrine Exists but Implementation Was Superseded",
            gap_type="DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED",
            gap_priority="HERMES_REVIEW_NEEDED",
            terrain_refs=("concept://doctrine_describes_superseded_implementation",),
            classification_refs=("DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED",),
            affected_actor="Hermes",
            affected_world="Operations",
            affected_lane="Doctrine coherence",
            current_visibility=("source note metadata", "newer artifact metadata"),
            missing_visibility=("supersession receipt",),
            why_it_matters="Docs can describe an approach that later implementation replaced.",
            recommended_resolution_type="MARK_SUPERSEDED_CANDIDATE",
            requires_hermes_review=True,
            requires_operator_decision=True,
            next_safe_move="Prepare supersession candidate only; no archive or delete action.",
        ),
        _gap(
            "built_but_unsafe_execution_gap",
            display_name="Built but Unsafe Execution Gap",
            gap_type="BUILT_BUT_UNSAFE",
            gap_priority="CRITICAL_SECURITY_GAP",
            terrain_refs=("artifact://unsafe_execution_posture_example",),
            classification_refs=("BUILT_BUT_UNSAFE", "UNSAFE_EXECUTION_POSTURE"),
            affected_actor="Guardian",
            affected_world="Security",
            affected_lane="Execution posture",
            current_visibility=("implementation metadata", "authority mismatch signal"),
            missing_visibility=("security delta receipt", "Guardian quarantine decision"),
            why_it_matters="Implementation that violates safety posture must be quarantined, not activated.",
            negative_filter_applied=True,
            should_not_build_reason="Unsafe implementation is not activation authority.",
            recommended_resolution_type="QUARANTINE",
            requires_guardian_review=True,
            requires_security_delta=True,
            next_safe_move="Route to Guardian/security delta review and keep action authority false.",
        ),
    )


def gap_detector_policy() -> WorkTerrainGapDetectorPolicy:
    return WorkTerrainGapDetectorPolicy(
        metadata_only=True,
        body_ingestion_allowed=False,
        semantic_review_allowed=False,
        file_mutation_allowed=False,
        auto_archive_allowed=False,
        auto_consolidation_allowed=False,
        auto_stable_map_promotion_allowed=False,
        auto_implementation_allowed=False,
        negative_filtering_required=True,
        built_status_requires_validation=True,
        operator_attention_dedup_required=True,
        chief_reconciliation_role="Chief reconciles source lineage, built status, validation, and completion claims later.",
        hermes_review_role="Hermes reviews doctrine coherence, overlap, staleness, and supersession candidates later.",
        guardian_review_role="Guardian quarantines protected, unsafe, or authority-conflicting terrain before promotion.",
        operator_final_authority="Winship remains final authority for promotion, archive, consolidation, or implementation decisions.",
    )


def _prior_lane_status(repo_root: str | Path, ref: str) -> str:
    return "OBSERVED" if (Path(repo_root) / ref).is_file() else "NOT_OBSERVED_OR_PENDING"


def build_openclaw_work_terrain_gap_detector(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    filters = default_negative_filters()
    built_rules = default_built_status_validation_rules()
    gaps = default_gap_examples()
    policy = gap_detector_policy()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_gap_detector_contract",
        "core_doctrine": {
            "terrain_records_broadly": True,
            "bodies_selectively": True,
            "truth_only_through_receipts": True,
            "gap_detection_is_not_cleanup_authority": True,
            "gap_detection_is_not_build_authority": True,
            "file_existing_does_not_mean_current": True,
            "stable_map_gap_is_not_source_truth_gap_by_itself": True,
            "generated_artifact_is_proof_detail_not_doctrine": True,
        },
        "taxonomy_adjustments_from_review": {
            "review_verdict": "PROCEED_WITH_MINOR_ADJUSTMENTS",
            "classification_or_gap_terms_added": [
                "PARTIALLY_BUILT",
                "BUILT_BUT_UNSAFE",
                "UNSAFE_EXECUTION_POSTURE",
                "CONCEPTUALLY_VALID_BUT_PREMATURE",
                "HISTORICAL_RESIDUE_ONLY",
                "IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE",
                "DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED",
            ],
            "relationship_signal_additions": ["VALIDATED_BY_TEST"],
            "explicit_gap_priority_buckets_added": True,
            "negative_filtering_required": True,
            "receipt_test_validation_before_built_claim": True,
        },
        "gap_record_model": {
            "model_name": "WorkTerrainGapRecord",
            "fields": list(GAP_RECORD_FIELDS),
        },
        "negative_filter_model": {
            "model_name": "WorkTerrainNegativeFilter",
            "fields": list(NEGATIVE_FILTER_FIELDS),
        },
        "built_status_validation_rule_model": {
            "model_name": "WorkTerrainBuiltStatusValidationRule",
            "fields": list(BUILT_STATUS_VALIDATION_RULE_FIELDS),
        },
        "gap_detector_policy_model": {
            "model_name": "WorkTerrainGapDetectorPolicy",
            "fields": list(GAP_DETECTOR_POLICY_FIELDS),
        },
        "gap_types": list(GAP_TYPES),
        "gap_priorities": list(GAP_PRIORITIES),
        "recommended_resolution_types": list(RECOMMENDED_RESOLUTION_TYPES),
        "built_statuses": list(BUILT_STATUSES),
        "negative_filters": [asdict(item) for item in filters],
        "built_status_validation_rules": [asdict(rule) for rule in built_rules],
        "default_gap_examples": [asdict(gap) for gap in gaps],
        "gap_detector_policy": asdict(policy),
        "relationship_to_prior_lanes": {
            "openclaw_work_terrain_query_contract": {
                "read_model_ref": QUERY_CONTRACT_READ_MODEL_REF,
                "relationship": "Prompt 1 defines focused terrain query grammar.",
                "status": _prior_lane_status(repo_root, QUERY_CONTRACT_READ_MODEL_REF),
            },
            "openclaw_work_terrain_relationship_index": {
                "read_model_ref": RELATIONSHIP_INDEX_READ_MODEL_REF,
                "relationship": "Prompt 2 defines relationship records consumed by gap detection.",
                "status": _prior_lane_status(repo_root, RELATIONSHIP_INDEX_READ_MODEL_REF),
            },
            "openclaw_work_terrain_classification_candidate": {
                "read_model_ref": CLASSIFICATION_CANDIDATE_READ_MODEL_REF,
                "relationship": "Prompt 3 defines classification candidates and staleness posture consumed by filters.",
                "status": _prior_lane_status(repo_root, CLASSIFICATION_CANDIDATE_READ_MODEL_REF),
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "gap_record_exists": True,
            "gap_types_exist": all(item in GAP_TYPES for item in ("PARTIALLY_BUILT", "BUILT_BUT_UNSAFE", "UNKNOWN_FAIL_CLOSED")),
            "gap_priority_buckets_exist": len(GAP_PRIORITIES) == 11,
            "negative_filters_exist": len(filters) == 6,
            "built_status_validation_rule_exists": len(built_rules) == 6,
            "default_gap_examples_exist": len(gaps) == 12,
            "old_prompt_filter_prevents_implementation_gap": any(
                item.filter_id == "old_prompt_filter"
                and "MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION" in item.blocked_gap_types_after_filter
                for item in filters
            ),
            "generated_artifact_filter_prevents_doctrine_treatment": any(
                item.filter_id == "generated_artifact_filter"
                and "GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE" in item.allowed_gap_types_after_filter
                for item in filters
            ),
            "reference_only_filter_prevents_activation": any(item.filter_id == "reference_only_filter" for item in filters),
            "built_status_requires_validation": policy.built_status_requires_validation,
            "validated_by_test_signal_represented": any(
                rule.built_claim_source == "VALIDATED_BY_TEST" for rule in built_rules
            ),
            "built_but_unsafe_routes_to_security_or_quarantine": any(
                gap.gap_id == "built_but_unsafe_execution_gap"
                and gap.requires_security_delta
                and gap.recommended_resolution_type == "QUARANTINE"
                for gap in gaps
            ),
            "auto_archive_consolidation_stable_map_implementation_false": (
                not policy.auto_archive_allowed
                and not policy.auto_consolidation_allowed
                and not policy.auto_stable_map_promotion_allowed
                and not policy.auto_implementation_allowed
            ),
            "no_action_authority": all(not gap.action_allowed for gap in gaps),
            "prior_lane_refs_represented": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_work_terrain_gap_detector(payload: dict[str, Any]) -> str:
    policy = payload["gap_detector_policy"]
    lines = [
        "# OpenClaw Work Terrain Gap Detector v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract defines safe candidate gaps between OpenClaw terrain records, relationships, classifications, read-models, stable-map visibility, receipts, tests, and built-artifact claims. A gap is a review target, not an automatic task, cleanup order, archive instruction, or build request.",
        "",
        "## What A Terrain Gap Means",
        "",
        "- A source note can describe something built, but completion still needs tests, receipts, commits, or stable-map/read-model evidence.",
        "- A built artifact can lack source lineage without being wrong; it becomes a Chief reconciliation candidate.",
        "- Old prompts and generated artifacts are filtered so they do not become build-now gaps.",
        "- Built-but-unsafe terrain routes to Guardian or security delta review, never activation.",
        "",
        "## Priority Buckets",
        "",
        "- " + ", ".join(payload["gap_priorities"]),
        "",
        "## Negative Filters",
        "",
    ]
    for item in payload["negative_filters"]:
        lines.append(f"- `{item['filter_id']}`: {item['effect']}")
    lines.extend(
        [
            "",
            "## Built Status Validation",
            "",
            "- File existence alone is not enough to claim built.",
            "- `VALIDATED_BY_TEST` is represented as a relationship signal for stronger built-status evidence.",
            "- Worker reports, screenshots, generated files, tests, receipts, and commits remain evidence inputs, not doctrine by themselves.",
            "",
            "## Default Gap Examples",
            "",
        ]
    )
    for gap in payload["default_gap_examples"]:
        lines.append(
            f"- `{gap['gap_id']}`: `{gap['gap_priority']}` / `{gap['gap_type']}` / {gap['why_it_matters']}"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            f"- Metadata only: `{str(policy['metadata_only']).lower()}`",
            f"- Body ingestion allowed: `{str(policy['body_ingestion_allowed']).lower()}`",
            f"- Semantic review allowed now: `{str(policy['semantic_review_allowed']).lower()}`",
            f"- File mutation allowed: `{str(policy['file_mutation_allowed']).lower()}`",
            f"- Auto archive/consolidation/stable-map promotion/implementation allowed: `{str(policy['auto_archive_allowed']).lower()}` / `{str(policy['auto_consolidation_allowed']).lower()}` / `{str(policy['auto_stable_map_promotion_allowed']).lower()}` / `{str(policy['auto_implementation_allowed']).lower()}`",
            "- Chief reconciles source lineage and built-status claims.",
            "- Hermes reviews concept coherence and stale/supersession candidates.",
            "- Guardian quarantines protected, unsafe, or authority-conflicting terrain.",
            "- Winship remains final authority.",
            "",
            "## Next Batch Lane",
            "",
            "- Prompt 5 validates the Work Terrain batch, commits it if clean, refreshes the stable map once, and stages the bundle for Mac import. This prompt does none of those things.",
            "",
            "## Boundary",
            "",
            "- No commit, staging, stable-map refresh, broad AI semantic review, raw body ingestion, broad private scan, file moves/deletes/rewrites/archive operations, network, git push/pull/fetch, Mac sync/import, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, C-drive scan/write, credential/account/browser/email/Coupa access, or authority escalation.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_work_terrain_gap_detector(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkTerrainGapDetectorExportResult:
    payload = build_openclaw_work_terrain_gap_detector(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_openclaw_work_terrain_gap_detector(payload), encoding="utf-8")
    return WorkTerrainGapDetectorExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        gap_count=len(payload["default_gap_examples"]),
        negative_filter_count=len(payload["negative_filters"]),
        built_validation_rule_count=len(payload["built_status_validation_rules"]),
        action_authority_granted=payload["authority_boundary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Work Terrain Gap Detector.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_work_terrain_gap_detector(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "gap_count": result.gap_count,
        "negative_filter_count": result.negative_filter_count,
        "built_validation_rule_count": result.built_validation_rule_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Work Terrain Gap Detector: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BUILT_STATUSES",
    "GAP_PRIORITIES",
    "GAP_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "RECOMMENDED_RESOLUTION_TYPES",
    "SCHEMA_VERSION",
    "WorkTerrainBuiltStatusValidationRule",
    "WorkTerrainGapDetectorPolicy",
    "WorkTerrainGapRecord",
    "WorkTerrainNegativeFilter",
    "build_openclaw_work_terrain_gap_detector",
    "default_built_status_validation_rules",
    "default_gap_examples",
    "default_negative_filters",
    "export_openclaw_work_terrain_gap_detector",
    "format_openclaw_work_terrain_gap_detector",
    "gap_detector_policy",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
