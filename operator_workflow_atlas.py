"""Operator workflow atlas and gap scan v0.

This module builds a deterministic read-model from named Repo A evidence
surfaces. It treats old docs/files as evidence only, does not scan broad
private roots, and does not grant runtime, send, submit, deployment, or
approval authority.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


SCHEMA_VERSION = "operator_workflow_atlas_v0"
JSON_EXPORT_NAME = "operator_workflow_atlas.json"
OPERATOR_EXPORT_NAME = "operator_workflow_atlas_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

STATUS_CATEGORIES = (
    "CONFIRMED_BUILT_AND_WIRED",
    "BUILT_NOT_WIRED_TO_STEEL_THREAD",
    "PLANNED_NOT_BUILT",
    "DESIRED_INFERRED_FROM_EVIDENCE",
    "LEGACY_OR_STALE_EVIDENCE",
    "BLOCKED_BY_MISSING_INGEST_OR_TAGGING",
    "SHOULD_NOT_BUILD_YET",
    "UNKNOWN_NEEDS_OPERATOR_CONFIRMATION",
)

CONFIDENCE_LEVELS = ("high", "medium", "low")

NO_AUTHORITY_FLAGS = {
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "customer_deployment_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "approval_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_executed": False,
    "broad_private_ingest_performed": False,
}

EVIDENCE_NOT_TRUTH_STATUSES = {
    "governed_read_model_evidence",
    "operator_doc_evidence_only",
    "contract_doc_evidence_only",
    "code_metadata_evidence_only",
    "legacy_or_stale_evidence_only",
    "synthetic_example_evidence_only",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _repo_path(path: str | Path, *, repo_root: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _evidence(
    path: str,
    *,
    role: str,
    truth_status: str,
    repo_root: str | Path,
    confidence: str = "medium",
) -> dict[str, Any]:
    if truth_status not in EVIDENCE_NOT_TRUTH_STATUSES:
        raise ValueError(f"unsupported evidence truth_status: {truth_status}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"unsupported evidence confidence: {confidence}")
    absolute = _repo_path(path, repo_root=repo_root)
    return {
        "path": path,
        "source_present": absolute.exists(),
        "evidence_role": role,
        "truth_status": truth_status,
        "confidence": confidence,
    }


def _workflow(
    *,
    workflow_name: str,
    domain_world: str,
    operator_value: str,
    current_evidence_sources: tuple[dict[str, Any], ...],
    current_implementation_status: str,
    steel_thread_readiness: str,
    shared_bottleneck: str,
    next_safe_lane: str,
    confidence: str,
    operator_confirmation_needed: bool,
    confirmation_reason: str,
) -> dict[str, Any]:
    if current_implementation_status not in STATUS_CATEGORIES:
        raise ValueError(f"unsupported workflow status: {current_implementation_status}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"unsupported workflow confidence: {confidence}")
    if not current_evidence_sources:
        raise ValueError(f"workflow needs evidence: {workflow_name}")
    for source in current_evidence_sources:
        if source["truth_status"] not in EVIDENCE_NOT_TRUTH_STATUSES:
            raise ValueError(f"workflow source promoted to truth: {workflow_name}")
    return {
        "workflow_name": workflow_name,
        "domain_world": domain_world,
        "operator_value": operator_value,
        "current_evidence_sources": list(current_evidence_sources),
        "current_implementation_status": current_implementation_status,
        "steel_thread_readiness": steel_thread_readiness,
        "shared_bottleneck": shared_bottleneck,
        "next_safe_lane": next_safe_lane,
        "confidence": confidence,
        "operator_confirmation_needed": operator_confirmation_needed,
        "confirmation_reason": confirmation_reason,
        "old_files_treated_as_evidence_not_truth": True,
    }


def build_workflow_atlas(*, repo_root: str | Path = Path("."), generated_at: str | None = None) -> dict[str, Any]:
    root = Path(repo_root)
    workflows = _workflow_records(repo_root=root)
    recommendations = _recommended_first_three_lanes()
    status_counts = Counter(item["current_implementation_status"] for item in workflows)
    confidence_counts = Counter(item["confidence"] for item in workflows)
    bottleneck_map = _shared_bottleneck_map(workflows)
    sufficiency = _markdown_source_classification_sufficiency()
    gate_pass_count = sum(
        1 for item in recommendations if item["post_preflight_gate_evaluation"]["gate_status"] == PASS
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "repo_a_canonical": True,
        "repo_b_model": "pre_split_capability_tree_reference_only",
        "old_files_treated_as_evidence_not_truth": True,
        "operator_manual_rewrite_required": False,
        "operator_manual_rewrite_reason": (
            "Existing Repo A read-models/docs expose enough workflow evidence to propose the next batch lanes. "
            "Operator confirmation is still required for specific facts and authority gates."
        ),
        "workflows_classified_with_confidence": True,
        "status_categories": list(STATUS_CATEGORIES),
        "confidence_levels": list(CONFIDENCE_LEVELS),
        "workflow_count": len(workflows),
        "workflow_status_counts": dict(sorted(status_counts.items())),
        "workflow_confidence_counts": dict(sorted(confidence_counts.items())),
        "workflow_atlas": workflows,
        "built_implemented": _names_with_status(workflows, "CONFIRMED_BUILT_AND_WIRED"),
        "built_not_integrated": _names_with_status(workflows, "BUILT_NOT_WIRED_TO_STEEL_THREAD"),
        "desired_not_built": [
            item["workflow_name"]
            for item in workflows
            if item["current_implementation_status"]
            in {
                "PLANNED_NOT_BUILT",
                "DESIRED_INFERRED_FROM_EVIDENCE",
                "BLOCKED_BY_MISSING_INGEST_OR_TAGGING",
                "UNKNOWN_NEEDS_OPERATOR_CONFIRMATION",
            }
        ],
        "not_built_should_not_build_yet": _names_with_status(workflows, "SHOULD_NOT_BUILD_YET"),
        "shared_bottleneck_map": bottleneck_map,
        "markdown_source_classification_sufficiency": sufficiency,
        "md_source_ingestion_required_before_next_batch": sufficiency[
            "required_before_next_post_preflight_batch"
        ],
        "recommended_first_3_post_preflight_batch_lanes": recommendations,
        "batch_gate_used": True,
        "batch_gate_pass_count": gate_pass_count,
        "batch_gate_all_recommendations_pass": gate_pass_count == len(recommendations),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _workflow_records(*, repo_root: Path) -> list[dict[str, Any]]:
    return [
        _workflow(
            workflow_name="Capital Hilton invoice manual review",
            domain_world="finance_ap_invoice",
            operator_value=(
                "Lets Winship manually prepare the Capital Hilton/Coupa invoice from governed facts, "
                "with PO and recipient gates still explicit."
            ),
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/capital_hilton_actionable_review_packet.json",
                    role="actionable review-only packet",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/cassandra_governed_review_packet_request_proof.json",
                    role="generic governed review packet proof",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/cassandra_clara_fact_packet.json",
                    role="Cassandra/Clara governed facts packet",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="CONFIRMED_BUILT_AND_WIRED",
            steel_thread_readiness="review_only_packet_visible_and_mirrored_no_send_or_submit",
            shared_bottleneck="manual_confirmation_receipt_binding",
            next_safe_lane="Capital Hilton Manual Coupa PO Confirmation v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="PO/Coupa state, recipient posture, and final inclusion remain manual confirmation gates.",
        ),
        _workflow(
            workflow_name="Cassandra governed request to review packet",
            domain_world="operator_comms_to_review_packet",
            operator_value="Turns a governed Cassandra/Clara ask into a review-only packet without send authority.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/cassandra_governed_review_packet_request_proof.json",
                    role="request route and proof receipts",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/cassandra_send_status_dry_run.json",
                    role="send-capable service dry-run status",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="CONFIRMED_BUILT_AND_WIRED",
            steel_thread_readiness="works_for_capital_hilton_review_packet_review_only",
            shared_bottleneck="generic_review_packet_contract",
            next_safe_lane="Reuse Generic Review Packet For Second Workflow v0",
            confidence="high",
            operator_confirmation_needed=False,
            confirmation_reason="Workflow proof exists; future workflows still need their own evidence packets.",
        ),
        _workflow(
            workflow_name="Guardian HITL observational receipts",
            domain_world="approval_hitl_authority",
            operator_value="Shows request/decision/proposal approval evidence in SQLite without switching runtime authority.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/guardian_hitl_dual_write_compatibility.json",
                    role="Chief request and decision receipt support",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "docs/operations/GUARDIAN_HITL_DUAL_WRITE_RECEIPT_PROOF_V0.md",
                    role="operator proof note",
                    truth_status="operator_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/guardian_hitl_cassandra_proposal_shadow.json",
                    role="Cassandra HITL proposal shadow",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="CONFIRMED_BUILT_AND_WIRED",
            steel_thread_readiness="observational_only_old_json_still_authoritative",
            shared_bottleneck="approval_receipt_equivalence",
            next_safe_lane="HITL Transition Criteria Review v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Caller switching, old JSON retirement, and send authority remain separate operator decisions.",
        ),
        _workflow(
            workflow_name="Cassandra/Chief structured fact evidence",
            domain_world="memory_authority",
            operator_value="Provides parsed contact/invoice/email posture facts as evidence, not truth, for review packets.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/cassandra_chief_structured_fact_import.json",
                    role="approved structured fact import read-model",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/cassandra_chief_memory_import_approval.json",
                    role="operator approval receipt for categories",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="CONFIRMED_BUILT_AND_WIRED",
            steel_thread_readiness="available_as_parsed_evidence_not_truth_no_send_authority",
            shared_bottleneck="sqlite_fact_coverage",
            next_safe_lane="Operator Confirmation Packet For Imported Facts v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Imported records need operator confirmation before external use.",
        ),
        _workflow(
            workflow_name="Cassandra live receive into governed intake",
            domain_world="operator_comms",
            operator_value="Lets Cassandra receive operator messages through governed intake metadata without replies or sends.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/cassandra_listener_governed_intake_synthetic_proof.json",
                    role="receive path proof and live-test posture",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/cassandra_listener_governed_shadow.json",
                    role="legacy listener to governed intake mapping",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="medium",
                ),
            ),
            current_implementation_status="BUILT_NOT_WIRED_TO_STEEL_THREAD",
            steel_thread_readiness="receive_metadata_path_exists_but_work_packet_projection_needs_current_proof",
            shared_bottleneck="governed_receive_to_work_packet_projection",
            next_safe_lane="Cassandra Intake-to-Work Packet Current Proof v0",
            confidence="medium",
            operator_confirmation_needed=False,
            confirmation_reason="No new operator facts needed, but current live proof should be refreshed before authority decisions.",
        ),
        _workflow(
            workflow_name="Work Board and Agent Work Packets",
            domain_world="work_routing",
            operator_value="Turns governed intents into visible work routing artifacts without auto-execution.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/work_board.json",
                    role="read-only Work Board status",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/agent_work_packets.json",
                    role="agent packet read-model",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/intent_router.json",
                    role="non-executing intent routing",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="BUILT_NOT_WIRED_TO_STEEL_THREAD",
            steel_thread_readiness="substrate_exists_but_zero_or_limited_live_projection_for_new_workflows",
            shared_bottleneck="governed_receive_to_work_packet_projection",
            next_safe_lane="Cassandra Intake-to-Work Packet Current Proof v0",
            confidence="high",
            operator_confirmation_needed=False,
            confirmation_reason="Needs proof linkage from live/governed request into board/packet outputs.",
        ),
        _workflow(
            workflow_name="Mission Control operator helm visibility",
            domain_world="mission_control",
            operator_value="Shows ready/blocked/proof posture to Winship without backend clutter or execution buttons.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/sync_health.json",
                    role="Mac mirror trust status",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/approved_module_registry.json",
                    role="module posture for helm display",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_V0.md",
                    role="operator roadmap evidence",
                    truth_status="operator_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
            ),
            current_implementation_status="BUILT_NOT_WIRED_TO_STEEL_THREAD",
            steel_thread_readiness="Mac surfaces exist_for_some_packets_but_not_all_workflows",
            shared_bottleneck="mission_control_surface",
            next_safe_lane="Mission Control Workflow Atlas Surface v0",
            confidence="medium",
            operator_confirmation_needed=False,
            confirmation_reason="No new authority needed; UI scope should stay read-only.",
        ),
        _workflow(
            workflow_name="Active machinery quarantine review",
            domain_world="runtime_safety",
            operator_value="Helps Winship decide what machinery should be blocked, replaced, wrapped, retired, or kept.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/active_machinery_quarantine_decision_packet.json",
                    role="quarantine decision packet",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/active_machinery_block_later_guardrail.json",
                    role="metadata guardrail for block-later items",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="BUILT_NOT_WIRED_TO_STEEL_THREAD",
            steel_thread_readiness="warning_and_decision_packets_exist_runtime_not_changed",
            shared_bottleneck="runtime_machinery_guardrail_review",
            next_safe_lane="Active Machinery Guardrail To Work Board Review v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Any destructive quarantine, service disable, or launcher edit needs explicit approval.",
        ),
        _workflow(
            workflow_name="Report Bridge client-safe status helper",
            domain_world="client_project_reporting",
            operator_value="Could produce sanitized client/project status packets without raw client data or deployment authority.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/report_bridge.json",
                    role="sanitized report bridge read-model",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/project_capsules.json",
                    role="project capsule read-model",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/custom_build_module_detangling_contract.json",
                    role="synthetic detangling contract examples",
                    truth_status="synthetic_example_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
            ),
            current_implementation_status="BUILT_NOT_WIRED_TO_STEEL_THREAD",
            steel_thread_readiness="substrate_exists_but_no_real_operator_workflow_packet_proof_yet",
            shared_bottleneck="report_bridge_client_capsule_boundary",
            next_safe_lane="Report Bridge Client Status Packet Proof v0",
            confidence="medium",
            operator_confirmation_needed=False,
            confirmation_reason="Can use synthetic/sanitized metadata first; real client data remains out of scope.",
        ),
        _workflow(
            workflow_name="Niles album progress review",
            domain_world="music_art",
            operator_value="Would give Winship a review-only album/progress packet without importing old album logs as truth.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/approved_module_registry.json",
                    role="Niles Album Matrix module candidate",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_V0.md",
                    role="roadmap evidence for Niles/album surface",
                    truth_status="operator_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/custom_build_module_detangling_contract.json",
                    role="Cassandra/Niles module boundary pressure evidence",
                    truth_status="synthetic_example_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
            ),
            current_implementation_status="PLANNED_NOT_BUILT",
            steel_thread_readiness="needs_missing_facts_packet_before_any_album_csv_or_session_import",
            shared_bottleneck="generic_review_packet_non_finance_reuse",
            next_safe_lane="Niles Album Review Packet From Governed Evidence v0",
            confidence="medium",
            operator_confirmation_needed=True,
            confirmation_reason="Album progress source of truth and inclusion rules remain unconfirmed.",
        ),
        _workflow(
            workflow_name="Remote builder bridge",
            domain_world="remote_build_infrastructure",
            operator_value="Eventually lets governed build requests become approved external build jobs.",
            current_evidence_sources=(
                _evidence(
                    "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_V0.md",
                    role="roadmap blocker evidence",
                    truth_status="operator_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/active_machinery_block_later_guardrail.json",
                    role="block-later guardrail evidence for runner surfaces",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="SHOULD_NOT_BUILD_YET",
            steel_thread_readiness="blocked_until_explicit_operator_action_job_packet_and_receipts",
            shared_bottleneck="remote_runtime_authority_gate",
            next_safe_lane="Remote Builder Bridge Spec Only v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Any implementation would add runtime/tool/deployment risk and needs a separate authority gate.",
        ),
        _workflow(
            workflow_name="Send, reply, and portal submission automation",
            domain_world="external_action_authority",
            operator_value="Eventually could send emails/messages or submit portals after exact packet approval.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/capital_hilton_actionable_review_packet.json",
                    role="review-only packet explicitly blocks send/submit",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "generated/read_models/guardian_hitl_dual_write_compatibility.json",
                    role="HITL proof still observational",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="SHOULD_NOT_BUILD_YET",
            steel_thread_readiness="blocked_until_send_packet_contract_and_operator_approval",
            shared_bottleneck="send_path_authority_gate",
            next_safe_lane="Send Path Approval Packet Spec v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="External actions require explicit approval and receipt binding; no send/submit authority exists now.",
        ),
        _workflow(
            workflow_name="Markdown and source classification for broad workflow discovery",
            domain_world="source_classification",
            operator_value="Would improve the atlas and future workflow discovery without asking Winship to rewrite everything.",
            current_evidence_sources=(
                _evidence(
                    "generated/read_models/source_inventory.json",
                    role="metadata-only source inventory",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
                _evidence(
                    "docs/operations/OPENCLAW_CLASSIFICATION_TAGGING_PATTERN_V0.md",
                    role="classification doctrine evidence",
                    truth_status="contract_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/active_machinery_classification_orchestrator.json",
                    role="active machinery shard/classification surface",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="BLOCKED_BY_MISSING_INGEST_OR_TAGGING",
            steel_thread_readiness="not_needed_for_next_batch_but_needed_before_full_system_restructure",
            shared_bottleneck="markdown_source_evidence_tagging",
            next_safe_lane="Workflow Evidence Header Inventory v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Any broader source set must be bounded and reviewed before body reads or reorganization.",
        ),
        _workflow(
            workflow_name="Hard-drive/cloud/file ingest",
            domain_world="file_estate_ingest",
            operator_value="Eventually could classify broader files and cloud assets for workflows.",
            current_evidence_sources=(
                _evidence(
                    "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_V0.md",
                    role="high-level ingest roadmap evidence",
                    truth_status="operator_doc_evidence_only",
                    repo_root=repo_root,
                    confidence="medium",
                ),
                _evidence(
                    "generated/read_models/source_inventory.json",
                    role="current metadata-only inventory limits",
                    truth_status="governed_read_model_evidence",
                    repo_root=repo_root,
                    confidence="high",
                ),
            ),
            current_implementation_status="SHOULD_NOT_BUILD_YET",
            steel_thread_readiness="blocked_until_metadata_only_boundaries_and_operator_review",
            shared_bottleneck="file_estate_ingest_boundary",
            next_safe_lane="Metadata-Only File Estate Boundary Spec v0",
            confidence="high",
            operator_confirmation_needed=True,
            confirmation_reason="Broad ingest risks private/no-go content and must not precede bounded review.",
        ),
    ]


def _names_with_status(workflows: list[dict[str, Any]], status: str) -> list[str]:
    return [item["workflow_name"] for item in workflows if item["current_implementation_status"] == status]


def _shared_bottleneck_map(workflows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in workflows:
        grouped[item["shared_bottleneck"]].append(item)
    return {
        key: {
            "workflow_count": len(items),
            "workflows": [item["workflow_name"] for item in items],
            "status_counts": dict(sorted(Counter(item["current_implementation_status"] for item in items).items())),
            "next_safe_lanes": sorted({item["next_safe_lane"] for item in items}),
        }
        for key, items in sorted(grouped.items())
    }


def _markdown_source_classification_sufficiency() -> dict[str, Any]:
    return {
        "sufficient_for_next_post_preflight_batch": True,
        "required_before_next_post_preflight_batch": False,
        "full_system_restructure_requires_ingestion_or_tagging": True,
        "reason": (
            "Generated read-models and operations docs are sufficient to choose the next real batch lanes. "
            "They are not sufficient to claim full workflow coverage across every Markdown/source/file surface."
        ),
        "smallest_needed_later_lane": {
            "lane_name": "Workflow Evidence Header Inventory v0",
            "source_set": [
                "docs/operations",
                "docs/planning",
                "generated/read_models",
                "module/capsule/custom-build contract files",
                "read-model exporter scripts",
            ],
            "boundaries": [
                "metadata/header-only",
                "no broad drive/cloud scan",
                "no raw logs",
                "no private/no-go roots",
                "old docs evidence only, not truth",
                "no moves/deletes/reorganization",
            ],
            "expected_read_model_output": "generated/read_models/workflow_evidence_header_inventory.json",
            "validation": [
                "JSON validation",
                "no private/no-go body reads",
                "operator review buckets",
            ],
        },
    }


def _recommended_first_three_lanes() -> list[dict[str, Any]]:
    lanes = [
        evaluate_post_preflight_lane(
            lane_name="Capital Hilton Manual Confirmation Receipt v0",
            lane_summary=(
                "Turn the existing Capital Hilton review-only packet into a manual-confirmation receipt surface "
                "for PO/Coupa, recipient, and inclusion decisions without sending or submitting."
            ),
            named_operator_workflow="Capital Hilton invoice manual review",
            shared_bottleneck="manual_confirmation_receipt_binding",
            steel_thread_contract_link="cassandra_governed_review_packet_request_proof_v1",
            reusable_substrate_improvement=(
                "Generic manual-confirmation receipt fields become reusable for future review packets."
            ),
            workflow_proof_output="Capital Hilton manual confirmation checklist/receipt read-model.",
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Keeps finance/AP confirmation separate from send or portal authority.",
            },
            module_split_disposition={
                "disposition": "none",
                "recorded_future_work": False,
                "reason": "No module split needed for a confirmation receipt lane.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Review/receipt only; no send, submit, or runtime action.",
            },
            expected_artifacts=[
                {
                    "artifact_kind": "receipt",
                    "path_or_contract": "generated/read_models/capital_hilton_manual_confirmation_receipt.json",
                },
                {
                    "artifact_kind": "operator_packet",
                    "path_or_contract": "generated/read_models/capital_hilton_manual_confirmation_receipt_OPERATOR.md",
                },
            ],
            validation_required=[
                "focused finance packet tests",
                "JSON validation",
                "no-send/no-submit/no-credentials flags",
            ],
            synthetic_example=False,
        ),
        evaluate_post_preflight_lane(
            lane_name="Niles Album Review Packet From Governed Evidence v0",
            lane_summary=(
                "Apply the generic review packet shape to the Niles album workflow and produce a review-only "
                "packet or missing-facts packet without importing old album logs as truth."
            ),
            named_operator_workflow="Niles album progress review",
            shared_bottleneck="generic_review_packet_non_finance_reuse",
            steel_thread_contract_link="cassandra_governed_review_packet_request_proof_v1",
            reusable_substrate_improvement="Prove the generic packet contract works outside finance/AP.",
            workflow_proof_output="Niles album review packet or missing-facts packet.",
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Record Cassandra/Niles boundary pressure without extracting modules.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "future_work_id": "niles_album_matrix_boundary_review",
                "reason": "Niles module boundary should be tracked, not solved abstractly before a packet proof.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Review-only packet; no sends, model execution, or file ingestion authority.",
            },
            expected_artifacts=[
                {
                    "artifact_kind": "review_packet",
                    "path_or_contract": "generated/read_models/niles_album_review_packet.json",
                },
                {
                    "artifact_kind": "operator_packet",
                    "path_or_contract": "generated/read_models/niles_album_review_packet_OPERATOR.md",
                },
            ],
            validation_required=[
                "focused review packet tests",
                "old album files evidence-not-truth assertions",
                "JSON validation",
            ],
            synthetic_example=False,
        ),
        evaluate_post_preflight_lane(
            lane_name="Report Bridge Client Status Packet Proof v0",
            lane_summary=(
                "Use Report Bridge and Project Capsule metadata to produce a sanitized client-safe status packet "
                "from synthetic or already-sanitized evidence only."
            ),
            named_operator_workflow="Client-safe project status review",
            shared_bottleneck="report_bridge_client_capsule_boundary",
            steel_thread_contract_link="custom_build_module_detangling_contract_v0",
            reusable_substrate_improvement=(
                "Turns report bridge/client capsule boundaries into a reusable review packet contract."
            ),
            workflow_proof_output="Client-safe status packet proof with no raw client data.",
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Records reusable client helper shape without generating a client repo.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "future_work_id": "report_bridge_client_status_helper",
                "reason": "Useful for future custom builds but not an extraction lane.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Sanitized review-only status packet; no deployment/customer authority.",
            },
            expected_artifacts=[
                {
                    "artifact_kind": "review_packet",
                    "path_or_contract": "generated/read_models/report_bridge_client_status_packet.json",
                },
                {
                    "artifact_kind": "test_proof",
                    "path_or_contract": "tests/test_report_bridge_client_status_packet.py",
                },
            ],
            validation_required=[
                "no raw client data proof",
                "JSON validation",
                "no deployment/customer authority flags",
            ],
            synthetic_example=False,
        ),
    ]
    return [
        {
            "rank": index,
            "lane_name": lane["lane_name"],
            "goal": lane["lane_summary"],
            "named_operator_workflow": lane["named_operator_workflow"],
            "shared_bottleneck": lane["shared_bottleneck"],
            "reusable_substrate_improvement": lane["reusable_substrate_improvement"],
            "workflow_proof_output": lane["workflow_proof_output"],
            "bounded_detangling": lane["detangling_scope"],
            "operator_approval_required_before_start": False,
            "operator_confirmation_required_inside_workflow": index == 1,
            "post_preflight_gate_evaluation": lane,
        }
        for index, lane in enumerate(lanes, start=1)
    ]


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Operator Workflow Atlas",
        "",
        "This is a grounded gap scan from current Repo A read-models and operations docs. Old files/docs are evidence, not truth.",
        "",
        "At a glance:",
        f"- Workflows classified: {read_model['workflow_count']}.",
        f"- Confirmed built and wired: {len(read_model['built_implemented'])}.",
        f"- Built but not fully steel-threaded: {len(read_model['built_not_integrated'])}.",
        f"- Desired/planned/blocked but not built: {len(read_model['desired_not_built'])}.",
        f"- Should not build yet: {len(read_model['not_built_should_not_build_yet'])}.",
        f"- Manual rewrite required from Winship: {'yes' if read_model['operator_manual_rewrite_required'] else 'no'}.",
        f"- MD/source ingestion required before next batch: {'yes' if read_model['md_source_ingestion_required_before_next_batch'] else 'no'}.",
        "",
        "Built / Implemented:",
    ]
    lines.extend(f"- {name}" for name in read_model["built_implemented"])
    lines.extend(["", "Built / Not Fully Integrated:"])
    lines.extend(f"- {name}" for name in read_model["built_not_integrated"])
    lines.extend(["", "Desired / Not Built:"])
    lines.extend(f"- {name}" for name in read_model["desired_not_built"])
    lines.extend(["", "Not Built / Should Not Build Yet:"])
    lines.extend(f"- {name}" for name in read_model["not_built_should_not_build_yet"])
    lines.extend(["", "Top Shared Bottlenecks:"])
    for bottleneck, info in read_model["shared_bottleneck_map"].items():
        if info["workflow_count"] > 1:
            lines.append(f"- `{bottleneck}`: {info['workflow_count']} workflows")
    lines.extend(["", "Recommended First 3 Batch Lanes:"])
    for item in read_model["recommended_first_3_post_preflight_batch_lanes"]:
        gate = item["post_preflight_gate_evaluation"]
        lines.extend(
            [
                f"{item['rank']}. {item['lane_name']}",
                f"   - workflow: {item['named_operator_workflow']}",
                f"   - bottleneck: `{item['shared_bottleneck']}`",
                f"   - gate: `{gate['gate_status']}`",
                f"   - output: {item['workflow_proof_output']}",
            ]
        )
    sufficiency = read_model["markdown_source_classification_sufficiency"]
    lines.extend(
        [
            "",
            "Markdown / Source Classification:",
            f"- Sufficient for next batch: {'yes' if sufficiency['sufficient_for_next_post_preflight_batch'] else 'no'}.",
            f"- Full-system restructure still needs ingestion/tagging: {'yes' if sufficiency['full_system_restructure_requires_ingestion_or_tagging'] else 'no'}.",
            f"- Smallest later lane: {sufficiency['smallest_needed_later_lane']['lane_name']}.",
            "",
            "Boundaries:",
            "- No runtime authority added.",
            "- No send/submit/customer deployment authority added.",
            "- No Repo B execution.",
            "- No broad private/source ingest.",
            "",
            "Next recommended lane: Capital Hilton Manual Confirmation Receipt v0",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_workflow_atlas(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    repo_root: str | Path = Path("."),
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_workflow_atlas(repo_root=repo_root, generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "workflow_count": read_model["workflow_count"],
        "batch_gate_used": read_model["batch_gate_used"],
        "batch_gate_all_recommendations_pass": read_model["batch_gate_all_recommendations_pass"],
        **NO_AUTHORITY_FLAGS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator workflow atlas read-model.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--repo-root", default=Path(".").as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    args = parser.parse_args(argv)
    result = export_operator_workflow_atlas(export_root=args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        operator_path = Path(result["operator_path"])
        print(operator_path.read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
