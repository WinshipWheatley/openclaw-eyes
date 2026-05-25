"""Invoice Delivery Run Package Assembler v0.

This deterministic read-model composes the Capital Hilton invoice workflow
packages into one end-to-end readiness surface. It answers whether the run
package is ready, what is missing, why it matters, and how the operator can fix
it. It assembles package/readiness metadata only. It does not execute a run
package, run workflows, send email, access Mail/Gmail, access Coupa, open a
browser, reveal secrets, execute approval, write payment tracking, perform
external actions, ingest raw bodies, mutate Mission Control Swift, run Mac
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

SCHEMA_VERSION = "invoice_delivery_run_package_assembler_v0"
READ_MODEL_ID = "invoice_delivery_run_package_assembler"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_INVOICE_DELIVERY_RUN_PACKAGE_ASSEMBLER"

DELIVERY_CHANNELS = (
    "EMAIL_TO_CONTACT",
    "COUPA_SUPPLIER_PORTAL",
    "LOCAL_RECORDS",
    "PAYMENT_TRACKING",
    "UNKNOWN",
)

READINESS_STATUSES = (
    "NOT_READY_MISSING_INPUTS",
    "PARTIAL_READY_FOR_REVIEW",
    "READY_FOR_GUARDIAN_REVIEW",
    "WAITING_FOR_OPERATOR_APPROVAL",
    "APPROVED_NOT_EXECUTABLE",
    "EXECUTION_GATED",
    "COMPLETION_BLOCKED_MISSING_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

EXECUTION_GATE_STATUSES = (
    "NO_EXECUTION_AUTHORITY",
    "MISSING_APPROVAL",
    "MISSING_PROOF",
    "MISSING_SECRET_REF",
    "MISSING_ADAPTER",
    "FUTURE_EXECUTION_TARGET_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

COMPONENT_TYPES = (
    "DELIVERY_FACTS",
    "INVOICE_ARTIFACT",
    "EMAIL_PACKAGE",
    "COUPA_PACKAGE",
    "GUARDIAN_APPROVAL",
    "ACTION_COVENANT",
    "SECRET_REF",
    "FINAL_READBACK",
    "PAYMENT_TRACKING",
)

READBACK_STATUSES = (
    "RUN_PACKAGE_READY_FOR_REVIEW",
    "NOT_READY_MISSING_ARTIFACT",
    "NOT_READY_MISSING_EMAIL_PACKAGE",
    "NOT_READY_MISSING_COUPA_PACKAGE",
    "NOT_READY_MISSING_APPROVAL",
    "NOT_READY_MISSING_SECRET_REF",
    "NOT_READY_MISSING_PROOF",
    "BLOCKED_EXECUTION_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "DELIVERY_FACTS_MISSING",
    "INVOICE_ARTIFACT_MISSING",
    "EMAIL_PACKAGE_MISSING",
    "COUPA_PACKAGE_MISSING",
    "APPROVAL_MISSING",
    "ACTION_COVENANT_MISSING",
    "SECRET_REF_MISSING",
    "PROOF_MISSING",
    "EXECUTION_ADAPTER_MISSING",
    "EMAIL_SEND_ATTEMPTED",
    "COUPA_SUBMIT_ATTEMPTED",
    "BROWSER_ATTEMPTED",
    "COMPLETION_CLAIM_WITHOUT_RECEIPTS",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
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
    "live_attachment_send_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "run package execution",
    "workflow run",
    "email send",
    "Mail/Gmail send",
    "Coupa access or submit",
    "browser automation",
    "secret reveal",
    "approval execution",
    "payment tracking write",
    "external action",
    "credential handling",
)

CAPITAL_HILTON_REQUIRED_PROOFS = (
    "delivery facts confirmed",
    "invoice artifact saved receipt",
    "invoice artifact hash/fingerprint",
    "email delivery package ref",
    "Coupa supplier portal package ref",
    "Guardian approval packet",
    "protected secret ref if future Coupa login is required",
    "exact operator approval receipt",
    "future email send receipt",
    "future Coupa submit/confirmation receipt if Coupa required",
    "future attachment proof receipt",
    "future payment tracking update receipt",
)

CAPITAL_HILTON_COMPLETION_RECEIPTS = (
    "email send receipt, future",
    "Coupa submit/confirmation receipt, future if Coupa required",
    "invoice artifact saved receipt",
    "attachment proof receipt",
    "Guardian approval receipt",
    "operator approval receipt",
    "payment tracking update receipt, future",
)


@dataclass(frozen=True)
class InvoiceDeliveryRunPackageAssembler:
    assembler_id: str
    doctrine: tuple[str, ...]
    source_workflow_policy: tuple[str, ...]
    component_package_policy: tuple[str, ...]
    readiness_policy: tuple[str, ...]
    approval_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    execution_gate_policy: tuple[str, ...]
    final_readback_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryRunPackage:
    run_package_id: str
    source_workflow_ref: str
    client_ref: str
    tenant_ref: str
    delivery_goal: str
    delivery_channels: tuple[str, ...]
    delivery_facts_ref: str
    invoice_artifact_ref: str
    email_delivery_package_ref: str
    coupa_package_ref: str
    guardian_approval_ref: str
    action_covenant_ref: str
    required_secret_refs: tuple[str, ...]
    required_proofs: tuple[str, ...]
    available_proofs: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    readiness_status: str
    execution_gate_status: str
    completion_target: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryComponentStatus:
    component_status_id: str
    run_package_ref: str
    component_type: str
    component_ref: str
    status: str
    ready: bool
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryReadinessReadback:
    readback_id: str
    run_package_ref: str
    status: str
    operator_headline: str
    operator_message: str
    ready_summary: str
    missing_summary: str
    blocked_summary: str
    component_summaries: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryExecutionGate:
    gate_id: str
    run_package_ref: str
    required_operator_approval_ref: str
    required_guardian_approval_ref: str
    required_action_covenant_ref: str
    required_secret_refs: tuple[str, ...]
    required_adapter_refs: tuple[str, ...]
    missing_gates: tuple[str, ...]
    external_action_allowed: bool
    workflow_run_allowed: bool
    email_send_allowed: bool
    coupa_submit_allowed: bool
    browser_allowed: bool
    action_executed: bool
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryCompletionTarget:
    completion_target_id: str
    run_package_ref: str
    completion_label: str
    required_receipts: tuple[str, ...]
    available_receipts: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    proof_bullets: tuple[str, ...]
    completion_allowed: bool
    completion_readback: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryRunPackageBlocker:
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


def build_assembler() -> InvoiceDeliveryRunPackageAssembler:
    return InvoiceDeliveryRunPackageAssembler(
        assembler_id="invoice_delivery_run_package_assembler_v0",
        doctrine=(
            "Assembler composes packages, not actions.",
            "Assembler states readiness honestly and exposes missing inputs.",
            "Assembler does not execute packages, dispatch agents, send email, access Coupa, open browsers, authorize approvals, or claim completion.",
            "Truth comes from component refs, proof refs, and future receipts.",
        ),
        source_workflow_policy=(
            "Capital Hilton invoice workflow is the first proof case.",
            "Delivery facts, package refs, approval refs, and proof refs remain source-addressable.",
            "Raw private bodies and credentials are excluded.",
        ),
        component_package_policy=(
            "Component statuses summarize delivery facts, invoice artifact, email package, Coupa package, Guardian approval, action covenant, secret refs, final readback, and payment tracking.",
            "Missing components produce how_to_fix guidance.",
            "Component readiness does not imply execution authority.",
        ),
        readiness_policy=(
            "Not-ready packages list missing items and why they matter.",
            "Review-ready packages still have no execution authority.",
            "Do not say ready to run unless all required packages, proofs, gates, adapters, and receipts exist.",
        ),
        approval_policy=(
            "Guardian packet and exact operator approval receipt are required before any future execution adapter could act.",
            "Approval execution remains false in this lane.",
            "Natural chat confirmation is not sufficient authority.",
        ),
        proof_policy=(
            "Required proofs include artifact/hash, email package, Coupa package, protected secret ref if needed, approvals, and future send/submit/payment receipts.",
            "Completion is blocked until receipts exist.",
        ),
        execution_gate_policy=(
            "All action flags are false.",
            "Missing gates must name approval, proof, secret, and adapter needs explicitly.",
            "Future adapter requirements are visible but not active.",
        ),
        final_readback_policy=(
            "Final completion readback is a future target only.",
            "No readback may claim sent, submitted, recorded, or complete without receipts.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Show run-package readiness to the operator and resolve missing refs before any future gated execution.",
    )


def build_run_package(
    *,
    run_package_id: str,
    delivery_facts_ref: str,
    invoice_artifact_ref: str,
    email_delivery_package_ref: str,
    coupa_package_ref: str,
    guardian_approval_ref: str,
    action_covenant_ref: str,
    required_secret_refs: tuple[str, ...],
    available_proofs: tuple[str, ...],
    missing_items: tuple[str, ...],
    readiness_status: str,
    execution_gate_status: str,
) -> InvoiceDeliveryRunPackage:
    return InvoiceDeliveryRunPackage(
        run_package_id=run_package_id,
        source_workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        delivery_goal="Deliver and track the Capital Hilton invoice using local records/email follow-up and the official Coupa/PO payment rail.",
        delivery_channels=("EMAIL_TO_CONTACT", "COUPA_SUPPLIER_PORTAL", "LOCAL_RECORDS", "PAYMENT_TRACKING"),
        delivery_facts_ref=delivery_facts_ref,
        invoice_artifact_ref=invoice_artifact_ref,
        email_delivery_package_ref=email_delivery_package_ref,
        coupa_package_ref=coupa_package_ref,
        guardian_approval_ref=guardian_approval_ref,
        action_covenant_ref=action_covenant_ref,
        required_secret_refs=required_secret_refs,
        required_proofs=CAPITAL_HILTON_REQUIRED_PROOFS,
        available_proofs=available_proofs,
        missing_items=missing_items,
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        readiness_status=readiness_status,
        execution_gate_status=execution_gate_status,
        completion_target="INVOICE_SENT_AND_RECORDED",
        next_safe_move="Resolve missing package/proof/gate items; do not execute.",
    )


def component(
    *,
    run_package_ref: str,
    component_type: str,
    component_ref: str,
    status: str,
    ready: bool,
    missing_items: tuple[str, ...],
    how_to_fix: str,
) -> InvoiceDeliveryComponentStatus:
    return InvoiceDeliveryComponentStatus(
        component_status_id=_stable_id("invoice_delivery_component", run_package_ref, component_type, status),
        run_package_ref=run_package_ref,
        component_type=component_type,
        component_ref=component_ref,
        status=status,
        ready=ready,
        missing_items=missing_items,
        blocked_actions=COMMON_BLOCKED_ACTIONS if not ready else (),
        how_to_fix=how_to_fix,
        next_safe_move=how_to_fix,
    )


def build_execution_gate(package: InvoiceDeliveryRunPackage) -> InvoiceDeliveryExecutionGate:
    required_adapters = (
        "future_gated_email_send_adapter",
        "future_gated_coupa_browser_adapter",
        "future_payment_tracking_receipt_adapter",
    )
    missing = list(package.missing_items)
    if not package.guardian_approval_ref:
        missing.append("Guardian approval packet")
    if not package.action_covenant_ref:
        missing.append("Action Covenant")
    if package.required_secret_refs and not all(ref.startswith("secret_ref:") for ref in package.required_secret_refs):
        missing.append("protected secret ref")
    missing.extend(("exact operator approval receipt", "future execution adapters", "future send/submit/payment receipts"))
    return InvoiceDeliveryExecutionGate(
        gate_id=_stable_id("invoice_delivery_execution_gate", package.run_package_id),
        run_package_ref=package.run_package_id,
        required_operator_approval_ref="operator_approval_receipt:future_exact_approval",
        required_guardian_approval_ref=package.guardian_approval_ref or "missing",
        required_action_covenant_ref=package.action_covenant_ref or "missing",
        required_secret_refs=package.required_secret_refs,
        required_adapter_refs=required_adapters,
        missing_gates=tuple(dict.fromkeys(missing)),
        external_action_allowed=False,
        workflow_run_allowed=False,
        email_send_allowed=False,
        coupa_submit_allowed=False,
        browser_allowed=False,
        action_executed=False,
        next_safe_move="Keep execution locked; collect approval/proof/adapter receipts in future gated lanes.",
    )


def build_completion_target(
    package: InvoiceDeliveryRunPackage,
    *,
    available_receipts: tuple[str, ...],
) -> InvoiceDeliveryCompletionTarget:
    missing_receipts = tuple(receipt for receipt in CAPITAL_HILTON_COMPLETION_RECEIPTS if receipt not in available_receipts)
    return InvoiceDeliveryCompletionTarget(
        completion_target_id=_stable_id("invoice_delivery_completion_target", package.run_package_id),
        run_package_ref=package.run_package_id,
        completion_label="INVOICE_SENT_AND_RECORDED",
        required_receipts=CAPITAL_HILTON_COMPLETION_RECEIPTS,
        available_receipts=available_receipts,
        missing_receipts=missing_receipts,
        proof_bullets=(
            "Invoice artifact/hash proves the local attachment package.",
            "Guardian and operator receipts prove approval posture.",
            "Future email and Coupa receipts would prove external delivery/submission.",
            "Future payment tracking receipt would prove local status recording.",
        ),
        completion_allowed=False,
        completion_readback=(
            "Completion target is modeled only. Nothing has been sent, submitted, opened, approved, or recorded as complete."
        ),
        next_safe_move="Do not claim completion until all required receipts exist.",
    )


def build_readback(
    package: InvoiceDeliveryRunPackage,
    components: tuple[InvoiceDeliveryComponentStatus, ...],
    gate: InvoiceDeliveryExecutionGate,
    completion: InvoiceDeliveryCompletionTarget,
) -> InvoiceDeliveryReadinessReadback:
    component_by_type = {row.component_type: row for row in components}
    if not component_by_type.get("INVOICE_ARTIFACT", component(run_package_ref=package.run_package_id, component_type="INVOICE_ARTIFACT", component_ref="", status="", ready=False, missing_items=(), how_to_fix="")).ready:
        status = "NOT_READY_MISSING_ARTIFACT"
        headline = "Invoice run package needs an artifact"
        fix = "Generate, attach, and hash the Winship-branded invoice PDF/XLSX before package review."
    elif not component_by_type.get("EMAIL_PACKAGE", component(run_package_ref=package.run_package_id, component_type="EMAIL_PACKAGE", component_ref="", status="", ready=False, missing_items=(), how_to_fix="")).ready:
        status = "NOT_READY_MISSING_EMAIL_PACKAGE"
        headline = "Invoice run package needs an email package"
        fix = "Compile the email delivery package with recipient, draft, attachment, and approval refs."
    elif not component_by_type.get("COUPA_PACKAGE", component(run_package_ref=package.run_package_id, component_type="COUPA_PACKAGE", component_ref="", status="", ready=False, missing_items=(), how_to_fix="")).ready:
        status = "NOT_READY_MISSING_COUPA_PACKAGE"
        headline = "Invoice run package needs a Coupa package"
        fix = "Confirm PO/reference and compile the Coupa supplier portal package."
    elif not component_by_type.get("GUARDIAN_APPROVAL", component(run_package_ref=package.run_package_id, component_type="GUARDIAN_APPROVAL", component_ref="", status="", ready=False, missing_items=(), how_to_fix="")).ready:
        status = "NOT_READY_MISSING_APPROVAL"
        headline = "Invoice run package needs Guardian approval"
        fix = "Create Guardian approval packet and wait for exact operator approval receipt in a future gated lane."
    elif package.required_secret_refs and not component_by_type.get("SECRET_REF", component(run_package_ref=package.run_package_id, component_type="SECRET_REF", component_ref="", status="", ready=False, missing_items=(), how_to_fix="")).ready:
        status = "NOT_READY_MISSING_SECRET_REF"
        headline = "Invoice run package needs a protected secret ref"
        fix = "Use the protected Enter Secret flow in a future lane; do not put credentials in chat."
    elif gate.missing_gates or completion.missing_receipts:
        status = "RUN_PACKAGE_READY_FOR_REVIEW" if package.readiness_status in ("READY_FOR_GUARDIAN_REVIEW", "WAITING_FOR_OPERATOR_APPROVAL") else "NOT_READY_MISSING_PROOF"
        headline = "Invoice run package is review-only"
        fix = "Review the package and collect missing approval/proof/adapter receipts; execution remains locked."
    else:
        status = "BLOCKED_EXECUTION_GATE"
        headline = "Invoice run package gate failed closed"
        fix = "Regenerate package with all execution flags false and explicit future receipts."

    ready_count = sum(1 for row in components if row.ready)
    missing_summary = "; ".join(package.missing_items) if package.missing_items else "Future approval/execution receipts are still missing."
    blocked_summary = ", ".join(COMMON_BLOCKED_ACTIONS)
    if package.readiness_status == "NOT_READY_MISSING_INPUTS":
        message = (
            "OpenClaw has assembled the Capital Hilton invoice delivery run package shape. "
            f"It is not ready to execute yet. The workflow still needs {missing_summary}. "
            "Nothing has been sent, submitted, opened, approved, or recorded as complete."
        )
    else:
        message = (
            "OpenClaw has assembled the Capital Hilton invoice delivery run package for review. "
            "It still has no execution authority. Nothing has been sent, submitted, opened, approved, or recorded as complete."
        )
    return InvoiceDeliveryReadinessReadback(
        readback_id=_stable_id("invoice_delivery_readiness_readback", package.run_package_id, status),
        run_package_ref=package.run_package_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        ready_summary=f"{ready_count} of {len(components)} components are ready for review.",
        missing_summary=missing_summary,
        blocked_summary=blocked_summary,
        component_summaries=tuple(f"{row.component_type}: {row.status}" for row in components),
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_blockers() -> tuple[InvoiceDeliveryRunPackageBlocker, ...]:
    return (
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_facts", "DELIVERY_FACTS_MISSING", "Delivery facts refs are missing.", "critical", "Delivery facts are missing.", True, "Capture delivery facts first."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_artifact", "INVOICE_ARTIFACT_MISSING", "Invoice artifact/hash refs are missing.", "critical", "Invoice artifact is missing.", True, "Generate/attach/hash invoice artifact."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_email", "EMAIL_PACKAGE_MISSING", "Email delivery package ref is missing.", "high", "Email package is missing.", True, "Compile email delivery package."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_coupa", "COUPA_PACKAGE_MISSING", "Coupa package ref is missing.", "high", "Coupa package is missing.", True, "Compile Coupa package with PO/reference posture."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_approval", "APPROVAL_MISSING", "Guardian approval packet or operator receipt is missing.", "critical", "Approval is missing.", True, "Create Guardian packet and future operator receipt."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_covenant", "ACTION_COVENANT_MISSING", "Action Covenant is missing.", "critical", "Action Covenant is missing.", True, "Create covenant for gated actions."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_secret", "SECRET_REF_MISSING", "Protected secret ref is missing for future portal access.", "critical", "Protected secret ref is missing.", True, "Use future protected secret intake; do not expose credentials."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_proof", "PROOF_MISSING", "Required proof or receipt refs are missing.", "critical", "Proof is missing.", True, "Attach proof refs or wait for future receipts."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_adapter", "EXECUTION_ADAPTER_MISSING", "Future gated execution adapter is missing.", "critical", "Execution adapter is missing.", True, "Keep package review-only."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_email_send", "EMAIL_SEND_ATTEMPTED", "Assembler attempts email send.", "critical", "Email send is blocked.", True, "Return run package/readback only."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_coupa_submit", "COUPA_SUBMIT_ATTEMPTED", "Assembler attempts Coupa submit.", "critical", "Coupa submit is blocked.", True, "Return run package/readback only."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_browser", "BROWSER_ATTEMPTED", "Assembler attempts browser access.", "critical", "Browser access is blocked.", True, "Stay local and deterministic."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_completion", "COMPLETION_CLAIM_WITHOUT_RECEIPTS", "Completion is claimed without receipts.", "critical", "Completion claim is blocked without receipts.", True, "Require send/submit/artifact/approval/payment receipts."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_external", "EXTERNAL_ACTION_ATTEMPTED", "Assembler attempts external action.", "critical", "External action is blocked.", True, "Keep package read-model only."),
        InvoiceDeliveryRunPackageBlocker("invoice_run_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown run package state.", "high", "Unknown run package state fails closed.", True, "Ask for scoped missing refs."),
    )


def _bundle(
    *,
    package: InvoiceDeliveryRunPackage,
    components: tuple[InvoiceDeliveryComponentStatus, ...],
    available_receipts: tuple[str, ...],
) -> dict[str, Any]:
    gate = build_execution_gate(package)
    completion = build_completion_target(package, available_receipts=available_receipts)
    readback = build_readback(package, components, gate, completion)
    return {
        "run_package": asdict(package),
        "components": [asdict(row) for row in components],
        "execution_gate": asdict(gate),
        "completion_target": asdict(completion),
        "readiness_readback": asdict(readback),
    }


def build_not_ready_example() -> dict[str, Any]:
    package = build_run_package(
        run_package_id="invoice_delivery_run_package_capital_hilton_not_ready_v0",
        delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        invoice_artifact_ref="",
        email_delivery_package_ref="",
        coupa_package_ref="",
        guardian_approval_ref="",
        action_covenant_ref="",
        required_secret_refs=(),
        available_proofs=("delivery facts confirmed",),
        missing_items=(
            "confirmed Coupa PO/reference",
            "final invoice artifact/hash",
            "confirmed recipient/contact route",
            "email delivery package",
            "Coupa supplier portal package",
            "Guardian approval",
            "exact operator approval",
            "send/submit receipts",
        ),
        readiness_status="NOT_READY_MISSING_INPUTS",
        execution_gate_status="NO_EXECUTION_AUTHORITY",
    )
    components = (
        component(run_package_ref=package.run_package_id, component_type="DELIVERY_FACTS", component_ref=package.delivery_facts_ref, status="READY", ready=True, missing_items=(), how_to_fix="Use captured delivery facts."),
        component(run_package_ref=package.run_package_id, component_type="INVOICE_ARTIFACT", component_ref="", status="MISSING_ARTIFACT_AND_HASH", ready=False, missing_items=("final invoice artifact/hash",), how_to_fix="Generate/attach/hash Winship-branded invoice PDF/XLSX."),
        component(run_package_ref=package.run_package_id, component_type="EMAIL_PACKAGE", component_ref="", status="MISSING_EMAIL_PACKAGE", ready=False, missing_items=("confirmed recipient/contact route", "email delivery package"), how_to_fix="Confirm recipient and compile email delivery package."),
        component(run_package_ref=package.run_package_id, component_type="COUPA_PACKAGE", component_ref="", status="MISSING_COUPA_PACKAGE", ready=False, missing_items=("confirmed Coupa PO/reference", "Coupa supplier portal package"), how_to_fix="Confirm PO/reference and compile Coupa package."),
        component(run_package_ref=package.run_package_id, component_type="GUARDIAN_APPROVAL", component_ref="", status="MISSING_APPROVAL", ready=False, missing_items=("Guardian approval",), how_to_fix="Create Guardian approval packet."),
        component(run_package_ref=package.run_package_id, component_type="ACTION_COVENANT", component_ref="", status="MISSING_COVENANT", ready=False, missing_items=("Action Covenant",), how_to_fix="Create action covenant for SEND_EMAIL/SUBMIT_COUPA as needed."),
        component(run_package_ref=package.run_package_id, component_type="SECRET_REF", component_ref="", status="NOT_REQUESTED_YET", ready=False, missing_items=("protected secret ref if future Coupa login required",), how_to_fix="Use future protected secret intake only if portal login becomes required."),
        component(run_package_ref=package.run_package_id, component_type="FINAL_READBACK", component_ref="", status="FUTURE_TARGET_ONLY", ready=False, missing_items=("send/submit receipts",), how_to_fix="Do not create final completion readback until receipts exist."),
        component(run_package_ref=package.run_package_id, component_type="PAYMENT_TRACKING", component_ref="", status="FUTURE_TARGET_ONLY", ready=False, missing_items=("payment tracking update receipt, future",), how_to_fix="Do not write payment tracking in this lane."),
    )
    return _bundle(package=package, components=components, available_receipts=())


def build_ready_for_review_example() -> dict[str, Any]:
    package = build_run_package(
        run_package_id="invoice_delivery_run_package_capital_hilton_ready_for_review_v0",
        delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        invoice_artifact_ref="invoice_artifact_ref:capital_hilton_pdf_2026-05-25",
        email_delivery_package_ref="email_delivery_package_capital_hilton_ready_for_review_v0",
        coupa_package_ref="coupa_package_capital_hilton_complete_except_approval_v0",
        guardian_approval_ref="guardian_approval_capital_hilton_coupa_submit_v0",
        action_covenant_ref="capital_hilton_coupa_submit_covenant_v0",
        required_secret_refs=("secret_ref:coupa_use_once_capital_hilton",),
        available_proofs=(
            "delivery facts confirmed",
            "invoice artifact saved receipt",
            "invoice artifact hash/fingerprint",
            "email delivery package ref",
            "Coupa supplier portal package ref",
            "Guardian approval packet",
            "protected secret ref if future Coupa login is required",
        ),
        missing_items=("exact operator approval receipt", "future email send receipt", "future Coupa submit/confirmation receipt if Coupa required", "future payment tracking update receipt"),
        readiness_status="WAITING_FOR_OPERATOR_APPROVAL",
        execution_gate_status="NO_EXECUTION_AUTHORITY",
    )
    components = (
        component(run_package_ref=package.run_package_id, component_type="DELIVERY_FACTS", component_ref=package.delivery_facts_ref, status="READY", ready=True, missing_items=(), how_to_fix="Use captured delivery facts."),
        component(run_package_ref=package.run_package_id, component_type="INVOICE_ARTIFACT", component_ref=package.invoice_artifact_ref, status="READY_WITH_HASH", ready=True, missing_items=(), how_to_fix="Use artifact/hash refs; do not send."),
        component(run_package_ref=package.run_package_id, component_type="EMAIL_PACKAGE", component_ref=package.email_delivery_package_ref, status="READY_FOR_REVIEW_NOT_SEND", ready=True, missing_items=("future email send receipt",), how_to_fix="Review only; future send adapter remains gated."),
        component(run_package_ref=package.run_package_id, component_type="COUPA_PACKAGE", component_ref=package.coupa_package_ref, status="READY_FOR_REVIEW_NOT_SUBMIT", ready=True, missing_items=("future Coupa submit/confirmation receipt if Coupa required",), how_to_fix="Review only; future Coupa adapter remains gated."),
        component(run_package_ref=package.run_package_id, component_type="GUARDIAN_APPROVAL", component_ref=package.guardian_approval_ref, status="PACKET_EXISTS_NOT_APPROVED", ready=True, missing_items=("exact operator approval receipt",), how_to_fix="Wait for future exact operator approval receipt."),
        component(run_package_ref=package.run_package_id, component_type="ACTION_COVENANT", component_ref=package.action_covenant_ref, status="COVENANT_EXISTS", ready=True, missing_items=("exact operator approval receipt",), how_to_fix="Use exact phrase only in future approval lane."),
        component(run_package_ref=package.run_package_id, component_type="SECRET_REF", component_ref=package.required_secret_refs[0], status="PROTECTED_REF_MODELED", ready=True, missing_items=(), how_to_fix="Keep secret value hidden; future adapter can use only approved ref."),
        component(run_package_ref=package.run_package_id, component_type="FINAL_READBACK", component_ref="", status="FUTURE_TARGET_ONLY", ready=False, missing_items=("send/submit receipts",), how_to_fix="Create final readback only after receipts exist."),
        component(run_package_ref=package.run_package_id, component_type="PAYMENT_TRACKING", component_ref="", status="FUTURE_TARGET_ONLY", ready=False, missing_items=("payment tracking update receipt, future",), how_to_fix="Do not write payment tracking in this lane."),
    )
    return _bundle(package=package, components=components, available_receipts=("invoice artifact saved receipt", "Guardian approval receipt"))


def build_missing_artifact_example() -> dict[str, Any]:
    package = build_run_package(
        run_package_id="invoice_delivery_run_package_missing_artifact_v0",
        delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        invoice_artifact_ref="",
        email_delivery_package_ref="email_delivery_package_pending_missing_attachment",
        coupa_package_ref="coupa_package_capital_hilton_missing_artifact",
        guardian_approval_ref="",
        action_covenant_ref="capital_hilton_invoice_covenant_v0",
        required_secret_refs=(),
        available_proofs=("delivery facts confirmed",),
        missing_items=("invoice artifact saved receipt", "invoice artifact hash/fingerprint"),
        readiness_status="NOT_READY_MISSING_INPUTS",
        execution_gate_status="MISSING_PROOF",
    )
    components = (
        component(run_package_ref=package.run_package_id, component_type="DELIVERY_FACTS", component_ref=package.delivery_facts_ref, status="READY", ready=True, missing_items=(), how_to_fix="Use captured delivery facts."),
        component(run_package_ref=package.run_package_id, component_type="INVOICE_ARTIFACT", component_ref="", status="MISSING_ARTIFACT_AND_HASH", ready=False, missing_items=("invoice artifact saved receipt", "invoice artifact hash/fingerprint"), how_to_fix="Generate, attach, and hash the Winship-branded invoice PDF/XLSX."),
        component(run_package_ref=package.run_package_id, component_type="EMAIL_PACKAGE", component_ref=package.email_delivery_package_ref, status="BLOCKED_BY_ARTIFACT", ready=False, missing_items=("invoice artifact/hash",), how_to_fix="Recompile email package after artifact/hash exists."),
        component(run_package_ref=package.run_package_id, component_type="COUPA_PACKAGE", component_ref=package.coupa_package_ref, status="BLOCKED_BY_ARTIFACT", ready=False, missing_items=("invoice artifact/hash",), how_to_fix="Recompile Coupa package after artifact/hash exists."),
    )
    return _bundle(package=package, components=components, available_receipts=())


def build_missing_coupa_package_example() -> dict[str, Any]:
    package = build_run_package(
        run_package_id="invoice_delivery_run_package_missing_coupa_package_v0",
        delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        invoice_artifact_ref="invoice_artifact_ref:capital_hilton_pdf_2026-05-25",
        email_delivery_package_ref="email_delivery_package_capital_hilton_ready_for_review_v0",
        coupa_package_ref="",
        guardian_approval_ref="guardian_approval_capital_hilton_email_v0",
        action_covenant_ref="capital_hilton_invoice_covenant_v0",
        required_secret_refs=(),
        available_proofs=("delivery facts confirmed", "invoice artifact saved receipt", "invoice artifact hash/fingerprint", "email delivery package ref"),
        missing_items=("confirmed Coupa PO/reference", "Coupa supplier portal package ref"),
        readiness_status="NOT_READY_MISSING_INPUTS",
        execution_gate_status="MISSING_PROOF",
    )
    components = (
        component(run_package_ref=package.run_package_id, component_type="DELIVERY_FACTS", component_ref=package.delivery_facts_ref, status="READY", ready=True, missing_items=(), how_to_fix="Use captured delivery facts."),
        component(run_package_ref=package.run_package_id, component_type="INVOICE_ARTIFACT", component_ref=package.invoice_artifact_ref, status="READY_WITH_HASH", ready=True, missing_items=(), how_to_fix="Use artifact/hash refs."),
        component(run_package_ref=package.run_package_id, component_type="EMAIL_PACKAGE", component_ref=package.email_delivery_package_ref, status="READY_FOR_REVIEW_NOT_SEND", ready=True, missing_items=("future email send receipt",), how_to_fix="Review only; future send adapter remains gated."),
        component(run_package_ref=package.run_package_id, component_type="COUPA_PACKAGE", component_ref="", status="MISSING_COUPA_PACKAGE", ready=False, missing_items=("confirmed Coupa PO/reference", "Coupa supplier portal package ref"), how_to_fix="Confirm PO/reference and compile Coupa package."),
    )
    return _bundle(package=package, components=components, available_receipts=("invoice artifact saved receipt",))


def build_completion_blocked_example() -> dict[str, Any]:
    return build_ready_for_review_example()


def build_examples() -> dict[str, Any]:
    return {
        "capital_hilton_not_ready": build_not_ready_example(),
        "capital_hilton_ready_for_review_not_execution": build_ready_for_review_example(),
        "missing_artifact_blocks_attachment": build_missing_artifact_example(),
        "missing_coupa_package_blocks_payment_rail": build_missing_coupa_package_example(),
        "completion_target_blocked": build_completion_blocked_example(),
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    assembler = build_assembler()
    blockers = build_blockers()
    examples = build_examples()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "delivery_channels": DELIVERY_CHANNELS,
        "readiness_statuses": READINESS_STATUSES,
        "execution_gate_statuses": EXECUTION_GATE_STATUSES,
        "component_types": COMPONENT_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "assembler": asdict(assembler),
        "invoice_delivery_run_package_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "capital_hilton_required_operator_readback": (
            "OpenClaw has assembled the Capital Hilton invoice delivery run package shape. "
            "It is not ready to execute yet. The workflow still needs [missing items]. "
            "Nothing has been sent, submitted, opened, approved, or recorded as complete."
        ),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
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
            "OpenClaw can now assemble the Capital Hilton invoice delivery run package shape across "
            "delivery facts, invoice artifact refs, email package refs, Coupa package refs, Guardian/covenant refs, "
            "proof plans, execution gates, and future completion receipts. It does not execute."
        ),
        "next_safe_move": "Resolve missing PO/artifact/contact/approval/proof refs, then keep execution locked until future gated adapters exist.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    not_ready = payload["examples"]["capital_hilton_not_ready"]["readiness_readback"]
    review = payload["examples"]["capital_hilton_ready_for_review_not_execution"]["readiness_readback"]
    completion = payload["examples"]["completion_target_blocked"]["completion_target"]
    lines = [
        "# Invoice Delivery Run Package Assembler",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton Not Ready",
        f"- Status: {not_ready['status']}",
        f"- Message: {not_ready['operator_message']}",
        f"- Missing: {not_ready['missing_summary']}",
        f"- Next: {not_ready['next_safe_move']}",
        "",
        "## Review Package",
        f"- Status: {review['status']}",
        f"- Message: {review['operator_message']}",
        f"- Next: {review['next_safe_move']}",
        "",
        "## Completion Target",
        f"- Label: {completion['completion_label']}",
        f"- Completion allowed: {str(completion['completion_allowed']).lower()}",
        f"- Missing receipts: {', '.join(completion['missing_receipts'])}",
        "",
        "## Blocked",
    ]
    for blocker in payload["invoice_delivery_run_package_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No run package execution, no workflow run, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no secret reveal, no approval execution, no payment tracking write, no external action, no credential handling, no raw-body ingestion.",
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
        "blocker_count": len(payload["invoice_delivery_run_package_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Invoice Delivery Run Package Assembler read-model.")
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
