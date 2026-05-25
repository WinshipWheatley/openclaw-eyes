"""Gated Coupa Submit Adapter v0.

This deterministic rail models the approval-bound Coupa supplier portal submit
boundary for OpenClaw. It checks Coupa package, run package, PO/reference,
invoice values, invoice artifacts, protected secret refs, Guardian approval,
exact operator approval, browser/provider adapter, and submit authority gates,
then returns readiness or a human blocked reason.

It does not access Coupa, open a browser, log in, submit invoices, reveal
secrets, execute payments, run workflows, dispatch agents, handle credentials,
ingest raw bodies, mutate Mission Control Swift, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "gated_coupa_submit_adapter_v0"
READ_MODEL_ID = "gated_coupa_submit_adapter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_APPROVAL_BOUND_COUPA_SUBMIT_RAIL_NO_SUBMIT"

EXACT_APPROVAL_PHRASE_REF = "approval_phrase_ref:APPROVE_SUBMIT_COUPA_capital_hilton_invoice_v0"
EXACT_APPROVAL_DISPLAY = "APPROVE SUBMIT_COUPA capital_hilton_invoice_v0"

PROVIDER_TARGETS = (
    "COUPA_BROWSER_ADAPTER",
    "COUPA_API_ADAPTER_FUTURE",
    "MANUAL_COUPA_HANDOFF",
    "UNKNOWN_FAIL_CLOSED",
)

REQUESTED_MODES = (
    "DRY_RUN_ONLY",
    "READINESS_CHECK_ONLY",
    "LIVE_SUBMIT_GATED_FUTURE",
    "MANUAL_SUBMIT_HANDOFF",
    "UNKNOWN_FAIL_CLOSED",
)

READINESS_STATUSES = (
    "COUPA_ADAPTER_READY_BUT_NOT_EXECUTED",
    "SUBMIT_BLOCKED_MISSING_GATES",
    "SUBMIT_BLOCKED_MISSING_PO",
    "SUBMIT_BLOCKED_MISSING_VALUES",
    "SUBMIT_BLOCKED_MISSING_ARTIFACT",
    "SUBMIT_BLOCKED_MISSING_SECRET_REF",
    "SUBMIT_BLOCKED_MISSING_PROVIDER",
    "SUBMIT_BLOCKED_PRIVACY_BOUNDARY",
    "SUBMIT_BLOCKED_UNSUPPORTED_PROVIDER",
    "SUBMIT_DRY_RUN_READY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "GENERIC_APPROVAL_USED",
    "EXACT_APPROVAL_MISSING",
    "GUARDIAN_APPROVAL_MISSING",
    "PO_REFERENCE_MISSING",
    "PO_REFERENCE_UNCONFIRMED",
    "INVOICE_VALUES_MISSING",
    "VALUE_MISMATCH",
    "ARTIFACT_REF_MISSING",
    "ARTIFACT_HASH_MISSING",
    "SECRET_REF_MISSING",
    "PROVIDER_ADAPTER_MISSING",
    "RAW_CREDENTIAL_INCLUDED",
    "RAW_PO_EXPOSED",
    "BROWSER_ATTEMPTED_WITHOUT_GATES",
    "SUBMIT_ATTEMPTED_WITHOUT_GATES",
    "PROVIDER_CALLED_IN_TEST",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_portal_login_allowed": False,
    "live_provider_call_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_payment_action_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_approval_execution_allowed": False,
    "live_email_send_allowed": False,
    "live_file_mutation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "Coupa access",
    "Coupa submit",
    "browser open",
    "portal login",
    "provider call",
    "secret reveal",
    "payment action",
    "external action",
    "workflow run",
    "agent dispatch",
    "credential handling",
)

REQUIRED_SUBMIT_PROOFS = (
    "valid Coupa supplier portal package ref",
    "valid invoice delivery run package ref",
    "confirmed Coupa PO/reference",
    "confirmed invoice dates/rate/subtotal refs",
    "invoice artifact refs",
    "invoice artifact hash/fingerprint refs",
    "protected Coupa credential/secret ref",
    "Guardian approval ref",
    "exact operator approval receipt ref",
    "exact approval phrase matched to package",
    "browser/Coupa adapter available for selected mode",
    "submit authority granted for live submit mode",
)

CAPITAL_HILTON_VALUE_REFS = (
    "dates_ref:capital_hilton_2026_05_performance_dates",
    "rate_ref:capital_hilton_400_per_show",
    "subtotal_ref:capital_hilton_1600_usd",
)


@dataclass(frozen=True)
class GatedCoupaSubmitAdapter:
    adapter_id: str
    doctrine: tuple[str, ...]
    source_package_policy: tuple[str, ...]
    po_reference_policy: tuple[str, ...]
    invoice_value_policy: tuple[str, ...]
    artifact_policy: tuple[str, ...]
    secret_policy: tuple[str, ...]
    guardian_policy: tuple[str, ...]
    operator_approval_policy: tuple[str, ...]
    browser_adapter_policy: tuple[str, ...]
    submit_receipt_policy: tuple[str, ...]
    fail_closed_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class CoupaSubmitRequest:
    request_id: str
    source_coupa_package_ref: str
    source_run_package_ref: str
    source_guardian_approval_ref: str
    source_operator_approval_ref: str
    client_ref: str
    tenant_ref: str
    coupa_po_ref: str
    invoice_value_refs: tuple[str, ...]
    invoice_artifact_refs: tuple[str, ...]
    protected_secret_refs: tuple[str, ...]
    provider_target: str
    exact_approval_phrase_ref: str
    submit_authority: bool
    requested_mode: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class CoupaSubmitGateCheck:
    gate_check_id: str
    submit_request_ref: str
    po_confirmed: bool
    invoice_values_confirmed: bool
    invoice_artifact_present: bool
    invoice_artifact_hash_present: bool
    secret_ref_present: bool
    guardian_approval_present: bool
    operator_approval_present: bool
    exact_phrase_matched: bool
    browser_adapter_available: bool
    provider_adapter_available: bool
    submit_authority_granted: bool
    missing_gates: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CoupaProviderBoundary:
    provider_boundary_id: str
    provider_target: str
    provider_available: bool
    provider_submit_method_ref: str
    credential_policy: str
    live_browser_allowed: bool
    live_submit_allowed: bool
    dry_run_available: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class CoupaSubmitReadinessReadback:
    readback_id: str
    submit_request_ref: str
    status: str
    operator_headline: str
    operator_message: str
    ready_summary: str
    missing_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class CoupaSubmitReceipt:
    receipt_id: str
    submit_request_ref: str
    provider_target: str
    coupa_po_ref: str
    invoice_value_refs: tuple[str, ...]
    invoice_artifact_refs: tuple[str, ...]
    submitted: bool
    provider_confirmation_ref: str
    submit_timestamp_policy: str
    proof_refs: tuple[str, ...]
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class CoupaSubmitAdapterBlocker:
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


def _stringify_for_scan(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return stable_json(value) if not isinstance(value, str) else value


def _raw_secret_marker_visible(value: Any) -> bool:
    text = _stringify_for_scan(value).lower()
    markers = (
        "raw_credential",
        "raw_password",
        "password_value",
        "credential_contents",
        "secret_value",
        "session_cookie",
        "oauth_token_value",
    )
    return any(marker in text for marker in markers)


def _raw_po_visible(value: Any) -> bool:
    text = _stringify_for_scan(value)
    return bool(re.search(r"\bPO[-_ ]?\d{5,}\b", text))


def _po_confirmed(po_ref: str) -> bool:
    lower = po_ref.lower()
    return bool(po_ref) and "confirmed" in lower and "candidate" not in lower and "missing" not in lower


def _invoice_values_confirmed(refs: tuple[str, ...]) -> bool:
    return all(required in refs for required in CAPITAL_HILTON_VALUE_REFS) and not any("mismatch" in ref.lower() for ref in refs)


def _artifact_present(refs: tuple[str, ...]) -> bool:
    return any(ref.startswith("invoice_artifact_ref:") for ref in refs)


def _artifact_hash_present(refs: tuple[str, ...]) -> bool:
    return any(ref.startswith("artifact_hash_ref:") or "hash_ref:" in ref for ref in refs)


def _secret_ref_present(refs: tuple[str, ...]) -> bool:
    return any(ref.startswith(("secret_ref:", "protected_secret_ref:")) for ref in refs)


def build_adapter() -> GatedCoupaSubmitAdapter:
    return GatedCoupaSubmitAdapter(
        adapter_id="gated_coupa_submit_adapter_v0",
        doctrine=(
            "No Coupa access, browser open, portal login, or submit without every proof, secret, approval, provider, and authority gate.",
            "Default and fixture modes never call browser/Coupa providers.",
            "Generic chat approval is not enough for high-consequence Coupa submit.",
            "Missing gates produce a human blocked reason and how_to_fix.",
            "Any future completion claim requires a Coupa submit receipt.",
        ),
        source_package_policy=(
            "Coupa supplier portal package ref must identify the exact package under review.",
            "Run package ref binds Coupa submit to the invoice delivery workflow.",
            "Missing package refs block submit readiness.",
        ),
        po_reference_policy=(
            "PO/reference must be confirmed by protected/source refs.",
            "Candidate or missing PO blocks submit readiness.",
            "Raw PO strings are blocked from generated outputs unless represented as safe refs.",
        ),
        invoice_value_policy=(
            "Invoice values must include confirmed dates, rate, and subtotal refs.",
            "Value mismatches block readiness.",
            "Values come from receipts/readbacks/source refs, not chat phrases.",
        ),
        artifact_policy=(
            "Invoice artifacts are refs only.",
            "Artifact hash/fingerprint proof is required.",
            "Missing artifacts or hashes block readiness.",
        ),
        secret_policy=(
            "Protected Coupa credential refs are required for any future portal login.",
            "Raw credentials are never accepted as gate satisfaction.",
            "Secret reveal remains blocked.",
        ),
        guardian_policy=(
            "Guardian approval ref is required for submit readiness.",
            "Approval execution does not happen here.",
            "Missing Guardian review blocks the rail.",
        ),
        operator_approval_policy=(
            "Exact operator approval receipt must bind to this package/covenant.",
            f"Expected phrase ref is {EXACT_APPROVAL_PHRASE_REF}.",
            "Generic phrases such as submit it, yes, or go ahead are blocked.",
        ),
        browser_adapter_policy=(
            "Browser/Coupa provider methods may be named as future boundaries but are not called.",
            "Capital Hilton Coupa PO retrieval automation candidate is static future-only context.",
            "No browser open is allowed in fixture/default/test mode.",
        ),
        submit_receipt_policy=(
            "Submit receipt is modeled with submitted=false in this lane.",
            "Provider confirmation ref is absent unless a future gated live submit occurs.",
            "Final completion cannot be claimed without receipt refs.",
        ),
        fail_closed_policy=(
            "Unknown provider, unknown mode, raw credential marker, raw PO marker, generic approval, or missing gate fails closed.",
            "Blocked output must include how_to_fix.",
            "Tests must prove no provider call, no browser, and submitted=false.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use DRY_RUN_ONLY or READINESS_CHECK_ONLY until a future Coupa/browser provider adapter is explicitly gated.",
    )


def build_provider_boundary(provider_target: str) -> CoupaProviderBoundary:
    if provider_target == "MANUAL_COUPA_HANDOFF":
        return CoupaProviderBoundary(
            provider_boundary_id="coupa_provider_manual_handoff_v0",
            provider_target=provider_target,
            provider_available=True,
            provider_submit_method_ref="manual_coupa_review_handoff:no_browser_or_provider_call",
            credential_policy="Protected credential refs may be listed for future gates; contents are never handled here.",
            live_browser_allowed=False,
            live_submit_allowed=False,
            dry_run_available=True,
            blocked_reason="Manual handoff can be modeled for readiness only; it does not open Coupa or submit.",
            next_safe_move="Keep as dry-run/readiness output until a future submit adapter is approved.",
        )
    if provider_target == "COUPA_BROWSER_ADAPTER":
        return CoupaProviderBoundary(
            provider_boundary_id="coupa_provider_browser_future_v0",
            provider_target=provider_target,
            provider_available=False,
            provider_submit_method_ref="capital_hilton_coupa_po_retrieval_automation_candidate:future_browser_boundary_static_reference_only",
            credential_policy="Protected credential refs would be required later; contents are never handled here.",
            live_browser_allowed=False,
            live_submit_allowed=False,
            dry_run_available=True,
            blocked_reason="Coupa/browser adapter is future-gated and not connected in this lane.",
            next_safe_move="Build a separately approved browser/Coupa adapter after proof, secret, and approval gates are complete.",
        )
    if provider_target == "COUPA_API_ADAPTER_FUTURE":
        return CoupaProviderBoundary(
            provider_boundary_id="coupa_provider_api_future_v0",
            provider_target=provider_target,
            provider_available=False,
            provider_submit_method_ref="coupa_api_submit_adapter_future:not_connected",
            credential_policy="No API credentials are accepted or inspected.",
            live_browser_allowed=False,
            live_submit_allowed=False,
            dry_run_available=True,
            blocked_reason="Coupa API adapter is future-only.",
            next_safe_move="Keep submit blocked until an approved provider adapter exists.",
        )
    return CoupaProviderBoundary(
        provider_boundary_id="coupa_provider_unknown_fail_closed_v0",
        provider_target=provider_target,
        provider_available=False,
        provider_submit_method_ref="unknown",
        credential_policy="Unknown provider receives no credential handling.",
        live_browser_allowed=False,
        live_submit_allowed=False,
        dry_run_available=False,
        blocked_reason="Unsupported provider target.",
        next_safe_move="Select MANUAL_COUPA_HANDOFF for dry-run readiness or build a future gated provider.",
    )


def build_capital_hilton_request(
    *,
    request_id: str = "coupa_submit_request_capital_hilton_dry_run_v0",
    provider_target: str = "MANUAL_COUPA_HANDOFF",
    requested_mode: str = "DRY_RUN_ONLY",
    coupa_po_ref: str = "coupa_po_ref:confirmed_capital_hilton_po_metadata_v0",
    invoice_value_refs: tuple[str, ...] = CAPITAL_HILTON_VALUE_REFS,
    invoice_artifact_refs: tuple[str, ...] = (
        "invoice_artifact_ref:capital_hilton_pdf_2026-05-25",
        "artifact_hash_ref:capital_hilton_invoice_pdf_v0",
    ),
    protected_secret_refs: tuple[str, ...] = ("secret_ref:coupa_capital_hilton_task_scoped_v0",),
    source_guardian_approval_ref: str = "guardian_approval_capital_hilton_coupa_submit_v0",
    source_operator_approval_ref: str = "operator_approval_receipt:capital_hilton_submit_coupa_exact_v0",
    exact_approval_phrase_ref: str = EXACT_APPROVAL_PHRASE_REF,
    submit_authority: bool = False,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> CoupaSubmitRequest:
    return CoupaSubmitRequest(
        request_id=request_id,
        source_coupa_package_ref="coupa_package_ref:capital_hilton_supplier_portal_package_v0",
        source_run_package_ref="invoice_delivery_run_package_ref:capital_hilton_v0",
        source_guardian_approval_ref=source_guardian_approval_ref,
        source_operator_approval_ref=source_operator_approval_ref,
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        coupa_po_ref=coupa_po_ref,
        invoice_value_refs=invoice_value_refs,
        invoice_artifact_refs=invoice_artifact_refs,
        protected_secret_refs=protected_secret_refs,
        provider_target=provider_target,
        exact_approval_phrase_ref=exact_approval_phrase_ref,
        submit_authority=submit_authority,
        requested_mode=requested_mode,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def build_gate_check(request: CoupaSubmitRequest, provider: CoupaProviderBoundary) -> CoupaSubmitGateCheck:
    po_confirmed = _po_confirmed(request.coupa_po_ref)
    values_confirmed = _invoice_values_confirmed(request.invoice_value_refs)
    artifact_present = _artifact_present(request.invoice_artifact_refs)
    artifact_hash = _artifact_hash_present(request.invoice_artifact_refs)
    secret_ref = _secret_ref_present(request.protected_secret_refs)
    guardian_approval = bool(request.source_guardian_approval_ref)
    operator_approval = bool(request.source_operator_approval_ref)
    exact_phrase = request.exact_approval_phrase_ref == EXACT_APPROVAL_PHRASE_REF
    browser_available = provider.provider_available
    provider_available = provider.provider_available

    missing: list[str] = []
    if not request.source_coupa_package_ref:
        missing.append("Coupa supplier portal package ref")
    if not request.source_run_package_ref:
        missing.append("invoice delivery run package ref")
    if not request.coupa_po_ref:
        missing.append("confirmed Coupa PO/reference")
    elif not po_confirmed:
        missing.append("confirmed Coupa PO/reference")
    if not request.invoice_value_refs:
        missing.append("confirmed invoice dates/rate/subtotal refs")
    elif not values_confirmed:
        missing.append("confirmed invoice dates/rate/subtotal refs")
    if not artifact_present:
        missing.append("invoice artifact refs")
    if artifact_present and not artifact_hash:
        missing.append("invoice artifact hash/fingerprint refs")
    if not secret_ref:
        missing.append("protected Coupa credential/secret ref")
    if not guardian_approval:
        missing.append("Guardian approval ref")
    if not operator_approval:
        missing.append("exact operator approval receipt ref")
    if not exact_phrase:
        missing.append("exact approval phrase ref")
    if request.requested_mode == "LIVE_SUBMIT_GATED_FUTURE":
        if not provider_available:
            missing.append("browser/Coupa provider adapter")
        if not request.submit_authority:
            missing.append("submit authority for exact package")
    if request.submit_authority and missing:
        missing.append("submit attempted before all gates")
    if _raw_secret_marker_visible(request):
        missing.append("raw credential removed from request")
    if _raw_po_visible(request):
        missing.append("raw PO/reference removed from request")

    return CoupaSubmitGateCheck(
        gate_check_id=_stable_id("coupa_submit_gate_check", request.request_id),
        submit_request_ref=request.request_id,
        po_confirmed=po_confirmed,
        invoice_values_confirmed=values_confirmed,
        invoice_artifact_present=artifact_present,
        invoice_artifact_hash_present=artifact_hash,
        secret_ref_present=secret_ref,
        guardian_approval_present=guardian_approval,
        operator_approval_present=operator_approval,
        exact_phrase_matched=exact_phrase,
        browser_adapter_available=browser_available,
        provider_adapter_available=provider_available,
        submit_authority_granted=request.submit_authority,
        missing_gates=tuple(dict.fromkeys(missing)),
        next_safe_move=(
            "Dry-run gates are satisfied; do not open browser or call provider."
            if not missing and request.requested_mode == "DRY_RUN_ONLY"
            else "Resolve missing gates; do not access Coupa or submit."
        ),
    )


def _readiness_status(request: CoupaSubmitRequest, gate: CoupaSubmitGateCheck) -> str:
    if request.provider_target not in PROVIDER_TARGETS or request.requested_mode not in REQUESTED_MODES:
        return "SUBMIT_BLOCKED_UNSUPPORTED_PROVIDER"
    if _raw_secret_marker_visible(request) or _raw_po_visible(request):
        return "SUBMIT_BLOCKED_PRIVACY_BOUNDARY"
    if "confirmed Coupa PO/reference" in gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_PO"
    if "confirmed invoice dates/rate/subtotal refs" in gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_VALUES"
    if "invoice artifact refs" in gate.missing_gates or "invoice artifact hash/fingerprint refs" in gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_ARTIFACT"
    if "protected Coupa credential/secret ref" in gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_SECRET_REF"
    if request.requested_mode == "LIVE_SUBMIT_GATED_FUTURE" and "browser/Coupa provider adapter" in gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_PROVIDER"
    if gate.missing_gates:
        return "SUBMIT_BLOCKED_MISSING_GATES"
    if request.requested_mode == "DRY_RUN_ONLY":
        return "SUBMIT_DRY_RUN_READY"
    if request.requested_mode in ("READINESS_CHECK_ONLY", "MANUAL_SUBMIT_HANDOFF", "LIVE_SUBMIT_GATED_FUTURE"):
        return "COUPA_ADAPTER_READY_BUT_NOT_EXECUTED"
    return "UNKNOWN_FAIL_CLOSED"


def build_readback(
    request: CoupaSubmitRequest,
    gate: CoupaSubmitGateCheck,
    provider: CoupaProviderBoundary,
) -> CoupaSubmitReadinessReadback:
    status = _readiness_status(request, gate)
    if status == "SUBMIT_DRY_RUN_READY":
        headline = "Capital Hilton Coupa submit dry-run ready"
        message = (
            "OpenClaw dry-ran the Capital Hilton Coupa submit package. All modeled proof, secret, and approval refs are present, "
            "but nothing was opened, submitted, or called."
        )
        fix = "Review the dry-run output. A future live Coupa/browser adapter still needs explicit approval and separate submit authority."
    elif status == "COUPA_ADAPTER_READY_BUT_NOT_EXECUTED":
        headline = "Coupa adapter ready but not executed"
        message = "The Coupa submit gates are modeled as satisfied, but this lane does not open a browser or submit."
        fix = "Use this as readiness proof only; future live submit requires a separately approved Coupa/browser adapter."
    elif status == "SUBMIT_BLOCKED_MISSING_PO":
        headline = "Coupa submit blocked: PO/reference missing"
        message = "OpenClaw cannot prepare Coupa submit readiness because the Coupa PO/reference is missing or unconfirmed."
        fix = "Provide, attach, or confirm the Coupa PO/reference as a protected/source ref, then rerun the submit readiness check."
    elif status == "SUBMIT_BLOCKED_MISSING_VALUES":
        headline = "Coupa submit blocked: invoice values missing"
        message = "Invoice dates/rate/subtotal refs are missing or not confirmed."
        fix = "Confirm the delivery dates, rate, and subtotal refs from receipts/readbacks before rerunning."
    elif status == "SUBMIT_BLOCKED_MISSING_ARTIFACT":
        headline = "Coupa submit blocked: invoice artifact proof missing"
        message = "The invoice artifact ref or hash/fingerprint proof is missing."
        fix = "Generate or verify the invoice artifact and attach its hash/fingerprint ref."
    elif status == "SUBMIT_BLOCKED_MISSING_SECRET_REF":
        headline = "Coupa submit blocked: protected secret ref missing"
        message = "A future Coupa portal login requires a protected credential ref, not a raw password in chat."
        fix = "Use a future Enter Secret protected flow to create a scoped secret_ref; do not paste credentials into chat."
    elif status == "SUBMIT_BLOCKED_MISSING_PROVIDER":
        headline = "Coupa submit blocked: provider missing"
        message = "The submit package has proof/approval shape, but no gated Coupa/browser adapter is connected."
        fix = "Connect a future gated Coupa/browser adapter after exact approvals, protected secret refs, and proof rails are complete."
    elif status == "SUBMIT_BLOCKED_PRIVACY_BOUNDARY":
        headline = "Coupa submit blocked: privacy boundary"
        message = "The submit request tried to include a raw credential or raw PO/reference marker."
        fix = "Use protected secret refs and tokenized/source PO refs only, then regenerate the submit check."
    elif status == "SUBMIT_BLOCKED_UNSUPPORTED_PROVIDER":
        headline = "Coupa submit blocked: unsupported provider"
        message = "The requested provider or mode is not supported by this adapter."
        fix = "Use MANUAL_COUPA_HANDOFF with DRY_RUN_ONLY, or add a future gated provider boundary."
    elif status == "SUBMIT_BLOCKED_MISSING_GATES":
        headline = "Coupa submit blocked: missing gates"
        message = "OpenClaw cannot submit because one or more required approval/proof gates are missing."
        if "Guardian approval ref" in gate.missing_gates or "exact operator approval receipt ref" in gate.missing_gates:
            fix = "Create the Guardian approval packet and exact operator approval receipt for this Coupa package, then rerun the readiness check."
        elif "exact approval phrase ref" in gate.missing_gates:
            fix = f"Use the exact approval phrase for this package: {EXACT_APPROVAL_DISPLAY}."
        else:
            fix = "Resolve the listed missing gates, then rerun the Coupa submit readiness check."
    else:
        headline = "Coupa submit adapter failed closed"
        message = "The Coupa submit adapter could not prove a safe readiness state."
        fix = "Regenerate with scoped package, confirmed PO, invoice values, artifact/hash, protected secret ref, Guardian approval, and exact operator approval refs."

    return CoupaSubmitReadinessReadback(
        readback_id=_stable_id("coupa_submit_readiness", request.request_id, status),
        submit_request_ref=request.request_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        ready_summary=(
            f"provider={provider.provider_target}; mode={request.requested_mode}; "
            f"po_confirmed={gate.po_confirmed}; values_confirmed={gate.invoice_values_confirmed}; "
            f"artifact_hash_present={gate.invoice_artifact_hash_present}; secret_ref_present={gate.secret_ref_present}; "
            f"exact_phrase_matched={gate.exact_phrase_matched}"
        ),
        missing_gates=gate.missing_gates,
        blocked_actions=BLOCKED_ACTIONS,
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_receipt(request: CoupaSubmitRequest) -> CoupaSubmitReceipt:
    proof_refs = tuple(
        ref
        for ref in (
            request.source_coupa_package_ref,
            request.source_run_package_ref,
            request.coupa_po_ref,
            *request.invoice_value_refs,
            *request.invoice_artifact_refs,
            *request.protected_secret_refs,
            request.source_guardian_approval_ref,
            request.source_operator_approval_ref,
            request.exact_approval_phrase_ref,
        )
        if ref
    )
    return CoupaSubmitReceipt(
        receipt_id=_stable_id("coupa_submit_receipt", request.request_id),
        submit_request_ref=request.request_id,
        provider_target=request.provider_target,
        coupa_po_ref=request.coupa_po_ref,
        invoice_value_refs=request.invoice_value_refs,
        invoice_artifact_refs=request.invoice_artifact_refs,
        submitted=False,
        provider_confirmation_ref="",
        submit_timestamp_policy="not_submitted_no_timestamp",
        proof_refs=proof_refs,
        external_authority=False,
        next_safe_move="Keep this receipt as not-submitted proof until a future gated live submit produces a Coupa confirmation receipt.",
    )


def build_blockers() -> tuple[CoupaSubmitAdapterBlocker, ...]:
    return (
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_generic_approval", "GENERIC_APPROVAL_USED", "Generic chat phrase is used for Coupa submit approval.", "critical", "Generic approval is blocked for Coupa submit.", True, "Use exact approval phrase bound to the package."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_exact_missing", "EXACT_APPROVAL_MISSING", "Exact approval phrase ref is missing or mismatched.", "critical", "Exact approval is missing.", True, f"Use {EXACT_APPROVAL_DISPLAY}."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_guardian_missing", "GUARDIAN_APPROVAL_MISSING", "Guardian approval ref is missing.", "critical", "Guardian approval is missing.", True, "Create Guardian approval packet."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_po_missing", "PO_REFERENCE_MISSING", "PO/reference ref is missing.", "critical", "Coupa PO/reference is missing.", True, "Provide or attach confirmed PO/reference ref."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_po_unconfirmed", "PO_REFERENCE_UNCONFIRMED", "PO/reference is only candidate or unconfirmed.", "critical", "Coupa PO/reference must be confirmed.", True, "Confirm PO/reference before submit readiness."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_values_missing", "INVOICE_VALUES_MISSING", "Invoice dates/rate/subtotal refs are missing.", "critical", "Invoice values are missing.", True, "Confirm invoice value refs."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_value_mismatch", "VALUE_MISMATCH", "Invoice value refs indicate a mismatch.", "critical", "Invoice value mismatch blocks submit.", True, "Resolve value mismatch from receipts/readbacks."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_artifact_missing", "ARTIFACT_REF_MISSING", "Invoice artifact ref is missing.", "high", "Invoice artifact ref is missing.", True, "Generate or attach invoice artifact ref."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_artifact_hash", "ARTIFACT_HASH_MISSING", "Artifact hash/fingerprint ref is missing.", "high", "Artifact hash/fingerprint is missing.", True, "Hash/fingerprint invoice artifact."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_secret", "SECRET_REF_MISSING", "Protected Coupa secret ref is missing.", "critical", "Protected secret ref is missing.", True, "Use protected secret intake later."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_provider", "PROVIDER_ADAPTER_MISSING", "No gated Coupa/browser adapter is connected.", "critical", "Provider adapter is missing.", True, "Connect a future gated Coupa/browser adapter."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_raw_credential", "RAW_CREDENTIAL_INCLUDED", "Raw credential marker appears in request.", "critical", "Raw credential is blocked.", True, "Use protected secret refs only."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_raw_po", "RAW_PO_EXPOSED", "Raw PO/reference marker appears in output.", "critical", "Raw PO/reference exposure is blocked.", True, "Use tokenized/source PO refs."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_browser_without_gates", "BROWSER_ATTEMPTED_WITHOUT_GATES", "Browser access requested before all gates are present.", "critical", "Browser attempt without gates is blocked.", True, "Clear browser authority and resolve missing gates."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_submit_without_gates", "SUBMIT_ATTEMPTED_WITHOUT_GATES", "Submit authority requested before all gates are present.", "critical", "Submit attempted without gates.", True, "Clear submit authority and resolve missing gates."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_provider_called_test", "PROVIDER_CALLED_IN_TEST", "Provider call occurs in test or fixture mode.", "critical", "Provider calls are blocked in tests.", True, "Use dry-run/readiness modeling only."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_external_action", "EXTERNAL_ACTION_ATTEMPTED", "Adapter attempts external action.", "critical", "External action is blocked.", True, "Return readiness/readback only."),
        CoupaSubmitAdapterBlocker("coupa_submit_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown Coupa submit adapter state.", "high", "Unknown state fails closed.", True, "Ask for scoped package and approval refs."),
    )


def _bundle(request: CoupaSubmitRequest) -> dict[str, Any]:
    provider = build_provider_boundary(request.provider_target)
    gate = build_gate_check(request, provider)
    readback = build_readback(request, gate, provider)
    receipt = build_receipt(request)
    return {
        "submit_request": asdict(request),
        "gate_check": asdict(gate),
        "provider_boundary": asdict(provider),
        "readiness_readback": asdict(readback),
        "submit_receipt": asdict(receipt),
    }


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    missing_po = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_missing_po_v0",
        requested_mode="READINESS_CHECK_ONLY",
        coupa_po_ref="",
        protected_secret_refs=(),
        source_guardian_approval_ref="",
        source_operator_approval_ref="",
        exact_approval_phrase_ref="",
        generated_at=generated_at,
    )
    missing_secret_ref_case = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_missing_secret_ref_v0",
        requested_mode="READINESS_CHECK_ONLY",
        protected_secret_refs=(),
        generated_at=generated_at,
    )
    missing_approval = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_missing_approval_v0",
        requested_mode="READINESS_CHECK_ONLY",
        source_guardian_approval_ref="",
        source_operator_approval_ref="",
        exact_approval_phrase_ref="",
        generated_at=generated_at,
    )
    dry_run_ready = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_dry_run_ready_v0",
        requested_mode="DRY_RUN_ONLY",
        generated_at=generated_at,
    )
    generic_submit_it = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_generic_submit_it_v0",
        requested_mode="READINESS_CHECK_ONLY",
        source_operator_approval_ref="operator_phrase_ref:submit_it_generic",
        exact_approval_phrase_ref="chat_phrase_ref:submit_it",
        generated_at=generated_at,
    )
    provider_missing = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_provider_missing_v0",
        provider_target="COUPA_BROWSER_ADAPTER",
        requested_mode="LIVE_SUBMIT_GATED_FUTURE",
        generated_at=generated_at,
    )
    raw_credential_marker_case = build_capital_hilton_request(
        request_id="coupa_submit_request_capital_hilton_raw_credential_blocked_v0",
        requested_mode="READINESS_CHECK_ONLY",
        protected_secret_refs=("raw_credential_ref:blocked_fixture_marker",),
        generated_at=generated_at,
    )
    return {
        "capital_hilton_submit_blocked_missing_po": _bundle(missing_po),
        "capital_hilton_submit_blocked_missing_secret_ref": _bundle(missing_secret_ref_case),
        "capital_hilton_submit_blocked_missing_approval": _bundle(missing_approval),
        "capital_hilton_dry_run_ready_not_executed": _bundle(dry_run_ready),
        "generic_submit_it_blocked": _bundle(generic_submit_it),
        "provider_missing": _bundle(provider_missing),
        "raw_credential_blocked": _bundle(raw_credential_marker_case),
    }


def build_payload(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    adapter = build_adapter()
    examples = build_examples(generated_at=generated_at)
    blockers = build_blockers()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "provider_targets": PROVIDER_TARGETS,
        "requested_modes": REQUESTED_MODES,
        "readiness_statuses": READINESS_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "required_submit_proofs": REQUIRED_SUBMIT_PROOFS,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "adapter": asdict(adapter),
        "coupa_submit_adapter_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "coupa_provider_static_audit": {
            "repo_b_coupa_or_browser_adapter_found": False,
            "repo_a_future_candidate_ref": "capital_hilton_coupa_po_retrieval_automation_candidate",
            "identified_submit_method_ref": "none_currently_connected",
            "called": False,
            "browser_opened": False,
            "reason": "Static candidate exists for future protected portal automation, but no approved submit provider is connected.",
        },
        "capital_hilton_expected_operator_readback": (
            "OpenClaw checked the Capital Hilton Coupa submit package. Nothing was opened, submitted, logged in, or called. "
            "If gates are missing, the readback lists exactly what to fix before any future Coupa/browser adapter can act."
        ),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "provider_call_performed": False,
            "browser_open_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "portal_login_performed": False,
            "secret_reveal_performed": False,
            "payment_action_performed": False,
            "external_action_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "credential_handling_performed": False,
            "raw_credential_included": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw now has a gated Coupa submit readiness rail. It can prove why a submit is blocked or dry-run ready, "
            "but it does not open Coupa, open a browser, reveal secrets, or submit."
        ),
        "next_safe_move": "Use the dry-run output to resolve missing gates; build any live Coupa/browser adapter as a separate approved lane.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    missing_po = payload["examples"]["capital_hilton_submit_blocked_missing_po"]["readiness_readback"]
    dry_run = payload["examples"]["capital_hilton_dry_run_ready_not_executed"]["readiness_readback"]
    provider = payload["examples"]["provider_missing"]["readiness_readback"]
    lines = [
        "# Gated Coupa Submit Adapter",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton",
        f"- Missing PO status: {missing_po['status']}",
        f"- Missing PO fix: {missing_po['how_to_fix']}",
        f"- Dry-run status: {dry_run['status']}",
        f"- Dry-run message: {dry_run['operator_message']}",
        f"- Provider missing status: {provider['status']}",
        f"- Provider missing fix: {provider['how_to_fix']}",
        "",
        "## Blockers",
    ]
    for blocker in payload["coupa_submit_adapter_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No Coupa access, no Coupa submit, no browser, no portal login, no provider call, no secret reveal, no payment action, no external action, no workflow run, no agent dispatch, no credential handling, no raw credential, no raw-body ingestion.",
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
    dry_run = payload["examples"]["capital_hilton_dry_run_ready_not_executed"]["readiness_readback"]
    missing_po = payload["examples"]["capital_hilton_submit_blocked_missing_po"]["readiness_readback"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "dry_run_status": dry_run["status"],
        "missing_po_status": missing_po["status"],
        "blocker_count": len(payload["coupa_submit_adapter_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    fixture: str = "capital_hilton_dry_run",
    generated_at: str = DEFAULT_GENERATED_AT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    format_name: str = "summary",
) -> dict[str, Any]:
    if fixture != "capital_hilton_dry_run":
        raise ValueError("Only capital_hilton_dry_run fixture is supported in v0")
    payload = build_payload(generated_at=generated_at)
    write_exports(payload, export_root)
    return payload if format_name == "json" else _summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run/export gated Coupa submit adapter.")
    parser.add_argument("--fixture", choices=("capital_hilton_dry_run",), default="capital_hilton_dry_run")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        fixture=args.fixture,
        generated_at=args.generated_at,
        export_root=Path(args.export_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
