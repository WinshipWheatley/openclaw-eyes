"""Operator Attention Promotion Contract v0.

This read-model defines how stored facts, receipts, breadcrumbs, proof gaps,
memory candidates, worker outputs, lane states, security deltas, and world
transitions become operator-visible attention or stay quiet with proof. It is
classification only: no queue, repair, launch, send, submit, approval, file
move, source-note mutation, tool/model/agent/runtime activation, or authority
grant is created here.
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

SCHEMA_VERSION = "operator_attention_promotion_contract_v0"
READ_MODEL_ID = "operator_attention_promotion_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

PROMOTION_LIFECYCLE_STATES = (
    "OBSERVED",
    "CLASSIFIED",
    "PROOF_LINKED",
    "MEMORY_CANDIDATE",
    "HELM_ATTENTION",
    "WORLD_LANE",
    "PROOF_DETAIL",
    "HOLDING_CELL_ITEM",
    "CUE_CANDIDATE",
    "READY_FOR_SECURITY_DELTA_REVIEW",
    "READY_FOR_WORLD_PREVIEW",
    "QUIET_WITH_PROOF",
    "PARKED",
    "QUARANTINED",
    "OBSOLETE_OR_REJECTED",
    "UNKNOWN_FAIL_CLOSED",
)

PROMOTION_DESTINATIONS = (
    "HELM_ATTENTION",
    "WORLD_LANE",
    "PROOF_EVIDENCE_DRAWER",
    "HOLDING_CELL",
    "MEMORY_CANDIDATE_INBOX",
    "CUE_CANDIDATE",
    "SECURITY_DELTA_REVIEW",
    "CHIEF_RECONCILIATION",
    "HERMES_ARCHITECTURE_REVIEW",
    "GUARDIAN_REVIEW",
    "QUIET_WITH_PROOF",
    "QUARANTINE",
    "REJECT_OR_OBSOLETE",
)

ATTENTION_CLASSES = (
    "NEEDS_OPERATOR_DECISION",
    "NEEDS_PROOF",
    "NEEDS_CONTEXT",
    "NEEDS_SECURITY_GATE",
    "NEEDS_WORLD_TRANSITION",
    "NEEDS_CHIEF_RECONCILIATION",
    "NEEDS_HERMES_REVIEW",
    "NEEDS_GUARDIAN_REVIEW",
    "SYSTEM_HEALTH_WARNING",
    "BUILT_NOT_SURFACED",
    "DUPLICATE_OR_OVERLAP",
    "BLOCKED_NOT_AUTHORIZED",
    "HOLDING_CELL",
    "CUE_CANDIDATE",
    "QUIET_WITH_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

NO_ACTION_AUTHORITY_FLAGS = {
    "promotion_is_execution": False,
    "auto_promotion_allowed": False,
    "queue_execution_allowed": False,
    "cue_candidate_execution_allowed": False,
    "holding_cell_auto_queue_allowed": False,
    "tool_execution_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "runtime_dispatch_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_access_allowed": False,
    "financial_payment_account_access_allowed": False,
    "credential_handling_allowed": False,
    "send_submit_approval_allowed": False,
    "file_move_delete_allowed": False,
    "source_note_mutation_allowed": False,
    "stable_map_auto_promotion_allowed": False,
    "world_lane_action_authority_granted": False,
}

REQUIRED_RECORD_FIELDS = (
    "promotion_id",
    "display_name",
    "source_type",
    "source_refs",
    "receipt_refs",
    "read_model_refs",
    "stable_map_refs",
    "lane_id",
    "world_id",
    "actor_id",
    "attention_class",
    "current_lifecycle_state",
    "promotion_destination",
    "proof_status",
    "memory_status",
    "security_status",
    "operator_action_required",
    "world_transition_required",
    "chief_reconciliation_required",
    "hermes_review_required",
    "guardian_review_required",
    "security_delta_required",
    "quiet_condition",
    "trigger_condition",
    "dependency_marker",
    "review_cadence",
    "next_safe_move",
    "what_would_promote_it",
    "what_keeps_it_parked",
    "what_blocks_execution",
    "authority_required",
    "authority_granted",
    "receipt_requirements",
    "conflict_locks",
    "staleness_policy",
    "quarantine_policy",
)


@dataclass(frozen=True)
class OperatorAttentionPromotionRecord:
    promotion_id: str
    display_name: str
    source_type: str
    source_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    read_model_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    lane_id: str
    world_id: str
    actor_id: str
    attention_class: str
    current_lifecycle_state: str
    promotion_destination: str
    proof_status: str
    memory_status: str
    security_status: str
    operator_action_required: bool
    world_transition_required: bool
    chief_reconciliation_required: bool
    hermes_review_required: bool
    guardian_review_required: bool
    security_delta_required: bool
    quiet_condition: str
    trigger_condition: str
    dependency_marker: str
    review_cadence: str
    next_safe_move: str
    what_would_promote_it: str
    what_keeps_it_parked: str
    what_blocks_execution: tuple[str, ...]
    authority_required: tuple[str, ...]
    authority_granted: bool
    receipt_requirements: tuple[str, ...]
    conflict_locks: tuple[str, ...]
    staleness_policy: str
    quarantine_policy: str


@dataclass(frozen=True)
class PromotionExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    lifecycle_state_count: int
    destination_count: int
    attention_class_count: int
    default_record_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record(
    promotion_id: str,
    *,
    display_name: str,
    source_type: str,
    source_refs: tuple[str, ...],
    lane_id: str,
    world_id: str,
    attention_class: str,
    current_lifecycle_state: str,
    promotion_destination: str,
    proof_status: str,
    memory_status: str,
    security_status: str,
    next_safe_move: str,
    what_would_promote_it: str,
    what_keeps_it_parked: str,
    what_blocks_execution: tuple[str, ...],
    receipt_requirements: tuple[str, ...],
    receipt_refs: tuple[str, ...] = (),
    read_model_refs: tuple[str, ...] = (),
    stable_map_refs: tuple[str, ...] = (),
    actor_id: str = "none",
    operator_action_required: bool = False,
    world_transition_required: bool = False,
    chief_reconciliation_required: bool = False,
    hermes_review_required: bool = False,
    guardian_review_required: bool = False,
    security_delta_required: bool = False,
    quiet_condition: str = "not_quiet_until_classified",
    trigger_condition: str = "none",
    dependency_marker: str = "none",
    review_cadence: str = "manual_review_only",
    authority_required: tuple[str, ...] = (),
    authority_granted: bool = False,
    conflict_locks: tuple[str, ...] = (),
    staleness_policy: str = "fail_closed_if_stale",
    quarantine_policy: str = "quarantine_on_conflict_or_authority_overclaim",
) -> OperatorAttentionPromotionRecord:
    return OperatorAttentionPromotionRecord(
        promotion_id=promotion_id,
        display_name=display_name,
        source_type=source_type,
        source_refs=source_refs,
        receipt_refs=receipt_refs,
        read_model_refs=read_model_refs,
        stable_map_refs=stable_map_refs,
        lane_id=lane_id,
        world_id=world_id,
        actor_id=actor_id,
        attention_class=attention_class,
        current_lifecycle_state=current_lifecycle_state,
        promotion_destination=promotion_destination,
        proof_status=proof_status,
        memory_status=memory_status,
        security_status=security_status,
        operator_action_required=operator_action_required,
        world_transition_required=world_transition_required,
        chief_reconciliation_required=chief_reconciliation_required,
        hermes_review_required=hermes_review_required,
        guardian_review_required=guardian_review_required,
        security_delta_required=security_delta_required,
        quiet_condition=quiet_condition,
        trigger_condition=trigger_condition,
        dependency_marker=dependency_marker,
        review_cadence=review_cadence,
        next_safe_move=next_safe_move,
        what_would_promote_it=what_would_promote_it,
        what_keeps_it_parked=what_keeps_it_parked,
        what_blocks_execution=what_blocks_execution,
        authority_required=authority_required,
        authority_granted=authority_granted,
        receipt_requirements=receipt_requirements,
        conflict_locks=conflict_locks,
        staleness_policy=staleness_policy,
        quarantine_policy=quarantine_policy,
    )


def default_promotion_records() -> tuple[OperatorAttentionPromotionRecord, ...]:
    return (
        _record(
            "capital_hilton_proof_gap",
            display_name="Capital Hilton Proof Gap",
            source_type="capital_hilton_proof_metadata",
            source_refs=("capital_hilton_proof_metadata",),
            receipt_refs=("Finance World preview receipt",),
            read_model_refs=("capital_hilton_proof_metadata_packet.json",),
            stable_map_refs=("capital_hilton_proof_metadata",),
            lane_id="capital_hilton",
            world_id="Finance",
            actor_id="Cassandra",
            attention_class="NEEDS_PROOF",
            current_lifecycle_state="HELM_ATTENTION",
            promotion_destination="HELM_ATTENTION",
            proof_status="MISSING_PROTECTED_PROOF",
            memory_status="not_memory_candidate",
            security_status="guardian_gate_required",
            operator_action_required=True,
            world_transition_required=True,
            guardian_review_required=True,
            quiet_condition="quiet_after_protected_proof_metadata_is_classified_and_receipted",
            trigger_condition="protected finance proof metadata intake exists",
            dependency_marker="protected_finance_proof_metadata_intake",
            review_cadence="active_until_proof_gap_resolved",
            next_safe_move="Classify protected finance proof metadata; Finance World remains preview-only.",
            what_would_promote_it="Protected proof refs, Guardian gate, and Security Delta clearance for any new authority.",
            what_keeps_it_parked="Missing proof count and protected proof requirement.",
            what_blocks_execution=("missing proof", "protected proof required", "no finance action authority"),
            authority_required=("Guardian gate", "Operator final authority for future action"),
            receipt_requirements=("protected proof metadata receipt", "Capital Hilton lane receipt"),
            conflict_locks=("finance_action_locked",),
        ),
        _record(
            "stable_map_receipt_current",
            display_name="Stable Map Receipt Current",
            source_type="sync_health_stable_map_receipt",
            source_refs=("sync_health.json", "openclaw_map_receipt.json"),
            receipt_refs=("Mac stable-map import receipt",),
            read_model_refs=("sync_health.json", "openclaw_map_manifest.json"),
            stable_map_refs=("map_current",),
            lane_id="check_transmission",
            world_id="System",
            attention_class="QUIET_WITH_PROOF",
            current_lifecycle_state="QUIET_WITH_PROOF",
            promotion_destination="PROOF_EVIDENCE_DRAWER",
            proof_status="RECEIPTED_CURRENT",
            memory_status="not_memory_candidate",
            security_status="read_only_current",
            quiet_condition="map receipt matches PC bundle",
            next_safe_move="None; keep raw mirror mismatch as proof/detail.",
            what_would_promote_it="New mismatch that blocks app-visible stable map truth.",
            what_keeps_it_parked="Stable map is current and operator action is not required.",
            what_blocks_execution=("stable map readback is not execution authority",),
            receipt_requirements=("stable map receipt", "sync health readback"),
            staleness_policy="reopen_if_map_generation_or_bundle_hash_changes",
        ),
        _record(
            "markdown_knowledge_atlas_visibility_gap",
            display_name="Markdown Knowledge Atlas Visibility Gap",
            source_type="markdown_knowledge_atlas",
            source_refs=("markdown_knowledge_atlas.py", "markdown_evidence_ingestion.py", "corpus_atlas.py"),
            read_model_refs=("security_pass_contract.json",),
            lane_id="markdown_terrain",
            world_id="System",
            attention_class="BUILT_NOT_SURFACED",
            current_lifecycle_state="PROOF_DETAIL",
            promotion_destination="PROOF_EVIDENCE_DRAWER",
            proof_status="metadata_capability_evidenced",
            memory_status="not_memory_candidate",
            security_status="metadata_readback_allowed",
            hermes_review_required=True,
            quiet_condition="quiet_until_app_visibility_lane_is_selected",
            trigger_condition="operator asks for Markdown terrain visibility",
            dependency_marker="future app/stable-map visibility lane",
            next_safe_move="Consider stable-map/app visibility later; no new crawler needed.",
            what_would_promote_it="Stable-map summary lane or app visibility request.",
            what_keeps_it_parked="Capability exists as metadata substrate but is not active UI work.",
            what_blocks_execution=("broad body ingestion blocked", "file moves blocked", "no new crawler needed"),
            receipt_requirements=("metadata readback receipt",),
        ),
        _record(
            "future_invoicing_state_machine_audit",
            display_name="Future Invoicing State Machine Audit",
            source_type="worker_output_stress_test_artifact",
            source_refs=("future_invoicing_state_machine_audit",),
            read_model_refs=("security_pass_contract.json",),
            lane_id="future_invoicing",
            world_id="Finance",
            attention_class="HOLDING_CELL",
            current_lifecycle_state="PARKED",
            promotion_destination="HOLDING_CELL",
            proof_status="stress_test_artifact_only",
            memory_status="not_memory_candidate",
            security_status="high_risk_future_gated",
            guardian_review_required=True,
            security_delta_required=True,
            quiet_condition="quiet_while_parked_with_future_gate_label",
            trigger_condition="finance/account/payment gates exist",
            dependency_marker="future finance authority contracts",
            review_cadence="review_after_security_delta_and_finance_gate_work",
            next_safe_move="Keep parked until finance/account/payment gates exist.",
            what_would_promote_it="Invoice math, idempotency, ledger, account, Guardian, and Operator gates.",
            what_keeps_it_parked="No ledger, invoice, account, email, or payment authority.",
            what_blocks_execution=("invoice generation blocked", "ledger write blocked", "email dispatch blocked", "account access blocked"),
            authority_required=("Security Delta Review", "Guardian gate", "Operator approval"),
            receipt_requirements=("stress-test artifact receipt",),
        ),
        _record(
            "autonomous_capital_pipeline_experiment",
            display_name="Autonomous Capital Pipeline Experiment",
            source_type="parked_r_and_d_experiment",
            source_refs=("parked_autonomous_capital_pipeline_experiment",),
            read_model_refs=("parked_autonomous_capital_pipeline_experiment.json",),
            lane_id="autonomous_capital_pipeline_r_and_d_experiment",
            world_id="R&D",
            attention_class="HOLDING_CELL",
            current_lifecycle_state="PARKED",
            promotion_destination="HOLDING_CELL",
            proof_status="parked_stress_test_reference",
            memory_status="not_memory_candidate",
            security_status="high_risk_future_gated",
            guardian_review_required=True,
            security_delta_required=True,
            quiet_condition="quiet_until_future budget/legal/account/payment gates exist",
            trigger_condition="future sandboxed R&D gates defined",
            dependency_marker="budget/legal/compliance/account/payment/security gates",
            review_cadence="manual_future_lane_review",
            next_safe_move="No action; preserve until future gates exist.",
            what_would_promote_it="Budget-token policy, legal/compliance/tax review, account/payment policy, Guardian gate, Operator approval.",
            what_keeps_it_parked="No spend, account, deployment, marketplace, payment, or autonomy authority.",
            what_blocks_execution=("spend blocked", "account creation blocked", "deployment blocked", "payment/payout blocked", "queue/autonomy blocked"),
            authority_required=("Security Delta Review", "Guardian gate", "Operator approval"),
            receipt_requirements=("parked R&D experiment read-model",),
        ),
        _record(
            "orphaned_capability_found",
            display_name="Orphaned Capability Found",
            source_type="worker_orphan_detection",
            source_refs=("orphaned_capability_detection",),
            read_model_refs=("security_pass_contract.json",),
            lane_id="orphaned_capability",
            world_id="System",
            attention_class="BUILT_NOT_SURFACED",
            current_lifecycle_state="CLASSIFIED",
            promotion_destination="CHIEF_RECONCILIATION",
            proof_status="candidate_until_reconciled",
            memory_status="not_memory_candidate",
            security_status="non_executing_metadata",
            chief_reconciliation_required=True,
            hermes_review_required=True,
            quiet_condition="quiet_after classified, reconciled, and either surfaced or parked",
            trigger_condition="capability evidence appears without app/stable-map surface",
            dependency_marker="Chief reconciliation and Hermes architecture review",
            next_safe_move="Classify, reconcile, and do not activate.",
            what_would_promote_it="Matched source task, tests, receipts, stable-map/app visibility decision.",
            what_keeps_it_parked="Built thing is not active because it exists.",
            what_blocks_execution=("capability not reconciled", "authority not granted", "activation blocked"),
            receipt_requirements=("worker output receipt", "test receipt", "Chief reconciliation receipt"),
        ),
        _record(
            "operator_missing_terrain_memory",
            display_name="Operator Missing Terrain Memory",
            source_type="operator_reported_context",
            source_refs=("operator says check out X",),
            lane_id="terrain_awareness",
            world_id="System",
            actor_id="Operator",
            attention_class="NEEDS_CONTEXT",
            current_lifecycle_state="MEMORY_CANDIDATE",
            promotion_destination="MEMORY_CANDIDATE_INBOX",
            proof_status="operator_answer_is_not_proof",
            memory_status="memory_candidate_receipt_required",
            security_status="capture_only",
            operator_action_required=True,
            quiet_condition="quiet_after memory candidate receipt or rejection",
            trigger_condition="operator reports terrain the system does not map",
            dependency_marker="coverage gap registry",
            next_safe_move="Capture as candidate, not proof.",
            what_would_promote_it="Receipted source card, proof ref, or classification pass.",
            what_keeps_it_parked="Operator memory is useful context but not source proof.",
            what_blocks_execution=("operator answer is not proof", "no automatic truth promotion"),
            receipt_requirements=("memory candidate receipt",),
        ),
        _record(
            "security_delta_needed_for_new_tool",
            display_name="Security Delta Needed For New Tool",
            source_type="new_tool_or_adapter_proposal",
            source_refs=("new adapter/tool proposal",),
            read_model_refs=("security_delta_review_contract.json",),
            lane_id="security_delta",
            world_id="System",
            attention_class="NEEDS_SECURITY_GATE",
            current_lifecycle_state="READY_FOR_SECURITY_DELTA_REVIEW",
            promotion_destination="SECURITY_DELTA_REVIEW",
            proof_status="authority_request_requires_review",
            memory_status="not_memory_candidate",
            security_status="fail_closed_until_reviewed",
            guardian_review_required=True,
            security_delta_required=True,
            quiet_condition="quiet_after delta review blocks or approves preview-only posture",
            trigger_condition="item requests tool/account/runtime/financial/send authority",
            dependency_marker="security_delta_review_contract",
            next_safe_move="Fail closed until reviewed.",
            what_would_promote_it="Security Delta decision and required Guardian/Operator gates.",
            what_keeps_it_parked="New authority request is not covered by existing class.",
            what_blocks_execution=("new tool authority", "account/network authority", "runtime/action authority"),
            authority_required=("Security Delta Review", "Guardian gate where sensitive", "Operator approval where required"),
            receipt_requirements=("security delta review receipt",),
            quarantine_policy="quarantine_if_authority_is_overclaimed_or_sensitive_material_is_exposed",
        ),
    )


def promotion_decision_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "helm_attention",
            "destination": "HELM_ATTENTION",
            "use_when": "operator decision, context, ambiguity, approval, risk inspection, security/proof gap",
            "executes": False,
        },
        {
            "rule_id": "world_lane",
            "destination": "WORLD_LANE",
            "use_when": "domain work is mapped enough to belong in a world while still preview-only/action-locked",
            "executes": False,
        },
        {
            "rule_id": "proof_evidence_drawer",
            "destination": "PROOF_EVIDENCE_DRAWER",
            "use_when": "important but not currently operator-actionable",
            "executes": False,
        },
        {
            "rule_id": "holding_cell",
            "destination": "HOLDING_CELL",
            "use_when": "valid but premature idea with trigger conditions",
            "executes": False,
        },
        {
            "rule_id": "memory_candidate",
            "destination": "MEMORY_CANDIDATE_INBOX",
            "use_when": "Winship or worker reports useful context that is not proof",
            "executes": False,
        },
        {
            "rule_id": "cue_candidate",
            "destination": "CUE_CANDIDATE",
            "use_when": "item may later become queueable after proof, package, authority, security delta, and conflict checks",
            "executes": False,
        },
        {
            "rule_id": "quiet_with_proof",
            "destination": "QUIET_WITH_PROOF",
            "use_when": "complete, parked, blocked with proof, obsolete, duplicated, or not operator-actionable",
            "executes": False,
        },
        {
            "rule_id": "quarantine",
            "destination": "QUARANTINE",
            "use_when": "proof conflicts, authority overclaimed, sensitive material exposed, or source trust unknown",
            "executes": False,
        },
    ]


def quiet_helm_policy() -> dict[str, Any]:
    return {
        "definition": "Quiet means classified, receipted, and retrievable; it does not mean forgotten.",
        "helm_reopens_when": [
            "operator decision is needed",
            "proof is missing",
            "safety/security risk exists",
            "world transition is needed",
            "operator context is required",
            "shared fix path is ready for review",
            "item is stale, conflicting, or quarantined",
        ],
        "default_quiet_item": {
            "quiet_reason": "classified_non_actionable_or_complete",
            "proof_refs": ["receipt refs or read-model refs"],
            "retrieval_path": "proof drawer, holding cell, memory inbox, or lane drill-down",
            "reopen_condition": "new proof gap, stale receipt, security delta, or operator request",
            "staleness_condition": "source receipt older than its review policy or superseded by newer map",
            "operator_visibility_level": "summary_or_drill_down_not_helm_noise",
        },
    }


def shared_fix_paths() -> list[dict[str, Any]]:
    return [
        {
            "shared_fix_path_id": "protected_finance_proof_metadata_intake",
            "linked_lanes": ["Capital Hilton", "Cassandra"],
            "linked_worlds": ["Finance World"],
            "linked_gates": ["Guardian gate"],
            "linked_surfaces": ["Package Preview"],
            "promotion_destination": "HELM_ATTENTION",
            "attention_class": "NEEDS_PROOF",
            "solving_once_can_update_multiple_lanes": True,
            "updates_only_after_receipts_and_gates_exist": True,
            "executes": False,
            "next_safe_move": "Show one shared fix path instead of multiple noisy cards.",
        }
    ]


def operator_answer_capture_tie_in() -> dict[str, Any]:
    return {
        "operator_answers_are_memory_candidates": True,
        "operator_answers_are_proof": False,
        "answered_questions_may_quiet_question": True,
        "answered_questions_may_reveal_proof_gap": True,
        "valid_capture_outcomes": ["i_dont_know", "park_this", "reject", "move_to_world", "needs_discovery"],
        "capture_equals_action_authority": False,
    }


def relationship_to_security_delta() -> dict[str, Any]:
    return {
        "new_authority_routes_to_security_delta": True,
        "new_tool_use_routes_to_security_delta": True,
        "new_account_access_routes_to_security_delta": True,
        "new_automation_routes_to_security_delta": True,
        "new_runtime_behavior_routes_to_security_delta": True,
        "new_financial_action_routes_to_security_delta": True,
        "fail_closed_if_not_reviewed": True,
    }


def _all_authority_flags_false() -> bool:
    return all(value is False for value in NO_ACTION_AUTHORITY_FLAGS.values())


def build_operator_attention_promotion_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    records = [asdict(item) for item in default_promotion_records()]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "operator_attention_promotion_contract_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": "DETERMINISTIC_NON_EXECUTING_PROMOTION_CLASSIFICATION",
        "core_doctrine": {
            "sqlite_receipts_are_durable_memory_and_proof": True,
            "read_models_are_curated_machine_state": True,
            "stable_map_is_app_facing_truth": True,
            "mission_control_is_human_attention_surface": True,
            "sqlite_row_is_not_automatically_operator_truth": True,
            "breadcrumb_is_not_queued_work": True,
            "memory_candidate_is_not_proof": True,
            "cue_candidate_is_not_executable": True,
            "worker_report_is_not_proof_until_reconciled": True,
            "world_lane_is_not_action_authority": True,
            "quiet_item_is_not_deleted": True,
        },
        "promotion_lifecycle_states": list(PROMOTION_LIFECYCLE_STATES),
        "promotion_destinations": list(PROMOTION_DESTINATIONS),
        "attention_classes": list(ATTENTION_CLASSES),
        "operator_attention_promotion_record_schema": {
            "structure": "OperatorAttentionPromotionRecord",
            "required_fields": list(REQUIRED_RECORD_FIELDS),
            "unknown_or_missing_decision_result": "UNKNOWN_FAIL_CLOSED",
        },
        "authority_boundary": dict(NO_ACTION_AUTHORITY_FLAGS),
        "promotion_decision_rules": promotion_decision_rules(),
        "default_records": records,
        "default_records_by_id": {item["promotion_id"]: item for item in records},
        "quiet_helm_policy": quiet_helm_policy(),
        "shared_fix_paths": shared_fix_paths(),
        "operator_answer_capture_tie_in": operator_answer_capture_tie_in(),
        "relationship_to_security_delta": relationship_to_security_delta(),
        "hard_rule": {
            "promotion_is_classification_not_execution": True,
            "may_run": False,
            "may_queue": False,
            "may_repair": False,
            "may_launch": False,
            "may_send_submit_approve": False,
            "may_move_files": False,
            "may_mutate_source_notes": False,
            "may_activate_agents": False,
        },
        "machine_proof": {
            "all_lifecycle_states_present": len(PROMOTION_LIFECYCLE_STATES) == 16,
            "all_destinations_present": len(PROMOTION_DESTINATIONS) == 13,
            "all_attention_classes_present": len(ATTENTION_CLASSES) == 16,
            "default_record_count": len(records),
            "quiet_helm_policy_present": True,
            "shared_fix_path_present": True,
            "operator_answers_are_candidates_not_proof": True,
            "new_authority_routes_to_security_delta_or_fail_closed": True,
            "cue_candidates_not_executable": True,
            "holding_cell_items_not_queued": True,
            "quiet_with_proof_preserves_evidence": True,
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
            "auto_promotion_allowed": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Operator Attention Promotion Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract decides what should happen to a stored thing now. A SQLite row, read-model, Markdown note, worker report, receipt, or stable-map summary does not automatically deserve helm attention. It must be classified into helm attention, world lane, proof detail, holding cell, memory candidate, cue candidate, quiet-with-proof, quarantine, or rejection.",
        "",
        "## Lifecycle",
        "",
    ]
    for state in payload["promotion_lifecycle_states"]:
        lines.append(f"- `{state}`")
    lines.extend(["", "## Destinations", ""])
    for destination in payload["promotion_destinations"]:
        lines.append(f"- `{destination}`")
    lines.extend(["", "## Attention Classes", ""])
    for attention_class in payload["attention_classes"]:
        lines.append(f"- `{attention_class}`")
    lines.extend(["", "## Default Records", ""])
    for record in payload["default_records"]:
        lines.append(
            f"- `{record['promotion_id']}`: `{record['attention_class']}` -> "
            f"`{record['promotion_destination']}`. Next: {record['next_safe_move']}"
        )
    lines.extend(
        [
            "",
            "## Quiet Helm",
            "",
            "- Quiet means classified, receipted, and retrievable. It does not mean forgotten.",
            "- Quiet items stay available in proof drawers, holding cells, memory inboxes, or lane drill-downs.",
            "",
            "## Shared Fix Paths",
            "",
        ]
    )
    for shared_path in payload["shared_fix_paths"]:
        lines.append(
            f"- `{shared_path['shared_fix_path_id']}` links {', '.join(shared_path['linked_lanes'])} "
            f"and {', '.join(shared_path['linked_worlds'])}; solving once may update several lanes only after receipts and gates exist."
        )
    lines.extend(
        [
            "",
            "## Capture And Security Delta",
            "",
            "- Operator answers are memory candidates, not proof.",
            "- A cue candidate is not executable.",
            "- A holding-cell item is not queued.",
            "- New authority, tool use, account access, automation, runtime behavior, or financial action routes to Security Delta Review or fails closed.",
            "",
            "## Machine Proof",
            "",
            f"- Default record count: `{proof['default_record_count']}`.",
            f"- Quiet helm policy present: `{str(proof['quiet_helm_policy_present']).lower()}`.",
            f"- Shared fix path present: `{str(proof['shared_fix_path_present']).lower()}`.",
            f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
            f"- Action authority granted: `{str(proof['action_authority_granted']).lower()}`.",
            f"- Auto-promotion allowed: `{str(proof['auto_promotion_allowed']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_attention_promotion_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PromotionExportResult:
    payload = build_operator_attention_promotion_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return PromotionExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        lifecycle_state_count=len(payload["promotion_lifecycle_states"]),
        destination_count=len(payload["promotion_destinations"]),
        attention_class_count=len(payload["attention_classes"]),
        default_record_count=len(payload["default_records"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Operator Attention Promotion Contract v0 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_attention_promotion_contract(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "lifecycle_state_count": result.lifecycle_state_count,
        "destination_count": result.destination_count,
        "attention_class_count": result.attention_class_count,
        "default_record_count": result.default_record_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Operator Attention Promotion Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ATTENTION_CLASSES",
    "NO_ACTION_AUTHORITY_FLAGS",
    "OperatorAttentionPromotionRecord",
    "PROMOTION_DESTINATIONS",
    "PROMOTION_LIFECYCLE_STATES",
    "READ_MODEL_ID",
    "REQUIRED_RECORD_FIELDS",
    "SCHEMA_VERSION",
    "build_operator_attention_promotion_contract",
    "default_promotion_records",
    "export_operator_attention_promotion_contract",
    "format_operator_markdown",
    "operator_answer_capture_tie_in",
    "quiet_helm_policy",
    "relationship_to_security_delta",
    "shared_fix_paths",
    "stable_json",
]
