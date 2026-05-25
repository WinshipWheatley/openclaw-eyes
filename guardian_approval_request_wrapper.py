"""Guardian Approval Request Wrapper v0.

This deterministic read-model turns pending Action Covenants into Guardian
review packets. Guardian explains the requested action, inputs, artifacts,
proofs, risks, missing items, blocked actions, and exact approval phrase that a
future execution lane would require.

It creates review packets and receipts only. It does not execute approvals,
authorize actions, send email, submit to Coupa, open browsers, generate
invoices, reveal secrets, mutate files, run workflows, dispatch agents, access
credentials, ingest raw bodies, mutate Mission Control Swift, run Mac
sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "guardian_approval_request_wrapper_v0"
READ_MODEL_ID = "guardian_approval_request_wrapper"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_GUARDIAN_APPROVAL_REQUEST_WRAPPER"

REQUESTED_ACTIONS = (
    "SEND_EMAIL",
    "SUBMIT_COUPA",
    "CREATE_GMAIL_DRAFT",
    "GENERATE_INVOICE_ARTIFACT",
    "ATTACH_FILE",
    "MUTATE_FILE",
    "OPEN_APP_AUTOMATION",
    "REVEAL_SECRET",
    "RUN_WORKFLOW_PACKAGE",
    "TEST_WORKFLOW_PACKAGE",
    "UNKNOWN_FAIL_CLOSED",
)

RISK_LEVELS = (
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    "UNKNOWN_FAIL_CLOSED",
)

GUARDIAN_RECOMMENDATIONS = (
    "APPROVAL_PACKET_READY",
    "NEEDS_MORE_PROOF",
    "NEEDS_OPERATOR_CLARIFICATION",
    "BLOCKED_UNSAFE",
    "BLOCKED_MISSING_COVENANT",
    "UNKNOWN_FAIL_CLOSED",
)

PROOF_STATUSES = (
    "PROOF_READY",
    "PROOF_MISSING",
    "PROOF_STALE",
    "PROOF_PROTECTED_REVIEW_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "APPROVAL_PACKET_READY",
    "NEEDS_MORE_PROOF",
    "NEEDS_OPERATOR_CLARIFICATION",
    "BLOCKED_UNSAFE",
    "BLOCKED_MISSING_COVENANT",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "MISSING_COVENANT",
    "AMBIGUOUS_ACTION",
    "MISSING_PROOF",
    "PROTECTED_REF_UNREVIEWED",
    "SECRET_REVEAL_UNGATED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "APPROVAL_PHRASE_MISSING",
    "CLIENT_BOUNDARY_RISK",
    "UNSUPPORTED_ACTION",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_approval_execution_allowed": False,
    "live_action_authorization_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_file_mutation_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_guardian_message_allowed": False,
    "live_approval_request_send_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "live approval execution",
    "action authorization",
    "email send",
    "Coupa submit",
    "browser automation",
    "secret reveal",
    "file mutation",
    "workflow run",
    "agent dispatch",
    "external action",
)


@dataclass(frozen=True)
class GuardianApprovalRequestWrapper:
    wrapper_id: str
    doctrine: tuple[str, ...]
    source_covenant_policy: tuple[str, ...]
    risk_review_policy: tuple[str, ...]
    proof_review_policy: tuple[str, ...]
    protected_data_policy: tuple[str, ...]
    approval_phrase_policy: tuple[str, ...]
    operator_display_policy: tuple[str, ...]
    receipt_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class GuardianApprovalRequest:
    approval_request_id: str
    source_covenant_ref: str
    source_workflow_ref: str
    source_package_ref: str
    requested_action: str
    action_summary: str
    risk_level: str
    operator_visible_summary: str
    required_inputs: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_proofs: tuple[str, ...]
    protected_refs: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    exact_approval_phrase: str
    expiration_policy: str
    guardian_recommendation: str
    next_safe_move: str


@dataclass(frozen=True)
class GuardianRiskReview:
    review_id: str
    approval_request_ref: str
    risk_summary: str
    data_exposure_risk: str
    external_action_risk: str
    reversibility: str
    missing_proof_risk: str
    credential_or_secret_risk: str
    client_boundary_risk: str
    recommendation: str
    next_safe_move: str


@dataclass(frozen=True)
class GuardianProofReview:
    proof_review_id: str
    approval_request_ref: str
    required_proofs: tuple[str, ...]
    available_proof_refs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    proof_status: str
    completion_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class GuardianApprovalReadback:
    readback_id: str
    approval_request_ref: str
    status: str
    operator_headline: str
    operator_message: str
    approval_summary: str
    risk_summary: str
    missing_items: tuple[str, ...]
    exact_approval_phrase: str
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class GuardianApprovalReceipt:
    receipt_id: str
    approval_request_ref: str
    action: str
    approval_packet_created: bool
    operator_approved: bool
    action_authorized: bool
    action_executed: bool
    external_authority: bool
    created_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class GuardianApprovalBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def build_wrapper() -> GuardianApprovalRequestWrapper:
    return GuardianApprovalRequestWrapper(
        wrapper_id="guardian_approval_request_wrapper_v0",
        doctrine=(
            "Guardian creates review packets, not execution.",
            "Every approval request binds to one covenant, action, package, and workflow.",
            "Proof and missing inputs must be visible before any future approval phrase can matter.",
            "Exact approval phrase is modeled for future gated execution but is not executed here.",
            "External authority remains false.",
        ),
        source_covenant_policy=(
            "Use Action Covenant Interrupter output as source context.",
            "Missing covenant fails closed.",
            "Ambiguous action requires operator clarification before Guardian packet is useful.",
        ),
        risk_review_policy=(
            "Review data exposure, external-action risk, reversibility, missing proof, sensitive refs, and client boundary.",
            "High and critical risk actions default to Guardian review and do not authorize execution.",
            "Unsupported destructive actions are blocked as unsafe.",
        ),
        proof_review_policy=(
            "Required proofs are listed as refs only.",
            "Missing proofs produce NEEDS_MORE_PROOF.",
            "Protected proofs remain protected refs; raw bodies are not required or exposed.",
            "Completion is false unless proof refs exist.",
        ),
        protected_data_policy=(
            "Protected refs may be named without raw values.",
            "Raw private bodies, credential material, and secret material are forbidden.",
            "Secret-use requests require protected secret refs and future approved adapters.",
        ),
        approval_phrase_policy=(
            "Exact approval phrase shape is inherited from the Action Covenant.",
            "Guardian displays the phrase but does not treat it as approval in this lane.",
            "A live approval adapter would need a separate receipt.",
        ),
        operator_display_policy=(
            "Show action, why it matters, inputs, artifacts, proofs, risks, missing items, allowed boundaries, and forbidden boundaries.",
            "Use human-readable cards/readbacks, not raw backend statuses.",
        ),
        receipt_policy=(
            "Approval packet creation produces a receipt model.",
            "operator_approved, action_authorized, action_executed, and external_authority remain false.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Feed covenant requests into this wrapper before any future Guardian/live approval adapter.",
    )


def build_approval_request(
    *,
    approval_request_id: str,
    source_covenant_ref: str,
    source_workflow_ref: str,
    source_package_ref: str,
    requested_action: str,
    action_summary: str,
    risk_level: str,
    required_inputs: tuple[str, ...],
    required_artifacts: tuple[str, ...],
    required_proofs: tuple[str, ...],
    protected_refs: tuple[str, ...],
    missing_items: tuple[str, ...],
    guardian_recommendation: str,
    expiration_policy: str = "expires when covenant/package/proof context changes or after bounded review window",
) -> GuardianApprovalRequest:
    exact_phrase = (
        ""
        if not source_covenant_ref
        else f"APPROVE {requested_action} {source_covenant_ref}"
    )
    return GuardianApprovalRequest(
        approval_request_id=approval_request_id,
        source_covenant_ref=source_covenant_ref,
        source_workflow_ref=source_workflow_ref,
        source_package_ref=source_package_ref,
        requested_action=requested_action,
        action_summary=action_summary,
        risk_level=risk_level,
        operator_visible_summary=(
            f"Guardian review packet for {requested_action}: {action_summary}. "
            f"Required phrase would be `{exact_phrase or 'missing covenant'}`."
        ),
        required_inputs=required_inputs,
        required_artifacts=required_artifacts,
        required_proofs=required_proofs,
        protected_refs=protected_refs,
        missing_items=missing_items,
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        exact_approval_phrase=exact_phrase,
        expiration_policy=expiration_policy,
        guardian_recommendation=guardian_recommendation,
        next_safe_move="Show this review packet; do not execute or authorize the action.",
    )


def build_risk_review(request: GuardianApprovalRequest) -> GuardianRiskReview:
    if not request.source_covenant_ref:
        recommendation = "BLOCKED_MISSING_COVENANT"
        summary = "No covenant is bound to this approval request."
    elif request.requested_action == "MUTATE_FILE" and request.risk_level == "CRITICAL":
        recommendation = "BLOCKED_UNSAFE"
        summary = "Destructive file mutation is unsafe and unsupported."
    elif request.missing_items:
        recommendation = "NEEDS_MORE_PROOF"
        summary = "Required inputs or proof refs are missing."
    elif request.requested_action == "UNKNOWN_FAIL_CLOSED":
        recommendation = "UNKNOWN_FAIL_CLOSED"
        summary = "Requested action is unknown."
    else:
        recommendation = "APPROVAL_PACKET_READY"
        summary = "Guardian packet is ready for operator review, but it grants no execution authority."

    return GuardianRiskReview(
        review_id=_stable_id("guardian_risk_review", request.approval_request_id, recommendation),
        approval_request_ref=request.approval_request_id,
        risk_summary=summary,
        data_exposure_risk=(
            "Protected refs only; raw private bodies are excluded."
            if request.protected_refs
            else "No protected refs named; still no raw bodies included."
        ),
        external_action_risk=(
            "High external-action risk: live send/submit/browser/action is forbidden in this lane."
            if request.requested_action in ("SEND_EMAIL", "SUBMIT_COUPA", "CREATE_GMAIL_DRAFT", "OPEN_APP_AUTOMATION")
            else "No live external action allowed."
        ),
        reversibility=(
            "Low reversibility until future adapter receipts exist."
            if request.risk_level in ("HIGH", "CRITICAL")
            else "Bounded and reversible if limited to deterministic test/readback."
        ),
        missing_proof_risk=(
            "Missing proof blocks packet readiness."
            if request.missing_items
            else "Required proof refs are modeled as available."
        ),
        credential_or_secret_risk=(
            "Secret/credential use is gated by protected refs and future adapter review."
            if request.requested_action == "REVEAL_SECRET"
            else "No credential or secret value is exposed."
        ),
        client_boundary_risk="Client/workflow scope must remain bound to the covenant and package refs.",
        recommendation=recommendation,
        next_safe_move=(
            "Collect missing proof before approval review."
            if recommendation == "NEEDS_MORE_PROOF"
            else "Keep this as review-only until a future approved gate exists."
        ),
    )


def build_proof_review(
    request: GuardianApprovalRequest,
    *,
    available_proof_refs: tuple[str, ...],
    proof_status: str | None = None,
) -> GuardianProofReview:
    missing = tuple(proof for proof in request.required_proofs if proof not in available_proof_refs)
    if proof_status is None:
        if missing:
            status = "PROOF_MISSING"
        elif request.protected_refs:
            status = "PROOF_PROTECTED_REVIEW_REQUIRED"
        else:
            status = "PROOF_READY"
    else:
        status = proof_status
    return GuardianProofReview(
        proof_review_id=_stable_id("guardian_proof_review", request.approval_request_id, status),
        approval_request_ref=request.approval_request_id,
        required_proofs=request.required_proofs,
        available_proof_refs=available_proof_refs,
        missing_proofs=missing,
        proof_status=status,
        completion_allowed=not missing and status == "PROOF_READY",
        next_safe_move=(
            "Attach or create the missing proof refs."
            if missing
            else "Proof refs are modeled; external completion still requires future receipts."
        ),
    )


def build_readback(
    request: GuardianApprovalRequest,
    risk_review: GuardianRiskReview,
    proof_review: GuardianProofReview,
) -> GuardianApprovalReadback:
    status = risk_review.recommendation
    if status == "APPROVAL_PACKET_READY" and proof_review.proof_status == "PROOF_PROTECTED_REVIEW_REQUIRED":
        status = "APPROVAL_PACKET_READY"
    elif status == "APPROVAL_PACKET_READY" and proof_review.missing_proofs:
        status = "NEEDS_MORE_PROOF"

    if status == "APPROVAL_PACKET_READY":
        headline = "Guardian approval packet ready for review"
        message = "Guardian can show the action, risk, proof refs, and exact phrase. Nothing is approved or executed."
        how = "Review the packet; future execution still needs a separate governed approval adapter."
    elif status == "NEEDS_MORE_PROOF":
        headline = "Guardian needs more proof"
        message = "The approval packet is blocked because required proof or artifact refs are missing."
        how = "Provide the missing proof refs, then regenerate the Guardian packet."
    elif status == "BLOCKED_UNSAFE":
        headline = "Guardian blocked an unsafe action"
        message = "The requested action is destructive or unsupported."
        how = "Ask for a scoped non-destructive review, backup plan, or metadata-only request."
    elif status == "BLOCKED_MISSING_COVENANT":
        headline = "Guardian needs an Action Covenant"
        message = "No covenant is bound to this approval request."
        how = "Create a covenant through the Action Covenant Interrupter first."
    else:
        headline = "Guardian needs clarification"
        message = "The requested action is ambiguous or unsupported."
        how = "Name the exact action, workflow, package, and proof refs."

    return GuardianApprovalReadback(
        readback_id=_stable_id("guardian_approval_readback", request.approval_request_id, status),
        approval_request_ref=request.approval_request_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        approval_summary=request.operator_visible_summary,
        risk_summary=risk_review.risk_summary,
        missing_items=tuple(dict.fromkeys((*request.missing_items, *proof_review.missing_proofs))),
        exact_approval_phrase=request.exact_approval_phrase,
        blocked_actions=request.blocked_actions,
        how_to_fix=how,
        next_safe_move=how,
    )


def build_receipt(
    request: GuardianApprovalRequest,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> GuardianApprovalReceipt:
    return GuardianApprovalReceipt(
        receipt_id=_stable_id("guardian_approval_receipt", request.approval_request_id, generated_at),
        approval_request_ref=request.approval_request_id,
        action=request.requested_action,
        approval_packet_created=True,
        operator_approved=False,
        action_authorized=False,
        action_executed=False,
        external_authority=False,
        created_at_policy=generated_at,
        next_safe_move="Keep approval packet as review-only until future governed approval/execution receipts exist.",
    )


def build_blockers() -> tuple[GuardianApprovalBlocker, ...]:
    return (
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_missing_covenant",
            blocker_type="MISSING_COVENANT",
            condition="Approval request lacks a concrete Action Covenant ref.",
            severity="critical",
            elioperator_warning="Guardian cannot review approval without a covenant.",
            fail_closed=True,
            next_safe_move="Create or match a covenant first.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_ambiguous_action",
            blocker_type="AMBIGUOUS_ACTION",
            condition="Requested action or target package is ambiguous.",
            severity="high",
            elioperator_warning="Ambiguous actions require operator clarification.",
            fail_closed=True,
            next_safe_move="Ask for the exact action, workflow, and package.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_missing_proof",
            blocker_type="MISSING_PROOF",
            condition="Required receipt, artifact, hash, or proof ref is missing.",
            severity="critical",
            elioperator_warning="Required proof is missing.",
            fail_closed=True,
            next_safe_move="Attach the missing proof refs before approval review.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_protected_ref",
            blocker_type="PROTECTED_REF_UNREVIEWED",
            condition="Protected proof or source refs are named but not reviewed.",
            severity="high",
            elioperator_warning="Protected refs need Guardian review before use.",
            fail_closed=True,
            next_safe_move="Keep protected content below the waterline and review refs only.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_secret",
            blocker_type="SECRET_REVEAL_UNGATED",
            condition="Secret reveal/use requested without protected ref and adapter gate.",
            severity="critical",
            elioperator_warning="Secret use requires a protected ref and future adapter gate.",
            fail_closed=True,
            next_safe_move="Use Protected Secret Intake and expose only token refs.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_external_action",
            blocker_type="EXTERNAL_ACTION_ATTEMPTED",
            condition="Approval packet attempts to send, submit, browse, or perform external action.",
            severity="critical",
            elioperator_warning="External action is blocked in the Guardian request wrapper.",
            fail_closed=True,
            next_safe_move="Return review packet only.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_phrase",
            blocker_type="APPROVAL_PHRASE_MISSING",
            condition="Exact approval phrase is absent or not bound to covenant/action.",
            severity="critical",
            elioperator_warning="Exact approval phrase is required.",
            fail_closed=True,
            next_safe_move="Regenerate request from a valid covenant.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_client_boundary",
            blocker_type="CLIENT_BOUNDARY_RISK",
            condition="Request crosses client/workflow boundary or lacks scoped refs.",
            severity="high",
            elioperator_warning="Client/workflow boundary risk must be resolved.",
            fail_closed=True,
            next_safe_move="Bind request to one workflow/package/client scope.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_unsupported",
            blocker_type="UNSUPPORTED_ACTION",
            condition="Requested action is unsupported or destructive.",
            severity="critical",
            elioperator_warning="Unsupported action is blocked.",
            fail_closed=True,
            next_safe_move="Ask for a scoped safe alternative.",
        ),
        GuardianApprovalBlocker(
            blocker_id="guardian_approval_blocker_unknown",
            blocker_type="UNKNOWN_FAIL_CLOSED",
            condition="Unknown request shape, action, risk, or proof posture.",
            severity="high",
            elioperator_warning="Unknown approval request fails closed.",
            fail_closed=True,
            next_safe_move="Ask for a scoped covenant/package.",
        ),
    )


def _packet(
    request: GuardianApprovalRequest,
    *,
    available_proof_refs: tuple[str, ...],
    generated_at: str,
    proof_status: str | None = None,
) -> dict[str, Any]:
    risk = build_risk_review(request)
    proof = build_proof_review(request, available_proof_refs=available_proof_refs, proof_status=proof_status)
    readback = build_readback(request, risk, proof)
    receipt = build_receipt(request, generated_at=generated_at)
    return {
        "approval_request": asdict(request),
        "risk_review": asdict(risk),
        "proof_review": asdict(proof),
        "readback": asdict(readback),
        "receipt": asdict(receipt),
    }


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    capital_proofs = (
        "recipient/contact confirmed",
        "invoice artifact/hash exists",
        "attachment ref exists",
        "send body reviewed",
    )
    capital = build_approval_request(
        approval_request_id="guardian_approval_capital_hilton_email_v0",
        source_covenant_ref="capital_hilton_invoice_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="workflow_execution_package_compiler:capital_hilton_email_package",
        requested_action="SEND_EMAIL",
        action_summary="Email the recipient contact candidate with the Winship-branded invoice PDF artifact for local records and payment follow-up.",
        risk_level="HIGH",
        required_inputs=("confirmed recipient contact route", "reviewed send body"),
        required_artifacts=("Winship-branded invoice PDF artifact ref", "invoice artifact hash ref"),
        required_proofs=capital_proofs,
        protected_refs=("protected_ref:invoice_pdf_artifact",),
        missing_items=(),
        guardian_recommendation="APPROVAL_PACKET_READY",
    )

    coupa_proofs = (
        "PO/reference confirmed",
        "invoice values confirmed",
        "portal action reviewed",
    )
    coupa = build_approval_request(
        approval_request_id="guardian_approval_capital_hilton_coupa_submit_v0",
        source_covenant_ref="capital_hilton_coupa_submit_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="workflow_execution_package_compiler:capital_hilton_coupa_package",
        requested_action="SUBMIT_COUPA",
        action_summary="Submit or confirm the Capital Hilton invoice through the official Coupa/PO rail.",
        risk_level="CRITICAL",
        required_inputs=("exact Coupa PO/reference", "confirmed invoice values"),
        required_artifacts=("Coupa invoice/payment rail package ref",),
        required_proofs=coupa_proofs,
        protected_refs=("protected_ref:coupa_portal_action_context",),
        missing_items=("portal action reviewed",),
        guardian_recommendation="NEEDS_MORE_PROOF",
    )

    protected_use = build_approval_request(
        approval_request_id="guardian_approval_coupa_secret_use_v0",
        source_covenant_ref="protected_secret_use_coupa_credential_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="protected_secret_intake_contract:coupa_secret_task_scope",
        requested_action="REVEAL_SECRET",
        action_summary="Use a protected Coupa credential ref in a future approved adapter without exposing the raw value.",
        risk_level="CRITICAL",
        required_inputs=("protected secret token ref", "task scope", "TTL policy"),
        required_artifacts=("protected secret intake receipt",),
        required_proofs=("protected secret token ref", "adapter-use gate receipt"),
        protected_refs=("secret_ref:coupa_password_task_scoped",),
        missing_items=("adapter-use gate receipt",),
        guardian_recommendation="NEEDS_MORE_PROOF",
    )

    test_package = build_approval_request(
        approval_request_id="guardian_approval_test_workflow_package_v0",
        source_covenant_ref="test_workflow_package_covenant_v0",
        source_workflow_ref="openclaw_backend_validation",
        source_package_ref="package_ref:bounded_test_fixture",
        requested_action="TEST_WORKFLOW_PACKAGE",
        action_summary="Run a focused deterministic test package with no external effects.",
        risk_level="MEDIUM",
        required_inputs=("package ref", "test rail ref"),
        required_artifacts=("test fixture package ref",),
        required_proofs=("test rail exists", "package ref exists"),
        protected_refs=(),
        missing_items=(),
        guardian_recommendation="APPROVAL_PACKET_READY",
    )

    missing_proof = build_approval_request(
        approval_request_id="guardian_approval_missing_invoice_hash_v0",
        source_covenant_ref="capital_hilton_invoice_missing_hash_covenant_v0",
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_package_ref="workflow_execution_package_compiler:capital_hilton_email_package",
        requested_action="SEND_EMAIL",
        action_summary="Email invoice artifact, but required artifact/hash proof is missing.",
        risk_level="HIGH",
        required_inputs=("confirmed recipient contact route", "reviewed send body"),
        required_artifacts=("Winship-branded invoice PDF artifact ref", "invoice artifact hash ref"),
        required_proofs=capital_proofs,
        protected_refs=("protected_ref:invoice_pdf_artifact",),
        missing_items=("invoice artifact/hash exists", "attachment ref exists"),
        guardian_recommendation="NEEDS_MORE_PROOF",
    )

    destructive = build_approval_request(
        approval_request_id="guardian_approval_delete_client_folder_blocked_v0",
        source_covenant_ref="delete_client_folder_rejected_covenant_v0",
        source_workflow_ref="unknown_client_folder_request",
        source_package_ref="none",
        requested_action="MUTATE_FILE",
        action_summary="Delete the client folder.",
        risk_level="CRITICAL",
        required_inputs=("scoped path ref", "backup plan", "operator destructive approval"),
        required_artifacts=("none",),
        required_proofs=("backup receipt", "safe scoped inventory"),
        protected_refs=(),
        missing_items=("backup receipt", "safe scoped inventory", "supported non-destructive plan"),
        guardian_recommendation="BLOCKED_UNSAFE",
    )

    return {
        "capital_hilton_email_approval": _packet(capital, available_proof_refs=capital_proofs, generated_at=generated_at),
        "coupa_submit_approval": _packet(
            coupa,
            available_proof_refs=("PO/reference confirmed", "invoice values confirmed"),
            generated_at=generated_at,
        ),
        "secret_reveal": _packet(
            protected_use,
            available_proof_refs=("protected secret token ref",),
            generated_at=generated_at,
            proof_status="PROOF_PROTECTED_REVIEW_REQUIRED",
        ),
        "test_package": _packet(
            test_package,
            available_proof_refs=("test rail exists", "package ref exists"),
            generated_at=generated_at,
        ),
        "missing_proof": _packet(
            missing_proof,
            available_proof_refs=("recipient/contact confirmed", "send body reviewed"),
            generated_at=generated_at,
        ),
        "destructive_action": _packet(
            destructive,
            available_proof_refs=(),
            generated_at=generated_at,
        ),
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    wrapper = build_wrapper()
    blockers = build_blockers()
    examples = build_examples(generated_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "requested_actions": REQUESTED_ACTIONS,
        "risk_levels": RISK_LEVELS,
        "guardian_recommendations": GUARDIAN_RECOMMENDATIONS,
        "proof_statuses": PROOF_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "wrapper": asdict(wrapper),
        "guardian_approval_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "approval_execution_performed": False,
            "action_authorization_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "secret_reveal_performed": False,
            "file_mutation_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "Guardian can now turn Action Covenants into deterministic review packets that show the requested action, "
            "risk, proofs, missing items, protected refs, blocked actions, and exact approval phrase. "
            "No approval is executed and no action is authorized."
        ),
        "next_safe_move": "Have the Action Covenant Interrupter hand high-consequence covenant requests to this Guardian wrapper.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["examples"]
    lines = [
        "# Guardian Approval Request Wrapper",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Packets",
        f"- Capital Hilton email: {examples['capital_hilton_email_approval']['readback']['status']}",
        f"- Coupa submit: {examples['coupa_submit_approval']['readback']['status']}",
        f"- Protected credential use: {examples['secret_reveal']['readback']['status']}",
        f"- Test package: {examples['test_package']['readback']['status']}",
        f"- Missing proof: {examples['missing_proof']['readback']['status']}",
        f"- Destructive action: {examples['destructive_action']['readback']['status']}",
        "",
        "## Exact Phrase Example",
        examples["capital_hilton_email_approval"]["approval_request"]["exact_approval_phrase"],
        "",
        "## Blocked",
    ]
    for blocker in payload["guardian_approval_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No live approval execution, no action authorization, no email send, no Coupa submit, no browser, no secret reveal, no file mutation, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "examples": tuple(payload["examples"].keys()),
        "blocker_count": len(payload["guardian_approval_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Guardian Approval Request Wrapper read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at)
    write_exports(payload, export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload, export_root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
