"""Gated Email Send Adapter v0.

This deterministic rail models the approval-bound email send boundary for
OpenClaw. It checks package, draft, recipient, attachment, Guardian, exact
operator approval, provider, and authority gates, then returns readiness or a
human blocked reason.

It does not send email, call Gmail/Mail/SMTP providers, send attachments, access
Coupa/browser/payment systems, execute approvals, run workflows, dispatch
agents, handle credentials, ingest raw bodies, mutate Mission Control Swift,
run Mac sync/import, or push.
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

SCHEMA_VERSION = "gated_email_send_adapter_v0"
READ_MODEL_ID = "gated_email_send_adapter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_APPROVAL_BOUND_EMAIL_SEND_RAIL_NO_SEND"

EXACT_APPROVAL_PHRASE_REF = "approval_phrase_ref:APPROVE_SEND_EMAIL_capital_hilton_invoice_v0"
EXACT_APPROVAL_DISPLAY = "APPROVE SEND_EMAIL capital_hilton_invoice_v0"

PROVIDER_TARGETS = (
    "GMAIL_SEND",
    "APPLE_MAIL_SEND",
    "SMTP_SEND_FUTURE",
    "MANUAL_SEND_HANDOFF",
    "UNKNOWN_FAIL_CLOSED",
)

REQUESTED_MODES = (
    "DRY_RUN_ONLY",
    "READINESS_CHECK_ONLY",
    "LIVE_SEND_GATED_FUTURE",
    "MANUAL_SEND_HANDOFF",
    "UNKNOWN_FAIL_CLOSED",
)

READINESS_STATUSES = (
    "SEND_ADAPTER_READY_BUT_NOT_EXECUTED",
    "SEND_BLOCKED_MISSING_GATES",
    "SEND_BLOCKED_MISSING_PROVIDER",
    "SEND_BLOCKED_MISSING_CREDENTIAL_REF",
    "SEND_BLOCKED_PRIVACY_BOUNDARY",
    "SEND_BLOCKED_UNSUPPORTED_PROVIDER",
    "SEND_DRY_RUN_READY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "GENERIC_APPROVAL_USED",
    "EXACT_APPROVAL_MISSING",
    "GUARDIAN_APPROVAL_MISSING",
    "RECIPIENT_UNCONFIRMED",
    "DRAFT_NOT_REVIEWED",
    "ATTACHMENT_REF_MISSING",
    "ATTACHMENT_HASH_MISSING",
    "PROVIDER_ADAPTER_MISSING",
    "CREDENTIAL_REF_MISSING",
    "RAW_EMAIL_ADDRESS_EXPOSED",
    "RAW_ATTACHMENT_BODY_INCLUDED",
    "SEND_ATTEMPTED_WITHOUT_GATES",
    "SEND_PROVIDER_CALLED_IN_TEST",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_email_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_smtp_send_allowed": False,
    "live_attachment_send_allowed": False,
    "live_provider_call_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_coupa_access_allowed": False,
    "live_browser_allowed": False,
    "live_approval_execution_allowed": False,
    "live_payment_action_allowed": False,
    "live_secret_reveal_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "email send",
    "Gmail send",
    "Mail send",
    "SMTP send",
    "provider send call",
    "attachment send",
    "external action",
    "workflow run",
    "agent dispatch",
    "credential handling",
    "raw attachment body",
)

REQUIRED_SEND_PROOFS = (
    "valid email delivery package ref",
    "reviewed draft ref",
    "confirmed recipient/contact ref",
    "attachment ref",
    "attachment hash/fingerprint ref",
    "Guardian approval ref",
    "exact operator approval receipt ref",
    "exact approval phrase matched to package",
    "provider adapter available for selected mode",
    "send authority granted for live send mode",
)


@dataclass(frozen=True)
class GatedEmailSendAdapter:
    adapter_id: str
    doctrine: tuple[str, ...]
    source_package_policy: tuple[str, ...]
    draft_policy: tuple[str, ...]
    recipient_policy: tuple[str, ...]
    attachment_policy: tuple[str, ...]
    guardian_policy: tuple[str, ...]
    operator_approval_policy: tuple[str, ...]
    provider_policy: tuple[str, ...]
    send_receipt_policy: tuple[str, ...]
    fail_closed_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendRequest:
    request_id: str
    source_email_delivery_package_ref: str
    source_draft_ref: str
    source_guardian_approval_ref: str
    source_operator_approval_ref: str
    client_ref: str
    tenant_ref: str
    provider_target: str
    recipient_refs: tuple[str, ...]
    subject_ref: str
    body_ref: str
    attachment_refs: tuple[str, ...]
    exact_approval_phrase_ref: str
    send_authority: bool
    requested_mode: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class EmailSendGateCheck:
    gate_check_id: str
    send_request_ref: str
    recipient_confirmed: bool
    draft_reviewed: bool
    attachment_refs_valid: bool
    attachment_hashes_present: bool
    guardian_approval_present: bool
    operator_approval_present: bool
    exact_phrase_matched: bool
    provider_adapter_available: bool
    credential_ref_available: bool
    send_authority_granted: bool
    missing_gates: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendProviderBoundary:
    provider_boundary_id: str
    provider_target: str
    provider_available: bool
    provider_send_method_ref: str
    credential_policy: str
    live_send_allowed: bool
    dry_run_available: bool
    blocked_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendReadinessReadback:
    readback_id: str
    send_request_ref: str
    status: str
    operator_headline: str
    operator_message: str
    ready_summary: str
    missing_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendReceipt:
    receipt_id: str
    send_request_ref: str
    provider_target: str
    recipient_refs: tuple[str, ...]
    attachment_refs: tuple[str, ...]
    sent: bool
    provider_message_id_ref: str
    send_timestamp_policy: str
    proof_refs: tuple[str, ...]
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendAdapterBlocker:
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


def _raw_email_visible(value: Any) -> bool:
    if is_dataclass(value):
        value = asdict(value)
    text = stable_json(value) if not isinstance(value, str) else value
    return bool(re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text))


def _raw_attachment_marker(value: Any) -> bool:
    if is_dataclass(value):
        value = asdict(value)
    text = stable_json(value).lower() if not isinstance(value, str) else value.lower()
    markers = ("raw_attachment_body", "attachment_body_raw", "file_body_raw", "attachment bytes")
    return any(marker in text for marker in markers)


def _is_confirmed_ref(refs: tuple[str, ...]) -> bool:
    return any("confirmed" in ref.lower() for ref in refs) and not any("candidate" in ref.lower() for ref in refs)


def _has_attachment_ref(refs: tuple[str, ...]) -> bool:
    return any(ref.startswith(("attachment_ref:", "email_attachment_ref:")) for ref in refs)


def _has_attachment_hash(refs: tuple[str, ...]) -> bool:
    return any(ref.startswith("artifact_hash_ref:") or "hash_ref:" in ref for ref in refs)


def build_adapter() -> GatedEmailSendAdapter:
    return GatedEmailSendAdapter(
        adapter_id="gated_email_send_adapter_v0",
        doctrine=(
            "No email send without every package, proof, approval, provider, and authority gate.",
            "Default and fixture modes never call providers.",
            "Generic chat approval is not enough for high-consequence send.",
            "Missing gates produce a human blocked reason and how_to_fix.",
            "Any future completion claim requires a send receipt.",
        ),
        source_package_policy=(
            "Email delivery package ref must identify the exact package under review.",
            "Package truth comes from delivery compiler/readbacks, not chat phrases.",
            "Missing package refs block send readiness.",
        ),
        draft_policy=(
            "Draft must be reviewed and referenced by ref.",
            "Draft body refs are allowed; raw external thread dumps are not.",
            "Unreviewed or missing draft refs block send readiness.",
        ),
        recipient_policy=(
            "Recipient must be confirmed by safe/contact refs.",
            "Candidate recipients block live send readiness.",
            "Raw private email addresses are blocked from generated output.",
        ),
        attachment_policy=(
            "Attachments are refs only.",
            "Each attachment package requires hash/fingerprint proof.",
            "Raw attachment bodies or file bytes block the rail.",
        ),
        guardian_policy=(
            "Guardian approval ref is required for send readiness.",
            "Approval execution does not happen here.",
            "Missing Guardian review blocks the rail.",
        ),
        operator_approval_policy=(
            "Exact approval receipt must bind to this package/covenant.",
            f"Expected phrase ref is {EXACT_APPROVAL_PHRASE_REF}.",
            "Generic phrases such as send it, yes, go ahead, or looks good are blocked.",
        ),
        provider_policy=(
            "Provider methods may be named as static boundaries but are not called.",
            "Repo B google.gmail.send is Class C and remains future-gated.",
            "No provider call is allowed in default, fixture, or test mode.",
        ),
        send_receipt_policy=(
            "Send receipt is modeled with sent=false in this lane.",
            "Provider message id is absent unless a future gated live send occurs.",
            "Final completion cannot be claimed without receipt refs.",
        ),
        fail_closed_policy=(
            "Unknown provider, unknown mode, raw body marker, generic approval, or missing gate fails closed.",
            "Blocked output must include how_to_fix.",
            "Tests must prove no provider call and sent=false.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use DRY_RUN_ONLY or READINESS_CHECK_ONLY until a future provider adapter is explicitly gated.",
    )


def build_provider_boundary(provider_target: str) -> EmailSendProviderBoundary:
    if provider_target == "MANUAL_SEND_HANDOFF":
        return EmailSendProviderBoundary(
            provider_boundary_id="email_send_provider_manual_handoff_v0",
            provider_target=provider_target,
            provider_available=True,
            provider_send_method_ref="manual_review_handoff_boundary:no_provider_call",
            credential_policy="No provider credentials are used for dry-run/manual readiness modeling.",
            live_send_allowed=False,
            dry_run_available=True,
            blocked_reason="Manual handoff can be modeled for readiness only; it does not send.",
            next_safe_move="Keep as dry-run/readiness output until a future send adapter is approved.",
        )
    if provider_target == "GMAIL_SEND":
        return EmailSendProviderBoundary(
            provider_boundary_id="email_send_provider_gmail_future_v0",
            provider_target=provider_target,
            provider_available=False,
            provider_send_method_ref="repo_b_google_access_broker:_exec_gmail_send/google.gmail.send_static_reference_only",
            credential_policy="Protected provider credential refs would be required later; values are never handled here.",
            live_send_allowed=False,
            dry_run_available=True,
            blocked_reason="Gmail send provider exists only as a future gated boundary and is not connected in this lane.",
            next_safe_move="Build a separately approved provider adapter after exact approvals and proof rails are complete.",
        )
    if provider_target == "APPLE_MAIL_SEND":
        return EmailSendProviderBoundary(
            provider_boundary_id="email_send_provider_apple_mail_future_v0",
            provider_target=provider_target,
            provider_available=False,
            provider_send_method_ref="apple_mail_send_adapter_future:not_connected",
            credential_policy="No Mail account access or credentials are used.",
            live_send_allowed=False,
            dry_run_available=True,
            blocked_reason="Apple Mail send provider is not connected.",
            next_safe_move="Use dry-run/readiness output; build a future gated adapter only with explicit approval.",
        )
    if provider_target == "SMTP_SEND_FUTURE":
        return EmailSendProviderBoundary(
            provider_boundary_id="email_send_provider_smtp_future_v0",
            provider_target=provider_target,
            provider_available=False,
            provider_send_method_ref="smtp_send_adapter_future:not_connected",
            credential_policy="No SMTP credentials are accepted or inspected.",
            live_send_allowed=False,
            dry_run_available=True,
            blocked_reason="SMTP provider is future-only.",
            next_safe_move="Keep send blocked until a provider adapter is approved.",
        )
    return EmailSendProviderBoundary(
        provider_boundary_id="email_send_provider_unknown_fail_closed_v0",
        provider_target=provider_target,
        provider_available=False,
        provider_send_method_ref="unknown",
        credential_policy="Unknown provider receives no credential handling.",
        live_send_allowed=False,
        dry_run_available=False,
        blocked_reason="Unsupported provider target.",
        next_safe_move="Select MANUAL_SEND_HANDOFF for dry-run readiness or build a future gated provider.",
    )


def build_capital_hilton_request(
    *,
    request_id: str = "email_send_request_capital_hilton_dry_run_v0",
    provider_target: str = "MANUAL_SEND_HANDOFF",
    requested_mode: str = "DRY_RUN_ONLY",
    recipient_refs: tuple[str, ...] = ("recipient_ref:annette_capital_hilton_confirmed",),
    source_guardian_approval_ref: str = "guardian_approval_capital_hilton_email_v0",
    source_operator_approval_ref: str = "operator_approval_receipt:capital_hilton_send_email_exact_v0",
    exact_approval_phrase_ref: str = EXACT_APPROVAL_PHRASE_REF,
    attachment_refs: tuple[str, ...] = (
        "email_attachment_ref:capital_hilton_pdf_2026-05-25",
        "artifact_hash_ref:capital_hilton_invoice_pdf_v0",
    ),
    send_authority: bool = False,
    source_draft_ref: str = "email_draft_ref:capital_hilton_local_eml_file_v0",
    subject_ref: str = "email_subject_ref:capital_hilton_invoice_followup_v0",
    body_ref: str = "email_body_ref:capital_hilton_invoice_followup_reviewed_v0",
    generated_at: str = DEFAULT_GENERATED_AT,
) -> EmailSendRequest:
    return EmailSendRequest(
        request_id=request_id,
        source_email_delivery_package_ref="email_delivery_package_capital_hilton_ready_for_review_v0",
        source_draft_ref=source_draft_ref,
        source_guardian_approval_ref=source_guardian_approval_ref,
        source_operator_approval_ref=source_operator_approval_ref,
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        provider_target=provider_target,
        recipient_refs=recipient_refs,
        subject_ref=subject_ref,
        body_ref=body_ref,
        attachment_refs=attachment_refs,
        exact_approval_phrase_ref=exact_approval_phrase_ref,
        send_authority=send_authority,
        requested_mode=requested_mode,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def build_gate_check(request: EmailSendRequest, provider: EmailSendProviderBoundary) -> EmailSendGateCheck:
    recipient_confirmed = _is_confirmed_ref(request.recipient_refs)
    draft_reviewed = bool(request.source_draft_ref and request.body_ref and "unreviewed" not in request.source_draft_ref.lower())
    attachment_refs_valid = _has_attachment_ref(request.attachment_refs) and not _raw_attachment_marker(request.attachment_refs)
    attachment_hashes_present = _has_attachment_hash(request.attachment_refs)
    guardian_approval_present = bool(request.source_guardian_approval_ref)
    operator_approval_present = bool(request.source_operator_approval_ref)
    exact_phrase_matched = request.exact_approval_phrase_ref == EXACT_APPROVAL_PHRASE_REF
    provider_adapter_available = provider.provider_available
    live_provider_target = request.requested_mode == "LIVE_SEND_GATED_FUTURE"
    credential_ref_available = not live_provider_target or request.provider_target == "MANUAL_SEND_HANDOFF"
    send_authority_granted = request.send_authority

    missing: list[str] = []
    if not request.source_email_delivery_package_ref:
        missing.append("email delivery package ref")
    if not recipient_confirmed:
        missing.append("confirmed recipient/contact ref")
    if not draft_reviewed:
        missing.append("reviewed draft ref")
    if not _has_attachment_ref(request.attachment_refs):
        missing.append("attachment ref")
    if _has_attachment_ref(request.attachment_refs) and not attachment_hashes_present:
        missing.append("attachment hash/fingerprint ref")
    if not guardian_approval_present:
        missing.append("Guardian approval ref")
    if not operator_approval_present:
        missing.append("exact operator approval receipt ref")
    if not exact_phrase_matched:
        missing.append("exact approval phrase ref")
    if request.requested_mode == "LIVE_SEND_GATED_FUTURE":
        if not provider_adapter_available:
            missing.append("provider adapter")
        if not credential_ref_available:
            missing.append("protected provider credential ref")
        if not send_authority_granted:
            missing.append("send authority for exact package")
    if request.send_authority and missing:
        missing.append("send attempted before all gates")
    if _raw_email_visible(request):
        missing.append("raw email address removed from request")
    if _raw_attachment_marker(request):
        missing.append("raw attachment body removed from request")
    return EmailSendGateCheck(
        gate_check_id=_stable_id("email_send_gate_check", request.request_id),
        send_request_ref=request.request_id,
        recipient_confirmed=recipient_confirmed,
        draft_reviewed=draft_reviewed,
        attachment_refs_valid=attachment_refs_valid,
        attachment_hashes_present=attachment_hashes_present,
        guardian_approval_present=guardian_approval_present,
        operator_approval_present=operator_approval_present,
        exact_phrase_matched=exact_phrase_matched,
        provider_adapter_available=provider_adapter_available,
        credential_ref_available=credential_ref_available,
        send_authority_granted=send_authority_granted,
        missing_gates=tuple(dict.fromkeys(missing)),
        next_safe_move=(
            "Dry-run gates are satisfied; do not call provider."
            if not missing and request.requested_mode == "DRY_RUN_ONLY"
            else "Resolve missing gates; do not send."
        ),
    )


def _readiness_status(request: EmailSendRequest, gate: EmailSendGateCheck, provider: EmailSendProviderBoundary) -> str:
    if request.provider_target not in PROVIDER_TARGETS or request.requested_mode not in REQUESTED_MODES:
        return "SEND_BLOCKED_UNSUPPORTED_PROVIDER"
    if _raw_email_visible(request) or _raw_attachment_marker(request):
        return "SEND_BLOCKED_PRIVACY_BOUNDARY"
    provider_missing_only = (
        request.requested_mode == "LIVE_SEND_GATED_FUTURE"
        and not gate.provider_adapter_available
        and gate.missing_gates == ("provider adapter",)
    )
    if provider_missing_only:
        return "SEND_BLOCKED_MISSING_PROVIDER"
    if request.requested_mode == "LIVE_SEND_GATED_FUTURE" and "protected provider credential ref" in gate.missing_gates and len(gate.missing_gates) == 1:
        return "SEND_BLOCKED_MISSING_CREDENTIAL_REF"
    if gate.missing_gates:
        if request.requested_mode == "LIVE_SEND_GATED_FUTURE" and "provider adapter" in gate.missing_gates and all(
            item in ("provider adapter", "protected provider credential ref", "send authority for exact package")
            for item in gate.missing_gates
        ):
            return "SEND_BLOCKED_MISSING_PROVIDER"
        return "SEND_BLOCKED_MISSING_GATES"
    if request.requested_mode == "DRY_RUN_ONLY":
        return "SEND_DRY_RUN_READY"
    if request.requested_mode == "READINESS_CHECK_ONLY":
        return "SEND_ADAPTER_READY_BUT_NOT_EXECUTED"
    if request.requested_mode == "LIVE_SEND_GATED_FUTURE":
        return "SEND_ADAPTER_READY_BUT_NOT_EXECUTED"
    if request.requested_mode == "MANUAL_SEND_HANDOFF":
        return "SEND_ADAPTER_READY_BUT_NOT_EXECUTED"
    return "UNKNOWN_FAIL_CLOSED"


def build_readback(
    request: EmailSendRequest,
    gate: EmailSendGateCheck,
    provider: EmailSendProviderBoundary,
) -> EmailSendReadinessReadback:
    status = _readiness_status(request, gate, provider)
    if status == "SEND_DRY_RUN_READY":
        headline = "Capital Hilton send dry-run ready"
        message = (
            "OpenClaw dry-ran the Capital Hilton email send package. All modeled approval and proof refs are present, "
            "but nothing was sent and no provider was called."
        )
        fix = "Review the dry-run output. A future live provider adapter still needs explicit approval and separate send authority."
    elif status == "SEND_ADAPTER_READY_BUT_NOT_EXECUTED":
        headline = "Send adapter ready but not executed"
        message = "The send package gates are modeled as satisfied, but this lane does not execute provider sends."
        fix = "Use this as readiness proof only; future live send requires a separately approved provider adapter."
    elif status == "SEND_BLOCKED_MISSING_PROVIDER":
        headline = "Send blocked: provider missing"
        message = "The send package has proof/approval shape, but no gated live provider adapter is connected."
        fix = "Connect a future gated provider adapter after exact approvals and proof rails are complete."
    elif status == "SEND_BLOCKED_MISSING_CREDENTIAL_REF":
        headline = "Send blocked: provider credential ref missing"
        message = "A live provider send would need a protected provider credential ref."
        fix = "Use a protected secret/ref flow later; do not paste credentials into chat."
    elif status == "SEND_BLOCKED_PRIVACY_BOUNDARY":
        headline = "Send blocked: privacy boundary"
        message = "The send request tried to include a raw email address or raw attachment body marker."
        fix = "Use tokenized recipient refs and attachment/hash refs only, then regenerate the send check."
    elif status == "SEND_BLOCKED_UNSUPPORTED_PROVIDER":
        headline = "Send blocked: unsupported provider"
        message = "The requested provider or mode is not supported by this adapter."
        fix = "Use MANUAL_SEND_HANDOFF with DRY_RUN_ONLY, or add a future gated provider boundary."
    elif status == "SEND_BLOCKED_MISSING_GATES":
        headline = "Send blocked: missing gates"
        message = "OpenClaw cannot send because one or more required approval/proof gates are missing."
        if "Guardian approval ref" in gate.missing_gates or "exact operator approval receipt ref" in gate.missing_gates:
            fix = "Create the Guardian approval packet and exact operator approval receipt for this package, then rerun the send readiness check."
        elif "attachment hash/fingerprint ref" in gate.missing_gates:
            fix = "Verify the invoice artifact and add its hash/fingerprint ref before rerunning the send check."
        elif "exact approval phrase ref" in gate.missing_gates:
            fix = f"Use the exact approval phrase for this package: {EXACT_APPROVAL_DISPLAY}."
        else:
            fix = "Resolve the listed missing gates, then rerun the send readiness check."
    else:
        headline = "Send adapter failed closed"
        message = "The send adapter could not prove a safe readiness state."
        fix = "Regenerate with scoped package, reviewed draft, confirmed recipient, attachment/hash, Guardian approval, and exact operator approval refs."

    return EmailSendReadinessReadback(
        readback_id=_stable_id("email_send_readiness", request.request_id, status),
        send_request_ref=request.request_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        ready_summary=(
            f"provider={provider.provider_target}; mode={request.requested_mode}; "
            f"recipient_confirmed={gate.recipient_confirmed}; draft_reviewed={gate.draft_reviewed}; "
            f"attachment_hashes_present={gate.attachment_hashes_present}; exact_phrase_matched={gate.exact_phrase_matched}"
        ),
        missing_gates=gate.missing_gates,
        blocked_actions=BLOCKED_ACTIONS,
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_receipt(request: EmailSendRequest) -> EmailSendReceipt:
    proof_refs = tuple(
        ref
        for ref in (
            request.source_email_delivery_package_ref,
            request.source_draft_ref,
            request.source_guardian_approval_ref,
            request.source_operator_approval_ref,
            request.exact_approval_phrase_ref,
            *request.attachment_refs,
        )
        if ref
    )
    return EmailSendReceipt(
        receipt_id=_stable_id("email_send_receipt", request.request_id),
        send_request_ref=request.request_id,
        provider_target=request.provider_target,
        recipient_refs=request.recipient_refs,
        attachment_refs=request.attachment_refs,
        sent=False,
        provider_message_id_ref="",
        send_timestamp_policy="not_sent_no_timestamp",
        proof_refs=proof_refs,
        external_authority=False,
        next_safe_move="Keep this receipt as not-sent proof until a future gated live send produces a provider receipt.",
    )


def build_blockers() -> tuple[EmailSendAdapterBlocker, ...]:
    return (
        EmailSendAdapterBlocker("email_send_blocker_generic_approval", "GENERIC_APPROVAL_USED", "Generic chat phrase is used for send approval.", "critical", "Generic approval is blocked for email send.", True, "Use exact approval phrase bound to the package."),
        EmailSendAdapterBlocker("email_send_blocker_exact_missing", "EXACT_APPROVAL_MISSING", "Exact approval phrase ref is missing or mismatched.", "critical", "Exact approval is missing.", True, f"Use {EXACT_APPROVAL_DISPLAY}."),
        EmailSendAdapterBlocker("email_send_blocker_guardian_missing", "GUARDIAN_APPROVAL_MISSING", "Guardian approval ref is missing.", "critical", "Guardian approval is missing.", True, "Create Guardian approval packet."),
        EmailSendAdapterBlocker("email_send_blocker_recipient", "RECIPIENT_UNCONFIRMED", "Recipient is missing or only candidate.", "critical", "Recipient must be confirmed.", True, "Confirm recipient/contact ref."),
        EmailSendAdapterBlocker("email_send_blocker_draft", "DRAFT_NOT_REVIEWED", "Reviewed draft ref is missing.", "critical", "Draft must be reviewed.", True, "Review or reference the draft artifact."),
        EmailSendAdapterBlocker("email_send_blocker_attachment", "ATTACHMENT_REF_MISSING", "Attachment ref is missing.", "high", "Attachment ref is missing.", True, "Attach invoice artifact ref."),
        EmailSendAdapterBlocker("email_send_blocker_attachment_hash", "ATTACHMENT_HASH_MISSING", "Attachment hash/fingerprint ref is missing.", "high", "Attachment hash/fingerprint is missing.", True, "Hash/fingerprint the invoice artifact."),
        EmailSendAdapterBlocker("email_send_blocker_provider", "PROVIDER_ADAPTER_MISSING", "No gated provider send adapter is connected.", "critical", "Provider adapter is missing.", True, "Connect a future gated provider adapter."),
        EmailSendAdapterBlocker("email_send_blocker_provider_credential", "CREDENTIAL_REF_MISSING", "Protected provider credential ref is missing for live provider mode.", "critical", "Provider credential ref is missing.", True, "Use protected secret/ref flow later."),
        EmailSendAdapterBlocker("email_send_blocker_raw_email", "RAW_EMAIL_ADDRESS_EXPOSED", "Raw private email address appears in send request or output.", "critical", "Raw email address exposure is blocked.", True, "Use tokenized recipient refs."),
        EmailSendAdapterBlocker("email_send_blocker_raw_attachment", "RAW_ATTACHMENT_BODY_INCLUDED", "Raw attachment body marker appears in send request.", "critical", "Raw attachment body is blocked.", True, "Use attachment refs and hash refs only."),
        EmailSendAdapterBlocker("email_send_blocker_send_without_gates", "SEND_ATTEMPTED_WITHOUT_GATES", "Send authority requested before all gates are present.", "critical", "Send attempted without gates.", True, "Clear send authority and resolve missing gates."),
        EmailSendAdapterBlocker("email_send_blocker_provider_called_test", "SEND_PROVIDER_CALLED_IN_TEST", "Provider send call occurs in test or fixture mode.", "critical", "Provider calls are blocked in tests.", True, "Use dry-run/readiness modeling only."),
        EmailSendAdapterBlocker("email_send_blocker_external_action", "EXTERNAL_ACTION_ATTEMPTED", "Adapter attempts external action.", "critical", "External action is blocked.", True, "Return readiness/readback only."),
        EmailSendAdapterBlocker("email_send_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown send adapter state.", "high", "Unknown state fails closed.", True, "Ask for scoped package and approval refs."),
    )


def _bundle(request: EmailSendRequest) -> dict[str, Any]:
    provider = build_provider_boundary(request.provider_target)
    gate = build_gate_check(request, provider)
    readback = build_readback(request, gate, provider)
    receipt = build_receipt(request)
    return {
        "send_request": asdict(request),
        "gate_check": asdict(gate),
        "provider_boundary": asdict(provider),
        "readiness_readback": asdict(readback),
        "send_receipt": asdict(receipt),
    }


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    missing_approval = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_missing_approval_v0",
        requested_mode="READINESS_CHECK_ONLY",
        recipient_refs=("recipient_ref:annette_capital_hilton_candidate",),
        source_guardian_approval_ref="",
        source_operator_approval_ref="",
        exact_approval_phrase_ref="",
        generated_at=generated_at,
    )
    missing_hash = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_missing_attachment_hash_v0",
        requested_mode="READINESS_CHECK_ONLY",
        attachment_refs=("email_attachment_ref:capital_hilton_pdf_2026-05-25",),
        generated_at=generated_at,
    )
    dry_run_ready = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_dry_run_ready_v0",
        requested_mode="DRY_RUN_ONLY",
        generated_at=generated_at,
    )
    generic_send_it = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_generic_send_it_v0",
        requested_mode="READINESS_CHECK_ONLY",
        source_operator_approval_ref="operator_phrase_ref:send_it_generic",
        exact_approval_phrase_ref="chat_phrase_ref:send_it",
        generated_at=generated_at,
    )
    provider_missing = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_provider_missing_v0",
        provider_target="GMAIL_SEND",
        requested_mode="LIVE_SEND_GATED_FUTURE",
        generated_at=generated_at,
    )
    raw_attachment = build_capital_hilton_request(
        request_id="email_send_request_capital_hilton_raw_attachment_body_blocked_v0",
        requested_mode="READINESS_CHECK_ONLY",
        attachment_refs=("email_attachment_ref:capital_hilton_pdf_2026-05-25", "raw_attachment_body_ref:blocked_fixture_marker"),
        generated_at=generated_at,
    )
    return {
        "capital_hilton_send_blocked_missing_approval": _bundle(missing_approval),
        "capital_hilton_send_blocked_missing_attachment_hash": _bundle(missing_hash),
        "capital_hilton_dry_run_ready_not_executed": _bundle(dry_run_ready),
        "generic_send_it_blocked": _bundle(generic_send_it),
        "provider_missing": _bundle(provider_missing),
        "raw_attachment_body_blocked": _bundle(raw_attachment),
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
        "required_send_proofs": REQUIRED_SEND_PROOFS,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "adapter": asdict(adapter),
        "email_send_adapter_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "repo_b_provider_static_audit": {
            "repo_b_google_broker_path": "/home/openclaw_external/openclaw-runtime/google_access_broker.py",
            "repo_b_google_policy_path": "/home/openclaw_external/openclaw-runtime/google_access_policy.py",
            "identified_send_method_ref": "google_access_broker._exec_gmail_send/google.gmail.send",
            "policy_class": "CLASS_C",
            "called": False,
            "reason": "Static boundary identification only; provider calls are blocked in this lane.",
        },
        "capital_hilton_expected_operator_readback": (
            "OpenClaw checked the Capital Hilton email send package. Nothing was sent and no provider was called. "
            "If gates are missing, the readback lists exactly what to fix before any future send adapter can act."
        ),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "provider_send_call_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "mail_send_performed": False,
            "smtp_send_performed": False,
            "attachment_send_performed": False,
            "external_action_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "credential_handling_performed": False,
            "raw_attachment_body_included": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw now has a gated email send readiness rail. It can prove why a send is blocked or dry-run ready, "
            "but it does not send or call providers."
        ),
        "next_safe_move": "Use the dry-run output to resolve missing gates; build any live provider send adapter as a separate approved lane.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    missing_approval = payload["examples"]["capital_hilton_send_blocked_missing_approval"]["readiness_readback"]
    dry_run = payload["examples"]["capital_hilton_dry_run_ready_not_executed"]["readiness_readback"]
    provider = payload["examples"]["provider_missing"]["readiness_readback"]
    lines = [
        "# Gated Email Send Adapter",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton",
        f"- Missing approval status: {missing_approval['status']}",
        f"- Missing approval fix: {missing_approval['how_to_fix']}",
        f"- Dry-run status: {dry_run['status']}",
        f"- Dry-run message: {dry_run['operator_message']}",
        f"- Provider missing status: {provider['status']}",
        f"- Provider missing fix: {provider['how_to_fix']}",
        "",
        "## Blockers",
    ]
    for blocker in payload["email_send_adapter_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No email send, no Gmail send, no Mail send, no SMTP send, no provider send call, no attachment send, no external action, no workflow run, no agent dispatch, no credential handling, no raw attachment body, no raw-body ingestion.",
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
    missing_approval = payload["examples"]["capital_hilton_send_blocked_missing_approval"]["readiness_readback"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "dry_run_status": dry_run["status"],
        "missing_approval_status": missing_approval["status"],
        "blocker_count": len(payload["email_send_adapter_blockers"]),
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
    parser = argparse.ArgumentParser(description="Run/export gated email send adapter.")
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
