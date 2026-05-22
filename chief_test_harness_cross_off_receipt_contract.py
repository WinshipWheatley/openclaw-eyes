"""Chief Test Harness / Cross-Off Receipt Contract v0.

This read-model defines how Chief can later verify completion, reconcile work
to its source, and recommend cross-off, requeue, park, quarantine, or
quiet-with-proof. It is receipt/decision metadata only: no repair execution,
source mutation, file deletion, queueing, self-authorization, tool/model/agent
activation, Mac sync/import, stable-map refresh, or external authority is
created here.
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

SCHEMA_VERSION = "chief_test_harness_cross_off_receipt_contract_v0"
READ_MODEL_ID = "chief_test_harness_cross_off_receipt_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

COMPLETION_STATUSES = (
    "NOT_STARTED",
    "IN_PROGRESS",
    "WORKER_REPORTED_DONE",
    "VALIDATION_PASSED",
    "VALIDATION_FAILED",
    "COMPLETED_WITH_PROOF",
    "COMPLETED_NEEDS_OPERATOR_REVIEW",
    "COMPLETED_NEEDS_GUARDIAN_REVIEW",
    "COMPLETED_NEEDS_HERMES_REVIEW",
    "PARTIAL_REQUEUE_REQUIRED",
    "FAILED_REPAIR_REQUIRED",
    "PARKED_WITH_PROOF",
    "DUPLICATE_OR_MERGED",
    "REJECTED_OR_OBSOLETE",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

RECONCILIATION_STATES = (
    "NOT_RECONCILED",
    "MATCHED_TO_MARKDOWN_ITEM",
    "MATCHED_TO_CUE_CANDIDATE",
    "MATCHED_TO_WORKER_REPORT",
    "MATCHED_TO_PACKAGE",
    "MATCHED_TO_STABLE_MAP_LANE",
    "MATCHED_TO_WORLD_LANE",
    "MATCHED_TO_RECEIPT",
    "BUILT_NOT_SURFACED",
    "SURFACED_NOT_VERIFIED",
    "RECONCILED_WITH_PROOF",
    "RECONCILED_NEEDS_REVIEW",
    "UNKNOWN_FAIL_CLOSED",
)

CROSS_OFF_DECISIONS = (
    "CROSS_OFF_ALLOWED_WITH_PROOF",
    "CROSS_OFF_BLOCKED_NEEDS_TESTS",
    "CROSS_OFF_BLOCKED_NEEDS_RECEIPT",
    "CROSS_OFF_BLOCKED_NEEDS_OPERATOR",
    "CROSS_OFF_BLOCKED_NEEDS_GUARDIAN",
    "CROSS_OFF_BLOCKED_NEEDS_HERMES",
    "REQUEUE_REQUIRED",
    "PARK_WITH_PROOF",
    "MERGE_WITH_EXISTING_LANE",
    "QUARANTINE",
    "REJECT_OBSOLETE",
    "UNKNOWN_FAIL_CLOSED",
)

NO_ACTION_AUTHORITY_FLAGS = {
    "chief_self_authorization_allowed": False,
    "automatic_cross_off_allowed": False,
    "repair_execution_allowed": False,
    "queue_execution_allowed": False,
    "tool_execution_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "runtime_dispatch_allowed": False,
    "source_mutation_allowed": False,
    "delete_source_allowed": False,
    "archive_source_allowed": False,
    "file_move_delete_allowed": False,
    "stable_map_auto_update_allowed": False,
    "attention_promotion_auto_update_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_access_allowed": False,
    "financial_payment_account_access_allowed": False,
    "credential_handling_allowed": False,
    "send_submit_approval_allowed": False,
    "authority_granted": False,
}

REQUIRED_HARNESS_FIELDS = (
    "receipt_id",
    "task_title",
    "source_type",
    "source_refs",
    "worker_report_refs",
    "package_refs",
    "changed_artifact_refs",
    "commit_refs",
    "test_commands",
    "test_results",
    "build_results",
    "screenshot_refs",
    "generated_read_model_refs",
    "stable_map_refs",
    "receipt_refs",
    "boundary_checks",
    "validation_status",
    "reconciliation_status",
    "completion_status",
    "chief_recommendation",
    "hermes_review_required",
    "guardian_gate_required",
    "operator_review_required",
    "cross_off_allowed",
    "requeue_required",
    "park_required",
    "quarantine_required",
    "quiet_with_proof_allowed",
    "next_safe_move",
)

REQUIRED_CROSS_OFF_FIELDS = (
    "cross_off_id",
    "source_task_ref",
    "completion_receipt_ref",
    "decision",
    "reason",
    "proof_refs",
    "tests_passed",
    "boundary_passed",
    "source_mutation_allowed",
    "delete_source_allowed",
    "archive_source_allowed",
    "stable_map_update_required",
    "attention_promotion_update_required",
    "operator_final_decision_required",
    "next_safe_move",
)

REQUIRED_REPAIR_FIELDS = (
    "recommendation_id",
    "failed_or_partial_task_ref",
    "failure_reason",
    "missing_proof",
    "missing_tests",
    "missing_receipts",
    "boundary_issue",
    "suggested_requeue_lane",
    "suggested_repair_package_type",
    "requires_operator_review",
    "requires_hermes_review",
    "requires_guardian_gate",
    "can_run_unattended",
    "why_not_unattended",
    "next_safe_move",
)

REQUIRED_QUIET_FIELDS = (
    "quiet_receipt_id",
    "item_ref",
    "quiet_reason",
    "proof_refs",
    "retrieval_path",
    "reopen_condition",
    "staleness_condition",
    "operator_visibility_level",
    "stable_map_update_required",
    "evidence_drawer_ref",
    "created_by",
    "authority_granted",
)


@dataclass(frozen=True)
class ChiefTestHarnessReceipt:
    receipt_id: str
    task_title: str
    source_type: str
    source_refs: tuple[str, ...]
    worker_report_refs: tuple[str, ...]
    package_refs: tuple[str, ...]
    changed_artifact_refs: tuple[str, ...]
    commit_refs: tuple[str, ...]
    test_commands: tuple[str, ...]
    test_results: tuple[str, ...]
    build_results: tuple[str, ...]
    screenshot_refs: tuple[str, ...]
    generated_read_model_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    boundary_checks: tuple[str, ...]
    validation_status: str
    reconciliation_status: str
    completion_status: str
    chief_recommendation: str
    hermes_review_required: bool
    guardian_gate_required: bool
    operator_review_required: bool
    cross_off_allowed: bool
    requeue_required: bool
    park_required: bool
    quarantine_required: bool
    quiet_with_proof_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class CrossOffDecisionRecord:
    cross_off_id: str
    source_task_ref: str
    completion_receipt_ref: str
    decision: str
    reason: str
    proof_refs: tuple[str, ...]
    tests_passed: bool
    boundary_passed: bool
    source_mutation_allowed: bool
    delete_source_allowed: bool
    archive_source_allowed: bool
    stable_map_update_required: bool
    attention_promotion_update_required: bool
    operator_final_decision_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChiefRepairRequeueRecommendation:
    recommendation_id: str
    failed_or_partial_task_ref: str
    failure_reason: str
    missing_proof: tuple[str, ...]
    missing_tests: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    boundary_issue: str
    suggested_requeue_lane: str
    suggested_repair_package_type: str
    requires_operator_review: bool
    requires_hermes_review: bool
    requires_guardian_gate: bool
    can_run_unattended: bool
    why_not_unattended: str
    next_safe_move: str


@dataclass(frozen=True)
class QuietWithProofReceipt:
    quiet_receipt_id: str
    item_ref: str
    quiet_reason: str
    proof_refs: tuple[str, ...]
    retrieval_path: str
    reopen_condition: str
    staleness_condition: str
    operator_visibility_level: str
    stable_map_update_required: bool
    evidence_drawer_ref: str
    created_by: str
    authority_granted: bool


@dataclass(frozen=True)
class ChiefHarnessExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    completion_status_count: int
    reconciliation_state_count: int
    harness_receipt_count: int
    cross_off_decision_count: int
    repair_requeue_count: int
    quiet_receipt_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_harness_receipts() -> tuple[ChiefTestHarnessReceipt, ...]:
    common_boundary = (
        "no live execution authority",
        "no queue/autonomy",
        "no credentials",
        "no send/submit/approval",
        "no unrelated dirty-file cleanup",
    )
    return (
        ChiefTestHarnessReceipt(
            receipt_id="security_pass_surface_checkpoint",
            task_title="Security Pass Surface Checkpoint",
            source_type="mac_codex_worker_report",
            source_refs=("Mission Control Security Pass cockpit lane",),
            worker_report_refs=("Mac Codex worker report",),
            package_refs=(),
            changed_artifact_refs=("Mission Control app surface files",),
            commit_refs=("5d7f3c3b1d516f5c0eba9daf38b548c789640320",),
            test_commands=("xcodebuild/build validation",),
            test_results=("build passed",),
            build_results=("build passed",),
            screenshot_refs=("Security Pass cockpit screenshots",),
            generated_read_model_refs=(),
            stable_map_refs=("security_pass",),
            receipt_refs=("Mac checkpoint commit",),
            boundary_checks=common_boundary,
            validation_status="VALIDATION_PASSED",
            reconciliation_status="RECONCILED_WITH_PROOF",
            completion_status="COMPLETED_WITH_PROOF",
            chief_recommendation="cross_off_allowed_with_proof",
            hermes_review_required=False,
            guardian_gate_required=False,
            operator_review_required=False,
            cross_off_allowed=True,
            requeue_required=False,
            park_required=False,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Mark complete by receipt; do not mutate source notes.",
        ),
        ChiefTestHarnessReceipt(
            receipt_id="security_pass_contract_pass_1",
            task_title="Security Pass Contract Pass 1",
            source_type="pc_codex_contract_lane",
            source_refs=("security_pass_contract pass 1",),
            worker_report_refs=("PC Codex pass 1 report",),
            package_refs=(),
            changed_artifact_refs=("security_pass_contract.py", "tests/test_security_pass_contract.py"),
            commit_refs=("f8cfaab2723b37b816470ff9af26f085fbaeb3ea",),
            test_commands=("python3 scripts/export_security_pass_contract.py --format summary", "python3 -m pytest tests/test_security_pass_contract.py -q"),
            test_results=("export passed", "tests passed"),
            build_results=(),
            screenshot_refs=(),
            generated_read_model_refs=("generated/read_models/security_pass_contract.json",),
            stable_map_refs=("security_pass later included in stable map",),
            receipt_refs=("local checkpoint commit", "stable map v5 receipt"),
            boundary_checks=common_boundary,
            validation_status="VALIDATION_PASSED",
            reconciliation_status="RECONCILED_WITH_PROOF",
            completion_status="COMPLETED_WITH_PROOF",
            chief_recommendation="cross_off_allowed_with_proof",
            hermes_review_required=False,
            guardian_gate_required=False,
            operator_review_required=False,
            cross_off_allowed=True,
            requeue_required=False,
            park_required=False,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Quiet with proof; stable map was updated later.",
        ),
        ChiefTestHarnessReceipt(
            receipt_id="markdown_knowledge_atlas_capability",
            task_title="Markdown Knowledge Atlas Capability",
            source_type="existing_backend_capability",
            source_refs=("markdown_knowledge_atlas.py", "markdown_evidence_ingestion.py", "corpus_atlas.py"),
            worker_report_refs=("Markdown terrain mapping readback",),
            package_refs=(),
            changed_artifact_refs=(),
            commit_refs=(),
            test_commands=("existing metadata/readback validation",),
            test_results=("capability evidenced",),
            build_results=(),
            screenshot_refs=(),
            generated_read_model_refs=("security_pass_contract.json",),
            stable_map_refs=("markdown_terrain_security_decision_summary",),
            receipt_refs=("security pass metadata decision",),
            boundary_checks=("no new crawler", "no broad body ingestion", "no file moves"),
            validation_status="VALIDATION_PASSED",
            reconciliation_status="BUILT_NOT_SURFACED",
            completion_status="PARKED_WITH_PROOF",
            chief_recommendation="quiet_with_proof_or_future_visibility_surface",
            hermes_review_required=True,
            guardian_gate_required=False,
            operator_review_required=False,
            cross_off_allowed=False,
            requeue_required=False,
            park_required=True,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Keep as proof/detail unless linked to an original task or future visibility lane.",
        ),
        ChiefTestHarnessReceipt(
            receipt_id="future_invoicing_state_machine_audit",
            task_title="Future Invoicing State Machine Audit",
            source_type="agy_gemini_report",
            source_refs=("future_invoicing_state_machine_audit",),
            worker_report_refs=("Agy/Gemini stress-test report",),
            package_refs=(),
            changed_artifact_refs=(),
            commit_refs=(),
            test_commands=(),
            test_results=(),
            build_results=(),
            screenshot_refs=(),
            generated_read_model_refs=("security_pass_contract.json",),
            stable_map_refs=(),
            receipt_refs=("worker output intake record",),
            boundary_checks=("no invoice generation", "no ledger write", "no email dispatch", "no account authority"),
            validation_status="NOT_EXECUTABLE_STRESS_TEST",
            reconciliation_status="MATCHED_TO_WORKER_REPORT",
            completion_status="PARKED_WITH_PROOF",
            chief_recommendation="preserve_as_stress_test_artifact",
            hermes_review_required=True,
            guardian_gate_required=True,
            operator_review_required=False,
            cross_off_allowed=False,
            requeue_required=False,
            park_required=True,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Park with proof; cross-off only if tied to a specific source task.",
        ),
        ChiefTestHarnessReceipt(
            receipt_id="capital_hilton_finance_preview",
            task_title="Capital Hilton Finance Preview",
            source_type="mac_codex_app_lane",
            source_refs=("Capital Hilton / Finance preview",),
            worker_report_refs=("Mac Finance World preview report",),
            package_refs=("Capital Hilton proof metadata packet",),
            changed_artifact_refs=("Finance World preview surface",),
            commit_refs=("5c0b3dd836c9f81e48c884bd3a7788b61f854cc0",),
            test_commands=("app build validation",),
            test_results=("preview surfaced",),
            build_results=("build passed",),
            screenshot_refs=("Finance World preview screenshots",),
            generated_read_model_refs=("capital_hilton_proof_metadata_packet.json",),
            stable_map_refs=("capital_hilton_proof_metadata",),
            receipt_refs=("Finance preview checkpoint",),
            boundary_checks=("no Coupa", "no invoice generation", "no send/submit/approval", "candidate facts not proof"),
            validation_status="VALIDATION_PASSED",
            reconciliation_status="MATCHED_TO_WORLD_LANE",
            completion_status="COMPLETED_WITH_PROOF",
            chief_recommendation="quiet_preview_with_proof_keep_action_blocked",
            hermes_review_required=False,
            guardian_gate_required=True,
            operator_review_required=False,
            cross_off_allowed=True,
            requeue_required=False,
            park_required=False,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Quiet preview completion while leaving invoice/action authority blocked.",
        ),
        ChiefTestHarnessReceipt(
            receipt_id="autonomous_capital_pipeline_experiment",
            task_title="Autonomous Capital Pipeline Experiment",
            source_type="parked_r_and_d_experiment_contract",
            source_refs=("parked_autonomous_capital_pipeline_experiment",),
            worker_report_refs=("Post-Security Governance Prompt 1",),
            package_refs=(),
            changed_artifact_refs=("parked_autonomous_capital_pipeline_experiment.py",),
            commit_refs=(),
            test_commands=("python3 -m pytest tests/test_parked_autonomous_capital_pipeline_experiment.py -q",),
            test_results=("tests passed",),
            build_results=(),
            screenshot_refs=(),
            generated_read_model_refs=("parked_autonomous_capital_pipeline_experiment.json",),
            stable_map_refs=(),
            receipt_refs=("parked R&D experiment read-model",),
            boundary_checks=("no spend authority", "no account authority", "no deployment", "no queue/autonomy"),
            validation_status="VALIDATION_PASSED",
            reconciliation_status="MATCHED_TO_RECEIPT",
            completion_status="PARKED_WITH_PROOF",
            chief_recommendation="cross_off_only_as_experiment_parked",
            hermes_review_required=False,
            guardian_gate_required=True,
            operator_review_required=False,
            cross_off_allowed=True,
            requeue_required=False,
            park_required=True,
            quarantine_required=False,
            quiet_with_proof_allowed=True,
            next_safe_move="Cross off only the parking task, not the future business experiment.",
        ),
    )


def default_cross_off_decisions() -> tuple[CrossOffDecisionRecord, ...]:
    return (
        CrossOffDecisionRecord(
            cross_off_id="security_pass_surface_checkpoint_cross_off",
            source_task_ref="Mission Control Security Pass cockpit lane",
            completion_receipt_ref="security_pass_surface_checkpoint",
            decision="CROSS_OFF_ALLOWED_WITH_PROOF",
            reason="Build proof, screenshot proof, commit, and boundary checks exist.",
            proof_refs=("build passed", "screenshots captured", "commit 5d7f3c3b1d516f5c0eba9daf38b548c789640320"),
            tests_passed=True,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=False,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Create/keep completion receipt; do not delete source task.",
        ),
        CrossOffDecisionRecord(
            cross_off_id="security_pass_contract_pass_1_cross_off",
            source_task_ref="security_pass_contract_pass_1",
            completion_receipt_ref="security_pass_contract_pass_1",
            decision="CROSS_OFF_ALLOWED_WITH_PROOF",
            reason="Contract, tests, generated read-model, commit, and later stable-map receipt exist.",
            proof_refs=("tests passed", "commit f8cfaab2723b37b816470ff9af26f085fbaeb3ea", "stable map v5 receipt"),
            tests_passed=True,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=False,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Quiet with proof.",
        ),
        CrossOffDecisionRecord(
            cross_off_id="markdown_knowledge_atlas_visibility_cross_off",
            source_task_ref="markdown_knowledge_atlas_capability",
            completion_receipt_ref="markdown_knowledge_atlas_capability",
            decision="PARK_WITH_PROOF",
            reason="Capability exists, but app visibility is future work and not tied to a concrete source task.",
            proof_refs=("metadata capability evidence",),
            tests_passed=True,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=True,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Keep as proof/detail or future visibility lane.",
        ),
        CrossOffDecisionRecord(
            cross_off_id="future_invoicing_audit_cross_off",
            source_task_ref="future_invoicing_state_machine_audit",
            completion_receipt_ref="future_invoicing_state_machine_audit",
            decision="PARK_WITH_PROOF",
            reason="Stress-test artifact captured; implementation remains blocked.",
            proof_refs=("worker output intake record",),
            tests_passed=False,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=False,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Preserve as future stress-test artifact.",
        ),
        CrossOffDecisionRecord(
            cross_off_id="capital_hilton_preview_cross_off",
            source_task_ref="capital_hilton_finance_preview",
            completion_receipt_ref="capital_hilton_finance_preview",
            decision="CROSS_OFF_ALLOWED_WITH_PROOF",
            reason="Preview built and receipted; action authority remains blocked.",
            proof_refs=("Finance preview checkpoint", "capital_hilton_proof_metadata_packet.json"),
            tests_passed=True,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=False,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Quiet preview lane with proof; keep invoice action blocked.",
        ),
        CrossOffDecisionRecord(
            cross_off_id="autonomous_capital_pipeline_parked_cross_off",
            source_task_ref="autonomous_capital_pipeline_experiment",
            completion_receipt_ref="autonomous_capital_pipeline_experiment",
            decision="PARK_WITH_PROOF",
            reason="Parking task completed; future experiment remains high-risk and blocked.",
            proof_refs=("parked_autonomous_capital_pipeline_experiment.json",),
            tests_passed=True,
            boundary_passed=True,
            source_mutation_allowed=False,
            delete_source_allowed=False,
            archive_source_allowed=False,
            stable_map_update_required=False,
            attention_promotion_update_required=True,
            operator_final_decision_required=False,
            next_safe_move="Cross off only the preservation/parking work.",
        ),
    )


def default_repair_requeue_recommendations() -> tuple[ChiefRepairRequeueRecommendation, ...]:
    return (
        ChiefRepairRequeueRecommendation(
            recommendation_id="partial_missing_tests_requeue",
            failed_or_partial_task_ref="partial_worker_output_without_tests",
            failure_reason="Worker reported done but validation proof is missing.",
            missing_proof=("test receipt",),
            missing_tests=("focused pytest or build command",),
            missing_receipts=("completion receipt",),
            boundary_issue="none_observed",
            suggested_requeue_lane="bounded_test_receipt_lane",
            suggested_repair_package_type="test_validation_package",
            requires_operator_review=False,
            requires_hermes_review=False,
            requires_guardian_gate=False,
            can_run_unattended=False,
            why_not_unattended="This contract only recommends requeue metadata; queue authority is not granted.",
            next_safe_move="Create a requeue candidate for missing tests.",
        ),
        ChiefRepairRequeueRecommendation(
            recommendation_id="authority_overclaim_quarantine",
            failed_or_partial_task_ref="worker_output_claims_new_authority",
            failure_reason="Output appears to require new account/tool/runtime/financial authority.",
            missing_proof=("security delta review receipt",),
            missing_tests=(),
            missing_receipts=("authority boundary receipt",),
            boundary_issue="authority_overclaim",
            suggested_requeue_lane="security_delta_review",
            suggested_repair_package_type="security_delta_review_package",
            requires_operator_review=True,
            requires_hermes_review=True,
            requires_guardian_gate=True,
            can_run_unattended=False,
            why_not_unattended="New authority must route to Security Delta Review or fail closed.",
            next_safe_move="Quarantine or route to Security Delta Review; do not run repair.",
        ),
    )


def default_quiet_with_proof_receipts() -> tuple[QuietWithProofReceipt, ...]:
    return (
        QuietWithProofReceipt(
            quiet_receipt_id="security_pass_surface_quiet_with_proof",
            item_ref="security_pass_surface_checkpoint",
            quiet_reason="completed_with_build_screenshot_commit_proof",
            proof_refs=("build passed", "screenshots captured", "checkpoint commit"),
            retrieval_path="evidence drawer / checkpoint commit / screenshot bundle",
            reopen_condition="regression, stale stable-map data, or operator request",
            staleness_condition="new Security Pass map generation supersedes surface",
            operator_visibility_level="summary_or_drill_down",
            stable_map_update_required=False,
            evidence_drawer_ref="security_pass_surface_checkpoint_evidence",
            created_by="ChiefTestHarnessReceipt",
            authority_granted=False,
        ),
        QuietWithProofReceipt(
            quiet_receipt_id="capital_hilton_preview_quiet_with_proof",
            item_ref="capital_hilton_finance_preview",
            quiet_reason="preview_built_action_still_blocked",
            proof_refs=("Finance preview checkpoint", "Capital Hilton proof metadata packet"),
            retrieval_path="Finance World preview proof drawer",
            reopen_condition="new protected proof metadata arrives or action authority requested",
            staleness_condition="Capital Hilton proof metadata bundle superseded",
            operator_visibility_level="world_preview_summary",
            stable_map_update_required=False,
            evidence_drawer_ref="capital_hilton_preview_evidence",
            created_by="ChiefTestHarnessReceipt",
            authority_granted=False,
        ),
    )


def chief_test_harness_boundary() -> dict[str, Any]:
    return {
        "chief_may_verify": [
            "build/test proof",
            "schema validation",
            "generated read-model presence",
            "stable-map inclusion",
            "screenshot proof",
            "receipt existence",
            "boundary assertions",
            "no authority leaks",
            "no dirty unrelated files swept in",
        ],
        "chief_may_not": [
            "run repairs automatically",
            "mutate files",
            "delete source tasks",
            "approve itself",
            "start agents",
            "start queue execution",
            "override Guardian/Operator/Hermes gates",
        ],
        "chief_self_authorization_allowed": False,
        "chief_repair_execution_allowed": False,
    }


def relationship_to_operator_attention_promotion() -> dict[str, str]:
    return {
        "completed_with_proof": "quiet_with_proof",
        "partial": "requeue_candidate",
        "built_not_surfaced": "visibility_gap",
        "failed": "repair_required",
        "duplicate": "merge_or_reject",
        "unsafe": "quarantine",
    }


def relationship_to_security_delta() -> dict[str, bool]:
    return {
        "new_authority_routes_to_security_delta": True,
        "fail_closed_if_security_delta_missing": True,
        "repair_path_grants_new_authority": False,
    }


def relationship_to_full_trust() -> dict[str, Any]:
    return {
        "full_trust_clearance_referenced_as_future_eligibility_state": True,
        "required_for_all_current_cross_off_examples": False,
        "full_trust_grants_execution_by_itself": False,
    }


def _all_authority_flags_false() -> bool:
    return all(value is False for value in NO_ACTION_AUTHORITY_FLAGS.values())


def build_chief_test_harness_cross_off_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    harness_receipts = [asdict(item) for item in default_harness_receipts()]
    cross_off_decisions = [asdict(item) for item in default_cross_off_decisions()]
    repair_requeue = [asdict(item) for item in default_repair_requeue_recommendations()]
    quiet_receipts = [asdict(item) for item in default_quiet_with_proof_receipts()]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "chief_test_harness_cross_off_receipt_contract_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": "DETERMINISTIC_NON_EXECUTING_CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPTS",
        "core_doctrine": {
            "chief_is_future_lead_foreman_for_verifying_work_completion": True,
            "worker_said_done_is_not_enough": True,
            "cross_off_is_not_deletion": True,
            "cross_off_creates_completion_receipt_or_candidate": True,
            "source_task_remains_traceable_after_cross_off": True,
            "chief_cannot_self_authorize": True,
        },
        "completion_statuses": list(COMPLETION_STATUSES),
        "reconciliation_states": list(RECONCILIATION_STATES),
        "cross_off_decisions": list(CROSS_OFF_DECISIONS),
        "schemas": {
            "ChiefTestHarnessReceipt": list(REQUIRED_HARNESS_FIELDS),
            "CrossOffDecisionRecord": list(REQUIRED_CROSS_OFF_FIELDS),
            "ChiefRepairRequeueRecommendation": list(REQUIRED_REPAIR_FIELDS),
            "QuietWithProofReceipt": list(REQUIRED_QUIET_FIELDS),
        },
        "authority_boundary": dict(NO_ACTION_AUTHORITY_FLAGS),
        "hard_rules": {
            "source_mutation_allowed": False,
            "delete_source_allowed": False,
            "automatic_cross_off_allowed": False,
            "cross_off_creates_receipt_not_file_deletion": True,
            "repair_requeue_is_recommendation_metadata_only": True,
            "repair_requeue_executes": False,
        },
        "chief_test_harness_boundary": chief_test_harness_boundary(),
        "default_harness_receipts": harness_receipts,
        "default_cross_off_decisions": cross_off_decisions,
        "default_repair_requeue_recommendations": repair_requeue,
        "default_quiet_with_proof_receipts": quiet_receipts,
        "relationship_to_operator_attention_promotion": relationship_to_operator_attention_promotion(),
        "relationship_to_security_delta": relationship_to_security_delta(),
        "relationship_to_full_trust": relationship_to_full_trust(),
        "machine_proof": {
            "all_completion_statuses_present": len(COMPLETION_STATUSES) == 16,
            "all_reconciliation_states_present": len(RECONCILIATION_STATES) == 13,
            "all_cross_off_decisions_present": len(CROSS_OFF_DECISIONS) == 12,
            "default_harness_receipt_count": len(harness_receipts),
            "default_cross_off_decision_count": len(cross_off_decisions),
            "default_repair_requeue_count": len(repair_requeue),
            "default_quiet_receipt_count": len(quiet_receipts),
            "cross_off_never_deletes_or_mutates_source": all(
                item["source_mutation_allowed"] is False
                and item["delete_source_allowed"] is False
                and item["archive_source_allowed"] is False
                for item in cross_off_decisions
            ),
            "automatic_cross_off_allowed": False,
            "repair_requeue_recommendations_do_not_execute": all(item["can_run_unattended"] is False for item in repair_requeue),
            "quiet_with_proof_preserves_retrieval_path_and_proof_refs": all(
                item["retrieval_path"] and item["proof_refs"] for item in quiet_receipts
            ),
            "chief_self_authorization_allowed": False,
            "chief_repair_execution_allowed": False,
            "new_authority_routes_to_security_delta": True,
            "completed_items_can_quiet_only_with_proof": True,
            "failed_partial_items_are_candidates_only": True,
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
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
        "# Chief Test Harness / Cross-Off Receipt Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract defines when Chief can later say work is complete enough to quiet the helm. A worker saying done is not enough. Chief needs source refs, changed artifacts, tests or validation proof, receipts, boundary checks, and required Operator/Guardian/Hermes review. Cross-off never deletes the source note; it creates a completion receipt or candidate.",
        "",
        "## Completion Statuses",
        "",
    ]
    for status in payload["completion_statuses"]:
        lines.append(f"- `{status}`")
    lines.extend(["", "## Reconciliation States", ""])
    for state in payload["reconciliation_states"]:
        lines.append(f"- `{state}`")
    lines.extend(["", "## Default Harness Receipts", ""])
    for receipt in payload["default_harness_receipts"]:
        lines.append(
            f"- `{receipt['receipt_id']}`: `{receipt['completion_status']}` / "
            f"`{receipt['reconciliation_status']}`. Recommendation: {receipt['chief_recommendation']}."
        )
    lines.extend(["", "## Cross-Off Decisions", ""])
    for decision in payload["default_cross_off_decisions"]:
        lines.append(
            f"- `{decision['cross_off_id']}`: `{decision['decision']}`. "
            f"Source mutation: `{str(decision['source_mutation_allowed']).lower()}`; delete source: `{str(decision['delete_source_allowed']).lower()}`."
        )
    lines.extend(
        [
            "",
            "## Repair / Requeue",
            "",
            "- Repair and requeue records are recommendations only.",
            "- They do not queue, run, repair, or grant unattended execution.",
            "",
            "## Quiet With Proof",
            "",
            "- Quiet receipts preserve proof refs, retrieval paths, reopen conditions, and evidence drawer refs.",
            "",
            "## Security Delta And FULL_TRUST",
            "",
            "- Any cross-off or repair path that requires new authority routes to Security Delta Review or fails closed.",
            "- FULL_TRUST_CLEARANCE is referenced only as a future eligibility state and does not grant execution by itself.",
            "",
            "## Machine Proof",
            "",
            f"- Default harness receipts: `{proof['default_harness_receipt_count']}`.",
            f"- Cross-off decisions: `{proof['default_cross_off_decision_count']}`.",
            f"- Repair/requeue recommendations: `{proof['default_repair_requeue_count']}`.",
            f"- Quiet receipts: `{proof['default_quiet_receipt_count']}`.",
            f"- Cross-off never deletes or mutates source: `{str(proof['cross_off_never_deletes_or_mutates_source']).lower()}`.",
            f"- Automatic cross-off allowed: `{str(proof['automatic_cross_off_allowed']).lower()}`.",
            f"- Chief self-authorization allowed: `{str(proof['chief_self_authorization_allowed']).lower()}`.",
            f"- Action authority granted: `{str(proof['action_authority_granted']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_chief_test_harness_cross_off_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ChiefHarnessExportResult:
    payload = build_chief_test_harness_cross_off_receipt_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return ChiefHarnessExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        completion_status_count=len(payload["completion_statuses"]),
        reconciliation_state_count=len(payload["reconciliation_states"]),
        harness_receipt_count=len(payload["default_harness_receipts"]),
        cross_off_decision_count=len(payload["default_cross_off_decisions"]),
        repair_requeue_count=len(payload["default_repair_requeue_recommendations"]),
        quiet_receipt_count=len(payload["default_quiet_with_proof_receipts"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Chief Test Harness / Cross-Off Receipt Contract v0 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_chief_test_harness_cross_off_receipt_contract(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "completion_status_count": result.completion_status_count,
        "reconciliation_state_count": result.reconciliation_state_count,
        "harness_receipt_count": result.harness_receipt_count,
        "cross_off_decision_count": result.cross_off_decision_count,
        "repair_requeue_count": result.repair_requeue_count,
        "quiet_receipt_count": result.quiet_receipt_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Chief Test Harness / Cross-Off Receipt Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "COMPLETION_STATUSES",
    "CROSS_OFF_DECISIONS",
    "ChiefRepairRequeueRecommendation",
    "ChiefTestHarnessReceipt",
    "CrossOffDecisionRecord",
    "NO_ACTION_AUTHORITY_FLAGS",
    "QuietWithProofReceipt",
    "READ_MODEL_ID",
    "RECONCILIATION_STATES",
    "SCHEMA_VERSION",
    "build_chief_test_harness_cross_off_receipt_contract",
    "chief_test_harness_boundary",
    "default_cross_off_decisions",
    "default_harness_receipts",
    "default_quiet_with_proof_receipts",
    "default_repair_requeue_recommendations",
    "export_chief_test_harness_cross_off_receipt_contract",
    "format_operator_markdown",
    "relationship_to_full_trust",
    "relationship_to_operator_attention_promotion",
    "relationship_to_security_delta",
    "stable_json",
]
