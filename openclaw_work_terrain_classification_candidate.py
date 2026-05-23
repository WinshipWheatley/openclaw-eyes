"""OpenClaw Work Terrain Classification / Staleness Candidate v0.

This read-model defines candidate classifications for OpenClaw work terrain.
It does not decide final truth, inspect raw bodies, run broad semantic review,
mutate files, archive anything, refresh the stable map, or grant authority.
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

SCHEMA_VERSION = "openclaw_work_terrain_classification_candidate_v0"
READ_MODEL_ID = "openclaw_work_terrain_classification_candidate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

QUERY_CONTRACT_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_query_contract.json"
RELATIONSHIP_INDEX_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_relationship_index.json"

CLASSIFICATIONS = (
    "CURRENT_CANONICAL",
    "CURRENT_SUPPORTING",
    "ACTIVE_HANDOFF",
    "OLD_PROMPT",
    "STALE_SUPERSEDED",
    "DUPLICATE_CONCEPT",
    "OVERLAPPING_CONCEPT",
    "ATTEMPTED_BUT_ABORTED",
    "BUILT_NOT_SURFACED",
    "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT",
    "BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
    "SOURCE_NOTE_LACKS_BUILT_ARTIFACT",
    "GENERATED_ARTIFACT",
    "REFERENCE_ONLY",
    "OPERATOR_MEMORY_ONLY",
    "SOURCE_CARD_CANDIDATE",
    "STABLE_MAP_CANDIDATE",
    "CONSOLIDATION_CANDIDATE",
    "ARCHIVE_CANDIDATE",
    "QUARANTINE_CANDIDATE",
    "UNKNOWN_FAIL_CLOSED",
)

ARTIFACT_TYPES = (
    "MARKDOWN_FILE",
    "SOURCE_NOTE",
    "OLD_PROMPT",
    "ACTIVE_HANDOFF",
    "WORKER_REPORT",
    "PYTHON_CONTRACT",
    "EXPORT_SCRIPT",
    "TEST_FILE",
    "GENERATED_READ_MODEL",
    "GENERATED_OPERATOR_DIGEST",
    "SQLITE_TABLE",
    "SQLITE_RECEIPT",
    "STABLE_MAP_SECTION",
    "MISSION_CONTROL_SURFACE",
    "MAC_SWIFT_SOURCE",
    "VALIDATION_SCREENSHOT",
    "COMMIT",
    "WORLD",
    "LANE",
    "ACTOR",
    "PACKAGE",
    "TOOL_ADAPTER",
    "PROTECTED_REFERENCE",
    "UNKNOWN_FAIL_CLOSED",
)

CLASSIFICATION_CANDIDATE_FIELDS = (
    "candidate_id",
    "terrain_ref",
    "display_name",
    "artifact_type",
    "candidate_classification",
    "classification_reason",
    "evidence_refs",
    "relationship_refs",
    "sqlite_refs",
    "read_model_refs",
    "stable_map_refs",
    "receipt_refs",
    "commit_refs",
    "confidence_posture",
    "requires_hermes_review",
    "requires_chief_reconciliation",
    "requires_operator_decision",
    "requires_security_delta",
    "can_promote_to_source_card",
    "can_promote_to_stable_map",
    "can_consolidate",
    "can_archive",
    "archive_action_allowed",
    "rewrite_action_allowed",
    "delete_action_allowed",
    "authority_granted",
    "next_safe_move",
)

CLASSIFICATION_RULE_FIELDS = (
    "rule_id",
    "display_name",
    "applies_to_artifact_types",
    "signals",
    "candidate_classification",
    "required_evidence",
    "review_required",
    "forbidden_inference",
    "next_safe_move",
)

CONSOLIDATION_CANDIDATE_FIELDS = (
    "consolidation_id",
    "concept_name",
    "source_fragments",
    "current_best_source",
    "proposed_canonical_doc",
    "merge_reason",
    "expected_benefit",
    "requires_hermes_review",
    "requires_chief_reconciliation",
    "requires_operator_approval",
    "rewrite_allowed",
    "archive_old_fragments_allowed",
    "delete_old_fragments_allowed",
    "receipt_required_before_action",
    "next_safe_move",
)

SUPERSESSION_CANDIDATE_FIELDS = (
    "supersession_id",
    "old_ref",
    "new_ref",
    "reason",
    "evidence_refs",
    "receipt_required",
    "operator_approval_required",
    "archive_action_allowed",
    "delete_action_allowed",
    "stable_map_update_required",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "body_ingestion_allowed": False,
    "broad_ai_semantic_review_allowed": False,
    "broad_private_root_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "file_archive_allowed": False,
    "auto_promotion_allowed": False,
    "auto_consolidation_allowed": False,
    "auto_archive_allowed": False,
    "auto_supersession_allowed": False,
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
class WorkTerrainClassificationCandidate:
    candidate_id: str
    terrain_ref: str
    display_name: str
    artifact_type: str
    candidate_classification: str
    classification_reason: str
    evidence_refs: tuple[str, ...]
    relationship_refs: tuple[str, ...]
    sqlite_refs: tuple[str, ...]
    read_model_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    commit_refs: tuple[str, ...]
    confidence_posture: str
    requires_hermes_review: bool
    requires_chief_reconciliation: bool
    requires_operator_decision: bool
    requires_security_delta: bool
    can_promote_to_source_card: bool
    can_promote_to_stable_map: bool
    can_consolidate: bool
    can_archive: bool
    archive_action_allowed: bool
    rewrite_action_allowed: bool
    delete_action_allowed: bool
    authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainClassificationRule:
    rule_id: str
    display_name: str
    applies_to_artifact_types: tuple[str, ...]
    signals: tuple[str, ...]
    candidate_classification: str
    required_evidence: tuple[str, ...]
    review_required: tuple[str, ...]
    forbidden_inference: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainConsolidationCandidate:
    consolidation_id: str
    concept_name: str
    source_fragments: tuple[str, ...]
    current_best_source: str
    proposed_canonical_doc: str
    merge_reason: str
    expected_benefit: str
    requires_hermes_review: bool
    requires_chief_reconciliation: bool
    requires_operator_approval: bool
    rewrite_allowed: bool
    archive_old_fragments_allowed: bool
    delete_old_fragments_allowed: bool
    receipt_required_before_action: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainSupersessionCandidate:
    supersession_id: str
    old_ref: str
    new_ref: str
    reason: str
    evidence_refs: tuple[str, ...]
    receipt_required: bool
    operator_approval_required: bool
    archive_action_allowed: bool
    delete_action_allowed: bool
    stable_map_update_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainClassificationExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    classification_candidate_count: int
    rule_count: int
    consolidation_candidate_count: int
    supersession_candidate_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _candidate(
    candidate_id: str,
    *,
    terrain_ref: str,
    display_name: str,
    artifact_type: str,
    candidate_classification: str,
    classification_reason: str,
    evidence_refs: tuple[str, ...] = (),
    relationship_refs: tuple[str, ...] = (),
    sqlite_refs: tuple[str, ...] = (),
    read_model_refs: tuple[str, ...] = (),
    stable_map_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    commit_refs: tuple[str, ...] = (),
    confidence_posture: str = "CANDIDATE_METADATA_ONLY",
    requires_hermes_review: bool = False,
    requires_chief_reconciliation: bool = False,
    requires_operator_decision: bool = False,
    requires_security_delta: bool = False,
    can_promote_to_source_card: bool = False,
    can_promote_to_stable_map: bool = False,
    can_consolidate: bool = False,
    can_archive: bool = False,
    next_safe_move: str,
) -> WorkTerrainClassificationCandidate:
    return WorkTerrainClassificationCandidate(
        candidate_id=candidate_id,
        terrain_ref=terrain_ref,
        display_name=display_name,
        artifact_type=artifact_type,
        candidate_classification=candidate_classification,
        classification_reason=classification_reason,
        evidence_refs=evidence_refs,
        relationship_refs=relationship_refs,
        sqlite_refs=sqlite_refs,
        read_model_refs=read_model_refs,
        stable_map_refs=stable_map_refs,
        receipt_refs=receipt_refs,
        commit_refs=commit_refs,
        confidence_posture=confidence_posture,
        requires_hermes_review=requires_hermes_review,
        requires_chief_reconciliation=requires_chief_reconciliation,
        requires_operator_decision=requires_operator_decision,
        requires_security_delta=requires_security_delta,
        can_promote_to_source_card=can_promote_to_source_card,
        can_promote_to_stable_map=can_promote_to_stable_map,
        can_consolidate=can_consolidate,
        can_archive=can_archive,
        archive_action_allowed=False,
        rewrite_action_allowed=False,
        delete_action_allowed=False,
        authority_granted=False,
        next_safe_move=next_safe_move,
    )


def default_classification_rules() -> tuple[WorkTerrainClassificationRule, ...]:
    return (
        WorkTerrainClassificationRule(
            rule_id="generated_read_models_are_not_doctrine",
            display_name="Generated Read-Models Are Not Doctrine",
            applies_to_artifact_types=("GENERATED_READ_MODEL", "GENERATED_OPERATOR_DIGEST"),
            signals=("generated path", "exporter output", "operator digest suffix"),
            candidate_classification="GENERATED_ARTIFACT",
            required_evidence=("source read-model or exporter reference",),
            review_required=("Chief if source lineage is unclear",),
            forbidden_inference="Do not treat generated artifacts as human-authored source truth by default.",
            next_safe_move="Keep as proof/detail until a source-card or stable-map promotion is receipted.",
        ),
        WorkTerrainClassificationRule(
            rule_id="old_prompts_are_not_current_truth",
            display_name="Old Prompts Are Not Current Truth",
            applies_to_artifact_types=("OLD_PROMPT", "MARKDOWN_FILE", "SOURCE_NOTE"),
            signals=("prompt wording", "past batch label", "superseded workflow language"),
            candidate_classification="OLD_PROMPT",
            required_evidence=("receipt refs", "stable-map refs", "Chief/Hermes review"),
            review_required=("Chief", "Hermes", "Operator where doctrine is affected"),
            forbidden_inference="Do not promote old prompt text to current truth without proof.",
            next_safe_move="Classify as history, residue, or source-card candidate after relationship comparison.",
        ),
        WorkTerrainClassificationRule(
            rule_id="built_artifacts_need_source_lineage",
            display_name="Built Artifacts Need Source Lineage",
            applies_to_artifact_types=("PYTHON_CONTRACT", "EXPORT_SCRIPT", "TEST_FILE", "GENERATED_READ_MODEL"),
            signals=("contract/test/exporter trio", "generated read-model present"),
            candidate_classification="BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
            required_evidence=("source note", "receipt", "commit", "stable-map linkage"),
            review_required=("Chief",),
            forbidden_inference="Implementation presence alone does not prove source lineage or completion.",
            next_safe_move="Ask Chief to reconcile implementation refs with source notes and receipts later.",
        ),
        WorkTerrainClassificationRule(
            rule_id="source_notes_need_built_artifact_check",
            display_name="Source Notes Need Built Artifact Check",
            applies_to_artifact_types=("SOURCE_NOTE", "MARKDOWN_FILE", "OLD_PROMPT"),
            signals=("describes feature", "names lane", "mentions desired behavior"),
            candidate_classification="SOURCE_NOTE_LACKS_BUILT_ARTIFACT",
            required_evidence=("relationship index result", "test/export/read-model refs"),
            review_required=("Chief",),
            forbidden_inference="Do not assume a note describes implemented work.",
            next_safe_move="Compare metadata refs to contracts, tests, generated outputs, and receipts.",
        ),
        WorkTerrainClassificationRule(
            rule_id="markdown_doctrine_needs_receipts",
            display_name="Markdown Doctrine Needs Receipts",
            applies_to_artifact_types=("MARKDOWN_FILE", "SOURCE_NOTE"),
            signals=("doctrine language", "canonical wording", "operator instruction"),
            candidate_classification="SOURCE_CARD_CANDIDATE",
            required_evidence=("relationship refs", "stable-map refs", "receipt refs"),
            review_required=("Hermes", "Chief", "Operator"),
            forbidden_inference="Do not treat Markdown as canonical doctrine without receipt comparison.",
            next_safe_move="Route to source-card candidate review when metadata links are sufficient.",
        ),
        WorkTerrainClassificationRule(
            rule_id="repo_b_is_reference_only",
            display_name="Repo B Is Reference-Only",
            applies_to_artifact_types=("SOURCE_NOTE", "PACKAGE", "WORKER_REPORT"),
            signals=("Repo B", "planner", "builder", "orchestrator", "legacy runtime"),
            candidate_classification="REFERENCE_ONLY",
            required_evidence=("explicit future approval for a bounded lane",),
            review_required=("Hermes", "Operator"),
            forbidden_inference="Do not infer active Repo B authority from references.",
            next_safe_move="Keep as reference-only unless explicitly promoted later.",
        ),
        WorkTerrainClassificationRule(
            rule_id="screenshots_are_validation_evidence",
            display_name="Screenshots Are Validation Evidence",
            applies_to_artifact_types=("VALIDATION_SCREENSHOT",),
            signals=("screenshot ref", "UI validation proof", "render proof"),
            candidate_classification="CURRENT_SUPPORTING",
            required_evidence=("linked task or receipt",),
            review_required=("Chief if completion is being crossed off",),
            forbidden_inference="Screenshots are not doctrine or action authority.",
            next_safe_move="Use screenshots as evidence refs in completion or surface validation.",
        ),
        WorkTerrainClassificationRule(
            rule_id="handoffs_are_orientation_not_final_truth",
            display_name="Handoffs Are Orientation, Not Final Truth",
            applies_to_artifact_types=("ACTIVE_HANDOFF", "WORKER_REPORT"),
            signals=("handoff", "worker report", "claimed completion"),
            candidate_classification="ACTIVE_HANDOFF",
            required_evidence=("tests", "receipts", "commit refs", "stable-map refs where relevant"),
            review_required=("Chief",),
            forbidden_inference="Do not treat handoff claims as done proof.",
            next_safe_move="Route to Chief reconciliation when completion or cross-off is implied.",
        ),
        WorkTerrainClassificationRule(
            rule_id="unknown_sensitive_private_fails_closed",
            display_name="Unknown Sensitive/Private Fails Closed",
            applies_to_artifact_types=("UNKNOWN_FAIL_CLOSED", "PROTECTED_REFERENCE", "MARKDOWN_FILE"),
            signals=("unknown sensitivity", "private marker", "protected finance reference"),
            candidate_classification="QUARANTINE_CANDIDATE",
            required_evidence=("operator-approved root or protected metadata receipt",),
            review_required=("Guardian", "Operator"),
            forbidden_inference="Do not inspect, summarize, or promote unknown sensitive/private terrain.",
            next_safe_move="Fail closed and request operator/Guardian approval before any body review.",
        ),
        WorkTerrainClassificationRule(
            rule_id="stable_map_is_app_facing_reflection",
            display_name="Stable Map Is App-Facing Reflection",
            applies_to_artifact_types=("STABLE_MAP_SECTION", "GENERATED_READ_MODEL"),
            signals=("stable map section", "Mission Control app-facing summary"),
            candidate_classification="STABLE_MAP_CANDIDATE",
            required_evidence=("source refs", "read-model refs", "receipt refs"),
            review_required=("Chief", "Hermes where concept coherence is affected"),
            forbidden_inference="Stable map is app-facing truth but not source-set authority.",
            next_safe_move="Use stable-map refs to find what needs source lineage and receipt backing.",
        ),
    )


def default_classification_examples() -> tuple[WorkTerrainClassificationCandidate, ...]:
    return (
        _candidate(
            "security_pass_contract_current_canonical",
            terrain_ref="security_pass_contract.py",
            display_name="Security Pass Contract",
            artifact_type="PYTHON_CONTRACT",
            candidate_classification="CURRENT_CANONICAL",
            classification_reason="Current backend security contract exists, tests passed, stable map surfaced it, and the Mac Security Pass surface is represented as read-only.",
            evidence_refs=("tests/test_security_pass_contract.py",),
            read_model_refs=("generated/read_models/security_pass_contract.json",),
            stable_map_refs=("stable_map.security_pass",),
            confidence_posture="STRONG_METADATA_WITH_TEST_AND_SURFACE_REFS",
            can_promote_to_source_card=True,
            can_promote_to_stable_map=True,
            next_safe_move="Keep canonical status candidate until Chief/Hermes confirm source lineage remains coherent.",
        ),
        _candidate(
            "capital_hilton_proof_intake_current_supporting",
            terrain_ref="capital_hilton_protected_proof_intake.py",
            display_name="Capital Hilton Protected Proof Intake",
            artifact_type="PYTHON_CONTRACT",
            candidate_classification="CURRENT_SUPPORTING",
            classification_reason="Supports the active Finance lane by structuring the 10 missing proof questions while action remains locked.",
            evidence_refs=("tests/test_capital_hilton_protected_proof_intake.py",),
            read_model_refs=("generated/read_models/capital_hilton_protected_proof_intake.json",),
            stable_map_refs=("stable_map.capital_hilton_protected_proof_intake",),
            requires_chief_reconciliation=True,
            next_safe_move="Use as supporting metadata for future proof intake UI/review; do not treat as proof.",
        ),
        _candidate(
            "capital_hilton_proof_resolution_batch_current_supporting",
            terrain_ref="capital_hilton_proof_resolution_batch_v0",
            display_name="Capital Hilton Proof Resolution Backend Batch",
            artifact_type="PACKAGE",
            candidate_classification="CURRENT_SUPPORTING",
            classification_reason="Models answer receipts, protected placeholders, Guardian packets, and proof progress rails; follow-through depends on stable-map/Mac import state.",
            evidence_refs=("tests/test_capital_hilton_answer_candidate_receipt.py", "tests/test_capital_hilton_proof_quieting_progress_state.py"),
            read_model_refs=("generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",),
            stable_map_refs=("stable_map.capital_hilton_proof_resolution_batch",),
            requires_chief_reconciliation=True,
            next_safe_move="Treat as current supporting backend rail; keep all invoice/account/send authority blocked.",
        ),
        _candidate(
            "old_invoicing_automation_prompt_archive_candidate",
            terrain_ref="old_prompt://future_invoicing_automation",
            display_name="Old Invoicing Automation Prompt",
            artifact_type="OLD_PROMPT",
            candidate_classification="ARCHIVE_CANDIDATE",
            classification_reason="High-risk future automation prompt should be preserved as history or stress-test material, not execution authority.",
            relationship_refs=("future_invoicing_audit_to_parked_stress_test",),
            stable_map_refs=("stable_map.parked_autonomous_capital_pipeline_experiment",),
            confidence_posture="CANDIDATE_REQUIRES_OPERATOR_ARCHIVE_DECISION",
            requires_hermes_review=True,
            requires_operator_decision=True,
            can_archive=True,
            next_safe_move="Preserve and review; no archive/move/delete action is allowed in this lane.",
        ),
        _candidate(
            "markdown_knowledge_atlas_built_not_surfaced",
            terrain_ref="markdown_knowledge_atlas.py",
            display_name="Markdown Knowledge Atlas Capability",
            artifact_type="PYTHON_CONTRACT",
            candidate_classification="BUILT_NOT_SURFACED",
            classification_reason="Backend capability exists while app/stable-map prominence may be incomplete.",
            evidence_refs=("scripts/build_markdown_knowledge_atlas.py", "markdown_evidence_ingestion.py", "corpus_atlas.py"),
            relationship_refs=("markdown_knowledge_atlas_built_not_prominently_surfaced",),
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            can_promote_to_stable_map=True,
            next_safe_move="Use gap detector to decide if this should become a surfaced capability candidate.",
        ),
        _candidate(
            "repo_b_planner_builder_reference_only",
            terrain_ref="repo_b_reference://planner_builder_orchestrator",
            display_name="Repo B Planner / Builder Reference",
            artifact_type="PACKAGE",
            candidate_classification="REFERENCE_ONLY",
            classification_reason="Repo B concept exists as reference terrain but no active authority is granted.",
            relationship_refs=("repo_b_planner_builder_reference_only",),
            confidence_posture="REFERENCE_ONLY_METADATA",
            requires_hermes_review=True,
            next_safe_move="Keep reference-only unless a future explicit bounded approval opens a lane.",
        ),
        _candidate(
            "generated_operator_markdown_generated_artifact",
            terrain_ref="generated/read_models/*_OPERATOR.md",
            display_name="Generated Operator Markdown",
            artifact_type="GENERATED_OPERATOR_DIGEST",
            candidate_classification="GENERATED_ARTIFACT",
            classification_reason="Generated digest/proof detail is not human-authored doctrine by default.",
            relationship_refs=("generated_operator_markdown_is_proof_detail",),
            read_model_refs=("generated/read_models/*.json",),
            confidence_posture="PROOF_DETAIL_NOT_SOURCE_TRUTH",
            next_safe_move="Keep as generated proof/detail unless source-card promotion is receipted.",
        ),
        _candidate(
            "duplicated_chief_concepts_overlap",
            terrain_ref="concept://chief/reconciliation_cross_off_test_harness",
            display_name="Overlapping Chief Concepts",
            artifact_type="SOURCE_NOTE",
            candidate_classification="OVERLAPPING_CONCEPT",
            classification_reason="Chief reconciliation, cross-off, test harness, and repair queue concepts overlap across terrain records.",
            relationship_refs=("chief_test_harness_source_to_contract",),
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            can_consolidate=True,
            next_safe_move="Hermes can review concept coherence; Chief can reconcile source lineage later.",
        ),
        _candidate(
            "source_note_matches_security_pass_surface",
            terrain_ref="source_concept://security_pass_surface",
            display_name="Security Pass Source Note To Surface",
            artifact_type="SOURCE_NOTE",
            candidate_classification="SOURCE_NOTE_MATCHES_BUILT_ARTIFACT",
            classification_reason="Security Pass concept is implemented in backend contract and surfaced through stable-map/Mac read-only surfaces.",
            relationship_refs=("security_pass_contract_to_security_pass_surface",),
            read_model_refs=("generated/read_models/security_pass_contract.json",),
            stable_map_refs=("stable_map.security_pass",),
            confidence_posture="CANDIDATE_MATCH_WITH_STABLE_MAP_REFS",
            requires_chief_reconciliation=True,
            next_safe_move="Chief can confirm source note lineage and completion receipts before cross-off.",
        ),
        _candidate(
            "built_artifact_lacks_source_note_example",
            terrain_ref="python_contract://example_orphaned_backend_contract",
            display_name="Built Artifact Lacks Source Note Example",
            artifact_type="PYTHON_CONTRACT",
            candidate_classification="BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
            classification_reason="Built artifact exists but a source-lineage note is missing or not linked.",
            relationship_refs=("built_artifact_lacks_source_note_example",),
            confidence_posture="EXAMPLE_GAP_SHAPE_NOT_LIVE_SCAN_RESULT",
            requires_chief_reconciliation=True,
            can_promote_to_source_card=True,
            next_safe_move="Use gap detector to find real instances from metadata; do not infer from this shape alone.",
        ),
    )


def default_consolidation_candidates() -> tuple[WorkTerrainConsolidationCandidate, ...]:
    return (
        WorkTerrainConsolidationCandidate(
            consolidation_id="chief_concepts_consolidation_candidate",
            concept_name="Chief reconciliation / cross-off / test harness",
            source_fragments=("chief test harness notes", "cross-off receipt contract", "repair/requeue recommendations"),
            current_best_source="chief_test_harness_cross_off_receipt_contract.py",
            proposed_canonical_doc="future_source_card://chief_reconciliation_contract",
            merge_reason="Chief concepts overlap and need one reviewed source-card lineage.",
            expected_benefit="Reduce duplicate Chief concepts while preserving traceability.",
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            requires_operator_approval=True,
            rewrite_allowed=False,
            archive_old_fragments_allowed=False,
            delete_old_fragments_allowed=False,
            receipt_required_before_action=True,
            next_safe_move="Prepare review packet only; no rewrite/archive/delete action.",
        ),
        WorkTerrainConsolidationCandidate(
            consolidation_id="invoice_automation_prompts_consolidation_candidate",
            concept_name="Invoice automation prompts and Capital Hilton proof posture",
            source_fragments=("old invoicing prompts", "Capital Hilton proof intake", "proof resolution backend batch"),
            current_best_source="capital_hilton_protected_proof_intake.py",
            proposed_canonical_doc="future_source_card://capital_hilton_proof_resolution",
            merge_reason="Separate finance proof rails from high-risk automation residue.",
            expected_benefit="Make safe proof-intake doctrine clear without enabling invoice action.",
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            requires_operator_approval=True,
            rewrite_allowed=False,
            archive_old_fragments_allowed=False,
            delete_old_fragments_allowed=False,
            receipt_required_before_action=True,
            next_safe_move="Review candidate only; preserve old prompts as traceable history until approved.",
        ),
        WorkTerrainConsolidationCandidate(
            consolidation_id="mission_control_design_doctrine_consolidation_candidate",
            concept_name="Mission Control design doctrine",
            source_fragments=("Mission Control surface notes", "stable-map operator digest", "security pass surface guidance"),
            current_best_source="generated/read_models/openclaw_map_OPERATOR.md",
            proposed_canonical_doc="future_source_card://mission_control_app_contract",
            merge_reason="Design and app-facing contract notes may overlap across generated and source terrain.",
            expected_benefit="Separate generated proof/detail from human-authored app doctrine.",
            requires_hermes_review=True,
            requires_chief_reconciliation=True,
            requires_operator_approval=True,
            rewrite_allowed=False,
            archive_old_fragments_allowed=False,
            delete_old_fragments_allowed=False,
            receipt_required_before_action=True,
            next_safe_move="Hermes can review coherence after metadata gap detection; no edits now.",
        ),
    )


def default_supersession_candidates() -> tuple[WorkTerrainSupersessionCandidate, ...]:
    return (
        WorkTerrainSupersessionCandidate(
            supersession_id="security_pass_prompt_to_contract_supersession_candidate",
            old_ref="source_concept://security_pass_prompt",
            new_ref="security_pass_contract.py",
            reason="Backend contract and stable-map surface may supersede an older prompt as operational reference.",
            evidence_refs=("tests/test_security_pass_contract.py", "stable_map.security_pass"),
            receipt_required=True,
            operator_approval_required=True,
            archive_action_allowed=False,
            delete_action_allowed=False,
            stable_map_update_required=False,
            next_safe_move="Keep old ref traceable; Chief/Hermes/Operator review required before marking superseded.",
        ),
        WorkTerrainSupersessionCandidate(
            supersession_id="capital_hilton_old_invoice_prompt_to_proof_intake_candidate",
            old_ref="old_prompt://capital_hilton_invoice_generation",
            new_ref="capital_hilton_protected_proof_intake.py",
            reason="Safe proof intake may supersede older action-oriented invoicing prompt language.",
            evidence_refs=("generated/read_models/capital_hilton_protected_proof_intake.json",),
            receipt_required=True,
            operator_approval_required=True,
            archive_action_allowed=False,
            delete_action_allowed=False,
            stable_map_update_required=False,
            next_safe_move="Preserve old prompt until a receipted decision marks it stale/superseded.",
        ),
    )


def future_ai_judgment_policy() -> dict[str, Any]:
    return {
        "policy_id": "work_terrain_future_ai_judgment_policy",
        "allowed_later_after_metadata_and_relationship_classification": [
            "compare selected safe excerpts",
            "propose canonical/stale/duplicate labels",
            "propose consolidation candidates",
            "recommend source-card promotion",
            "recommend stable-map promotion",
            "recommend archive/supersession candidates",
        ],
        "blocked_now": [
            "broad body summarization",
            "automatic truth promotion",
            "moving/deleting/rewriting files",
            "vector memory over all docs",
            "private-note use without approval",
            "AI deciding final doctrine without Hermes/Chief/Operator review",
        ],
        "broad_ai_semantic_review_allowed_now": False,
        "final_doctrine_decision_by_ai_allowed": False,
        "operator_final_authority_required": True,
        "hermes_review_required_for_concept_coherence": True,
        "chief_reconciliation_required_for_completion_source_lineage": True,
    }


def _prior_lane_status(repo_root: str | Path, ref: str) -> str:
    return "OBSERVED" if (Path(repo_root) / ref).is_file() else "NOT_OBSERVED_OR_PENDING"


def build_openclaw_work_terrain_classification_candidate(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rules = default_classification_rules()
    examples = default_classification_examples()
    consolidations = default_consolidation_candidates()
    supersessions = default_supersession_candidates()
    ai_policy = future_ai_judgment_policy()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_classification_candidate_contract",
        "core_doctrine": {
            "terrain_records_broadly": True,
            "bodies_selectively": True,
            "truth_only_through_receipts": True,
            "classification_is_candidate_judgment_not_authority": True,
            "file_can_be_known_without_being_current": True,
            "note_can_be_useful_without_being_doctrine": True,
            "generated_artifact_can_be_evidence_without_source_truth": True,
            "consolidation_candidate_is_not_permission_to_rewrite": True,
            "archive_candidate_is_not_permission_to_archive": True,
            "supersession_candidate_is_not_permission_to_delete": True,
        },
        "classification_candidate_model": {
            "model_name": "WorkTerrainClassificationCandidate",
            "fields": list(CLASSIFICATION_CANDIDATE_FIELDS),
        },
        "classification_rule_model": {
            "model_name": "WorkTerrainClassificationRule",
            "fields": list(CLASSIFICATION_RULE_FIELDS),
        },
        "candidate_classifications": list(CLASSIFICATIONS),
        "artifact_types": list(ARTIFACT_TYPES),
        "classification_rules": [asdict(rule) for rule in rules],
        "default_classification_examples": [asdict(example) for example in examples],
        "consolidation_candidate_model": {
            "model_name": "WorkTerrainConsolidationCandidate",
            "fields": list(CONSOLIDATION_CANDIDATE_FIELDS),
            "rules": {
                "rewrite_allowed": False,
                "archive_old_fragments_allowed": False,
                "delete_old_fragments_allowed": False,
                "receipt_required_before_action": True,
            },
            "examples": [asdict(candidate) for candidate in consolidations],
        },
        "supersession_candidate_model": {
            "model_name": "WorkTerrainSupersessionCandidate",
            "fields": list(SUPERSESSION_CANDIDATE_FIELDS),
            "rules": {
                "archive_action_allowed": False,
                "delete_action_allowed": False,
                "receipt_required": True,
                "old_refs_remain_traceable": True,
            },
            "examples": [asdict(candidate) for candidate in supersessions],
        },
        "future_ai_judgment_policy": ai_policy,
        "relationship_to_prior_lanes": {
            "openclaw_work_terrain_query_contract": {
                "read_model_ref": QUERY_CONTRACT_READ_MODEL_REF,
                "relationship": "Prompt 1 defines metadata-first terrain queries.",
                "status": _prior_lane_status(repo_root, QUERY_CONTRACT_READ_MODEL_REF),
            },
            "openclaw_work_terrain_relationship_index": {
                "read_model_ref": RELATIONSHIP_INDEX_READ_MODEL_REF,
                "relationship": "Prompt 2 defines candidate relationships this lane classifies.",
                "status": _prior_lane_status(repo_root, RELATIONSHIP_INDEX_READ_MODEL_REF),
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "classification_candidate_model_exists": True,
            "classifications_exist": all(item in CLASSIFICATIONS for item in ("CURRENT_CANONICAL", "ARCHIVE_CANDIDATE", "UNKNOWN_FAIL_CLOSED")),
            "rules_exist": len(rules) == 10,
            "examples_exist": len(examples) == 10,
            "consolidation_candidate_exists": len(consolidations) == 3,
            "supersession_candidate_exists": len(supersessions) == 2,
            "future_ai_judgment_policy_exists": bool(ai_policy),
            "archive_delete_rewrite_false": all(
                not example.archive_action_allowed and not example.rewrite_action_allowed and not example.delete_action_allowed
                for example in examples
            ),
            "generated_artifacts_not_source_truth": any(rule.rule_id == "generated_read_models_are_not_doctrine" for rule in rules),
            "old_prompts_not_truth_by_default": any(rule.rule_id == "old_prompts_are_not_current_truth" for rule in rules),
            "repo_b_reference_only": any(example.candidate_id == "repo_b_planner_builder_reference_only" and example.candidate_classification == "REFERENCE_ONLY" for example in examples),
            "ai_judgment_blocked_now": ai_policy["broad_ai_semantic_review_allowed_now"] is False,
            "no_action_authority": True,
            "prior_lane_refs_represented": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_work_terrain_classification_candidate(payload: dict[str, Any]) -> str:
    ai_policy = payload["future_ai_judgment_policy"]
    lines = [
        "# OpenClaw Work Terrain Classification / Staleness Candidate v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract gives OpenClaw safe candidate labels for work terrain: current, supporting, old prompt, stale, duplicate, overlapping, generated, reference-only, source-card candidate, stable-map candidate, consolidation candidate, archive candidate, quarantine candidate, and fail-closed unknown. These labels are not final truth and do not allow cleanup.",
        "",
        "## What Candidate Classification Means",
        "",
        "- A current/stale/superseded label is a review candidate until receipts, source lineage, and review gates support it.",
        "- Old prompts can be history, residue, or future source-card candidates; they are not current doctrine by default.",
        "- Generated files are proof/detail, not human-authored doctrine by default.",
        "- Consolidation candidates are review packets, not permission to rewrite.",
        "- Supersession candidates keep old refs traceable; they are not permission to delete.",
        "",
        "## Default Examples",
        "",
    ]
    for example in payload["default_classification_examples"]:
        lines.append(
            f"- `{example['candidate_id']}`: `{example['candidate_classification']}` / {example['classification_reason']}"
        )
    lines.extend(
        [
            "",
            "## Consolidation / Supersession Boundary",
            "",
            "- Rewrite allowed: `false`",
            "- Archive old fragments allowed: `false`",
            "- Delete old fragments allowed: `false`",
            "- Receipt required before action: `true`",
            "",
            "## Future AI Judgment Policy",
            "",
            "- Allowed later after metadata and relationship classification: "
            + ", ".join(ai_policy["allowed_later_after_metadata_and_relationship_classification"]),
            "- Blocked now: " + ", ".join(ai_policy["blocked_now"]),
            "- Hermes reviews concept coherence. Chief reconciles completion/source lineage. Winship remains final authority.",
            "",
            "## Next Batch Lane",
            "",
            "- Prompt 4 will add a gap detector: missing source notes, built-but-unsurfaced artifacts, source notes without implementation, stable-map origin gaps, and receipt/test/commit gaps.",
            "",
            "## Boundary",
            "",
            "- No commit, staging, stable-map refresh, broad AI semantic review, raw body ingestion, broad private scan, file moves/deletes/rewrites/archive operations, network, git push/pull/fetch, Mac sync/import, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, C-drive scan/write, credential/account/browser/email/Coupa access, or authority escalation.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_work_terrain_classification_candidate(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkTerrainClassificationExportResult:
    payload = build_openclaw_work_terrain_classification_candidate(
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
    operator_path.write_text(format_openclaw_work_terrain_classification_candidate(payload), encoding="utf-8")
    return WorkTerrainClassificationExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        classification_candidate_count=len(payload["default_classification_examples"]),
        rule_count=len(payload["classification_rules"]),
        consolidation_candidate_count=len(payload["consolidation_candidate_model"]["examples"]),
        supersession_candidate_count=len(payload["supersession_candidate_model"]["examples"]),
        action_authority_granted=payload["authority_boundary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Work Terrain Classification Candidate.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_work_terrain_classification_candidate(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "classification_candidate_count": result.classification_candidate_count,
        "rule_count": result.rule_count,
        "consolidation_candidate_count": result.consolidation_candidate_count,
        "supersession_candidate_count": result.supersession_candidate_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Work Terrain Classification Candidate: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ARTIFACT_TYPES",
    "AUTHORITY_BOUNDARY",
    "CLASSIFICATIONS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "WorkTerrainClassificationCandidate",
    "WorkTerrainClassificationRule",
    "WorkTerrainConsolidationCandidate",
    "WorkTerrainSupersessionCandidate",
    "build_openclaw_work_terrain_classification_candidate",
    "default_classification_examples",
    "default_classification_rules",
    "default_consolidation_candidates",
    "default_supersession_candidates",
    "export_openclaw_work_terrain_classification_candidate",
    "format_openclaw_work_terrain_classification_candidate",
    "future_ai_judgment_policy",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
