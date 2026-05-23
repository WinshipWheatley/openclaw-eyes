"""Capital Hilton Coupa / PO retrieval automation candidate contract v0.

This read-model treats the Capital Hilton Coupa / PO / payment-reference
lookup as a future governed automation candidate. It does not access Coupa,
open browsers, use network, handle credentials, read portal bodies, generate
invoices, send messages, write ledgers, or grant runtime authority.
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

SCHEMA_VERSION = "capital_hilton_coupa_po_retrieval_automation_candidate_v0"
READ_MODEL_ID = "capital_hilton_coupa_po_retrieval_automation_candidate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

PROOF_ITEM_ID = "coupa_po_payment_reference_metadata"
SHARED_EXECUTION_PATH_ID = "protected_finance_proof_metadata_intake"

PROOF_RESOLUTION_BATCH_REF = "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json"
PROTECTED_REFERENCE_PLACEHOLDER_REF = "generated/read_models/capital_hilton_protected_reference_placeholder.json"
GUARDIAN_REVIEW_PACKET_REF = "generated/read_models/capital_hilton_guardian_review_packet.json"
PROOF_QUIETING_PROGRESS_STATE_REF = "generated/read_models/capital_hilton_proof_quieting_progress_state.json"
PROTECTED_PROOF_INTAKE_REF = "generated/read_models/capital_hilton_protected_proof_intake.json"

AUTOMATION_STATUSES = (
    "MANUAL_FALLBACK_ONLY_CURRENTLY",
    "ASSISTED_MANUAL_CANDIDATE",
    "SUPERVISED_AUTOMATION_CANDIDATE",
    "READ_ONLY_AUTOMATION_CANDIDATE",
    "PROTECTED_LOGIN_AUTOMATION_CANDIDATE",
    "AUTONOMOUS_RETRIEVAL_CANDIDATE",
    "BLOCKED_PENDING_SECURITY_DELTA",
    "BLOCKED_PENDING_PROTECTED_ACCESS_BROKER",
    "UNKNOWN_FAIL_CLOSED",
)

AUTOMATION_STAGES = (
    "STAGE_0_MANUAL_INSTRUCTIONS",
    "STAGE_1_GUIDED_MANUAL_SESSION",
    "STAGE_2_SUPERVISED_BROWSER_PREVIEW",
    "STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN",
    "STAGE_4_PROTECTED_CREDENTIAL_BROKER_TRIAL",
    "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL",
    "STAGE_6_ACTION_OR_SUBMISSION_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

GATE_TYPES = (
    "SECURITY_DELTA",
    "PROTECTED_ACCESS",
    "CREDENTIAL_BROKER",
    "BROWSER_AUTOMATION",
    "COMPLIANCE_TERMS",
    "GUARDIAN_REVIEW",
    "OPERATOR_APPROVAL",
    "RECEIPT_PROOF",
    "NO_MUTATION_BOUNDARY",
)

NO_CURRENT_AUTHORITY_FLAGS = {
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "network_operation_allowed": False,
    "credential_handling_allowed": False,
    "protected_credential_broker_active": False,
    "portal_login_allowed": False,
    "portal_read_allowed": False,
    "portal_write_allowed": False,
    "invoice_generation_allowed": False,
    "invoice_submission_allowed": False,
    "ledger_write_allowed": False,
    "email_send_allowed": False,
    "payment_mutation_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}

FUTURE_NON_AUTHORITY_FLAGS = {
    "protected_access_broker_required_future": True,
    "credential_broker_required_future": True,
    "browser_automation_required_future": True,
    "network_required_future": True,
    "read_only_portal_lookup_future_candidate": True,
    "autonomous_retrieval_future_candidate": True,
    "future_flags_grant_current_authority": False,
}

REQUIRED_INPUT_CANDIDATES = (
    "client/vendor identity",
    "invoice lane/session id",
    "expected date range",
    "expected amount",
    "Capital Hilton label",
    "PO/payment reference target",
    "credential broker token later, not now",
    "operator authorization later",
    "Guardian approval later",
)

REQUIRED_SAFE_OUTPUTS = (
    "PO/reference number if found",
    "no-reference-found receipt",
    "lookup attempted receipt",
    "portal route label",
    "timestamp",
    "source surface label",
    "redacted proof metadata",
    "hash/receipt reference",
)

BLOCKED_OUTPUTS = (
    "credentials",
    "session cookies",
    "raw portal screenshots unless protected-reference only",
    "raw portal body scrape",
    "bank/check/remit data unless protected metadata only",
    "invoice submission",
    "payment request mutation",
    "email/send/submit action",
)

REQUIRED_RECEIPTS = (
    "operator_authorization_receipt_future",
    "security_delta_receipt_future",
    "protected_access_broker_receipt_future",
    "credential_broker_receipt_future",
    "read_only_lookup_attempt_receipt_future",
    "no_mutation_boundary_receipt_future",
    "guardian_metadata_review_receipt_future",
    "rollback_or_stop_receipt_if_triggered",
)

REQUIRED_GATES = (
    "security_delta_for_external_portal",
    "protected_access_broker_gate",
    "credential_handling_gate",
    "browser_automation_sandbox_gate",
    "read_only_lookup_contract_gate",
    "portal_terms_compliance_gate",
    "guardian_metadata_review_gate",
    "operator_authorization_gate",
    "receipt_and_rollback_gate",
    "no_submission_mutation_gate",
)


@dataclass(frozen=True)
class ExternalWorkflowAutomationCandidate:
    candidate_id: str
    display_name: str
    workflow_name: str
    target_world: str
    target_lane: str
    external_surface: str
    business_purpose: str
    current_manual_fallback: str
    automation_goal: str
    automation_status: str
    automation_stage: str
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]
    safe_outputs: tuple[str, ...]
    blocked_outputs: tuple[str, ...]
    required_receipts: tuple[str, ...]
    required_gates: tuple[str, ...]
    failure_modes: tuple[str, ...]
    rollback_or_stop_conditions: tuple[str, ...]
    guardian_review_required: bool
    operator_approval_required: bool
    protected_access_broker_required: bool
    credential_broker_required: bool
    browser_automation_required: bool
    network_required_future: bool
    current_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class AutomationReadinessGate:
    gate_id: str
    display_name: str
    gate_type: str
    required_for_stage: tuple[str, ...]
    required_evidence: tuple[str, ...]
    allowed_result: tuple[str, ...]
    blocked_result: tuple[str, ...]
    current_status: str
    next_safe_move: str


@dataclass(frozen=True)
class ExternalWorkflowStopCondition:
    condition_id: str
    trigger: str
    severity: str
    required_stop_action: str
    operator_visibility: str
    receipt_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class AutomationTrialStage:
    stage_id: str
    display_name: str
    what_it_tests: str
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    required_gates: tuple[str, ...]
    success_receipt: str
    failure_receipt: str
    can_advance_to_next_stage: bool
    next_stage: str


@dataclass(frozen=True)
class CoupaPoRetrievalAutomationCandidateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    candidate_count: int
    readiness_gate_count: int
    stop_condition_count: int
    trial_stage_count: int
    current_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_default_automation_candidate() -> ExternalWorkflowAutomationCandidate:
    return ExternalWorkflowAutomationCandidate(
        candidate_id="capital_hilton_coupa_po_reference_retrieval",
        display_name="Capital Hilton Coupa / PO Reference Retrieval",
        workflow_name="Capital Hilton Coupa / PO / payment-reference retrieval",
        target_world="Finance",
        target_lane="Capital Hilton",
        external_surface="Coupa supplier portal / Hilton AP payment reference surface",
        business_purpose=(
            "Retrieve or confirm Coupa / PO / payment reference metadata needed for the "
            "Capital Hilton invoice packet."
        ),
        current_manual_fallback=(
            "Winship manually logs in and copies only safe metadata, such as a PO/reference "
            "number, or confirms that no reference exists."
        ),
        automation_goal=(
            "OpenClaw eventually performs a governed read-only lookup and records a protected "
            "metadata receipt without exposing credentials or raw portal contents."
        ),
        automation_status="BLOCKED_PENDING_PROTECTED_ACCESS_BROKER",
        automation_stage="STAGE_0_MANUAL_INSTRUCTIONS",
        required_inputs=REQUIRED_INPUT_CANDIDATES,
        required_outputs=("protected metadata receipt", "lookup status receipt", "stop receipt if blocked"),
        safe_outputs=REQUIRED_SAFE_OUTPUTS,
        blocked_outputs=BLOCKED_OUTPUTS,
        required_receipts=REQUIRED_RECEIPTS,
        required_gates=REQUIRED_GATES,
        failure_modes=(
            "login challenge / MFA required",
            "credentials unavailable",
            "portal layout changed",
            "unexpected payment/account page",
            "mutation/submit button encountered",
            "raw sensitive data exposed",
            "unknown account/session state",
            "PO/reference ambiguous",
            "duplicate invoice/reference risk",
            "compliance/terms uncertainty",
            "Guardian quarantine trigger",
            "operator cancels",
        ),
        rollback_or_stop_conditions=(
            "stop before credential entry when broker is unavailable",
            "stop before any submit, save, payment, invoice, or mutation control",
            "stop and quarantine if raw sensitive portal content becomes exposed",
            "stop and request operator decision if PO/reference is ambiguous",
            "stop and record failure receipt if compliance or terms are uncertain",
        ),
        guardian_review_required=True,
        operator_approval_required=True,
        protected_access_broker_required=True,
        credential_broker_required=True,
        browser_automation_required=True,
        network_required_future=True,
        current_authority_granted=False,
        next_safe_move=(
            "keep manual fallback available while modeling security delta, protected access "
            "broker, read-only lookup, receipt, and rollback requirements"
        ),
    )


def build_readiness_gates() -> list[AutomationReadinessGate]:
    def gate(
        gate_id: str,
        display_name: str,
        gate_type: str,
        required_for_stage: tuple[str, ...],
        required_evidence: tuple[str, ...],
        allowed_result: tuple[str, ...],
        blocked_result: tuple[str, ...],
        next_safe_move: str,
    ) -> AutomationReadinessGate:
        return AutomationReadinessGate(
            gate_id=gate_id,
            display_name=display_name,
            gate_type=gate_type,
            required_for_stage=required_for_stage,
            required_evidence=required_evidence,
            allowed_result=allowed_result,
            blocked_result=blocked_result,
            current_status="NOT_SATISFIED_CURRENTLY",
            next_safe_move=next_safe_move,
        )

    return [
        gate(
            "security_delta_for_external_portal",
            "Security Delta for External Portal",
            "SECURITY_DELTA",
            ("STAGE_2_SUPERVISED_BROWSER_PREVIEW", "STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN"),
            ("security pass delta receipt", "external portal risk review"),
            ("read-only preview may be considered later",),
            ("live portal access now", "action authority"),
            "prepare a security delta before any Coupa/browser/network lane",
        ),
        gate(
            "protected_access_broker_gate",
            "Protected Access Broker Gate",
            "PROTECTED_ACCESS",
            ("STAGE_4_PROTECTED_CREDENTIAL_BROKER_TRIAL", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("protected access broker contract", "Guardian review receipt"),
            ("brokered access may be trialed later without exposing raw secrets",),
            ("direct credential access by agents",),
            "define broker requirements without activating the broker",
        ),
        gate(
            "credential_handling_gate",
            "Credential Handling Gate",
            "CREDENTIAL_BROKER",
            ("STAGE_4_PROTECTED_CREDENTIAL_BROKER_TRIAL",),
            ("credential broker receipt", "operator authorization receipt"),
            ("credential never printed, stored, or delivered to agent",),
            ("credential storage", "credential display", "credential inference"),
            "keep credentials outside normal read-models and outside agent context",
        ),
        gate(
            "browser_automation_sandbox_gate",
            "Browser Automation Sandbox Gate",
            "BROWSER_AUTOMATION",
            ("STAGE_2_SUPERVISED_BROWSER_PREVIEW", "STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN"),
            ("sandbox receipt", "read-only navigation plan", "hard-stop controls"),
            ("supervised read-only preview candidate",),
            ("unsupervised browser run now", "submit/save/mutation controls"),
            "model sandbox and hard-stop controls before any browser trial",
        ),
        gate(
            "read_only_lookup_contract_gate",
            "Read-Only Lookup Contract Gate",
            "RECEIPT_PROOF",
            ("STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("read-only scope contract", "lookup receipt schema", "no-mutation receipt"),
            ("lookup metadata receipt may be produced later",),
            ("portal body scrape", "invoice submit", "payment mutation"),
            "define lookup receipt and no-mutation proof before lookup",
        ),
        gate(
            "portal_terms_compliance_gate",
            "Portal Terms Compliance Gate",
            "COMPLIANCE_TERMS",
            ("STAGE_2_SUPERVISED_BROWSER_PREVIEW", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("operator compliance decision", "terms posture receipt"),
            ("automation remains eligible for later review",),
            ("terms uncertainty", "forbidden automation"),
            "confirm terms posture before any portal automation candidate advances",
        ),
        gate(
            "guardian_metadata_review_gate",
            "Guardian Metadata Review Gate",
            "GUARDIAN_REVIEW",
            ("STAGE_1_GUIDED_MANUAL_SESSION", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("Guardian metadata review packet", "redaction receipt"),
            ("protected metadata may be promoted later",),
            ("raw sensitive output", "action approval"),
            "route only redacted metadata and receipts to Guardian",
        ),
        gate(
            "operator_authorization_gate",
            "Operator Authorization Gate",
            "OPERATOR_APPROVAL",
            ("STAGE_1_GUIDED_MANUAL_SESSION", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("operator approval receipt", "scope confirmation"),
            ("bounded trial may proceed later",),
            ("silent account access", "automatic activation"),
            "require explicit operator authority for each future external-access trial",
        ),
        gate(
            "receipt_and_rollback_gate",
            "Receipt and Rollback Gate",
            "RECEIPT_PROOF",
            ("STAGE_2_SUPERVISED_BROWSER_PREVIEW", "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL"),
            ("success receipt schema", "failure receipt schema", "rollback stop plan"),
            ("trial can be audited later",),
            ("unreceipted portal activity", "unstoppable run"),
            "define success, failure, and stop receipts before any automation trial",
        ),
        gate(
            "no_submission_mutation_gate",
            "No Submission / Mutation Gate",
            "NO_MUTATION_BOUNDARY",
            ("STAGE_2_SUPERVISED_BROWSER_PREVIEW", "STAGE_6_ACTION_OR_SUBMISSION_BLOCKED"),
            ("no-submit boundary receipt", "hard-stop trigger list"),
            ("read-only retrieval boundary preserved",),
            ("invoice submission", "payment request mutation", "email send", "ledger write"),
            "keep submit, save, payment, invoice, send, and ledger actions blocked",
        ),
    ]


def build_stop_conditions() -> list[ExternalWorkflowStopCondition]:
    rows = (
        ("login_challenge_mfa_required", "login challenge / MFA required", "HARD_STOP", "stop before credential or challenge handling"),
        ("credentials_unavailable", "credentials unavailable", "HARD_STOP", "fall back to manual path"),
        ("portal_layout_changed", "portal layout changed", "HARD_STOP", "stop and require supervised review"),
        ("unexpected_payment_account_page", "unexpected payment/account page", "QUARANTINE", "stop and quarantine metadata posture"),
        ("mutation_submit_button_encountered", "mutation/submit button encountered", "HARD_STOP", "stop before interacting with mutation control"),
        ("raw_sensitive_data_exposed", "raw sensitive data exposed", "QUARANTINE", "stop and route to Guardian quarantine"),
        ("unknown_account_session_state", "unknown account/session state", "HARD_STOP", "stop and require operator review"),
        ("po_reference_ambiguous", "PO/reference ambiguous", "OPERATOR_DECISION", "stop and ask operator to clarify"),
        ("duplicate_invoice_reference_risk", "duplicate invoice/reference risk", "HARD_STOP", "stop and require receipt review"),
        ("compliance_terms_uncertainty", "compliance/terms uncertainty", "HARD_STOP", "stop until terms posture is receipted"),
        ("guardian_quarantine_trigger", "Guardian quarantine trigger", "QUARANTINE", "stop and require Guardian review"),
        ("operator_cancels", "operator cancels", "HARD_STOP", "stop immediately and record cancellation receipt"),
    )
    return [
        ExternalWorkflowStopCondition(
            condition_id=condition_id,
            trigger=trigger,
            severity=severity,
            required_stop_action=required_stop_action,
            operator_visibility="operator_visible_required",
            receipt_required=True,
            next_safe_move="record stop receipt and keep manual fallback available",
        )
        for condition_id, trigger, severity, required_stop_action in rows
    ]


def build_trial_stages() -> list[AutomationTrialStage]:
    blocked_common = (
        "credential storage",
        "raw portal body scrape",
        "invoice generation",
        "invoice submission",
        "payment mutation",
        "email send",
        "ledger write",
    )
    return [
        AutomationTrialStage(
            stage_id="manual_reference_capture",
            display_name="Manual Reference Capture",
            what_it_tests="Manual fallback while automation is not authorized.",
            allowed_actions=("operator manually records safe PO/reference metadata", "operator records no-reference-found"),
            blocked_actions=blocked_common + ("browser automation by OpenClaw", "Coupa access by OpenClaw"),
            required_gates=("guardian_metadata_review_gate",),
            success_receipt="manual_safe_metadata_capture_receipt",
            failure_receipt="manual_lookup_unavailable_receipt",
            can_advance_to_next_stage=False,
            next_stage="guided_manual_readback",
        ),
        AutomationTrialStage(
            stage_id="guided_manual_readback",
            display_name="Guided Manual Readback",
            what_it_tests="System gives instructions and captures safe operator-entered metadata.",
            allowed_actions=("show bounded instructions", "capture safe metadata entered by operator"),
            blocked_actions=blocked_common + ("browser automation", "credential handling"),
            required_gates=("operator_authorization_gate", "guardian_metadata_review_gate"),
            success_receipt="guided_manual_readback_receipt",
            failure_receipt="guided_manual_blocked_receipt",
            can_advance_to_next_stage=False,
            next_stage="supervised_browser_navigation_preview",
        ),
        AutomationTrialStage(
            stage_id="supervised_browser_navigation_preview",
            display_name="Supervised Browser Navigation Preview",
            what_it_tests="Future supervised navigation shape with operator watching.",
            allowed_actions=("future supervised preview only after gates",),
            blocked_actions=blocked_common + ("credential storage", "submit/save/mutation"),
            required_gates=(
                "security_delta_for_external_portal",
                "browser_automation_sandbox_gate",
                "portal_terms_compliance_gate",
                "receipt_and_rollback_gate",
                "no_submission_mutation_gate",
            ),
            success_receipt="supervised_navigation_preview_receipt_future",
            failure_receipt="supervised_navigation_stop_receipt_future",
            can_advance_to_next_stage=False,
            next_stage="read_only_lookup_dry_run",
        ),
        AutomationTrialStage(
            stage_id="read_only_lookup_dry_run",
            display_name="Read-Only Lookup Dry Run",
            what_it_tests="Future proof that portal navigation can find a reference without mutation.",
            allowed_actions=("future read-only lookup after all gates",),
            blocked_actions=blocked_common + ("portal write", "body scrape"),
            required_gates=("read_only_lookup_contract_gate", "receipt_and_rollback_gate", "no_submission_mutation_gate"),
            success_receipt="read_only_lookup_dry_run_receipt_future",
            failure_receipt="read_only_lookup_stop_receipt_future",
            can_advance_to_next_stage=False,
            next_stage="protected_credential_broker_trial",
        ),
        AutomationTrialStage(
            stage_id="protected_credential_broker_trial",
            display_name="Protected Credential Broker Trial",
            what_it_tests="Future high-security broker use without raw credential exposure.",
            allowed_actions=("future brokered credential handoff to protected access layer only",),
            blocked_actions=blocked_common + ("credential print/store/inspect", "direct agent credential access"),
            required_gates=("protected_access_broker_gate", "credential_handling_gate", "operator_authorization_gate"),
            success_receipt="protected_credential_broker_trial_receipt_future",
            failure_receipt="protected_credential_broker_stop_receipt_future",
            can_advance_to_next_stage=False,
            next_stage="autonomous_read_only_retrieval",
        ),
        AutomationTrialStage(
            stage_id="autonomous_read_only_retrieval",
            display_name="Autonomous Read-Only Retrieval",
            what_it_tests="Future target: governed read-only retrieval with receipts and stop controls.",
            allowed_actions=("future autonomous read-only retrieval after all gates",),
            blocked_actions=blocked_common + ("invoice action", "account mutation"),
            required_gates=REQUIRED_GATES,
            success_receipt="autonomous_read_only_retrieval_receipt_future",
            failure_receipt="autonomous_read_only_retrieval_stop_receipt_future",
            can_advance_to_next_stage=False,
            next_stage="submission_or_invoice_action",
        ),
        AutomationTrialStage(
            stage_id="submission_or_invoice_action",
            display_name="Submission or Invoice Action",
            what_it_tests="Explicitly blocked action class in this contract.",
            allowed_actions=(),
            blocked_actions=blocked_common + ("Coupa submit", "invoice submit", "approval action"),
            required_gates=("no_submission_mutation_gate",),
            success_receipt="not_available_in_this_contract",
            failure_receipt="submission_or_action_blocked_receipt",
            can_advance_to_next_stage=False,
            next_stage="UNKNOWN_FAIL_CLOSED",
        ),
    ]


def build_capital_hilton_coupa_po_retrieval_automation_candidate(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidate = build_default_automation_candidate()
    gates = build_readiness_gates()
    stop_conditions = build_stop_conditions()
    trial_stages = build_trial_stages()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_coupa_po_retrieval_automation_candidate_v0",
        "generated_at": generated_at or utc_now(),
        **NO_CURRENT_AUTHORITY_FLAGS,
        "contract_status": "deterministic_future_automation_candidate_no_current_authority",
        "core_doctrine": {
            "manual_fallback_allowed": True,
            "guided_assistance_bridge": True,
            "governed_automation_target": True,
            "autonomy_requires_receipts_gates_rollback_and_trust_clearance": True,
            "not_currently_authorized_is_not_cannot_ever_automate": True,
        },
        "automation_statuses": list(AUTOMATION_STATUSES),
        "automation_stages": list(AUTOMATION_STAGES),
        "gate_types": list(GATE_TYPES),
        "automation_candidates": [asdict(candidate)],
        "readiness_gates": [asdict(gate) for gate in gates],
        "stop_conditions": [asdict(condition) for condition in stop_conditions],
        "trial_ladder": [asdict(stage) for stage in trial_stages],
        "future_candidate_flags_non_authority": FUTURE_NON_AUTHORITY_FLAGS,
        "relationship_to_capital_hilton_proof_resolution": {
            "proof_item_id_supported": PROOF_ITEM_ID,
            "shared_execution_path_id": SHARED_EXECUTION_PATH_ID,
            "capital_hilton_proof_resolution_batch": {
                "read_model_ref": PROOF_RESOLUTION_BATCH_REF,
                "relationship": "automation candidate supports the Coupa/PO payment-reference lane",
            },
            "capital_hilton_protected_reference_placeholder": {
                "read_model_ref": PROTECTED_REFERENCE_PLACEHOLDER_REF,
                "potential_future_output": "protected reference placeholder or metadata receipt",
                "created_now": False,
            },
            "capital_hilton_guardian_review_packet": {
                "read_model_ref": GUARDIAN_REVIEW_PACKET_REF,
                "potential_future_output": "Guardian metadata review packet for Coupa/PO metadata",
                "guardian_review_required": True,
                "created_now": False,
            },
            "capital_hilton_proof_quieting_progress_state": {
                "read_model_ref": PROOF_QUIETING_PROGRESS_STATE_REF,
                "potential_future_transition": "coupa_po_payment_reference_metadata may move only after protected metadata and receipts exist",
                "transitioned_now": False,
            },
            "capital_hilton_protected_proof_intake": {
                "read_model_ref": PROTECTED_PROOF_INTAKE_REF,
                "relationship": "this candidate addresses the Coupa / PO / payment reference metadata proof item",
            },
            "lookup_receipt_may_be_created_later": True,
            "lookup_receipt_created_now": False,
            "proof_satisfied_now": False,
        },
        "authority_boundary": {
            **NO_CURRENT_AUTHORITY_FLAGS,
            "all_current_authority_flags_false": all(value is False for value in NO_CURRENT_AUTHORITY_FLAGS.values()),
            "future_candidate_flags_are_non_authority": FUTURE_NON_AUTHORITY_FLAGS,
            "stage_6_submission_or_invoice_action_blocked": True,
        },
        "machine_proof": {
            "default_candidate_exists": candidate.candidate_id == "capital_hilton_coupa_po_reference_retrieval",
            "candidate_count": 1,
            "automation_statuses_exist": set(AUTOMATION_STATUSES)
            == {
                "MANUAL_FALLBACK_ONLY_CURRENTLY",
                "ASSISTED_MANUAL_CANDIDATE",
                "SUPERVISED_AUTOMATION_CANDIDATE",
                "READ_ONLY_AUTOMATION_CANDIDATE",
                "PROTECTED_LOGIN_AUTOMATION_CANDIDATE",
                "AUTONOMOUS_RETRIEVAL_CANDIDATE",
                "BLOCKED_PENDING_SECURITY_DELTA",
                "BLOCKED_PENDING_PROTECTED_ACCESS_BROKER",
                "UNKNOWN_FAIL_CLOSED",
            },
            "automation_stages_exist": set(AUTOMATION_STAGES)
            == {
                "STAGE_0_MANUAL_INSTRUCTIONS",
                "STAGE_1_GUIDED_MANUAL_SESSION",
                "STAGE_2_SUPERVISED_BROWSER_PREVIEW",
                "STAGE_3_READ_ONLY_PORTAL_LOOKUP_DRY_RUN",
                "STAGE_4_PROTECTED_CREDENTIAL_BROKER_TRIAL",
                "STAGE_5_AUTONOMOUS_READ_ONLY_RETRIEVAL",
                "STAGE_6_ACTION_OR_SUBMISSION_BLOCKED",
                "UNKNOWN_FAIL_CLOSED",
            },
            "readiness_gate_count": len(gates),
            "stop_condition_count": len(stop_conditions),
            "trial_stage_count": len(trial_stages),
            "manual_fallback_modeled": "manual" in candidate.current_manual_fallback.lower(),
            "supervised_and_autonomous_candidates_modeled_future_gated": True,
            "all_current_authority_flags_false": all(value is False for value in NO_CURRENT_AUTHORITY_FLAGS.values()),
            "future_candidate_flags_do_not_grant_authority": FUTURE_NON_AUTHORITY_FLAGS[
                "future_flags_grant_current_authority"
            ]
            is False,
            "no_credential_storage": True,
            "no_coupa_browser_network_authority": (
                NO_CURRENT_AUTHORITY_FLAGS["coupa_access_allowed"] is False
                and NO_CURRENT_AUTHORITY_FLAGS["browser_automation_allowed"] is False
                and NO_CURRENT_AUTHORITY_FLAGS["network_operation_allowed"] is False
            ),
            "no_invoice_send_submit_ledger_authority": (
                NO_CURRENT_AUTHORITY_FLAGS["invoice_generation_allowed"] is False
                and NO_CURRENT_AUTHORITY_FLAGS["invoice_submission_allowed"] is False
                and NO_CURRENT_AUTHORITY_FLAGS["email_send_allowed"] is False
                and NO_CURRENT_AUTHORITY_FLAGS["ledger_write_allowed"] is False
            ),
            "mutation_submission_stage_blocked": next(
                stage for stage in trial_stages if stage.stage_id == "submission_or_invoice_action"
            ).allowed_actions
            == (),
            "relationship_to_capital_hilton_proof_item_exists": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_coupa_po_retrieval_automation_candidate(payload: dict[str, Any]) -> str:
    candidate = payload["automation_candidates"][0]
    lines = [
        "# Capital Hilton Coupa / PO Retrieval Automation Candidate v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Manual lookup is the fallback, not the goal. This contract says the Capital Hilton Coupa / PO lookup should be treated as a future governed automation candidate, while keeping all live access blocked right now.",
        "",
        "## What The Candidate Is",
        "",
        f"- `{candidate['candidate_id']}`: retrieve or confirm safe Coupa / PO / payment-reference metadata for `{payload['relationship_to_capital_hilton_proof_resolution']['proof_item_id_supported']}`.",
        f"- Current status: `{candidate['automation_status']}` at `{candidate['automation_stage']}`.",
        "- Automation goal: future read-only lookup with protected metadata receipts, no credential exposure, no raw portal contents, and no mutation.",
        "",
        "## Manual Fallback",
        "",
        "- Winship can still manually log in and copy only safe metadata, or confirm no reference exists.",
        "- That manual answer still needs proof metadata, receipts, and Guardian review before it can quiet the proof item.",
        "",
        "## Future Trial Ladder",
        "",
    ]
    for stage in payload["trial_ladder"]:
        lines.append(f"- `{stage['stage_id']}`: {stage['what_it_tests']}")
    lines.extend(
        [
            "",
            "## Required Gates Before Automation",
            "",
        ]
    )
    for gate in payload["readiness_gates"]:
        lines.append(f"- `{gate['gate_id']}`: `{gate['current_status']}`")
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            "- Login challenge, missing credentials, layout changes, unexpected account pages, submit/mutation controls, raw sensitive data, ambiguous PO/reference, duplicate risk, terms uncertainty, Guardian quarantine, or operator cancellation all stop the workflow and require receipts.",
            "",
            "## What Is Blocked Now",
            "",
            "- Coupa access, browser automation, network operation, credential handling, portal login/read/write, invoice generation, invoice submission, payment mutation, ledger write, email send, model/tool/agent/queue/runtime execution.",
            "",
            "## Why This Helps The Invoice Workflow",
            "",
            "- The system can build toward a governed read-only lookup instead of telling Winship to manually log in forever. The next safe move is to define the security delta, protected access broker, read-only lookup receipt, Guardian review, and rollback requirements.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_coupa_po_retrieval_automation_candidate(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CoupaPoRetrievalAutomationCandidateExportResult:
    payload = build_capital_hilton_coupa_po_retrieval_automation_candidate(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_coupa_po_retrieval_automation_candidate(payload), encoding="utf-8")
    return CoupaPoRetrievalAutomationCandidateExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        candidate_count=payload["machine_proof"]["candidate_count"],
        readiness_gate_count=payload["machine_proof"]["readiness_gate_count"],
        stop_condition_count=payload["machine_proof"]["stop_condition_count"],
        trial_stage_count=payload["machine_proof"]["trial_stage_count"],
        current_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Capital Hilton Coupa / PO retrieval automation candidate read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_coupa_po_retrieval_automation_candidate(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "candidate_count": result.candidate_count,
        "readiness_gate_count": result.readiness_gate_count,
        "stop_condition_count": result.stop_condition_count,
        "trial_stage_count": result.trial_stage_count,
        "current_authority_granted": result.current_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Coupa / PO Retrieval Automation Candidate: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTOMATION_STAGES",
    "AUTOMATION_STATUSES",
    "GATE_TYPES",
    "JSON_EXPORT_NAME",
    "NO_CURRENT_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "AutomationReadinessGate",
    "AutomationTrialStage",
    "ExternalWorkflowAutomationCandidate",
    "ExternalWorkflowStopCondition",
    "build_capital_hilton_coupa_po_retrieval_automation_candidate",
    "build_default_automation_candidate",
    "build_readiness_gates",
    "build_stop_conditions",
    "build_trial_stages",
    "export_capital_hilton_coupa_po_retrieval_automation_candidate",
    "format_capital_hilton_coupa_po_retrieval_automation_candidate",
    "stable_json",
]
