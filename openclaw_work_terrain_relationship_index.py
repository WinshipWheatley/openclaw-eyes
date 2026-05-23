"""OpenClaw Work Terrain Relationship Index v0.

This read-model defines metadata-only relationship records between OpenClaw
terrain artifacts. It does not inspect raw bodies, scan private roots, classify
staleness, mutate files, refresh the stable map, or grant action authority.
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

SCHEMA_VERSION = "openclaw_work_terrain_relationship_index_v0"
READ_MODEL_ID = "openclaw_work_terrain_relationship_index"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

SOURCE_READ_MODEL_REF = "generated/read_models/openclaw_work_terrain_query_contract.json"
SOURCE_OPERATOR_REF = "generated/read_models/openclaw_work_terrain_query_contract_OPERATOR.md"

RELATIONSHIP_TYPES = (
    "DESCRIBES",
    "IMPLEMENTS",
    "VALIDATES",
    "EXPORTS",
    "SURFACES",
    "PROVES",
    "CLAIMS_COMPLETION",
    "SUPERSEDES",
    "DUPLICATES",
    "CONFLICTS_WITH",
    "DERIVED_FROM",
    "GENERATED_FROM",
    "REFERENCES",
    "OWNS",
    "BELONGS_TO_WORLD",
    "BELONGS_TO_LANE",
    "BELONGS_TO_ACTOR",
    "BUILT_NOT_SURFACED",
    "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT",
    "BUILT_ARTIFACT_LACKS_SOURCE_NOTE",
    "SOURCE_NOTE_LACKS_BUILT_ARTIFACT",
    "STABLE_MAP_SECTION_LACKS_SOURCE_NOTE",
    "UNKNOWN_FAIL_CLOSED",
)

RELATIONSHIP_STATUSES = (
    "CANDIDATE",
    "METADATA_LINKED",
    "RECEIPT_LINKED",
    "TEST_LINKED",
    "COMMIT_LINKED",
    "STABLE_MAP_LINKED",
    "RECONCILED_WITH_PROOF",
    "NEEDS_CHIEF_RECONCILIATION",
    "NEEDS_HERMES_REVIEW",
    "NEEDS_OPERATOR_REVIEW",
    "CONFLICTING",
    "STALE_OR_SUPERSEDED",
    "UNKNOWN_FAIL_CLOSED",
)

ENTITY_ARTIFACT_TYPES = (
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

OUTPUT_SHAPE_NAMES = (
    "SourceNotesDescribingBuiltArtifacts",
    "BuiltArtifactsLackingSourceNotes",
    "StableMapSectionsLackingSourceOrigin",
    "MarkdownIdeasWithoutImplementation",
    "GeneratedReadModelsAsProofDetail",
    "DuplicateOrOverlappingConcepts",
    "WorldLaneActorOwnership",
    "ReceiptsSupportingCompletion",
)

ACTORS = (
    "Chief",
    "Guardian",
    "Cassandra",
    "Hermes",
    "Niles",
    "Codex",
    "Gemini / Agy",
    "Operator / Winship",
)

WORLDS = (
    "Finance",
    "Build",
    "Security",
    "Music / Art",
    "Communications",
    "Operations",
    "Research",
    "Business Development",
)

LANES_AND_CONCEPTS = (
    "Capital Hilton",
    "Security Pass",
    "Work Terrain",
    "Markdown Atlas",
    "Agent Council",
    "Package Preview",
    "Tool Adapter Receipt",
    "Stable Map",
    "Mission Control",
    "Repo B Planner / Builder",
    "Struna",
    "Niles Producer lane",
)

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "body_ingestion_allowed": False,
    "broad_private_root_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "file_archive_allowed": False,
    "auto_promotion_allowed": False,
    "auto_stable_map_update_allowed": False,
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
    "credential_account_browser_email_coupa_access_allowed": False,
    "authority_escalation_allowed": False,
}


RELATIONSHIP_RECORD_FIELDS = (
    "relationship_id",
    "relationship_type",
    "source_ref",
    "target_ref",
    "source_artifact_type",
    "target_artifact_type",
    "source_lane",
    "target_lane",
    "source_actor",
    "target_actor",
    "source_world",
    "target_world",
    "evidence_refs",
    "receipt_refs",
    "stable_map_refs",
    "sqlite_refs",
    "read_model_refs",
    "commit_refs",
    "confidence_posture",
    "relationship_status",
    "requires_chief_reconciliation",
    "requires_hermes_review",
    "requires_guardian_review",
    "operator_review_required",
    "authority_granted",
    "next_safe_move",
)

OUTPUT_SHAPE_FIELDS = (
    "query_name",
    "input_refs",
    "candidate_relationships",
    "missing_relationships",
    "review_required",
    "next_safe_move",
)

POLICY_FIELDS = (
    "metadata_only",
    "body_ingestion_allowed",
    "relationship_truth_status",
    "auto_promotion_allowed",
    "auto_archive_allowed",
    "auto_rewrite_allowed",
    "auto_delete_allowed",
    "stable_map_update_allowed",
    "chief_reconciliation_role",
    "hermes_review_role",
    "operator_final_authority",
)


@dataclass(frozen=True)
class WorkTerrainRelationshipRecord:
    relationship_id: str
    relationship_type: str
    source_ref: str
    target_ref: str
    source_artifact_type: str
    target_artifact_type: str
    source_lane: str
    target_lane: str
    source_actor: str
    target_actor: str
    source_world: str
    target_world: str
    evidence_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    sqlite_refs: tuple[str, ...]
    read_model_refs: tuple[str, ...]
    commit_refs: tuple[str, ...]
    confidence_posture: str
    relationship_status: str
    requires_chief_reconciliation: bool
    requires_hermes_review: bool
    requires_guardian_review: bool
    operator_review_required: bool
    authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainRelationshipOutputShape:
    query_name: str
    input_refs: tuple[str, ...]
    candidate_relationships: tuple[str, ...]
    missing_relationships: tuple[str, ...]
    review_required: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainRelationshipPolicy:
    metadata_only: bool
    body_ingestion_allowed: bool
    relationship_truth_status: str
    auto_promotion_allowed: bool
    auto_archive_allowed: bool
    auto_rewrite_allowed: bool
    auto_delete_allowed: bool
    stable_map_update_allowed: bool
    chief_reconciliation_role: str
    hermes_review_role: str
    operator_final_authority: str


@dataclass(frozen=True)
class WorkTerrainRelationshipIndexExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    relationship_count: int
    output_shape_count: int
    ownership_actor_count: int
    body_ingestion_allowed: bool
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _record(
    relationship_id: str,
    *,
    relationship_type: str,
    source_ref: str,
    target_ref: str,
    source_artifact_type: str,
    target_artifact_type: str,
    source_lane: str = "unknown",
    target_lane: str = "unknown",
    source_actor: str = "unknown",
    target_actor: str = "unknown",
    source_world: str = "unknown",
    target_world: str = "unknown",
    evidence_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    stable_map_refs: tuple[str, ...] = (),
    sqlite_refs: tuple[str, ...] = (),
    read_model_refs: tuple[str, ...] = (),
    commit_refs: tuple[str, ...] = (),
    confidence_posture: str = "CANDIDATE_METADATA_ONLY",
    relationship_status: str = "CANDIDATE",
    requires_chief_reconciliation: bool = False,
    requires_hermes_review: bool = False,
    requires_guardian_review: bool = False,
    operator_review_required: bool = False,
    next_safe_move: str,
) -> WorkTerrainRelationshipRecord:
    return WorkTerrainRelationshipRecord(
        relationship_id=relationship_id,
        relationship_type=relationship_type,
        source_ref=source_ref,
        target_ref=target_ref,
        source_artifact_type=source_artifact_type,
        target_artifact_type=target_artifact_type,
        source_lane=source_lane,
        target_lane=target_lane,
        source_actor=source_actor,
        target_actor=target_actor,
        source_world=source_world,
        target_world=target_world,
        evidence_refs=evidence_refs,
        receipt_refs=receipt_refs,
        stable_map_refs=stable_map_refs,
        sqlite_refs=sqlite_refs,
        read_model_refs=read_model_refs,
        commit_refs=commit_refs,
        confidence_posture=confidence_posture,
        relationship_status=relationship_status,
        requires_chief_reconciliation=requires_chief_reconciliation,
        requires_hermes_review=requires_hermes_review,
        requires_guardian_review=requires_guardian_review,
        operator_review_required=operator_review_required,
        authority_granted=False,
        next_safe_move=next_safe_move,
    )


def default_relationship_examples() -> tuple[WorkTerrainRelationshipRecord, ...]:
    return (
        _record(
            "chief_test_harness_source_to_contract",
            relationship_type="SOURCE_NOTE_MATCHES_BUILT_ARTIFACT",
            source_ref="source_concept://chief/test_harness_cross_off",
            target_ref="chief_test_harness_cross_off_receipt_contract.py",
            source_artifact_type="SOURCE_NOTE",
            target_artifact_type="PYTHON_CONTRACT",
            source_lane="Chief / cross-off",
            target_lane="chief_test_harness_cross_off",
            source_actor="Chief",
            target_actor="Chief",
            source_world="Build",
            target_world="Build",
            evidence_refs=("tests/test_chief_test_harness_cross_off_receipt_contract.py",),
            stable_map_refs=("stable_map.chief_test_harness_cross_off",),
            read_model_refs=("generated/read_models/chief_test_harness_cross_off_receipt_contract.json",),
            relationship_status="TEST_LINKED",
            requires_chief_reconciliation=True,
            next_safe_move="Chief can reconcile source lineage against tests, receipts, and stable-map visibility later.",
        ),
        _record(
            "capital_hilton_proof_intake_contract_to_surface",
            relationship_type="SURFACES",
            source_ref="capital_hilton_protected_proof_intake.py",
            target_ref="mission_control_surface://capital_hilton/proof_intake",
            source_artifact_type="PYTHON_CONTRACT",
            target_artifact_type="MISSION_CONTROL_SURFACE",
            source_lane="Capital Hilton",
            target_lane="Capital Hilton",
            source_actor="Cassandra",
            target_actor="Cassandra",
            source_world="Finance",
            target_world="Finance",
            evidence_refs=("build proof metadata", "screenshot proof metadata"),
            stable_map_refs=("stable_map.capital_hilton_protected_proof_intake",),
            read_model_refs=("generated/read_models/capital_hilton_protected_proof_intake.json",),
            relationship_status="STABLE_MAP_LINKED",
            requires_guardian_review=True,
            operator_review_required=True,
            next_safe_move="Keep action blocked; use the surface to collect metadata-only proof references later.",
        ),
        _record(
            "capital_hilton_proof_resolution_backend_links",
            relationship_type="BELONGS_TO_LANE",
            source_ref="capital_hilton_proof_resolution_batch_v0",
            target_ref="lane://finance/capital_hilton",
            source_artifact_type="PACKAGE",
            target_artifact_type="LANE",
            source_lane="Capital Hilton",
            target_lane="Capital Hilton",
            source_actor="Codex",
            target_actor="Cassandra",
            source_world="Finance",
            target_world="Finance",
            evidence_refs=(
                "capital_hilton_answer_candidate_receipt.py",
                "capital_hilton_protected_reference_placeholder.py",
                "capital_hilton_guardian_review_packet.py",
                "capital_hilton_proof_quieting_progress_state.py",
            ),
            stable_map_refs=(
                "stable_map.capital_hilton_answer_candidate_receipt",
                "stable_map.capital_hilton_protected_reference_placeholder",
                "stable_map.capital_hilton_guardian_review_packet",
                "stable_map.capital_hilton_proof_quieting_progress_state",
            ),
            read_model_refs=(
                "generated/read_models/capital_hilton_answer_candidate_receipt.json",
                "generated/read_models/capital_hilton_protected_reference_placeholder.json",
                "generated/read_models/capital_hilton_guardian_review_packet.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            relationship_status="METADATA_LINKED",
            requires_guardian_review=True,
            operator_review_required=True,
            next_safe_move="Use these links as backend rails only; invoice/Coupa/browser/email/send authority remains blocked.",
        ),
        _record(
            "markdown_knowledge_atlas_built_not_prominently_surfaced",
            relationship_type="BUILT_NOT_SURFACED",
            source_ref="markdown_knowledge_atlas.py",
            target_ref="stable_map.section://markdown_knowledge_atlas",
            source_artifact_type="PYTHON_CONTRACT",
            target_artifact_type="STABLE_MAP_SECTION",
            source_lane="Markdown Atlas",
            target_lane="Work Terrain",
            source_actor="Codex",
            target_actor="Chief",
            source_world="Operations",
            target_world="Operations",
            evidence_refs=("scripts/build_markdown_knowledge_atlas.py", "markdown_evidence_ingestion.py", "corpus_atlas.py"),
            relationship_status="NEEDS_CHIEF_RECONCILIATION",
            requires_chief_reconciliation=True,
            requires_hermes_review=True,
            next_safe_move="Chief/Hermes can later decide whether visibility or consolidation is warranted.",
        ),
        _record(
            "security_pass_contract_to_security_pass_surface",
            relationship_type="SURFACES",
            source_ref="security_pass_contract.py",
            target_ref="mission_control_surface://security_pass_cockpit",
            source_artifact_type="PYTHON_CONTRACT",
            target_artifact_type="MISSION_CONTROL_SURFACE",
            source_lane="Security Pass",
            target_lane="Security Pass",
            source_actor="Guardian",
            target_actor="Guardian",
            source_world="Security",
            target_world="Security",
            evidence_refs=("tests/test_security_pass_contract.py",),
            stable_map_refs=("stable_map.security_pass",),
            read_model_refs=("generated/read_models/security_pass_contract.json",),
            relationship_status="STABLE_MAP_LINKED",
            next_safe_move="Keep the surface read-only; use receipts and tests for completion proof.",
        ),
        _record(
            "future_invoicing_audit_to_parked_stress_test",
            relationship_type="DERIVED_FROM",
            source_ref="worker_report://agy_gemini/future_invoicing_audit",
            target_ref="parked_autonomous_capital_pipeline_experiment.py",
            source_artifact_type="WORKER_REPORT",
            target_artifact_type="PYTHON_CONTRACT",
            source_lane="Capital experiment stress test",
            target_lane="parked_autonomous_capital_pipeline_experiment",
            source_actor="Gemini / Agy",
            target_actor="Codex",
            source_world="Research",
            target_world="Research",
            stable_map_refs=("stable_map.parked_autonomous_capital_pipeline_experiment",),
            read_model_refs=("generated/read_models/parked_autonomous_capital_pipeline_experiment.json",),
            relationship_status="RECONCILED_WITH_PROOF",
            requires_hermes_review=True,
            next_safe_move="Preserve as parked stress-test artifact; do not treat it as implementation authority.",
        ),
        _record(
            "repo_b_planner_builder_reference_only",
            relationship_type="REFERENCES",
            source_ref="concept://repo_b_planner_builder",
            target_ref="repo_b_reference://planner_builder_orchestrator",
            source_artifact_type="SOURCE_NOTE",
            target_artifact_type="PACKAGE",
            source_lane="Repo B Planner / Builder",
            target_lane="Repo B Planner / Builder",
            source_actor="Operator / Winship",
            target_actor="Chief",
            source_world="Build",
            target_world="Build",
            confidence_posture="REFERENCE_ONLY_METADATA",
            relationship_status="CANDIDATE",
            requires_hermes_review=True,
            next_safe_move="Keep Repo B reference-only unless an explicit bounded approval opens a future lane.",
        ),
        _record(
            "generated_operator_markdown_is_proof_detail",
            relationship_type="GENERATED_FROM",
            source_ref="generated/read_models/*_OPERATOR.md",
            target_ref="generated/read_models/*.json",
            source_artifact_type="GENERATED_OPERATOR_DIGEST",
            target_artifact_type="GENERATED_READ_MODEL",
            source_lane="Generated read-models",
            target_lane="Generated read-models",
            source_actor="Codex",
            target_actor="Operator / Winship",
            source_world="Operations",
            target_world="Operations",
            confidence_posture="PROOF_DETAIL_NOT_HUMAN_DOCTRINE",
            relationship_status="METADATA_LINKED",
            next_safe_move="Treat generated operator Markdown as digest/proof detail unless a source-card promotion is later receipted.",
        ),
    )


def default_output_shapes() -> tuple[WorkTerrainRelationshipOutputShape, ...]:
    return tuple(
        WorkTerrainRelationshipOutputShape(
            query_name=name,
            input_refs=("metadata_query_result_refs",),
            candidate_relationships=("relationship_record_ids",),
            missing_relationships=("missing_source_note_refs", "missing_receipt_refs"),
            review_required=("Chief", "Hermes", "Guardian where protected", "Operator where final authority is needed"),
            next_safe_move="Return candidate relationship records only; do not ingest bodies, mutate files, or promote truth.",
        )
        for name in OUTPUT_SHAPE_NAMES
    )


def default_relationship_policy() -> WorkTerrainRelationshipPolicy:
    return WorkTerrainRelationshipPolicy(
        metadata_only=True,
        body_ingestion_allowed=False,
        relationship_truth_status="candidate_until_receipted",
        auto_promotion_allowed=False,
        auto_archive_allowed=False,
        auto_rewrite_allowed=False,
        auto_delete_allowed=False,
        stable_map_update_allowed=False,
        chief_reconciliation_role="Chief may later reconcile completion, source lineage, tests, receipts, and cross-off proof.",
        hermes_review_role="Hermes may later review concept coherence and overlapping doctrine without rewriting files.",
        operator_final_authority="Operator remains final authority for promotion, archive, rewrite, deletion, action, or source-truth decisions.",
    )


def default_ownership_map() -> dict[str, Any]:
    return {
        "metadata_only": True,
        "unknowns_fail_closed": True,
        "actors": [
            {"actor": actor, "artifact_type": "ACTOR", "authority_granted": False}
            for actor in ACTORS
        ],
        "worlds": [
            {"world": world, "artifact_type": "WORLD", "runtime_authority_granted": False}
            for world in WORLDS
        ],
        "lanes_and_concepts": [
            {
                "lane_or_concept": lane,
                "artifact_type": "LANE",
                "classification_status": "metadata_candidate",
                "authority_granted": False,
            }
            for lane in LANES_AND_CONCEPTS
        ],
        "common_mappings": [
            {
                "lane": "Capital Hilton",
                "world": "Finance",
                "actors": ["Cassandra", "Guardian", "Operator / Winship"],
                "notes": "Proof metadata and protected reference lane; action remains blocked.",
            },
            {
                "lane": "Security Pass",
                "world": "Security",
                "actors": ["Guardian", "Hermes", "Chief"],
                "notes": "Read-only security posture and authority-boundary review.",
            },
            {
                "lane": "Work Terrain",
                "world": "Operations",
                "actors": ["Chief", "Hermes", "Codex"],
                "notes": "Metadata relationship, classification, and gap detection only.",
            },
            {
                "lane": "Niles Producer lane",
                "world": "Music / Art",
                "actors": ["Niles", "Operator / Winship"],
                "notes": "Creative terrain; no runtime action implied by relationship metadata.",
            },
        ],
    }


def _source_query_contract_observed(repo_root: str | Path) -> bool:
    root = Path(repo_root)
    return (root / SOURCE_READ_MODEL_REF).is_file() and (root / SOURCE_OPERATOR_REF).is_file()


def build_openclaw_work_terrain_relationship_index(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    relationships = default_relationship_examples()
    output_shapes = default_output_shapes()
    policy = default_relationship_policy()
    ownership = default_ownership_map()
    prompt_1_observed = _source_query_contract_observed(repo_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_relationship_index_contract",
        "core_doctrine": {
            "terrain_records_broadly": True,
            "bodies_selectively": True,
            "truth_only_through_receipts": True,
            "relationship_record_does_not_make_truth": True,
            "relationship_record_grants_authority": False,
            "source_note_linked_to_artifact_does_not_prove_completion": True,
            "built_artifact_without_source_note_is_reconciliation_gap": True,
            "generated_artifacts_are_proof_detail_not_doctrine_by_default": True,
        },
        "relationship_record_model": {
            "model_name": "WorkTerrainRelationshipRecord",
            "fields": list(RELATIONSHIP_RECORD_FIELDS),
        },
        "relationship_types": list(RELATIONSHIP_TYPES),
        "relationship_statuses": list(RELATIONSHIP_STATUSES),
        "entity_artifact_types": list(ENTITY_ARTIFACT_TYPES),
        "relationship_query_output_shapes": {
            "model_name": "WorkTerrainRelationshipOutputShape",
            "fields": list(OUTPUT_SHAPE_FIELDS),
            "shapes": [asdict(shape) for shape in output_shapes],
            "live_query_engine_implemented": False,
        },
        "default_relationship_examples": [asdict(record) for record in relationships],
        "ownership_map": ownership,
        "work_terrain_relationship_policy": asdict(policy),
        "relationship_to_prompt_1": {
            "extends": "openclaw_work_terrain_query_contract",
            "source_read_model_ref": SOURCE_READ_MODEL_REF,
            "source_operator_ref": SOURCE_OPERATOR_REF,
            "prompt_1_observed": prompt_1_observed,
            "prompt_1_status": "OBSERVED" if prompt_1_observed else "NOT_OBSERVED_OR_PENDING",
            "does_not_duplicate_prompt_1": True,
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "relationship_record_model_exists": True,
            "relationship_types_exist": all(item in RELATIONSHIP_TYPES for item in ("BUILT_NOT_SURFACED", "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT")),
            "relationship_statuses_exist": "UNKNOWN_FAIL_CLOSED" in RELATIONSHIP_STATUSES,
            "entity_artifact_types_exist": "GENERATED_OPERATOR_DIGEST" in ENTITY_ARTIFACT_TYPES,
            "output_shapes_exist": len(output_shapes) == len(OUTPUT_SHAPE_NAMES),
            "default_examples_exist": len(relationships) == 8,
            "built_not_surfaced_relationship_exists": any(record.relationship_type == "BUILT_NOT_SURFACED" for record in relationships),
            "source_note_built_artifact_relationships_exist": any(record.relationship_type == "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT" for record in relationships),
            "generated_operator_markdown_is_proof_detail_not_doctrine": any(
                record.relationship_id == "generated_operator_markdown_is_proof_detail"
                and record.confidence_posture == "PROOF_DETAIL_NOT_HUMAN_DOCTRINE"
                for record in relationships
            ),
            "repo_b_reference_only": any(
                record.relationship_id == "repo_b_planner_builder_reference_only"
                and record.confidence_posture == "REFERENCE_ONLY_METADATA"
                for record in relationships
            ),
            "ownership_map_exists": bool(ownership["actors"]) and bool(ownership["worlds"]) and bool(ownership["lanes_and_concepts"]),
            "no_action_authority": True,
            "no_body_ingestion": policy.body_ingestion_allowed is False,
            "no_file_mutation": all(
                AUTHORITY_BOUNDARY[key] is False
                for key in ("file_move_allowed", "file_delete_allowed", "file_rename_allowed", "file_rewrite_allowed")
            ),
            "no_auto_stable_map_promotion": policy.stable_map_update_allowed is False,
            "chief_hermes_guardian_review_fields_exist": all(
                field in RELATIONSHIP_RECORD_FIELDS
                for field in ("requires_chief_reconciliation", "requires_hermes_review", "requires_guardian_review")
            ),
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_work_terrain_relationship_index(payload: dict[str, Any]) -> str:
    policy = payload["work_terrain_relationship_policy"]
    lines = [
        "# OpenClaw Work Terrain Relationship Index v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract defines how OpenClaw terrain records can be linked without pretending the links are proof. A Markdown source note can describe a built contract, a Python file can export a read-model, a test can validate it, a stable-map section can surface it, and a receipt can later prove completion. This lane only models those relationships.",
        "",
        "## Why Relationships Matter",
        "",
        "- Source notes can describe built artifacts, but the source note does not prove the artifact is complete.",
        "- Built artifacts can exist without a source note; that is a reconciliation gap, not an automatic error.",
        "- Stable-map sections can exist without a clear source origin; that needs lineage review before doctrine promotion.",
        "- Generated read-models and operator Markdown are proof/detail digests by default, not human-authored doctrine.",
        "",
        "## Default Relationship Examples",
        "",
    ]
    for record in payload["default_relationship_examples"]:
        lines.append(
            f"- `{record['relationship_id']}`: `{record['relationship_type']}` / `{record['relationship_status']}`"
        )
    lines.extend(
        [
            "",
            "## Review Roles",
            "",
            f"- Chief: {policy['chief_reconciliation_role']}",
            f"- Hermes: {policy['hermes_review_role']}",
            f"- Operator: {policy['operator_final_authority']}",
            "- Guardian reviews protected/sensitive metadata lanes only; Guardian review is not action approval.",
            "",
            "## Policy",
            "",
            f"- Metadata only: `{str(policy['metadata_only']).lower()}`",
            f"- Body ingestion allowed: `{str(policy['body_ingestion_allowed']).lower()}`",
            f"- Relationship truth status: `{policy['relationship_truth_status']}`",
            f"- Auto-promotion allowed: `{str(policy['auto_promotion_allowed']).lower()}`",
            f"- Auto-archive/rewrite/delete allowed: `{str(any(policy[key] for key in ('auto_archive_allowed', 'auto_rewrite_allowed', 'auto_delete_allowed'))).lower()}`",
            f"- Stable-map update allowed in this lane: `{str(policy['stable_map_update_allowed']).lower()}`",
            "",
            "## What The Next Lane Adds",
            "",
            "- Prompt 3 will add classification/staleness candidate states: current, old prompt, superseded, overlapping, source-missing, surfaced-missing, and review-needed candidates.",
            "",
            "## Boundary",
            "",
            "- No file moves, deletes, renames, rewrites, archive actions, body ingestion, broad private scan, semantic review, stable-map refresh, Mac sync/import, network, git push/pull/fetch, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, account/browser/email/Coupa access, credentials, or authority escalation.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_work_terrain_relationship_index(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkTerrainRelationshipIndexExportResult:
    payload = build_openclaw_work_terrain_relationship_index(
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
    operator_path.write_text(format_openclaw_work_terrain_relationship_index(payload), encoding="utf-8")
    return WorkTerrainRelationshipIndexExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        relationship_count=len(payload["default_relationship_examples"]),
        output_shape_count=len(payload["relationship_query_output_shapes"]["shapes"]),
        ownership_actor_count=len(payload["ownership_map"]["actors"]),
        body_ingestion_allowed=payload["authority_boundary"]["body_ingestion_allowed"],
        action_authority_granted=payload["authority_boundary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Work Terrain Relationship Index.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_work_terrain_relationship_index(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "relationship_count": result.relationship_count,
        "output_shape_count": result.output_shape_count,
        "ownership_actor_count": result.ownership_actor_count,
        "body_ingestion_allowed": result.body_ingestion_allowed,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Work Terrain Relationship Index: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "ENTITY_ARTIFACT_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "OUTPUT_SHAPE_NAMES",
    "READ_MODEL_ID",
    "RELATIONSHIP_STATUSES",
    "RELATIONSHIP_TYPES",
    "SCHEMA_VERSION",
    "WorkTerrainRelationshipOutputShape",
    "WorkTerrainRelationshipPolicy",
    "WorkTerrainRelationshipRecord",
    "build_openclaw_work_terrain_relationship_index",
    "default_output_shapes",
    "default_relationship_examples",
    "default_relationship_policy",
    "default_ownership_map",
    "export_openclaw_work_terrain_relationship_index",
    "format_openclaw_work_terrain_relationship_index",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
