"""Coupa Supplier Portal Package Compiler v0.

This deterministic read-model assembles a safe Coupa supplier portal package
from PO/reference posture, invoice values, invoice artifact refs, protected
credential refs, Guardian approval refs, portal gates, and proof requirements.
It creates package/readback models only. It does not access Coupa, open a
browser, log in, submit invoices, reveal secrets, execute payments, run
workflows, dispatch agents, perform external actions, mutate Mission Control
Swift, run Mac sync/import, or push.
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

SCHEMA_VERSION = "coupa_supplier_portal_package_compiler_v0"
READ_MODEL_ID = "coupa_supplier_portal_package_compiler"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_SUBMITTING_COUPA_SUPPLIER_PORTAL_PACKAGE_COMPILER"

PO_STATUSES = (
    "PO_CONFIRMED",
    "PO_CANDIDATE",
    "PO_MISSING",
    "PO_BLOCKED_PRIVACY",
    "UNKNOWN_FAIL_CLOSED",
)

SUPPLIER_PORTAL_STATUSES = (
    "PORTAL_NOT_ACCESSED",
    "PORTAL_ACCESS_FUTURE_GATED",
    "PORTAL_BLOCKED_NO_CREDENTIAL_REF",
    "PORTAL_BLOCKED_NO_PO",
    "UNKNOWN_FAIL_CLOSED",
)

SUBMIT_GATE_STATUSES = (
    "NOT_READY_MISSING_INPUTS",
    "READY_FOR_GUARDIAN_REVIEW",
    "WAITING_FOR_OPERATOR_APPROVAL",
    "APPROVED_NOT_SUBMITTED_FUTURE",
    "SUBMIT_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

PORTAL_ACTION_STATUSES = (
    "NOT_STARTED",
    "PACKAGE_ONLY",
    "FUTURE_SUBMIT_TARGET",
    "BLOCKED_MISSING_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "COUPA_PACKAGE_READY_FOR_REVIEW",
    "NOT_READY_MISSING_PO",
    "NOT_READY_MISSING_VALUES",
    "NOT_READY_MISSING_ARTIFACT",
    "NOT_READY_MISSING_APPROVAL",
    "NOT_READY_MISSING_SECRET_REF",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_BROWSER_GATE",
    "BLOCKED_SUBMIT_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "PO_REFERENCE_MISSING",
    "PO_REFERENCE_UNCONFIRMED",
    "INVOICE_VALUES_MISSING",
    "VALUE_MISMATCH",
    "ARTIFACT_REF_MISSING",
    "ARTIFACT_HASH_MISSING",
    "SECRET_REF_MISSING",
    "APPROVAL_MISSING",
    "BROWSER_GATE_MISSING",
    "SUBMIT_GATE_MISSING",
    "RAW_PO_EXPOSED",
    "RAW_CREDENTIAL_INCLUDED",
    "COUPA_ACCESS_ATTEMPTED",
    "COUPA_SUBMIT_ATTEMPTED",
    "BROWSER_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_portal_login_allowed": False,
    "live_invoice_submit_allowed": False,
    "live_payment_action_allowed": False,
    "live_external_action_allowed": False,
    "live_approval_execution_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_file_mutation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "Coupa access",
    "Coupa submit",
    "browser open or automation",
    "portal login",
    "secret reveal",
    "payment action",
    "approval execution",
    "workflow run",
    "agent dispatch",
    "external action",
    "credential handling",
)

CAPITAL_HILTON_REQUIRED_PROOFS = (
    "confirmed Coupa PO/reference",
    "confirmed invoice dates/rate/subtotal",
    "invoice artifact ref",
    "invoice artifact hash/fingerprint",
    "protected credential/secret ref if future portal login required",
    "Guardian approval packet",
    "exact operator approval receipt",
    "future portal submission receipt",
    "future Coupa confirmation/proof",
)

CAPITAL_HILTON_VALUE_REFS = (
    "dates_ref:capital_hilton_2026_05_performance_dates",
    "rate_ref:capital_hilton_400_per_show",
    "subtotal_ref:capital_hilton_1600_usd",
)

CAPITAL_HILTON_ARTIFACT_REFS = (
    "invoice_artifact_ref:capital_hilton_pdf_2026-05-25",
    "invoice_artifact_ref:capital_hilton_xlsx_2026-05-25",
)

CAPITAL_HILTON_ATTACHMENT_REFS = (
    "email_attachment_ref:capital_hilton_pdf_2026-05-25",
    "email_attachment_ref:capital_hilton_xlsx_2026-05-25",
)


@dataclass(frozen=True)
class CoupaSupplierPortalPackageCompiler:
    compiler_id: str
    doctrine: tuple[str, ...]
    po_reference_policy: tuple[str, ...]
    invoice_value_policy: tuple[str, ...]
    artifact_policy: tuple[str, ...]
    credential_policy: tuple[str, ...]
    browser_adapter_policy: tuple[str, ...]
    approval_policy: tuple[str, ...]
    submit_gate_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class CoupaSupplierPortalPackage:
    package_id: str
    source_workflow_ref: str
    client_ref: str
    tenant_ref: str
    coupa_po_ref: str
    po_status: str
    supplier_portal_status: str
    invoice_value_refs: tuple[str, ...]
    invoice_artifact_refs: tuple[str, ...]
    invoice_attachment_refs: tuple[str, ...]
    credential_ref_status: str
    missing_inputs: tuple[str, ...]
    required_approvals: tuple[str, ...]
    required_proofs: tuple[str, ...]
    browser_gate_status: str
    submit_gate_status: str
    portal_action_status: str
    next_safe_move: str


@dataclass(frozen=True)
class CoupaPOReference:
    po_ref: str
    safe_display_label: str
    tokenized_po_ref: str
    source_ref: str
    confirmation_status: str
    privacy_class: str
    protected_ref_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class CoupaInvoiceValueSet:
    value_set_ref: str
    source_delivery_facts_ref: str
    dates_ref: str
    rate_ref: str
    subtotal_ref: str
    tax_or_fee_policy: str
    currency: str
    confirmation_status: str
    proof_refs: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CoupaPortalGate:
    gate_id: str
    package_ref: str
    required_covenant_ref: str
    required_guardian_approval_ref: str
    required_secret_ref: str
    exact_approval_phrase: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    coupa_access_allowed: bool
    coupa_submit_allowed: bool
    browser_allowed: bool
    action_executed: bool
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class CoupaPackageReadback:
    readback_id: str
    package_ref: str
    status: str
    operator_headline: str
    operator_message: str
    package_summary: str
    po_summary: str
    invoice_value_summary: str
    artifact_summary: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    approval_status: str
    proof_status: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class CoupaProofPlan:
    proof_plan_id: str
    package_ref: str
    required_proofs: tuple[str, ...]
    available_proof_refs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    completion_label: str
    completion_allowed: bool
    final_readback_target: str
    next_safe_move: str


@dataclass(frozen=True)
class CoupaPackageBlocker:
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


def build_compiler() -> CoupaSupplierPortalPackageCompiler:
    return CoupaSupplierPortalPackageCompiler(
        compiler_id="coupa_supplier_portal_package_compiler_v0",
        doctrine=(
            "Compiler creates a Coupa package, not a Coupa action.",
            "Package binds PO/reference posture, invoice values, invoice artifact refs, protected credential refs, approval refs, gates, and proof requirements.",
            "Package must state missing items and blocked actions clearly.",
            "Readbacks must never claim portal access, login, submission, or payment completion.",
            "Browser, Coupa, credential, submit, and external authority remain false.",
        ),
        po_reference_policy=(
            "PO/reference should be represented as a safe/tokenized ref.",
            "Raw PO/reference is not exposed in normal read-models unless future fixture policy says it is public-safe.",
            "Missing or candidate PO/reference blocks submit readiness.",
        ),
        invoice_value_policy=(
            "Invoice values come from receipts, readbacks, or source refs, not chat vibes.",
            "Capital Hilton basis is four performance dates at $400/show for a $1,600 subtotal.",
            "Value mismatch blocks package readiness.",
        ),
        artifact_policy=(
            "Invoice artifacts are refs with hash/fingerprint proof.",
            "Raw artifact bodies are not copied into the Coupa package read-model.",
            "Missing artifact ref or hash blocks package readiness.",
        ),
        credential_policy=(
            "Future portal login requires a protected secret ref only.",
            "Raw credentials are forbidden in chat, package inputs, read-models, and operator markdown.",
            "Secret reveal and credential handling remain false.",
        ),
        browser_adapter_policy=(
            "This lane does not open Coupa, start a browser, or automate a portal.",
            "A future browser/Coupa adapter must require covenant, Guardian, exact approval, secret ref, and receipts.",
        ),
        approval_policy=(
            "Action Covenant and Guardian approval packet refs are required before any future Coupa adapter can act.",
            "Operator approval receipt is modeled as future proof, not created here.",
            "Approval execution remains disabled.",
        ),
        submit_gate_policy=(
            "Submit gate records missing items and exact approval phrase.",
            "coupa_access_allowed false, coupa_submit_allowed false, browser_allowed false, action_executed false, external_authority false.",
            "Even complete packages remain package/review artifacts until a future gated adapter exists.",
        ),
        proof_policy=(
            "Completion requires confirmed PO/reference, confirmed values, artifact ref/hash, protected secret ref if portal login is required, Guardian packet, exact operator approval receipt, future portal submission receipt, and future Coupa confirmation/proof.",
            "COUPA INVOICE SUBMITTED is a future target only.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this compiler to assemble Coupa payment-rail refs before Guardian/operator review; do not access Coupa.",
    )


def build_po_reference(
    *,
    po_ref: str = "coupa_po_ref:capital_hilton_candidate",
    confirmation_status: str = "PO_CANDIDATE",
    safe_display_label: str = "Capital Hilton Coupa PO/reference candidate",
    tokenized_po_ref: str = "po_token_ref:capital_hilton_candidate",
    source_ref: str = "source_ref:operator_or_protected_evidence_pending",
) -> CoupaPOReference:
    return CoupaPOReference(
        po_ref=po_ref,
        safe_display_label=safe_display_label,
        tokenized_po_ref=tokenized_po_ref,
        source_ref=source_ref,
        confirmation_status=confirmation_status,
        privacy_class="client_payment_reference_private_ref",
        protected_ref_required=True,
        next_safe_move="Confirm the Coupa PO/reference before any future submit package can be considered ready.",
    )


def build_invoice_values(
    *,
    confirmation_status: str = "VALUES_CONFIRMED",
    proof_refs: tuple[str, ...] = (
        "delivery_facts_ref:capital_hilton_four_performance_dates",
        "rate_ref:capital_hilton_400_per_show",
        "subtotal_ref:capital_hilton_1600_usd",
    ),
) -> CoupaInvoiceValueSet:
    return CoupaInvoiceValueSet(
        value_set_ref="coupa_invoice_values_ref:capital_hilton_2026_05_1600_usd",
        source_delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        dates_ref=CAPITAL_HILTON_VALUE_REFS[0],
        rate_ref=CAPITAL_HILTON_VALUE_REFS[1],
        subtotal_ref=CAPITAL_HILTON_VALUE_REFS[2],
        tax_or_fee_policy="no additional tax/fee modeled in v0; mismatch or extra fee requires review",
        currency="USD",
        confirmation_status=confirmation_status,
        proof_refs=proof_refs,
        next_safe_move="Use value refs as payment-rail package inputs; block on mismatch.",
    )


def build_package(
    *,
    package_id: str,
    coupa_po_ref: str,
    po_status: str,
    supplier_portal_status: str,
    invoice_value_refs: tuple[str, ...],
    invoice_artifact_refs: tuple[str, ...],
    invoice_attachment_refs: tuple[str, ...],
    credential_ref_status: str,
    missing_inputs: tuple[str, ...],
    browser_gate_status: str,
    submit_gate_status: str,
    portal_action_status: str,
) -> CoupaSupplierPortalPackage:
    return CoupaSupplierPortalPackage(
        package_id=package_id,
        source_workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        coupa_po_ref=coupa_po_ref,
        po_status=po_status,
        supplier_portal_status=supplier_portal_status,
        invoice_value_refs=invoice_value_refs,
        invoice_artifact_refs=invoice_artifact_refs,
        invoice_attachment_refs=invoice_attachment_refs,
        credential_ref_status=credential_ref_status,
        missing_inputs=missing_inputs,
        required_approvals=(
            "Action Covenant for SUBMIT_COUPA",
            "Guardian approval request packet",
            "future exact operator approval receipt",
        ),
        required_proofs=CAPITAL_HILTON_REQUIRED_PROOFS,
        browser_gate_status=browser_gate_status,
        submit_gate_status=submit_gate_status,
        portal_action_status=portal_action_status,
        next_safe_move="Review package and resolve missing Coupa gate items; do not open Coupa or submit.",
    )


def build_portal_gate(package: CoupaSupplierPortalPackage) -> CoupaPortalGate:
    covenant_ref = "capital_hilton_coupa_submit_covenant_v0"
    approval_ref = (
        "guardian_approval_capital_hilton_coupa_submit_v0"
        if "Guardian approval packet" not in package.missing_inputs
        else ""
    )
    secret_ref = (
        "secret_ref:coupa_use_once_capital_hilton"
        if package.credential_ref_status == "PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED"
        else ""
    )
    missing = list(package.missing_inputs)
    if not package.coupa_po_ref:
        missing.append("confirmed Coupa PO/reference")
    if not package.invoice_value_refs:
        missing.append("confirmed invoice dates/rate/subtotal")
    if not package.invoice_artifact_refs:
        missing.append("invoice artifact ref")
    if not package.invoice_attachment_refs:
        missing.append("invoice attachment ref")
    if not secret_ref:
        missing.append("protected credential/secret ref if future portal login required")
    if not approval_ref:
        missing.append("Guardian approval packet")
    if "exact operator approval receipt" not in missing:
        missing.append("exact operator approval receipt")
    if "future portal submission receipt" not in missing:
        missing.append("future portal submission receipt")
    return CoupaPortalGate(
        gate_id=_stable_id("coupa_portal_gate", package.package_id),
        package_ref=package.package_id,
        required_covenant_ref=covenant_ref,
        required_guardian_approval_ref=approval_ref or "missing",
        required_secret_ref=secret_ref or "missing",
        exact_approval_phrase=f"APPROVE SUBMIT_COUPA {covenant_ref}",
        missing_items=tuple(dict.fromkeys(missing)),
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        coupa_access_allowed=False,
        coupa_submit_allowed=False,
        browser_allowed=False,
        action_executed=False,
        external_authority=False,
        next_safe_move="Create/complete PO, secret-ref, Guardian, and future operator approval receipts before any future Coupa adapter could act.",
    )


def build_proof_plan(
    package: CoupaSupplierPortalPackage,
    *,
    available_proof_refs: tuple[str, ...],
) -> CoupaProofPlan:
    missing = tuple(proof for proof in package.required_proofs if proof not in available_proof_refs)
    return CoupaProofPlan(
        proof_plan_id=_stable_id("coupa_proof_plan", package.package_id),
        package_ref=package.package_id,
        required_proofs=package.required_proofs,
        available_proof_refs=available_proof_refs,
        missing_proofs=missing,
        completion_label="COUPA INVOICE SUBMITTED",
        completion_allowed=False,
        final_readback_target="future final readback only after portal submission and Coupa confirmation proof exist",
        next_safe_move=(
            "Collect missing proofs and approval receipts; COUPA INVOICE SUBMITTED remains a future target."
            if missing
            else "Proof refs are assembled, but future portal submission receipt is still required outside this lane."
        ),
    )


def build_readback(
    package: CoupaSupplierPortalPackage,
    po_reference: CoupaPOReference | None,
    values: CoupaInvoiceValueSet | None,
    portal_gate: CoupaPortalGate,
    proof_plan: CoupaProofPlan,
) -> CoupaPackageReadback:
    if package.po_status == "PO_MISSING" or not package.coupa_po_ref:
        status = "NOT_READY_MISSING_PO"
        headline = "Coupa package needs a PO/reference"
        message = (
            "OpenClaw has assembled the Coupa payment-rail package shape for Capital Hilton. "
            "Nothing has been opened or submitted. The package still needs the Coupa PO/reference, required proof, and Guardian/operator approval before any future Coupa/browser adapter can act."
        )
        fix = "Provide, attach, or confirm the Coupa PO/reference, or tell OpenClaw to keep discovery open."
    elif not package.invoice_value_refs or values is None:
        status = "NOT_READY_MISSING_VALUES"
        headline = "Coupa package needs invoice values"
        message = "The Coupa package is missing confirmed invoice dates, rate, or subtotal refs."
        fix = "Attach delivery fact/value refs for the dates, $400/show rate, and $1,600 subtotal."
    elif not package.invoice_artifact_refs:
        status = "NOT_READY_MISSING_ARTIFACT"
        headline = "Coupa package needs invoice artifact refs"
        message = "The Coupa package is missing invoice artifact refs and hash/fingerprint proof."
        fix = "Generate or attach the Winship-branded invoice artifacts and hash/fingerprint them."
    elif any("hash/fingerprint" in item for item in package.missing_inputs):
        status = "NOT_READY_MISSING_ARTIFACT"
        headline = "Coupa package needs artifact hash proof"
        message = "The invoice artifact ref exists, but its hash/fingerprint proof is missing."
        fix = "Hash/fingerprint the invoice artifact before Coupa package review."
    elif package.credential_ref_status != "PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED":
        status = "NOT_READY_MISSING_SECRET_REF"
        headline = "Coupa package needs protected credential ref"
        message = "Future portal access would require a protected secret ref. Do not put credentials in chat."
        fix = "Use the future Enter Secret protected flow to create a secret_ref; keep the raw credential hidden."
    elif "Guardian approval packet" in package.missing_inputs:
        status = "NOT_READY_MISSING_APPROVAL"
        headline = "Coupa package needs Guardian approval"
        message = "The Coupa package has PO/value/artifact posture, but the Guardian approval packet is missing."
        fix = "Create an Action Covenant and Guardian approval request for SUBMIT_COUPA."
    elif package.browser_gate_status == "BROWSER_BLOCKED" or portal_gate.browser_allowed:
        status = "BLOCKED_BROWSER_GATE"
        headline = "Coupa browser gate is locked"
        message = "A browser/Coupa action was attempted or improperly allowed in a package-only lane."
        fix = "Keep browser_allowed false and use a future approved Coupa/browser adapter."
    elif package.submit_gate_status == "SUBMIT_BLOCKED" or portal_gate.coupa_submit_allowed:
        status = "BLOCKED_SUBMIT_GATE"
        headline = "Coupa submit gate is locked"
        message = "A Coupa submit action was attempted or improperly allowed in a package-only lane."
        fix = "Keep coupa_submit_allowed false and return package/readback only."
    else:
        status = "COUPA_PACKAGE_READY_FOR_REVIEW"
        headline = "Coupa package ready for review"
        message = (
            "OpenClaw has assembled the Coupa payment-rail package shape for Capital Hilton. "
            "Nothing has been opened or submitted. Future Coupa/browser action still requires exact approval and a governed adapter."
        )
        fix = "Review the package; do not access Coupa until a future gated adapter and approval receipts exist."

    po_summary = (
        f"{po_reference.safe_display_label} ({po_reference.confirmation_status})"
        if po_reference
        else "No Coupa PO/reference ref"
    )
    value_summary = (
        f"{values.confirmation_status}; dates/rate/subtotal refs present"
        if values
        else "No invoice value set ref"
    )
    artifact_summary = (
        ", ".join(package.invoice_artifact_refs)
        if package.invoice_artifact_refs
        else "No invoice artifact refs"
    )
    return CoupaPackageReadback(
        readback_id=_stable_id("coupa_package_readback", package.package_id, status),
        package_ref=package.package_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        package_summary=f"{package.source_workflow_ref}; portal action {package.portal_action_status}; submit gate {package.submit_gate_status}",
        po_summary=po_summary,
        invoice_value_summary=value_summary,
        artifact_summary=artifact_summary,
        missing_items=tuple(dict.fromkeys((*package.missing_inputs, *portal_gate.missing_items, *proof_plan.missing_proofs))),
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        approval_status=package.submit_gate_status,
        proof_status="BLOCKED_MISSING_PROOF" if proof_plan.missing_proofs else "PROOF_REFS_MODELED_NOT_SUBMITTED",
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_blockers() -> tuple[CoupaPackageBlocker, ...]:
    return (
        CoupaPackageBlocker("coupa_blocker_po_missing", "PO_REFERENCE_MISSING", "No Coupa PO/reference ref is present.", "critical", "Coupa PO/reference is missing.", True, "Provide or confirm the Coupa PO/reference."),
        CoupaPackageBlocker("coupa_blocker_po_unconfirmed", "PO_REFERENCE_UNCONFIRMED", "PO/reference is only a candidate.", "high", "Coupa PO/reference must be confirmed before future submit.", True, "Confirm PO/reference via protected proof."),
        CoupaPackageBlocker("coupa_blocker_values_missing", "INVOICE_VALUES_MISSING", "Invoice date/rate/subtotal refs are missing.", "critical", "Invoice values are missing.", True, "Attach delivery facts/value refs."),
        CoupaPackageBlocker("coupa_blocker_value_mismatch", "VALUE_MISMATCH", "Invoice values differ across proofs.", "critical", "Invoice value mismatch blocks Coupa package readiness.", True, "Reconcile value refs before review."),
        CoupaPackageBlocker("coupa_blocker_artifact_missing", "ARTIFACT_REF_MISSING", "Invoice artifact refs are missing.", "high", "Invoice artifact ref is missing.", True, "Generate or attach invoice artifact refs."),
        CoupaPackageBlocker("coupa_blocker_artifact_hash", "ARTIFACT_HASH_MISSING", "Invoice artifact lacks hash/fingerprint proof.", "high", "Artifact hash/fingerprint is missing.", True, "Hash/fingerprint the artifact."),
        CoupaPackageBlocker("coupa_blocker_secret_missing", "SECRET_REF_MISSING", "Future portal login requires a protected secret ref.", "critical", "Protected credential ref is missing.", True, "Use the future Enter Secret protected flow; do not type credentials in chat."),
        CoupaPackageBlocker("coupa_blocker_approval_missing", "APPROVAL_MISSING", "Action Covenant or Guardian approval request is missing.", "critical", "Guardian/operator approval is missing.", True, "Create SUBMIT_COUPA covenant and Guardian packet."),
        CoupaPackageBlocker("coupa_blocker_browser_gate", "BROWSER_GATE_MISSING", "Browser gate model is absent.", "critical", "Browser gate is missing.", True, "Regenerate package with CoupaPortalGate."),
        CoupaPackageBlocker("coupa_blocker_submit_gate", "SUBMIT_GATE_MISSING", "Submit gate model is absent.", "critical", "Submit gate is missing.", True, "Regenerate package with CoupaPortalGate."),
        CoupaPackageBlocker("coupa_blocker_raw_po", "RAW_PO_EXPOSED", "Raw private PO/reference appears in normal read-model output.", "critical", "Raw PO/reference exposure is blocked.", True, "Use tokenized PO refs and safe labels."),
        CoupaPackageBlocker("coupa_blocker_raw_credential", "RAW_CREDENTIAL_INCLUDED", "Credential material appears in package/read-model.", "critical", "Credential exposure is blocked.", True, "Use protected secret refs only."),
        CoupaPackageBlocker("coupa_blocker_access", "COUPA_ACCESS_ATTEMPTED", "Compiler attempts Coupa access.", "critical", "Coupa access is blocked.", True, "Return package/readback only."),
        CoupaPackageBlocker("coupa_blocker_submit", "COUPA_SUBMIT_ATTEMPTED", "Compiler attempts Coupa submit.", "critical", "Coupa submit is blocked.", True, "Return package/readback only."),
        CoupaPackageBlocker("coupa_blocker_browser", "BROWSER_ATTEMPTED", "Compiler attempts browser open or automation.", "critical", "Browser access is blocked.", True, "Stay in deterministic package generation."),
        CoupaPackageBlocker("coupa_blocker_external", "EXTERNAL_ACTION_ATTEMPTED", "Compiler attempts external account, portal, payment, or runtime action.", "critical", "External action is blocked.", True, "Stay local and read-model only."),
        CoupaPackageBlocker("coupa_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown Coupa package state.", "high", "Unknown Coupa package state fails closed.", True, "Ask for scoped PO/value/artifact/secret/approval refs."),
    )


def _package_bundle(
    *,
    package: CoupaSupplierPortalPackage,
    po_reference: CoupaPOReference | None,
    values: CoupaInvoiceValueSet | None,
    available_proofs: tuple[str, ...],
) -> dict[str, Any]:
    portal_gate = build_portal_gate(package)
    proof_plan = build_proof_plan(package, available_proof_refs=available_proofs)
    readback = build_readback(package, po_reference, values, portal_gate, proof_plan)
    return {
        "package": asdict(package),
        "po_reference": asdict(po_reference) if po_reference else None,
        "invoice_values": asdict(values) if values else None,
        "portal_gate": asdict(portal_gate),
        "proof_plan": asdict(proof_plan),
        "readback": asdict(readback),
    }


def build_examples() -> dict[str, Any]:
    values = build_invoice_values()
    po_candidate = build_po_reference()
    po_confirmed = build_po_reference(
        po_ref="coupa_po_ref:capital_hilton_confirmed",
        confirmation_status="PO_CONFIRMED",
        safe_display_label="Capital Hilton Coupa PO/reference confirmed",
        tokenized_po_ref="po_token_ref:capital_hilton_confirmed",
        source_ref="protected_evidence_ref:capital_hilton_coupa_po_confirmation",
    )
    common_available = (
        "confirmed invoice dates/rate/subtotal",
        "invoice artifact ref",
        "invoice artifact hash/fingerprint",
    )
    missing_po_package = build_package(
        package_id="coupa_package_capital_hilton_missing_po_v0",
        coupa_po_ref="",
        po_status="PO_MISSING",
        supplier_portal_status="PORTAL_BLOCKED_NO_PO",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
        missing_inputs=("confirmed Coupa PO/reference",),
        browser_gate_status="BROWSER_GATE_LOCKED",
        submit_gate_status="NOT_READY_MISSING_INPUTS",
        portal_action_status="BLOCKED_MISSING_PROOF",
    )
    missing_approval_package = build_package(
        package_id="coupa_package_capital_hilton_complete_except_approval_v0",
        coupa_po_ref=po_confirmed.po_ref,
        po_status=po_confirmed.confirmation_status,
        supplier_portal_status="PORTAL_ACCESS_FUTURE_GATED",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
        missing_inputs=("Guardian approval packet", "exact operator approval receipt", "future portal submission receipt", "future Coupa confirmation/proof"),
        browser_gate_status="BROWSER_GATE_LOCKED",
        submit_gate_status="READY_FOR_GUARDIAN_REVIEW",
        portal_action_status="PACKAGE_ONLY",
    )
    missing_secret_package = build_package(
        package_id="coupa_package_capital_hilton_missing_secret_v0",
        coupa_po_ref=po_confirmed.po_ref,
        po_status=po_confirmed.confirmation_status,
        supplier_portal_status="PORTAL_BLOCKED_NO_CREDENTIAL_REF",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_MISSING",
        missing_inputs=("protected credential/secret ref if future portal login required",),
        browser_gate_status="BROWSER_GATE_LOCKED",
        submit_gate_status="NOT_READY_MISSING_INPUTS",
        portal_action_status="BLOCKED_MISSING_PROOF",
    )
    attempted_submit_package = build_package(
        package_id="coupa_package_capital_hilton_submit_attempt_blocked_v0",
        coupa_po_ref=po_confirmed.po_ref,
        po_status=po_confirmed.confirmation_status,
        supplier_portal_status="PORTAL_ACCESS_FUTURE_GATED",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
        missing_inputs=("Coupa submit attempted but blocked",),
        browser_gate_status="BROWSER_GATE_LOCKED",
        submit_gate_status="SUBMIT_BLOCKED",
        portal_action_status="PACKAGE_ONLY",
    )
    attempted_browser_package = build_package(
        package_id="coupa_package_capital_hilton_browser_attempt_blocked_v0",
        coupa_po_ref=po_confirmed.po_ref,
        po_status=po_confirmed.confirmation_status,
        supplier_portal_status="PORTAL_ACCESS_FUTURE_GATED",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
        missing_inputs=("browser attempted but blocked",),
        browser_gate_status="BROWSER_BLOCKED",
        submit_gate_status="SUBMIT_BLOCKED",
        portal_action_status="PACKAGE_ONLY",
    )
    ready_review_package = build_package(
        package_id="coupa_package_capital_hilton_ready_for_review_v0",
        coupa_po_ref=po_confirmed.po_ref,
        po_status=po_confirmed.confirmation_status,
        supplier_portal_status="PORTAL_ACCESS_FUTURE_GATED",
        invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
        invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
        invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
        credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
        missing_inputs=("exact operator approval receipt", "future portal submission receipt", "future Coupa confirmation/proof"),
        browser_gate_status="BROWSER_GATE_LOCKED",
        submit_gate_status="WAITING_FOR_OPERATOR_APPROVAL",
        portal_action_status="FUTURE_SUBMIT_TARGET",
    )
    return {
        "capital_hilton_missing_po": _package_bundle(
            package=missing_po_package,
            po_reference=None,
            values=values,
            available_proofs=common_available,
        ),
        "capital_hilton_complete_except_approval": _package_bundle(
            package=missing_approval_package,
            po_reference=po_confirmed,
            values=values,
            available_proofs=("confirmed Coupa PO/reference", *common_available, "protected credential/secret ref if future portal login required"),
        ),
        "missing_secret_ref": _package_bundle(
            package=missing_secret_package,
            po_reference=po_confirmed,
            values=values,
            available_proofs=("confirmed Coupa PO/reference", *common_available, "Guardian approval packet"),
        ),
        "attempted_coupa_submit": _package_bundle(
            package=attempted_submit_package,
            po_reference=po_confirmed,
            values=values,
            available_proofs=("confirmed Coupa PO/reference", *common_available, "protected credential/secret ref if future portal login required", "Guardian approval packet"),
        ),
        "attempted_browser": _package_bundle(
            package=attempted_browser_package,
            po_reference=po_confirmed,
            values=values,
            available_proofs=("confirmed Coupa PO/reference", *common_available, "protected credential/secret ref if future portal login required", "Guardian approval packet"),
        ),
        "capital_hilton_ready_for_review_future_gated": _package_bundle(
            package=ready_review_package,
            po_reference=po_confirmed,
            values=values,
            available_proofs=("confirmed Coupa PO/reference", *common_available, "protected credential/secret ref if future portal login required", "Guardian approval packet"),
        ),
        "po_candidate_not_submit_ready": _package_bundle(
            package=build_package(
                package_id="coupa_package_capital_hilton_po_candidate_v0",
                coupa_po_ref=po_candidate.po_ref,
                po_status=po_candidate.confirmation_status,
                supplier_portal_status="PORTAL_ACCESS_FUTURE_GATED",
                invoice_value_refs=CAPITAL_HILTON_VALUE_REFS,
                invoice_artifact_refs=CAPITAL_HILTON_ARTIFACT_REFS,
                invoice_attachment_refs=CAPITAL_HILTON_ATTACHMENT_REFS,
                credential_ref_status="PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED",
                missing_inputs=("confirmed Coupa PO/reference",),
                browser_gate_status="BROWSER_GATE_LOCKED",
                submit_gate_status="NOT_READY_MISSING_INPUTS",
                portal_action_status="BLOCKED_MISSING_PROOF",
            ),
            po_reference=po_candidate,
            values=values,
            available_proofs=common_available,
        ),
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    compiler = build_compiler()
    blockers = build_blockers()
    examples = build_examples()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "po_statuses": PO_STATUSES,
        "supplier_portal_statuses": SUPPLIER_PORTAL_STATUSES,
        "submit_gate_statuses": SUBMIT_GATE_STATUSES,
        "portal_action_statuses": PORTAL_ACTION_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "compiler": asdict(compiler),
        "coupa_package_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "capital_hilton_required_package": {
            "known": (
                "client: Capital Hilton",
                "workflow: capital_hilton_invoice_workflow",
                "official payment rail: Coupa supplier portal / PO",
                "invoice basis: 4 dates at $400 = $1,600",
                "companion invoice: Winship-branded Excel/PDF",
                "email to Annette is local records/payment follow-up, not official Coupa submission",
            ),
            "operator_readback": (
                "OpenClaw has assembled the Coupa payment-rail package shape for Capital Hilton. "
                "Nothing has been opened or submitted. The package still needs the Coupa PO/reference, required proof, and Guardian/operator approval before any future Coupa/browser adapter can act."
            ),
        },
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "portal_login_performed": False,
            "secret_reveal_performed": False,
            "payment_action_performed": False,
            "approval_execution_performed": False,
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
            "OpenClaw can now assemble a Coupa supplier portal payment-rail package from PO/reference, "
            "invoice value, artifact, protected secret, Guardian approval, portal gate, and proof refs. "
            "Nothing is opened, logged into, submitted, or paid."
        ),
        "next_safe_move": "Resolve missing PO/secret/approval proof refs, then keep Coupa/browser action locked until a future approved adapter exists.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    capital = payload["examples"]["capital_hilton_missing_po"]
    complete = payload["examples"]["capital_hilton_complete_except_approval"]
    lines = [
        "# Coupa Supplier Portal Package Compiler",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton Missing PO",
        f"- Status: {capital['readback']['status']}",
        f"- Message: {capital['readback']['operator_message']}",
        f"- PO/reference: {capital['readback']['po_summary']}",
        f"- Invoice values: {capital['readback']['invoice_value_summary']}",
        f"- Artifact: {capital['readback']['artifact_summary']}",
        f"- Next: {capital['readback']['next_safe_move']}",
        "",
        "## Complete Except Approval",
        f"- Status: {complete['readback']['status']}",
        f"- Message: {complete['readback']['operator_message']}",
        f"- Approval: {complete['readback']['approval_status']}",
        f"- Next: {complete['readback']['next_safe_move']}",
        "",
        "## Blocked",
    ]
    for blocker in payload["coupa_package_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No Coupa access, no Coupa submit, no browser, no portal login, no secret reveal, no payment action, no approval execution, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.",
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
        "blocker_count": len(payload["coupa_package_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Coupa Supplier Portal Package Compiler read-model.")
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
