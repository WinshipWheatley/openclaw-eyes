"""Repo A bounded wrapper for Cassandra draft-only communications work.

This module turns a scoped, tokenized context package into a local candidate
communications draft and readback. Repo B Cassandra/Clara draft-adjacent files
were inspected, but v0 does not call them because the available general email
path is tied to live LLM/SMTP/approval notification behavior and the outreach
dry-run is a fixed intro flow, not a safe scoped draft callable.

It does not send email, create Gmail/Mail drafts, access Gmail or Mail, read raw
email bodies, read attachment bodies, handle credentials, start Repo B services,
dispatch agents, execute workflows, mutate Mission Control Swift, sync Mac, or
push.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
REPO_B_RUNTIME_DIR = Path("/home/openclaw_external/openclaw-runtime")
REPO_B_CASSANDRA_PATHS = (
    REPO_B_RUNTIME_DIR / "cassandra_brain.py",
    REPO_B_RUNTIME_DIR / "chief_email_brain.py",
    REPO_B_RUNTIME_DIR / "cassandra_outreach.py",
    REPO_B_RUNTIME_DIR / "cassandra_capability.py",
)

SCHEMA_VERSION = "cassandra_draft_worker_wrapper_v0"
READ_MODEL_ID = "cassandra_draft_worker_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DRAFT_ONLY_COMMUNICATIONS_WORKER_WRAPPER"

DRAFT_ONLY_FIXTURE_MODE = "CASSANDRA_DRAFT_ONLY_FIXTURE"
DRAFT_ONLY_SUBPROCESS_MODE = "CASSANDRA_DRAFT_ONLY_SUBPROCESS_NOT_USED"

DRAFT_TYPES = (
    "INVOICE_FOLLOWUP_EMAIL",
    "PAYMENT_STATUS_EMAIL",
    "CLIENT_UPDATE_EMAIL",
    "INTERNAL_NOTE",
    "GENERAL_DRAFT",
    "UNKNOWN_NEEDS_FRAMING",
)

READBACK_STATUSES = (
    "DRAFT_READY_FOR_REVIEW",
    "MISSING_INPUTS",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_NO_RECIPIENT",
    "BLOCKED_NO_CONTEXT",
    "CASSANDRA_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "SEND_ATTEMPTED",
    "LIVE_GMAIL_ACCESS_ATTEMPTED",
    "LIVE_MAIL_ACCESS_ATTEMPTED",
    "CREDENTIAL_INCLUDED",
    "RAW_SECRET_INCLUDED",
    "RAW_EMAIL_BODY_INCLUDED",
    "RAW_ATTACHMENT_BODY_INCLUDED",
    "RECIPIENT_NOT_CONFIRMED",
    "ATTACHMENT_REF_MISSING",
    "APPROVAL_GATE_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "draft_allowed": True,
    "live_gmail_access_allowed": False,
    "live_mail_access_allowed": False,
    "live_send_allowed": False,
    "live_draft_create_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "raw_email_body_ingestion_allowed": False,
    "raw_attachment_body_ingestion_allowed": False,
    "telegram_output_allowed": False,
    "workflow_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "external_action_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

LOCKED_ACTIONS = (
    "email_send",
    "live_gmail_access",
    "live_mail_access",
    "live_gmail_draft_create",
    "attachment_upload_or_send",
    "guardian_approval_execution",
    "coupa_access_or_submit",
)

SECRETISH_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|token|secret|password|passwd|pwd|oauth|cookie|session[_-]?id|"
    r"client[_-]?secret|bearer\s+[a-z0-9._-]+"
    r")\b"
)

RAW_EMAIL_BODY_KEYS = {"raw_email_body", "email_body_raw", "raw_inbox_body", "gmail_body"}
RAW_ATTACHMENT_BODY_KEYS = {
    "raw_attachment_body",
    "attachment_body",
    "file_body",
    "raw_file_body",
    "invoice_body_raw",
}
CREDENTIAL_KEYS = {
    "credential",
    "credentials",
    "password",
    "token",
    "api_key",
    "oauth_token",
    "cookie",
    "secret",
    "secret_value",
    "raw_secret",
}


@dataclass(frozen=True)
class CassandraDraftWorkerRequest:
    request_id: str
    source_chat_request_ref: str
    workflow_ref: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    communication_goal: str
    draft_type: str
    target_recipient_ref: str
    target_contact_status: str
    source_context_refs: tuple[str, ...]
    source_artifact_refs: tuple[str, ...]
    attachment_refs: tuple[str, ...]
    tone_profile: str
    required_points: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    send_authority: bool
    approval_required: bool
    privacy_class: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class CassandraDraftContextPackage:
    package_id: str
    request_ref: str
    included_context: tuple[str, ...]
    excluded_context: tuple[dict[str, str], ...]
    tokenized_contact_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    known_facts: tuple[str, ...]
    missing_items: tuple[str, ...]
    locked_actions: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    truth_boundary: str
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class CassandraDraftWorkerPolicy:
    policy_id: str
    draft_allowed: bool
    live_gmail_access_allowed: bool
    live_mail_access_allowed: bool
    live_send_allowed: bool
    live_draft_create_allowed: bool
    credential_handling_allowed: bool
    raw_body_ingestion_allowed: bool
    external_action_allowed: bool
    approval_required_before_send: bool
    next_safe_move: str


@dataclass(frozen=True)
class CassandraDraftCandidate:
    draft_id: str
    request_ref: str
    draft_subject: str
    draft_body: str
    recipient_display_ref: str
    attachment_display_refs: tuple[str, ...]
    missing_placeholders: tuple[str, ...]
    tone_notes: str
    truth_boundary_notice: str
    approval_boundary_notice: str
    send_blocked_notice: str
    next_safe_move: str


@dataclass(frozen=True)
class CassandraDraftReadback:
    readback_id: str
    request_ref: str
    status: str
    operator_headline: str
    operator_message: str
    draft_candidate_ref: str
    missing_inputs: tuple[str, ...]
    locked_actions: tuple[str, ...]
    approval_required: bool
    next_safe_move: str
    generated_at: str


@dataclass(frozen=True)
class CassandraDraftWorkerBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value)).strip("._")[:120] or "unknown"


def _blocker(blocker_type: str, condition: str, warning: str, *, severity: str = "high") -> CassandraDraftWorkerBlocker:
    return CassandraDraftWorkerBlocker(
        blocker_id=f"cassandra_draft_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=warning,
        fail_closed=True,
        next_safe_move="Remove live authority or provide tokenized refs/summaries only, then regenerate the draft readback.",
    )


def _text_has_secretish_value(value: Any) -> bool:
    if value is None:
        return False
    text = stable_json(value) if not isinstance(value, str) else value
    if SECRETISH_RE.search(text):
        return True
    if re.search(r"\b[A-Za-z0-9_\-]{24,}\b", text) and any(
        marker in text.lower() for marker in ("key", "token", "secret", "password")
    ):
        return True
    return False


def _find_forbidden_keys(value: Any, keys: set[str]) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in keys or any(key_text.endswith(f"_{marker}") for marker in keys):
                found.append(key_text)
            found.extend(_find_forbidden_keys(item, keys))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_find_forbidden_keys(item, keys))
    return tuple(sorted(set(found)))


def make_capital_hilton_fixture_request(*, generated_at: str | None = None) -> CassandraDraftWorkerRequest:
    generated_at = generated_at or utc_now()
    return CassandraDraftWorkerRequest(
        request_id="cassandra_draft_capital_hilton_invoice_followup_v0",
        source_chat_request_ref="mission_control_chat_capital_hilton_workflow_ref",
        workflow_ref="capital_hilton_invoice_delivery_workflow",
        world_ref="finance",
        lane_ref="capital_hilton",
        client_ref="capital_hilton",
        tenant_ref="openclaw_local",
        communication_goal=(
            "Prepare a candidate email to Annette with the Winship-branded Excel/PDF "
            "invoice attached by reference for local records and payment follow-up, while "
            "Coupa/PO remains the official payment rail."
        ),
        draft_type="INVOICE_FOLLOWUP_EMAIL",
        target_recipient_ref="contact_ref_annette_candidate_tokenized",
        target_contact_status="CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
        source_context_refs=(
            "generated/read_models/workflow_execution_package_compiler.json",
            "generated/read_models/google_broker_readonly_readback.json",
            "generated/read_models/cassandra_draft_review_packet.json",
        ),
        source_artifact_refs=(
            "artifact_ref_winship_invoice_excel_pdf_candidate",
            "source_ref_capital_hilton_invoice_workflow_readback",
        ),
        attachment_refs=("artifact_ref_winship_invoice_excel_pdf_candidate",),
        tone_profile="concise_professional_warm",
        required_points=(
            "Winship-branded invoice PDF is for local records and payment follow-up.",
            "Official payment rail remains Coupa supplier portal / PO process.",
            "Ask for anything else needed to keep payment moving.",
            "Do not claim send, submit, approval, or invoice generation happened.",
        ),
        missing_inputs=(
            "exact Coupa PO/reference if required before final send",
            "confirmed Annette contact route",
            "final invoice artifact/hash",
        ),
        send_authority=False,
        approval_required=True,
        privacy_class="private_tokenized_business_context",
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=generated_at,
    )


def build_context_package(request: CassandraDraftWorkerRequest) -> CassandraDraftContextPackage:
    return CassandraDraftContextPackage(
        package_id=f"cassandra_context_package_{_safe_id(request.request_id)}",
        request_ref=request.request_id,
        included_context=(
            "Capital Hilton invoice workflow draft is understood.",
            "Four-date / $400 basis is treated as workflow context, not final send proof.",
            "Winship-branded Excel/PDF invoice artifact is referenced by artifact ref only.",
            "Coupa supplier portal / PO process remains the official payment rail if context is confirmed.",
            "Recipient is an Annette candidate represented by a tokenized contact ref.",
        ),
        excluded_context=(
            {"item": "raw Gmail body", "reason": "raw email bodies are not allowed in draft context packages"},
            {"item": "raw attachment body", "reason": "attachments are refs only in v0"},
            {"item": "credentials or secrets", "reason": "Cassandra receives tokenized refs and safe summaries only"},
            {"item": "send authority", "reason": "future Guardian/operator approval and send adapter are required"},
        ),
        tokenized_contact_refs=(request.target_recipient_ref,),
        source_refs=request.source_context_refs,
        artifact_refs=request.source_artifact_refs,
        known_facts=(
            "Candidate recipient is Annette, pending confirmation.",
            "Email purpose is local records and payment follow-up.",
            "The official payment route remains Coupa/PO if verified by source context.",
            "The invoice attachment is represented by artifact ref only.",
        ),
        missing_items=request.missing_inputs,
        locked_actions=LOCKED_ACTIONS,
        forbidden_claims=(
            "email was sent",
            "Gmail draft was created",
            "Mail draft was created",
            "Coupa was accessed or submitted",
            "Guardian approved the send",
            "invoice artifact was generated in this lane",
        ),
        truth_boundary="Candidate draft only. Receipts/readbacks decide truth; this wrapper does not execute communication.",
        privacy_boundary="No raw credentials, secrets, email bodies, protected evidence bodies, or attachment bodies are included.",
        next_safe_move="Review the candidate draft, confirm recipient/artifact/PO details, then request Guardian approval before any future send.",
    )


def build_policy() -> CassandraDraftWorkerPolicy:
    return CassandraDraftWorkerPolicy(
        policy_id="cassandra_draft_worker_policy_v0",
        draft_allowed=True,
        live_gmail_access_allowed=False,
        live_mail_access_allowed=False,
        live_send_allowed=False,
        live_draft_create_allowed=False,
        credential_handling_allowed=False,
        raw_body_ingestion_allowed=False,
        external_action_allowed=False,
        approval_required_before_send=True,
        next_safe_move="Use this wrapper for review-only candidate drafts; use a separate governed adapter for any future send.",
    )


def validate_request(
    request: CassandraDraftWorkerRequest,
    context: CassandraDraftContextPackage,
    *,
    extra_payload: Mapping[str, Any] | None = None,
) -> tuple[str | None, tuple[CassandraDraftWorkerBlocker, ...]]:
    blockers: list[CassandraDraftWorkerBlocker] = []
    extra_payload = dict(extra_payload or {})
    probe = {"request": asdict(request), "context": asdict(context), "extra_payload": extra_payload}

    if request.draft_type not in DRAFT_TYPES or request.draft_type == "UNKNOWN_NEEDS_FRAMING":
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", request.draft_type, "Draft type needs framing before Cassandra can draft."))
    if request.send_authority:
        blockers.append(_blocker("SEND_ATTEMPTED", request.request_id, "Send authority was requested; Cassandra draft worker is draft-only."))
    if not request.approval_required and request.draft_type != "INTERNAL_NOTE":
        blockers.append(_blocker("APPROVAL_GATE_MISSING", request.request_id, "External communications require approval before send."))
    if request.authority_boundary.get("live_gmail_access_allowed") is True:
        blockers.append(_blocker("LIVE_GMAIL_ACCESS_ATTEMPTED", request.request_id, "Live Gmail access is blocked in this wrapper."))
    if request.authority_boundary.get("live_mail_access_allowed") is True:
        blockers.append(_blocker("LIVE_MAIL_ACCESS_ATTEMPTED", request.request_id, "Live Mail access is blocked in this wrapper."))
    if any(value is True for key, value in request.authority_boundary.items() if key != "draft_allowed"):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", request.request_id, "Request authority boundary enabled a live or external action."))
    if not request.target_recipient_ref:
        blockers.append(_blocker("RECIPIENT_NOT_CONFIRMED", request.request_id, "No tokenized recipient ref was provided."))
    if not context.included_context:
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", request.request_id, "No scoped context was provided for the draft."))
    if not request.attachment_refs and request.draft_type == "INVOICE_FOLLOWUP_EMAIL":
        blockers.append(_blocker("ATTACHMENT_REF_MISSING", request.request_id, "Invoice follow-up draft needs an attachment artifact ref."))

    credential_keys = _find_forbidden_keys(probe, CREDENTIAL_KEYS)
    if credential_keys:
        blockers.append(_blocker("CREDENTIAL_INCLUDED", ",".join(credential_keys), "Credential-like fields are not allowed in draft packages."))
    raw_email_keys = _find_forbidden_keys(probe, RAW_EMAIL_BODY_KEYS)
    if raw_email_keys:
        blockers.append(_blocker("RAW_EMAIL_BODY_INCLUDED", ",".join(raw_email_keys), "Raw email bodies are not allowed in draft packages."))
    raw_attachment_keys = _find_forbidden_keys(probe, RAW_ATTACHMENT_BODY_KEYS)
    if raw_attachment_keys:
        blockers.append(_blocker("RAW_ATTACHMENT_BODY_INCLUDED", ",".join(raw_attachment_keys), "Raw attachment bodies are not allowed in draft packages."))
    if _text_has_secretish_value(extra_payload):
        blockers.append(_blocker("RAW_SECRET_INCLUDED", request.request_id, "Secret-like text was found in the draft package."))

    if blockers:
        blocker_types = {blocker.blocker_type for blocker in blockers}
        if "RECIPIENT_NOT_CONFIRMED" in blocker_types:
            return "BLOCKED_NO_RECIPIENT", tuple(blockers)
        if "RAW_EMAIL_BODY_INCLUDED" in blocker_types or "RAW_ATTACHMENT_BODY_INCLUDED" in blocker_types or "RAW_SECRET_INCLUDED" in blocker_types or "CREDENTIAL_INCLUDED" in blocker_types:
            return "BLOCKED_PRIVACY_BOUNDARY", tuple(blockers)
        if "ATTACHMENT_REF_MISSING" in blocker_types:
            return "MISSING_INPUTS", tuple(blockers)
        return "UNKNOWN_FAIL_CLOSED", tuple(blockers)
    return None, ()


def build_candidate(request: CassandraDraftWorkerRequest, context: CassandraDraftContextPackage) -> CassandraDraftCandidate:
    missing = tuple(request.missing_inputs)
    if request.draft_type == "INVOICE_FOLLOWUP_EMAIL" and request.client_ref == "capital_hilton":
        subject = "Capital Hilton Invoice Follow-Up"
        body = (
            "Hi Annette,\n\n"
            "I'm sending over the Winship-branded invoice PDF for the recent Capital Hilton dates "
            "for your local records and payment follow-up. My understanding is that the official "
            "payment rail remains the Coupa supplier portal / PO process.\n\n"
            "Please let me know if you need anything else from me to keep the payment moving.\n\n"
            "Best,\n"
            "Winship"
        )
    else:
        subject = "Draft for Review"
        body = (
            "Hi,\n\n"
            f"I'm following up about {request.communication_goal}.\n\n"
            "Please let me know what else you need.\n\n"
            "Best,\n"
            "Winship"
        )

    return CassandraDraftCandidate(
        draft_id=f"cassandra_draft_candidate_{_safe_id(request.request_id)}",
        request_ref=request.request_id,
        draft_subject=subject,
        draft_body=body,
        recipient_display_ref=request.target_recipient_ref,
        attachment_display_refs=request.attachment_refs,
        missing_placeholders=missing,
        tone_notes=f"Tone profile: {request.tone_profile}; concise and professional.",
        truth_boundary_notice=context.truth_boundary,
        approval_boundary_notice="Guardian/operator approval is required before any external send.",
        send_blocked_notice="Nothing has been sent, submitted, uploaded, or drafted in Gmail/Mail.",
        next_safe_move=context.next_safe_move,
    )


def _operator_message_for_status(
    status: str,
    candidate: CassandraDraftCandidate | None,
    request: CassandraDraftWorkerRequest,
    blockers: tuple[CassandraDraftWorkerBlocker, ...],
) -> tuple[str, str, str]:
    if status == "DRAFT_READY_FOR_REVIEW" and candidate is not None:
        return (
            "Cassandra draft ready for review",
            "A candidate Capital Hilton follow-up email is ready. Nothing has been sent or created in Gmail/Mail.",
            "Review the wording, confirm Annette/contact route, confirm the invoice artifact/hash and PO/reference, then request Guardian approval before any future send.",
        )
    if status == "BLOCKED_NO_RECIPIENT":
        return (
            "Draft blocked: recipient missing",
            "Cassandra cannot draft this safely because no tokenized recipient reference was provided.",
            "Confirm the recipient through a protected contact ref, then regenerate the draft package.",
        )
    if status == "MISSING_INPUTS":
        return (
            "Draft needs more context",
            "Cassandra needs a scoped recipient and attachment/source reference before creating this draft.",
            "Provide the missing artifact/contact refs or keep the workflow in discovery.",
        )
    if status == "BLOCKED_PRIVACY_BOUNDARY":
        return (
            "Draft blocked: privacy boundary",
            "The draft package tried to include raw secrets, credentials, raw email bodies, or raw attachment bodies.",
            "Replace raw values with tokenized refs and safe summaries, then regenerate the draft package.",
        )
    if status == "CASSANDRA_UNAVAILABLE":
        return (
            "Cassandra runtime not used",
            "Repo B Cassandra does not expose a safe general draft-only callable for this scoped package yet.",
            "Use the deterministic Repo A fixture draft now, or add a no-send Cassandra draft function behind the same boundary later.",
        )
    warning = blockers[0].elioperator_warning if blockers else "The draft worker failed closed."
    return (
        "Draft failed closed",
        warning,
        "Keep this as review-only and regenerate after removing unsafe authority or missing context.",
    )


def build_readback(
    request: CassandraDraftWorkerRequest,
    *,
    context: CassandraDraftContextPackage | None = None,
    mode: str = DRAFT_ONLY_FIXTURE_MODE,
    generated_at: str | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or request.created_at or utc_now()
    context = context or build_context_package(request)
    policy = build_policy()
    status, blockers = validate_request(request, context, extra_payload=extra_payload)
    candidate: CassandraDraftCandidate | None = None
    if status is None:
        candidate = build_candidate(request, context)
        status = "DRAFT_READY_FOR_REVIEW"

    headline, operator_message, next_safe_move = _operator_message_for_status(status, candidate, request, blockers)
    readback = CassandraDraftReadback(
        readback_id=f"cassandra_draft_readback_{_safe_id(request.request_id)}",
        request_ref=request.request_id,
        status=status,
        operator_headline=headline,
        operator_message=operator_message,
        draft_candidate_ref=candidate.draft_id if candidate else "",
        missing_inputs=request.missing_inputs,
        locked_actions=LOCKED_ACTIONS,
        approval_required=request.approval_required,
        next_safe_move=next_safe_move,
        generated_at=generated_at,
    )
    repo_b_status = {
        "repo_b_cassandra_path": str(REPO_B_RUNTIME_DIR),
        "inspected_files": tuple(str(path) for path in REPO_B_CASSANDRA_PATHS),
        "safe_general_draft_callable_found": False,
        "reason_not_called": (
            "Repo B general email path is tied to live LLM/SMTP/approval notification behavior; "
            "outreach dry-run is fixed-purpose and not a scoped package draft callable."
        ),
        "subprocess_used": False,
        "timeout_ms": 5000,
        "env_flags_for_future_subprocess": {
            "OPENCLAW_CASSANDRA_MODE": "DRAFT_ONLY",
            "OPENCLAW_SEND_ALLOWED": "0",
            "OPENCLAW_GMAIL_ALLOWED": "0",
            "OPENCLAW_TELEGRAM_ALLOWED": "0",
            "OPENCLAW_EXTERNAL_ACTION_ALLOWED": "0",
        },
    }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "mode": mode,
        "supported_draft_types": DRAFT_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "repo_b_cassandra_status": repo_b_status,
        "request": asdict(request),
        "context_package": asdict(context),
        "policy": asdict(policy),
        "draft_candidate": asdict(candidate) if candidate else None,
        "readback": asdict(readback),
        "active_blockers": tuple(asdict(blocker) for blocker in blockers),
        "capital_hilton_example": {
            "recipient_ref": request.target_recipient_ref,
            "subject": candidate.draft_subject if candidate else "",
            "body_summary": "Concise Capital Hilton invoice follow-up draft; candidate text only.",
            "attachment_refs": request.attachment_refs,
            "missing": request.missing_inputs,
            "locked": LOCKED_ACTIONS,
            "approval_boundary": "Guardian/operator approval required before future send.",
        },
        "security_summary": {
            "credential_exposure": False,
            "raw_secret_exposure": False,
            "raw_email_body_exposure": False,
            "raw_attachment_body_exposure": False,
            "live_gmail_or_mail_access": False,
            "send_or_live_draft_create": False,
            "telegram_output": False,
            "external_actions": False,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "candidate_draft_generated": candidate is not None,
            "repo_b_cassandra_called": False,
            "fixture_or_local_deterministic_mode": mode == DRAFT_ONLY_FIXTURE_MODE,
            "email_sent": False,
            "gmail_or_mail_accessed": False,
            "gmail_or_mail_draft_created": False,
            "telegram_output_sent": False,
            "credentials_accessed": False,
            "raw_email_body_included": False,
            "raw_attachment_body_included": False,
            "workflow_execution_performed": False,
            "agent_dispatch_performed": False,
            "mac_sync_import_run": False,
            "mission_control_swift_changed": False,
            "git_push_pull_fetch_run": False,
            "all_external_authority_flags_false": all(
                value is False for key, value in AUTHORITY_BOUNDARY.items() if key != "draft_allowed"
            ),
        },
    }
    return payload


def build_from_fixture(fixture: str, *, generated_at: str | None = None) -> dict[str, Any]:
    if fixture != "capital_hilton":
        request = make_capital_hilton_fixture_request(generated_at=generated_at)
        context = build_context_package(request)
        payload = build_readback(request, context=context, generated_at=generated_at)
        payload["readback"]["status"] = "UNKNOWN_FAIL_CLOSED"
        payload["readback"]["operator_headline"] = "Draft fixture unavailable"
        payload["readback"]["operator_message"] = f"Fixture {fixture!r} is not supported in v0."
        payload["active_blockers"] = (
            asdict(_blocker("UNKNOWN_FAIL_CLOSED", fixture, "Only the Capital Hilton fixture is supported in v0.")),
        )
        return payload
    request = make_capital_hilton_fixture_request(generated_at=generated_at)
    return build_readback(request, generated_at=generated_at)


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload["readback"]
    candidate = payload.get("draft_candidate") or {}
    blockers = payload.get("active_blockers") or ()
    lines = [
        "# Cassandra Draft Worker Wrapper",
        "",
        f"Status: {readback['status']}",
        f"Mode: {payload['mode']}",
        f"Headline: {readback['operator_headline']}",
        "",
        readback["operator_message"],
        "",
        "Draft:",
    ]
    if candidate:
        lines.extend(
            [
                f"- Subject: {candidate['draft_subject']}",
                f"- Recipient ref: {candidate['recipient_display_ref']}",
                f"- Attachment refs: {', '.join(candidate['attachment_display_refs'])}",
                "- Body: candidate text is present in the JSON readback for review only.",
            ]
        )
    else:
        lines.append("- No candidate draft was produced.")
    lines.extend(
        [
            "",
            "Boundary:",
            "- No email was sent.",
            "- No live Gmail or Mail access happened.",
            "- No Gmail/Mail draft was created.",
            "- Attachments are refs only; no raw attachment body is included.",
            "- Guardian/operator approval is required before any future send.",
            "",
            "Missing before execution:",
        ]
    )
    missing = readback.get("missing_inputs") or ()
    lines.extend(f"- {item}" for item in missing)
    if blockers:
        lines.extend(["", "Blocked items:"])
        lines.extend(f"- {item['elioperator_warning']}" for item in blockers)
    lines.extend(["", f"Next safe move: {readback['next_safe_move']}", ""])
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    readback = payload["readback"]
    candidate = payload.get("draft_candidate") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "mode": payload["mode"],
        "status": readback["status"],
        "operator_headline": readback["operator_headline"],
        "operator_message": readback["operator_message"],
        "subject": candidate.get("draft_subject", ""),
        "recipient_ref": candidate.get("recipient_display_ref", ""),
        "attachment_refs": candidate.get("attachment_display_refs", ()),
        "missing_inputs": readback["missing_inputs"],
        "locked_actions": readback["locked_actions"],
        "approval_required": readback["approval_required"],
        "repo_b_cassandra_called": payload["machine_proof"]["repo_b_cassandra_called"],
        "next_safe_move": readback["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Cassandra draft worker wrapper.")
    parser.add_argument("--fixture", choices=("capital_hilton",), default="capital_hilton")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_from_fixture(args.fixture, generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
