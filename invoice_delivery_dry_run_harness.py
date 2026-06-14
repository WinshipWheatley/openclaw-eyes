"""Invoice Delivery Dry-Run Harness v0.

This deterministic read-model simulates the Capital Hilton invoice delivery run
package without executing it. It answers what would be ready, what would block,
which proofs/approvals/adapters are missing, and what the operator should fix
next. It does not send email, access Mail/Gmail, access Coupa, open browsers,
reveal secrets, execute approvals, write payment tracking, run workflows,
dispatch agents, perform external actions, ingest raw bodies, mutate Mission
Control Swift, run Mac sync/import, or push.
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

SCHEMA_VERSION = "invoice_delivery_dry_run_harness_v0"
READ_MODEL_ID = "invoice_delivery_dry_run_harness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_INVOICE_DELIVERY_DRY_RUN_HARNESS"

REQUESTED_CHANNELS = (
    "EMAIL_TO_CONTACT",
    "COUPA_SUPPLIER_PORTAL",
    "LOCAL_RECORDS",
    "PAYMENT_TRACKING",
    "FULL_DELIVERY_SIMULATION",
    "UNKNOWN",
)

DRY_RUN_STATUSES = (
    "DRY_RUN_READY_REPORT",
    "DRY_RUN_BLOCKED_MISSING_INPUTS",
    "DRY_RUN_BLOCKED_MISSING_PROOF",
    "DRY_RUN_BLOCKED_MISSING_APPROVAL",
    "DRY_RUN_BLOCKED_MISSING_ADAPTER",
    "DRY_RUN_BLOCKED_UNSUPPORTED_PACKAGE",
    "UNKNOWN_FAIL_CLOSED",
)

STEP_TYPES = (
    "VALIDATE_DELIVERY_FACTS",
    "VERIFY_INVOICE_ARTIFACT",
    "VERIFY_EMAIL_PACKAGE",
    "VERIFY_COUPA_PACKAGE",
    "VERIFY_GUARDIAN_APPROVAL",
    "VERIFY_ACTION_COVENANT",
    "VERIFY_SECRET_REFS",
    "VERIFY_SEND_ADAPTER",
    "VERIFY_COUPA_ADAPTER",
    "VERIFY_FINAL_READBACK",
    "UNKNOWN",
)

ADAPTER_TYPES = (
    "EMAIL_SEND_ADAPTER",
    "GMAIL_DRAFT_ADAPTER",
    "MAIL_DRAFT_ADAPTER",
    "COUPA_BROWSER_ADAPTER",
    "COUPA_SUBMIT_ADAPTER",
    "INVOICE_ARTIFACT_ADAPTER",
    "PAYMENT_TRACKING_ADAPTER",
    "VISUAL_READBACK_ADAPTER",
    "UNKNOWN",
)

PROOF_TYPES = (
    "DELIVERY_FACTS_RECEIPT",
    "INVOICE_ARTIFACT_HASH",
    "RECIPIENT_CONFIRMATION",
    "PO_REFERENCE_CONFIRMATION",
    "GUARDIAN_APPROVAL",
    "OPERATOR_APPROVAL",
    "EMAIL_SEND_RECEIPT",
    "COUPA_SUBMIT_RECEIPT",
    "PAYMENT_TRACKING_RECEIPT",
    "UNKNOWN",
)

BLOCKER_TYPES = (
    "RUN_PACKAGE_MISSING",
    "DELIVERY_FACTS_MISSING",
    "INVOICE_ARTIFACT_MISSING",
    "EMAIL_PACKAGE_MISSING",
    "COUPA_PACKAGE_MISSING",
    "APPROVAL_MISSING",
    "ACTION_COVENANT_MISSING",
    "SECRET_REF_MISSING",
    "SEND_ADAPTER_MISSING",
    "COUPA_ADAPTER_MISSING",
    "PROOF_MISSING",
    "EXTERNAL_ACTION_ATTEMPTED",
    "COMPLETION_CLAIM_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_dry_run_external_action_allowed": False,
    "live_run_package_execution_allowed": False,
    "live_workflow_run_allowed": False,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_approval_execution_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_invoice_generation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_RISK_NOTES = (
    "Dry-run only: readiness is simulated from refs and modeled gates.",
    "No external adapters are called.",
    "No send, submit, browser, approval execution, or secret reveal occurs.",
    "Completion cannot be claimed without future receipts.",
)


@dataclass(frozen=True)
class InvoiceDeliveryDryRunHarness:
    harness_id: str
    doctrine: tuple[str, ...]
    source_run_package_policy: tuple[str, ...]
    dry_run_policy: tuple[str, ...]
    component_simulation_policy: tuple[str, ...]
    adapter_check_policy: tuple[str, ...]
    proof_check_policy: tuple[str, ...]
    approval_check_policy: tuple[str, ...]
    external_action_boundary: tuple[str, ...]
    final_readback_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryDryRunRequest:
    request_id: str
    source_workflow_ref: str
    source_run_package_ref: str
    client_ref: str
    tenant_ref: str
    dry_run_goal: str
    requested_channels: tuple[str, ...]
    included_component_refs: tuple[str, ...]
    excluded_component_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class InvoiceDeliveryDryRunResult:
    dry_run_id: str
    request_ref: str
    source_run_package_ref: str
    status: str
    operator_headline: str
    operator_message: str
    simulated_steps: tuple[str, ...]
    ready_steps: tuple[str, ...]
    blocked_steps: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    missing_approvals: tuple[str, ...]
    missing_adapters: tuple[str, ...]
    risk_notes: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class DryRunStep:
    step_id: str
    dry_run_ref: str
    step_type: str
    step_summary: str
    would_run: bool
    ready: bool
    blocked_reason: str
    required_inputs: tuple[str, ...]
    required_proofs: tuple[str, ...]
    required_approvals: tuple[str, ...]
    required_adapter: str
    external_action: bool
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class DryRunAdapterCheck:
    adapter_check_id: str
    dry_run_ref: str
    adapter_type: str
    adapter_ref: str
    required: bool
    available: bool
    gated: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class DryRunProofCheck:
    proof_check_id: str
    dry_run_ref: str
    proof_type: str
    required: bool
    available: bool
    proof_ref: str
    stale: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class DryRunReadback:
    readback_id: str
    dry_run_ref: str
    status: str
    operator_headline: str
    operator_message: str
    ready_summary: str
    blocked_summary: str
    missing_summary: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryDryRunBlocker:
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


def build_harness() -> InvoiceDeliveryDryRunHarness:
    return InvoiceDeliveryDryRunHarness(
        harness_id="invoice_delivery_dry_run_harness_v0",
        doctrine=(
            "Dry-run simulates readiness, not execution.",
            "No external adapters are called.",
            "No send, submit, browser, secret reveal, approval execution, or payment write occurs.",
            "Dry-run must not claim completion.",
            "Blocked and missing states include how_to_fix.",
        ),
        source_run_package_policy=(
            "Use the Invoice Delivery Run Package Assembler as source shape.",
            "Treat component refs as metadata/readback refs only.",
            "Unsupported or absent run package fails closed.",
        ),
        dry_run_policy=(
            "Each step says whether it would be part of future execution.",
            "would_run does not mean executed now.",
            "Readiness is reported as ready, blocked, or missing.",
        ),
        component_simulation_policy=(
            "Validate delivery facts, invoice artifact, email package, Coupa package, approvals, covenant, secret refs, adapters, and final readback.",
            "Missing component refs block the simulated run.",
        ),
        adapter_check_policy=(
            "Email, Coupa, payment, and visual adapters are checked as refs only.",
            "Future gated adapters may be required but are unavailable in v0.",
            "Adapter unavailability blocks execution but not review.",
        ),
        proof_check_policy=(
            "Proof checks report available/stale/missing proof refs.",
            "Future send/submit/payment receipts remain missing in v0.",
        ),
        approval_check_policy=(
            "Guardian packet and exact operator approval receipt are checked separately.",
            "Guardian packet may exist for review while operator approval receipt remains missing.",
        ),
        external_action_boundary=(
            "external_action false for every step.",
            "All live action authority false.",
            "No credentials or raw bodies are used.",
        ),
        final_readback_policy=(
            "Final readback target can be modeled only.",
            "Completion claim is blocked without receipts.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Run this harness before any future action-capable invoice adapter; use the missing list to plan the next lane.",
    )


def build_request(
    *,
    request_id: str,
    source_run_package_ref: str,
    included_component_refs: tuple[str, ...],
    excluded_component_refs: tuple[str, ...] = (),
    generated_at: str = DEFAULT_GENERATED_AT,
) -> InvoiceDeliveryDryRunRequest:
    return InvoiceDeliveryDryRunRequest(
        request_id=request_id,
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_run_package_ref=source_run_package_ref,
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        dry_run_goal="Simulate whether the Capital Hilton invoice delivery package could run right now without performing any action.",
        requested_channels=("FULL_DELIVERY_SIMULATION", "EMAIL_TO_CONTACT", "COUPA_SUPPLIER_PORTAL", "LOCAL_RECORDS", "PAYMENT_TRACKING"),
        included_component_refs=included_component_refs,
        excluded_component_refs=excluded_component_refs,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def step(
    *,
    dry_run_ref: str,
    step_type: str,
    step_summary: str,
    would_run: bool,
    ready: bool,
    blocked_reason: str,
    required_inputs: tuple[str, ...] = (),
    required_proofs: tuple[str, ...] = (),
    required_approvals: tuple[str, ...] = (),
    required_adapter: str = "",
    how_to_fix: str,
) -> DryRunStep:
    return DryRunStep(
        step_id=_stable_id("dry_run_step", dry_run_ref, step_type, step_summary),
        dry_run_ref=dry_run_ref,
        step_type=step_type,
        step_summary=step_summary,
        would_run=would_run,
        ready=ready,
        blocked_reason=blocked_reason,
        required_inputs=required_inputs,
        required_proofs=required_proofs,
        required_approvals=required_approvals,
        required_adapter=required_adapter,
        external_action=False,
        how_to_fix=how_to_fix,
        next_safe_move=how_to_fix,
    )


def adapter_check(
    *,
    dry_run_ref: str,
    adapter_type: str,
    adapter_ref: str,
    required: bool,
    available: bool,
    gated: bool,
    blocked_reason: str,
    next_safe_move: str,
) -> DryRunAdapterCheck:
    return DryRunAdapterCheck(
        adapter_check_id=_stable_id("dry_run_adapter", dry_run_ref, adapter_type, adapter_ref),
        dry_run_ref=dry_run_ref,
        adapter_type=adapter_type,
        adapter_ref=adapter_ref,
        required=required,
        available=available,
        gated=gated,
        blocked_reason=blocked_reason,
        next_safe_move=next_safe_move,
    )


def proof_check(
    *,
    dry_run_ref: str,
    proof_type: str,
    required: bool,
    available: bool,
    proof_ref: str,
    blocked_reason: str,
    next_safe_move: str,
    stale: bool = False,
) -> DryRunProofCheck:
    return DryRunProofCheck(
        proof_check_id=_stable_id("dry_run_proof", dry_run_ref, proof_type, proof_ref),
        dry_run_ref=dry_run_ref,
        proof_type=proof_type,
        required=required,
        available=available,
        proof_ref=proof_ref,
        stale=stale,
        blocked_reason=blocked_reason,
        next_safe_move=next_safe_move,
    )


def build_result(
    *,
    dry_run_ref: str,
    request: InvoiceDeliveryDryRunRequest,
    steps: tuple[DryRunStep, ...],
    adapter_checks: tuple[DryRunAdapterCheck, ...],
    proof_checks: tuple[DryRunProofCheck, ...],
    completion_claim_attempted: bool = False,
) -> InvoiceDeliveryDryRunResult:
    blocked_steps = tuple(row.step_summary for row in steps if not row.ready)
    ready_steps = tuple(row.step_summary for row in steps if row.ready)
    missing_inputs = tuple(dict.fromkeys(item for row in steps if not row.ready for item in row.required_inputs))
    missing_proofs = tuple(
        dict.fromkeys(check.proof_type for check in proof_checks if check.required and not check.available)
    )
    missing_adapters = tuple(
        dict.fromkeys(check.adapter_type for check in adapter_checks if check.required and not check.available)
    )
    missing_approvals = tuple(dict.fromkeys(item for row in steps if not row.ready for item in row.required_approvals))
    if completion_claim_attempted:
        status = "DRY_RUN_BLOCKED_MISSING_PROOF"
        headline = "Dry-run blocked a completion claim"
        fix = "Collect future send, submit, approval, attachment, and payment receipts before any completion readback."
    elif missing_inputs:
        status = "DRY_RUN_BLOCKED_MISSING_INPUTS"
        headline = "Dry-run found missing inputs"
        fix = "Fill the missing component inputs, then rerun the dry-run."
    elif missing_approvals:
        status = "DRY_RUN_BLOCKED_MISSING_APPROVAL"
        headline = "Dry-run found missing approval"
        fix = "Create Guardian packet and future exact operator approval receipt before any execution adapter."
    elif missing_proofs:
        status = "DRY_RUN_BLOCKED_MISSING_PROOF"
        headline = "Dry-run found missing proof"
        fix = "Attach missing proof refs and receipts, then rerun the dry-run."
    elif missing_adapters:
        status = "DRY_RUN_BLOCKED_MISSING_ADAPTER"
        headline = "Dry-run found missing adapters"
        fix = "Build gated email/Coupa/payment adapters only after approval and proof rails exist."
    else:
        status = "DRY_RUN_READY_REPORT"
        headline = "Dry-run report ready"
        fix = "Package is reviewable; future execution still requires gated adapters and receipts."
    missing_text = ", ".join((*missing_inputs, *missing_proofs, *missing_approvals, *missing_adapters)) or "future receipts"
    message = (
        "OpenClaw ran a dry-run of the Capital Hilton invoice delivery package. "
        "Nothing was sent, submitted, opened, approved, or changed. "
        f"The workflow is not executable yet because {missing_text}. Next safe move: {fix}"
    )
    return InvoiceDeliveryDryRunResult(
        dry_run_id=dry_run_ref,
        request_ref=request.request_id,
        source_run_package_ref=request.source_run_package_ref,
        status=status,
        operator_headline=headline,
        operator_message=message,
        simulated_steps=tuple(row.step_summary for row in steps),
        ready_steps=ready_steps,
        blocked_steps=blocked_steps,
        missing_inputs=missing_inputs,
        missing_proofs=missing_proofs,
        missing_approvals=missing_approvals,
        missing_adapters=missing_adapters,
        risk_notes=COMMON_RISK_NOTES,
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_readback(result: InvoiceDeliveryDryRunResult) -> DryRunReadback:
    return DryRunReadback(
        readback_id=_stable_id("dry_run_readback", result.dry_run_id, result.status),
        dry_run_ref=result.dry_run_id,
        status=result.status,
        operator_headline=result.operator_headline,
        operator_message=result.operator_message,
        ready_summary=f"{len(result.ready_steps)} ready step(s): " + (", ".join(result.ready_steps) if result.ready_steps else "none"),
        blocked_summary=f"{len(result.blocked_steps)} blocked step(s): " + (", ".join(result.blocked_steps) if result.blocked_steps else "none"),
        missing_summary=", ".join((*result.missing_inputs, *result.missing_proofs, *result.missing_approvals, *result.missing_adapters)) or "future receipts",
        how_to_fix=result.how_to_fix,
        next_safe_move=result.next_safe_move,
    )


def common_adapter_checks(dry_run_ref: str) -> tuple[DryRunAdapterCheck, ...]:
    return (
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="EMAIL_SEND_ADAPTER",
            adapter_ref="future_gated_email_send_adapter",
            required=True,
            available=False,
            gated=True,
            blocked_reason="No approved email send adapter exists in v0.",
            next_safe_move="Build gated email send adapter after approval and proof rails.",
        ),
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="COUPA_BROWSER_ADAPTER",
            adapter_ref="future_gated_coupa_browser_adapter",
            required=True,
            available=False,
            gated=True,
            blocked_reason="No approved Coupa browser adapter exists in v0.",
            next_safe_move="Build gated Coupa browser adapter later; do not open Coupa now.",
        ),
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="COUPA_SUBMIT_ADAPTER",
            adapter_ref="future_gated_coupa_submit_adapter",
            required=True,
            available=False,
            gated=True,
            blocked_reason="No approved Coupa submit adapter exists in v0.",
            next_safe_move="Build gated Coupa submit adapter later; keep submit locked.",
        ),
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="INVOICE_ARTIFACT_ADAPTER",
            adapter_ref="invoice_artifact_builder:bounded_local_artifact_generation",
            required=True,
            available=True,
            gated=True,
            blocked_reason="Available only as bounded local artifact builder; dry-run does not generate.",
            next_safe_move="Use artifact refs and hashes already generated by the builder.",
        ),
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="PAYMENT_TRACKING_ADAPTER",
            adapter_ref="future_payment_tracking_receipt_adapter",
            required=True,
            available=False,
            gated=True,
            blocked_reason="No approved payment tracking write adapter exists in v0.",
            next_safe_move="Model payment tracking as future receipt only.",
        ),
        adapter_check(
            dry_run_ref=dry_run_ref,
            adapter_type="VISUAL_READBACK_ADAPTER",
            adapter_ref="generated_read_model_operator_markdown",
            required=False,
            available=True,
            gated=False,
            blocked_reason="Readback export is deterministic and local.",
            next_safe_move="Use generated operator markdown for review.",
        ),
    )


def proof_checks_current(dry_run_ref: str) -> tuple[DryRunProofCheck, ...]:
    return (
        proof_check(dry_run_ref=dry_run_ref, proof_type="DELIVERY_FACTS_RECEIPT", required=True, available=True, proof_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal", blocked_reason="", next_safe_move="Use existing delivery facts."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="INVOICE_ARTIFACT_HASH", required=True, available=False, proof_ref="", blocked_reason="Invoice artifact hash is missing from current not-ready run package.", next_safe_move="Generate/hash invoice artifact."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="RECIPIENT_CONFIRMATION", required=True, available=False, proof_ref="", blocked_reason="Recipient/contact route is not confirmed.", next_safe_move="Confirm Annette/contact route."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="PO_REFERENCE_CONFIRMATION", required=True, available=False, proof_ref="", blocked_reason="Coupa PO/reference is not confirmed.", next_safe_move="Provide or confirm Coupa PO/reference."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="GUARDIAN_APPROVAL", required=True, available=False, proof_ref="", blocked_reason="Guardian approval packet is missing.", next_safe_move="Create Guardian approval request."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="OPERATOR_APPROVAL", required=True, available=False, proof_ref="", blocked_reason="Exact operator approval receipt is missing.", next_safe_move="Wait for future exact approval gate."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="EMAIL_SEND_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future email send receipt does not exist.", next_safe_move="No send in dry-run."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="COUPA_SUBMIT_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future Coupa submit receipt does not exist.", next_safe_move="No submit in dry-run."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="PAYMENT_TRACKING_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future payment tracking receipt does not exist.", next_safe_move="No payment tracking write in dry-run."),
    )


def proof_checks_review(dry_run_ref: str) -> tuple[DryRunProofCheck, ...]:
    return (
        proof_check(dry_run_ref=dry_run_ref, proof_type="DELIVERY_FACTS_RECEIPT", required=True, available=True, proof_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal", blocked_reason="", next_safe_move="Use existing delivery facts."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="INVOICE_ARTIFACT_HASH", required=True, available=True, proof_ref="invoice_artifact_ref:capital_hilton_pdf_2026-05-25", blocked_reason="", next_safe_move="Use artifact hash ref."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="RECIPIENT_CONFIRMATION", required=True, available=True, proof_ref="recipient_ref:annette_capital_hilton_confirmed", blocked_reason="", next_safe_move="Use confirmed recipient ref."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="PO_REFERENCE_CONFIRMATION", required=True, available=True, proof_ref="po_token_ref:capital_hilton_confirmed", blocked_reason="", next_safe_move="Use confirmed PO ref."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="GUARDIAN_APPROVAL", required=True, available=False, proof_ref="guardian_approval_capital_hilton_coupa_submit_v0", blocked_reason="Guardian packet is modeled but not approved.", next_safe_move="Route to Guardian/operator approval later."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="OPERATOR_APPROVAL", required=True, available=False, proof_ref="", blocked_reason="Exact operator approval receipt is missing.", next_safe_move="Wait for future exact approval gate."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="EMAIL_SEND_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future email send receipt does not exist.", next_safe_move="No send in dry-run."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="COUPA_SUBMIT_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future Coupa submit receipt does not exist.", next_safe_move="No submit in dry-run."),
        proof_check(dry_run_ref=dry_run_ref, proof_type="PAYMENT_TRACKING_RECEIPT", required=True, available=False, proof_ref="", blocked_reason="Future payment tracking receipt does not exist.", next_safe_move="No payment tracking write in dry-run."),
    )


def steps_current(dry_run_ref: str) -> tuple[DryRunStep, ...]:
    return (
        step(dry_run_ref=dry_run_ref, step_type="VALIDATE_DELIVERY_FACTS", step_summary="Validate Capital Hilton dates/rate basis", would_run=True, ready=True, blocked_reason="", required_proofs=("DELIVERY_FACTS_RECEIPT",), how_to_fix="Use captured delivery facts."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_INVOICE_ARTIFACT", step_summary="Verify invoice artifact/hash", would_run=True, ready=False, blocked_reason="Invoice artifact/hash is missing.", required_inputs=("final invoice artifact/hash",), required_proofs=("INVOICE_ARTIFACT_HASH",), how_to_fix="Generate, attach, and hash Winship-branded invoice PDF/XLSX."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_EMAIL_PACKAGE", step_summary="Verify email package", would_run=True, ready=False, blocked_reason="Recipient/contact route and email package are missing.", required_inputs=("confirmed recipient/contact route", "email delivery package"), required_proofs=("RECIPIENT_CONFIRMATION",), how_to_fix="Confirm recipient/contact and compile email delivery package."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_COUPA_PACKAGE", step_summary="Verify Coupa package", would_run=True, ready=False, blocked_reason="Coupa PO/reference and package are missing.", required_inputs=("confirmed Coupa PO/reference", "Coupa supplier portal package"), required_proofs=("PO_REFERENCE_CONFIRMATION",), how_to_fix="Confirm Coupa PO/reference and compile Coupa package."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_GUARDIAN_APPROVAL", step_summary="Verify Guardian approval", would_run=True, ready=False, blocked_reason="Guardian approval is missing.", required_approvals=("Guardian approval",), required_proofs=("GUARDIAN_APPROVAL",), how_to_fix="Create Guardian approval request."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_ACTION_COVENANT", step_summary="Verify action covenant", would_run=True, ready=False, blocked_reason="Action covenant is missing.", required_approvals=("Action Covenant",), how_to_fix="Create action covenant for SEND_EMAIL/SUBMIT_COUPA as needed."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_SECRET_REFS", step_summary="Verify protected secret refs", would_run=True, ready=False, blocked_reason="Protected secret ref may be needed for future Coupa login.", required_inputs=("protected secret ref if future Coupa login required",), how_to_fix="Use future protected secret intake only if portal login is required."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_SEND_ADAPTER", step_summary="Verify email send adapter", would_run=True, ready=False, blocked_reason="Email send adapter is missing/future-gated.", required_adapter="EMAIL_SEND_ADAPTER", how_to_fix="Build gated email send adapter after approval and proof rails."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_COUPA_ADAPTER", step_summary="Verify Coupa adapter", would_run=True, ready=False, blocked_reason="Coupa browser/submit adapters are missing/future-gated.", required_adapter="COUPA_BROWSER_ADAPTER", how_to_fix="Build gated Coupa adapter later; no Coupa access now."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_FINAL_READBACK", step_summary="Verify final completion readback", would_run=True, ready=False, blocked_reason="Future receipts are missing.", required_proofs=("EMAIL_SEND_RECEIPT", "COUPA_SUBMIT_RECEIPT", "PAYMENT_TRACKING_RECEIPT"), how_to_fix="Do not claim completion until future receipts exist."),
    )


def steps_review(dry_run_ref: str) -> tuple[DryRunStep, ...]:
    return (
        step(dry_run_ref=dry_run_ref, step_type="VALIDATE_DELIVERY_FACTS", step_summary="Validate Capital Hilton dates/rate basis", would_run=True, ready=True, blocked_reason="", required_proofs=("DELIVERY_FACTS_RECEIPT",), how_to_fix="Use captured delivery facts."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_INVOICE_ARTIFACT", step_summary="Verify invoice artifact/hash", would_run=True, ready=True, blocked_reason="", required_proofs=("INVOICE_ARTIFACT_HASH",), how_to_fix="Use artifact/hash refs."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_EMAIL_PACKAGE", step_summary="Verify email package", would_run=True, ready=True, blocked_reason="", required_proofs=("RECIPIENT_CONFIRMATION",), how_to_fix="Use email package for review only."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_COUPA_PACKAGE", step_summary="Verify Coupa package", would_run=True, ready=True, blocked_reason="", required_proofs=("PO_REFERENCE_CONFIRMATION",), how_to_fix="Use Coupa package for review only."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_GUARDIAN_APPROVAL", step_summary="Verify Guardian approval", would_run=True, ready=False, blocked_reason="Guardian approval packet is not approved.", required_approvals=("Guardian approval", "exact operator approval receipt"), required_proofs=("GUARDIAN_APPROVAL", "OPERATOR_APPROVAL"), how_to_fix="Route to Guardian/operator approval later; do not execute."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_ACTION_COVENANT", step_summary="Verify action covenant", would_run=True, ready=True, blocked_reason="", required_approvals=("Action Covenant",), how_to_fix="Use covenant as review context only."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_SECRET_REFS", step_summary="Verify protected secret refs", would_run=True, ready=True, blocked_reason="", required_inputs=("protected secret ref if future Coupa login required",), how_to_fix="Keep secret value hidden; dry-run uses ref only."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_SEND_ADAPTER", step_summary="Verify email send adapter", would_run=True, ready=False, blocked_reason="Email send adapter is missing/future-gated.", required_adapter="EMAIL_SEND_ADAPTER", how_to_fix="Build gated email send adapter after approval and proof rails."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_COUPA_ADAPTER", step_summary="Verify Coupa adapter", would_run=True, ready=False, blocked_reason="Coupa browser/submit adapters are missing/future-gated.", required_adapter="COUPA_BROWSER_ADAPTER", how_to_fix="Build gated Coupa adapter later; no Coupa access now."),
        step(dry_run_ref=dry_run_ref, step_type="VERIFY_FINAL_READBACK", step_summary="Verify final completion readback", would_run=True, ready=False, blocked_reason="Future receipts are missing.", required_proofs=("EMAIL_SEND_RECEIPT", "COUPA_SUBMIT_RECEIPT", "PAYMENT_TRACKING_RECEIPT"), how_to_fix="Do not claim completion until future receipts exist."),
    )


def bundle(
    *,
    request: InvoiceDeliveryDryRunRequest,
    steps: tuple[DryRunStep, ...],
    adapter_checks: tuple[DryRunAdapterCheck, ...],
    proof_checks: tuple[DryRunProofCheck, ...],
    completion_claim_attempted: bool = False,
) -> dict[str, Any]:
    result = build_result(
        dry_run_ref=request.request_id.replace("request_", "dry_run_"),
        request=request,
        steps=steps,
        adapter_checks=adapter_checks,
        proof_checks=proof_checks,
        completion_claim_attempted=completion_claim_attempted,
    )
    readback = build_readback(result)
    return {
        "request": asdict(request),
        "result": asdict(result),
        "steps": [asdict(row) for row in steps],
        "adapter_checks": [asdict(row) for row in adapter_checks],
        "proof_checks": [asdict(row) for row in proof_checks],
        "readback": asdict(readback),
    }


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    current_ref = "invoice_delivery_run_package_capital_hilton_not_ready_v0"
    review_ref = "invoice_delivery_run_package_capital_hilton_ready_for_review_v0"
    current_request = build_request(
        request_id="dry_run_request_capital_hilton_current_not_ready_v0",
        source_run_package_ref=current_ref,
        included_component_refs=("delivery_facts_ref",),
        generated_at=generated_at,
    )
    current_dry_run_ref = current_request.request_id.replace("request_", "dry_run_")
    current_steps = steps_current(current_dry_run_ref)
    current_adapters = common_adapter_checks(current_dry_run_ref)
    current_proofs = proof_checks_current(current_dry_run_ref)

    review_request = build_request(
        request_id="dry_run_request_capital_hilton_ready_for_review_v0",
        source_run_package_ref=review_ref,
        included_component_refs=("delivery_facts_ref", "invoice_artifact_ref", "email_package_ref", "coupa_package_ref", "guardian_packet_ref", "action_covenant_ref", "secret_ref"),
        generated_at=generated_at,
    )
    review_dry_run_ref = review_request.request_id.replace("request_", "dry_run_")
    review_steps = steps_review(review_dry_run_ref)
    review_adapters = common_adapter_checks(review_dry_run_ref)
    review_proofs = proof_checks_review(review_dry_run_ref)

    email_adapter_request = build_request(
        request_id="dry_run_request_missing_email_adapter_v0",
        source_run_package_ref=review_ref,
        included_component_refs=review_request.included_component_refs,
        generated_at=generated_at,
    )
    email_dry_run_ref = email_adapter_request.request_id.replace("request_", "dry_run_")
    email_steps = tuple(
        row if row.step_type != "VERIFY_SEND_ADAPTER" else step(
            dry_run_ref=email_dry_run_ref,
            step_type="VERIFY_SEND_ADAPTER",
            step_summary="Verify email send adapter",
            would_run=True,
            ready=False,
            blocked_reason="EMAIL_SEND_ADAPTER missing/future-gated.",
            required_adapter="EMAIL_SEND_ADAPTER",
            how_to_fix="Build gated email send adapter after approval and proof rails.",
        )
        for row in steps_review(email_dry_run_ref)
    )

    coupa_adapter_request = build_request(
        request_id="dry_run_request_missing_coupa_adapter_v0",
        source_run_package_ref=review_ref,
        included_component_refs=review_request.included_component_refs,
        generated_at=generated_at,
    )
    coupa_dry_run_ref = coupa_adapter_request.request_id.replace("request_", "dry_run_")
    coupa_steps = tuple(
        row if row.step_type != "VERIFY_COUPA_ADAPTER" else step(
            dry_run_ref=coupa_dry_run_ref,
            step_type="VERIFY_COUPA_ADAPTER",
            step_summary="Verify Coupa adapter",
            would_run=True,
            ready=False,
            blocked_reason="COUPA_BROWSER_ADAPTER and COUPA_SUBMIT_ADAPTER missing/future-gated.",
            required_adapter="COUPA_BROWSER_ADAPTER",
            how_to_fix="Build gated Coupa adapter later; no Coupa access now.",
        )
        for row in steps_review(coupa_dry_run_ref)
    )

    completion_request = build_request(
        request_id="dry_run_request_completion_claim_blocked_v0",
        source_run_package_ref=review_ref,
        included_component_refs=review_request.included_component_refs,
        generated_at=generated_at,
    )
    completion_dry_run_ref = completion_request.request_id.replace("request_", "dry_run_")

    return {
        "capital_hilton_current_not_ready": bundle(
            request=current_request,
            steps=current_steps,
            adapter_checks=current_adapters,
            proof_checks=current_proofs,
        ),
        "capital_hilton_ready_for_review_not_execution": bundle(
            request=review_request,
            steps=review_steps,
            adapter_checks=review_adapters,
            proof_checks=review_proofs,
        ),
        "missing_email_adapter": bundle(
            request=email_adapter_request,
            steps=email_steps,
            adapter_checks=common_adapter_checks(email_dry_run_ref),
            proof_checks=proof_checks_review(email_dry_run_ref),
        ),
        "missing_coupa_adapter": bundle(
            request=coupa_adapter_request,
            steps=coupa_steps,
            adapter_checks=common_adapter_checks(coupa_dry_run_ref),
            proof_checks=proof_checks_review(coupa_dry_run_ref),
        ),
        "completion_claim_blocked": bundle(
            request=completion_request,
            steps=steps_review(completion_dry_run_ref),
            adapter_checks=common_adapter_checks(completion_dry_run_ref),
            proof_checks=proof_checks_review(completion_dry_run_ref),
            completion_claim_attempted=True,
        ),
    }


def build_blockers() -> tuple[InvoiceDeliveryDryRunBlocker, ...]:
    return (
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_run_package", "RUN_PACKAGE_MISSING", "No source run package ref is present.", "critical", "Run package is missing.", True, "Assemble run package first."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_facts", "DELIVERY_FACTS_MISSING", "Delivery facts proof is missing.", "critical", "Delivery facts are missing.", True, "Capture delivery facts."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_artifact", "INVOICE_ARTIFACT_MISSING", "Invoice artifact/hash proof is missing.", "critical", "Invoice artifact/hash is missing.", True, "Generate/attach/hash invoice artifact."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_email_package", "EMAIL_PACKAGE_MISSING", "Email package ref is missing.", "high", "Email package is missing.", True, "Compile email package."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_coupa_package", "COUPA_PACKAGE_MISSING", "Coupa package ref is missing.", "high", "Coupa package is missing.", True, "Compile Coupa package."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_approval", "APPROVAL_MISSING", "Guardian or operator approval proof is missing.", "critical", "Approval proof is missing.", True, "Create approval packet and future receipt."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_covenant", "ACTION_COVENANT_MISSING", "Action covenant ref is missing.", "critical", "Action covenant is missing.", True, "Create action covenant."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_secret", "SECRET_REF_MISSING", "Protected secret ref is missing if future Coupa login is required.", "critical", "Protected secret ref is missing.", True, "Use protected secret intake later."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_send_adapter", "SEND_ADAPTER_MISSING", "Email send adapter is missing or future-gated.", "critical", "Email send adapter is missing.", True, "Build gated send adapter after proof/approval rails."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_coupa_adapter", "COUPA_ADAPTER_MISSING", "Coupa browser/submit adapter is missing or future-gated.", "critical", "Coupa adapter is missing.", True, "Build gated Coupa adapter later."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_proof", "PROOF_MISSING", "Required proof or receipt is missing.", "critical", "Proof is missing.", True, "Attach proof refs or future receipts."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_external", "EXTERNAL_ACTION_ATTEMPTED", "Dry-run attempts external action.", "critical", "External action is blocked.", True, "Keep dry-run read-model only."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_completion", "COMPLETION_CLAIM_ATTEMPTED", "Dry-run attempts to claim completion without receipts.", "critical", "Completion claim is blocked.", True, "Require future send/submit/payment receipts."),
        InvoiceDeliveryDryRunBlocker("dry_run_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown dry-run state.", "high", "Unknown dry-run state fails closed.", True, "Ask for a scoped run package ref."),
    )


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    harness = build_harness()
    examples = build_examples(generated_at)
    blockers = build_blockers()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "requested_channels": REQUESTED_CHANNELS,
        "dry_run_statuses": DRY_RUN_STATUSES,
        "step_types": STEP_TYPES,
        "adapter_types": ADAPTER_TYPES,
        "proof_types": PROOF_TYPES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "harness": asdict(harness),
        "invoice_delivery_dry_run_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "capital_hilton_required_operator_readback": (
            "OpenClaw ran a dry-run of the Capital Hilton invoice delivery package. "
            "Nothing was sent, submitted, opened, approved, or changed. "
            "The workflow is not executable yet because [missing items]. Next safe move: [specific fix]."
        ),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "dry_run_external_action_performed": False,
            "run_package_execution_performed": False,
            "workflow_run_performed": False,
            "email_send_performed": False,
            "mail_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "secret_reveal_performed": False,
            "approval_execution_performed": False,
            "payment_tracking_write_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
            "completion_claimed": False,
        },
        "operator_summary": (
            "OpenClaw can now dry-run the Capital Hilton invoice delivery package and report ready steps, "
            "blocked steps, missing proofs, missing approvals, missing adapters, and next fixes without executing."
        ),
        "next_safe_move": "Use the dry-run report to choose the next missing rail: artifact/proof, approval, email adapter, Coupa adapter, or payment receipt.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    current = payload["examples"]["capital_hilton_current_not_ready"]["readback"]
    review = payload["examples"]["capital_hilton_ready_for_review_not_execution"]["readback"]
    lines = [
        "# Invoice Delivery Dry-Run Harness",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton Current Dry-Run",
        f"- Status: {current['status']}",
        f"- Message: {current['operator_message']}",
        f"- Ready: {current['ready_summary']}",
        f"- Blocked: {current['blocked_summary']}",
        f"- Missing: {current['missing_summary']}",
        f"- Next: {current['next_safe_move']}",
        "",
        "## Review Package Dry-Run",
        f"- Status: {review['status']}",
        f"- Message: {review['operator_message']}",
        f"- Next: {review['next_safe_move']}",
        "",
        "## Blocked",
    ]
    for blocker in payload["invoice_delivery_dry_run_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No dry-run external action, no run package execution, no workflow run, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no secret reveal, no approval execution, no payment tracking write, no external action, no credential handling, no raw-body ingestion.",
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
        "blocker_count": len(payload["invoice_delivery_dry_run_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Invoice Delivery Dry-Run Harness read-model.")
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
