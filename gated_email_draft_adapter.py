"""Gated Email Draft Adapter v0.

This deterministic adapter prepares reviewable email draft artifacts from
candidate draft/package refs. It can generate a bounded local .eml review file
for operator review. It does not send email, create live Gmail/Mail drafts,
access Gmail/Mail/Coupa/browser/payment systems, execute approvals, run
workflows, dispatch agents, handle credentials, ingest raw bodies, mutate
Mission Control Swift, run Mac sync/import, or push.
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
DEFAULT_ARTIFACT_ROOT = Path("generated/email_drafts/gated_email_draft_adapter_v0")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"
DEFAULT_RECORD_DATE = "2026-05-25"

SCHEMA_VERSION = "gated_email_draft_adapter_v0"
READ_MODEL_ID = "gated_email_draft_adapter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_GATED_EMAIL_DRAFT_ADAPTER_NO_SEND"

PROVIDER_TARGETS = (
    "GMAIL_DRAFT",
    "APPLE_MAIL_DRAFT",
    "LOCAL_EML_FILE",
    "METADATA_ONLY_DRAFT",
    "UNKNOWN_FAIL_CLOSED",
)

REQUESTED_MODES = (
    "METADATA_ONLY",
    "LOCAL_EML_FILE",
    "LIVE_GMAIL_DRAFT_GATED",
    "LIVE_APPLE_MAIL_DRAFT_GATED",
    "UNKNOWN_FAIL_CLOSED",
)

DRAFT_STATUSES = (
    "METADATA_DRAFT_READY",
    "LOCAL_EML_READY",
    "LIVE_DRAFT_CREATED_GATED",
    "BLOCKED_MISSING_RECIPIENT",
    "BLOCKED_MISSING_BODY",
    "BLOCKED_MISSING_ATTACHMENT",
    "BLOCKED_PROVIDER_UNAVAILABLE",
    "BLOCKED_APPROVAL_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "DRAFT_READY_FOR_REVIEW",
    "LOCAL_DRAFT_ARTIFACT_READY",
    "METADATA_DRAFT_READY",
    "NOT_READY_MISSING_RECIPIENT",
    "NOT_READY_MISSING_BODY",
    "NOT_READY_MISSING_ATTACHMENT",
    "NOT_READY_MISSING_APPROVAL",
    "BLOCKED_PROVIDER_UNAVAILABLE",
    "BLOCKED_SEND_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "SEND_ATTEMPTED",
    "RECIPIENT_MISSING",
    "DRAFT_BODY_MISSING",
    "ATTACHMENT_REF_MISSING",
    "ATTACHMENT_HASH_MISSING",
    "PROVIDER_ADAPTER_MISSING",
    "APPROVAL_MISSING",
    "RAW_EMAIL_ADDRESS_EXPOSED",
    "RAW_ATTACHMENT_BODY_INCLUDED",
    "GMAIL_SEND_ATTEMPTED",
    "MAIL_SEND_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "bounded_local_eml_artifact_allowed": True,
    "bounded_local_file_hash_allowed": True,
    "local_generated_read_model_allowed": True,
    "live_email_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_attachment_send_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_gmail_draft_create_allowed": False,
    "live_mail_draft_create_allowed": False,
    "live_coupa_access_allowed": False,
    "live_browser_allowed": False,
    "live_approval_execution_allowed": False,
    "live_payment_action_allowed": False,
    "live_attachment_body_read_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "email send",
    "Gmail send",
    "Mail send",
    "attachment send",
    "live Gmail draft creation",
    "live Apple Mail draft creation",
    "Coupa access",
    "browser automation",
    "approval execution",
    "workflow run",
    "agent dispatch",
    "external action",
    "credential handling",
    "raw attachment body",
)

CAPITAL_HILTON_BODY = (
    "Hi Annette,\n\n"
    "I'm sending over the Winship-branded invoice PDF for the recent Capital Hilton dates "
    "for your local records and payment follow-up. My understanding is that the official "
    "payment rail remains the Coupa supplier portal / PO process.\n\n"
    "Please let me know if you need anything else from me to keep the payment moving.\n\n"
    "Best,\n"
    "Winship"
)


@dataclass(frozen=True)
class GatedEmailDraftAdapter:
    adapter_id: str
    doctrine: tuple[str, ...]
    source_package_policy: tuple[str, ...]
    draft_creation_policy: tuple[str, ...]
    recipient_policy: tuple[str, ...]
    attachment_policy: tuple[str, ...]
    approval_policy: tuple[str, ...]
    provider_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class EmailDraftCreationRequest:
    request_id: str
    source_email_delivery_package_ref: str
    source_draft_candidate_ref: str
    source_approval_ref: str
    client_ref: str
    tenant_ref: str
    provider_target: str
    recipient_refs: tuple[str, ...]
    subject: str
    body_ref_or_body_summary: str
    attachment_refs: tuple[str, ...]
    requested_mode: str
    approval_required: bool
    send_allowed: bool
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class EmailDraftArtifact:
    draft_ref: str
    provider_target: str
    draft_status: str
    safe_display_label: str
    recipient_display_refs: tuple[str, ...]
    subject_summary: str
    body_summary: str
    attachment_display_refs: tuple[str, ...]
    local_artifact_ref: str
    provider_draft_id_ref: str
    created_at_policy: str
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailDraftGate:
    gate_id: str
    draft_request_ref: str
    required_email_package_ref: str
    required_draft_candidate_ref: str
    required_recipient_ref: str
    required_attachment_refs: tuple[str, ...]
    required_approval_ref: str
    required_provider_adapter_ref: str
    missing_items: tuple[str, ...]
    draft_create_allowed: bool
    send_allowed: bool
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class EmailDraftReadback:
    readback_id: str
    draft_ref: str
    status: str
    operator_headline: str
    operator_message: str
    draft_summary: str
    recipient_summary: str
    attachment_summary: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailDraftProofPlan:
    proof_plan_id: str
    draft_ref: str
    required_proofs: tuple[str, ...]
    available_proof_refs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    draft_review_required: bool
    send_proof_future_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class EmailDraftAdapterBlocker:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _repo_relative(path: Path, *, repo_root: Path | str = Path.cwd()) -> str:
    try:
        return path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_repo_path(path: Path | str, *, repo_root: Path | str = Path.cwd()) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(repo_root) / candidate


def _validate_artifact_path(path: Path, *, repo_root: Path | str = Path.cwd()) -> None:
    resolved = path.resolve()
    root = Path(repo_root).resolve()
    allowed_root = (root / "generated" / "email_drafts").resolve()
    if not (resolved == allowed_root or str(resolved).startswith(str(allowed_root) + "/")):
        raise ValueError(f"email draft artifact path must stay under generated/email_drafts: {path}")
    if resolved.as_posix().lower().startswith(((Path("/mnt") / "c").as_posix() + "/").lower()):
        raise ValueError("email draft artifact path must not use C-drive")


def build_adapter() -> GatedEmailDraftAdapter:
    return GatedEmailDraftAdapter(
        adapter_id="gated_email_draft_adapter_v0",
        doctrine=(
            "Prepare reviewable draft artifacts, not sends.",
            "Local .eml review artifacts are allowed only under a bounded generated path.",
            "Live Gmail/Mail draft creation is unavailable in v0 unless a future gated adapter proves it.",
            "Attachments are refs only; no attachment body is read or included.",
            "External send authority remains false.",
        ),
        source_package_policy=(
            "Source package must name an email delivery package ref and candidate draft ref.",
            "Drafts can be prepared from candidate/confirmed recipient refs only as offline review artifacts.",
            "Missing package, body, recipient, or attachment refs block readiness.",
        ),
        draft_creation_policy=(
            "METADATA_ONLY emits read-model metadata only.",
            "LOCAL_EML_FILE writes a deterministic review artifact if bounded and gated.",
            "LIVE_GMAIL_DRAFT_GATED and LIVE_APPLE_MAIL_DRAFT_GATED return provider unavailable in v0.",
        ),
        recipient_policy=(
            "Recipient refs are safe display/token refs, not raw addresses.",
            "Raw private email addresses are blocked from normal read-models and local artifact headers.",
            "Unconfirmed recipients are allowed only for local/offline review artifacts and are not send-ready.",
        ),
        attachment_policy=(
            "Attachment refs are displayed as refs only.",
            "Artifact hash/fingerprint proof is required when attachment refs are present.",
            "No raw attachment body is copied into read-models or the local .eml artifact.",
        ),
        approval_policy=(
            "Approval is required before external send.",
            "Local draft review artifact does not create send authority.",
            "Live provider draft creation would require a future explicit Guardian/operator gate.",
        ),
        provider_policy=(
            "Gmail/Mail live draft adapters are unavailable and not called in v0.",
            "LOCAL_EML_FILE is a local generated artifact, not an email client draft.",
            "Provider draft ids are protected/safe refs only.",
        ),
        proof_policy=(
            "Draft review requires recipient ref, candidate draft ref, attachment ref/hash when applicable, and approval context.",
            "Future send approval/receipt remains outside this lane.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use local review draft artifacts for operator review; build live draft/send adapters only in future gated lanes.",
    )


def build_capital_hilton_request(
    *,
    requested_mode: str = "LOCAL_EML_FILE",
    provider_target: str = "LOCAL_EML_FILE",
    generated_at: str = DEFAULT_GENERATED_AT,
    recipient_refs: tuple[str, ...] = ("recipient_ref:annette_capital_hilton_candidate",),
    subject: str = "Capital Hilton Invoice Follow-Up",
    body_summary: str = "Candidate Capital Hilton invoice follow-up draft body from Cassandra draft worker.",
    attachment_refs: tuple[str, ...] = ("email_attachment_ref:capital_hilton_pdf_2026-05-25",),
    source_approval_ref: str = "guardian_approval_capital_hilton_email_v0",
    send_allowed: bool = False,
) -> EmailDraftCreationRequest:
    return EmailDraftCreationRequest(
        request_id=f"email_draft_request_capital_hilton_{requested_mode.lower()}_v0",
        source_email_delivery_package_ref="email_delivery_package_capital_hilton_ready_for_review_v0",
        source_draft_candidate_ref="cassandra_draft_candidate_cassandra_draft_capital_hilton_invoice_followup_v0",
        source_approval_ref=source_approval_ref,
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        provider_target=provider_target,
        recipient_refs=recipient_refs,
        subject=subject,
        body_ref_or_body_summary=body_summary,
        attachment_refs=attachment_refs,
        requested_mode=requested_mode,
        approval_required=True,
        send_allowed=send_allowed,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def _eml_filename() -> str:
    return f"CAPITAL_HILTON_INVOICE_FOLLOWUP_REVIEW_DRAFT_{DEFAULT_RECORD_DATE}.eml"


def _render_eml(request: EmailDraftCreationRequest) -> bytes:
    attachment_lines = "\n".join(f"- {ref}" for ref in request.attachment_refs) or "- no attachment refs"
    lines = [
        "X-OpenClaw-Review-Only: true",
        "X-OpenClaw-Provider-Target: LOCAL_EML_FILE",
        "X-OpenClaw-Recipient-Refs: " + ", ".join(request.recipient_refs),
        "X-OpenClaw-Attachment-Refs: " + ", ".join(request.attachment_refs),
        "Subject: " + request.subject,
        "Content-Type: text/plain; charset=utf-8",
        "",
        CAPITAL_HILTON_BODY,
        "",
        "Attachment refs only:",
        attachment_lines,
        "",
        "Boundary: local review artifact only. Nothing was sent, submitted, uploaded, opened, or approved.",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_local_eml(
    request: EmailDraftCreationRequest,
    *,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_file: bool = True,
) -> dict[str, Any]:
    root = _resolve_repo_path(artifact_root, repo_root=repo_root)
    path = root / _eml_filename()
    _validate_artifact_path(path, repo_root=repo_root)
    content = _render_eml(request)
    if write_file:
        root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        hash_value = _sha256_file(path)
        size = path.stat().st_size
        exists_status = "LOCAL_EML_EXISTS"
    else:
        hash_value = "sha256:" + hashlib.sha256(content).hexdigest()
        size = len(content)
        exists_status = "LOCAL_EML_MODELED_NOT_WRITTEN"
    rel_path = _repo_relative(path, repo_root=repo_root)
    return {
        "artifact_ref": "local_eml_artifact_ref:capital_hilton_invoice_followup_review_draft",
        "local_path_policy": f"bounded_local_eml_ref:{rel_path}",
        "hash_or_fingerprint": hash_value,
        "file_size_bytes": size,
        "exists_status": exists_status,
        "raw_attachment_body_included": False,
        "external_action": False,
    }


def build_gate(request: EmailDraftCreationRequest) -> EmailDraftGate:
    missing: list[str] = []
    if not request.source_email_delivery_package_ref:
        missing.append("email delivery package ref")
    if not request.source_draft_candidate_ref:
        missing.append("candidate draft ref")
    if not request.recipient_refs:
        missing.append("recipient/contact ref")
    if not request.body_ref_or_body_summary:
        missing.append("draft body/body summary")
    if not request.attachment_refs:
        missing.append("attachment ref")
    if request.requested_mode in ("LIVE_GMAIL_DRAFT_GATED", "LIVE_APPLE_MAIL_DRAFT_GATED") and not request.source_approval_ref:
        missing.append("Guardian/operator approval for live draft creation")
    if request.requested_mode in ("LIVE_GMAIL_DRAFT_GATED", "LIVE_APPLE_MAIL_DRAFT_GATED"):
        missing.append("live provider draft adapter")
    if request.send_allowed:
        missing.append("send attempted but blocked")
    draft_create_allowed = (
        request.requested_mode in ("METADATA_ONLY", "LOCAL_EML_FILE")
        and not request.send_allowed
        and not missing
    )
    return EmailDraftGate(
        gate_id=_stable_id("email_draft_gate", request.request_id),
        draft_request_ref=request.request_id,
        required_email_package_ref=request.source_email_delivery_package_ref or "missing",
        required_draft_candidate_ref=request.source_draft_candidate_ref or "missing",
        required_recipient_ref=request.recipient_refs[0] if request.recipient_refs else "missing",
        required_attachment_refs=request.attachment_refs,
        required_approval_ref=request.source_approval_ref or "missing",
        required_provider_adapter_ref=(
            "local_bounded_eml_artifact_writer"
            if request.requested_mode == "LOCAL_EML_FILE"
            else "metadata_only_no_provider"
            if request.requested_mode == "METADATA_ONLY"
            else "missing_live_provider_adapter"
        ),
        missing_items=tuple(dict.fromkeys(missing)),
        draft_create_allowed=draft_create_allowed,
        send_allowed=False,
        external_authority=False,
        next_safe_move=(
            "Prepare local review draft only; keep send blocked."
            if draft_create_allowed
            else "Resolve missing draft gate items; do not send."
        ),
    )


def build_artifact(
    request: EmailDraftCreationRequest,
    gate: EmailDraftGate,
    *,
    local_artifact: dict[str, Any] | None = None,
) -> EmailDraftArtifact:
    if request.send_allowed:
        status = "UNKNOWN_FAIL_CLOSED"
    elif not request.recipient_refs:
        status = "BLOCKED_MISSING_RECIPIENT"
    elif not request.body_ref_or_body_summary:
        status = "BLOCKED_MISSING_BODY"
    elif not request.attachment_refs:
        status = "BLOCKED_MISSING_ATTACHMENT"
    elif request.requested_mode in ("LIVE_GMAIL_DRAFT_GATED", "LIVE_APPLE_MAIL_DRAFT_GATED"):
        status = "BLOCKED_PROVIDER_UNAVAILABLE"
    elif request.requested_mode == "METADATA_ONLY":
        status = "METADATA_DRAFT_READY"
    elif request.requested_mode == "LOCAL_EML_FILE" and gate.draft_create_allowed and local_artifact:
        status = "LOCAL_EML_READY"
    else:
        status = "UNKNOWN_FAIL_CLOSED"
    return EmailDraftArtifact(
        draft_ref=f"email_draft_ref:capital_hilton_{request.requested_mode.lower()}_v0",
        provider_target=request.provider_target,
        draft_status=status,
        safe_display_label="Capital Hilton invoice follow-up draft for review",
        recipient_display_refs=request.recipient_refs,
        subject_summary=request.subject,
        body_summary=request.body_ref_or_body_summary,
        attachment_display_refs=request.attachment_refs,
        local_artifact_ref=(local_artifact or {}).get("artifact_ref", ""),
        provider_draft_id_ref="",
        created_at_policy=request.created_at,
        privacy_class="client_email_draft_private_ref",
        next_safe_move=(
            "Review local draft artifact; nothing has been sent."
            if status == "LOCAL_EML_READY"
            else "Review metadata draft; live provider creation remains unavailable."
            if status == "METADATA_DRAFT_READY"
            else "Resolve missing draft inputs or provider adapter."
        ),
    )


def build_proof_plan(
    request: EmailDraftCreationRequest,
    artifact: EmailDraftArtifact,
    *,
    local_artifact: dict[str, Any] | None = None,
) -> EmailDraftProofPlan:
    required = (
        "recipient/contact ref",
        "candidate draft ref",
        "attachment/artifact ref if applicable",
        "artifact hash/fingerprint if attachment applicable",
        "operator/Guardian approval for draft creation if live provider target is used",
        "future send approval/receipt, not in this lane",
    )
    available: list[str] = []
    if request.recipient_refs:
        available.append("recipient/contact ref")
    if request.source_draft_candidate_ref:
        available.append("candidate draft ref")
    if request.attachment_refs:
        available.append("attachment/artifact ref if applicable")
    if request.attachment_refs:
        available.append("artifact hash/fingerprint if attachment applicable")
    if request.requested_mode not in ("LIVE_GMAIL_DRAFT_GATED", "LIVE_APPLE_MAIL_DRAFT_GATED") or request.source_approval_ref:
        available.append("operator/Guardian approval for draft creation if live provider target is used")
    if local_artifact and local_artifact.get("hash_or_fingerprint"):
        available.append(f"local eml artifact hash {local_artifact['hash_or_fingerprint']}")
    missing = tuple(proof for proof in required if proof not in available)
    return EmailDraftProofPlan(
        proof_plan_id=_stable_id("email_draft_proof_plan", artifact.draft_ref),
        draft_ref=artifact.draft_ref,
        required_proofs=required,
        available_proof_refs=tuple(available),
        missing_proofs=missing,
        draft_review_required=True,
        send_proof_future_required=True,
        next_safe_move="Review the draft artifact; future send still requires approval and send receipt.",
    )


def build_readback(
    request: EmailDraftCreationRequest,
    artifact: EmailDraftArtifact,
    gate: EmailDraftGate,
    proof_plan: EmailDraftProofPlan,
) -> EmailDraftReadback:
    if request.send_allowed:
        status = "BLOCKED_SEND_GATE"
        headline = "Email send is blocked"
        message = "A send attempt was detected. The draft adapter does not send."
        fix = "Use this adapter for draft review only; route future send through a separate approval-gated adapter."
    elif not request.recipient_refs:
        status = "NOT_READY_MISSING_RECIPIENT"
        headline = "Draft needs a recipient"
        message = "OpenClaw cannot prepare the draft until a recipient/contact ref exists."
        fix = "Confirm Annette/contact route through Google read-only broker or operator input."
    elif not request.body_ref_or_body_summary:
        status = "NOT_READY_MISSING_BODY"
        headline = "Draft needs a body"
        message = "OpenClaw cannot prepare a review draft without a candidate draft body or summary."
        fix = "Run or reference Cassandra draft worker output."
    elif not request.attachment_refs:
        status = "NOT_READY_MISSING_ATTACHMENT"
        headline = "Draft needs an attachment ref"
        message = "The invoice draft needs an invoice artifact/attachment ref."
        fix = "Generate, attach, and hash the invoice artifact before draft review."
    elif artifact.draft_status == "BLOCKED_PROVIDER_UNAVAILABLE":
        status = "BLOCKED_PROVIDER_UNAVAILABLE"
        headline = "Live draft provider unavailable"
        message = "Live Gmail/Mail draft creation is not connected in this lane."
        fix = "Use local .eml or metadata draft review; build a future gated provider adapter later."
    elif request.requested_mode == "LOCAL_EML_FILE" and artifact.draft_status == "LOCAL_EML_READY":
        status = "LOCAL_DRAFT_ARTIFACT_READY"
        headline = "Local email draft artifact ready for review"
        message = (
            "OpenClaw prepared the Capital Hilton email draft package for review. "
            "Nothing has been sent. The draft still needs future approval and send receipts before a future send adapter can be approved."
        )
        fix = "Review the local .eml artifact and keep send gates locked."
    elif request.requested_mode == "METADATA_ONLY" and artifact.draft_status == "METADATA_DRAFT_READY":
        status = "METADATA_DRAFT_READY"
        headline = "Metadata email draft ready for review"
        message = (
            "OpenClaw prepared the Capital Hilton email draft metadata for review. "
            "Nothing has been sent or created in Gmail/Mail."
        )
        fix = "Review metadata; use local .eml mode if a file artifact is needed."
    else:
        status = "UNKNOWN_FAIL_CLOSED"
        headline = "Email draft adapter failed closed"
        message = "The draft adapter could not prove a safe draft posture."
        fix = "Regenerate with recipient, body, attachment, and safe requested mode."
    missing = tuple(dict.fromkeys((*gate.missing_items, *proof_plan.missing_proofs)))
    return EmailDraftReadback(
        readback_id=_stable_id("email_draft_readback", artifact.draft_ref, status),
        draft_ref=artifact.draft_ref,
        status=status,
        operator_headline=headline,
        operator_message=message,
        draft_summary=f"{artifact.subject_summary}; {artifact.body_summary}",
        recipient_summary=", ".join(artifact.recipient_display_refs) if artifact.recipient_display_refs else "No recipient ref",
        attachment_summary=", ".join(artifact.attachment_display_refs) if artifact.attachment_display_refs else "No attachment refs",
        missing_items=missing,
        blocked_actions=BLOCKED_ACTIONS,
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_blockers() -> tuple[EmailDraftAdapterBlocker, ...]:
    return (
        EmailDraftAdapterBlocker("email_draft_blocker_send", "SEND_ATTEMPTED", "Draft adapter attempts send.", "critical", "Email send is blocked.", True, "Return draft artifact/readback only."),
        EmailDraftAdapterBlocker("email_draft_blocker_recipient", "RECIPIENT_MISSING", "Recipient/contact ref is missing.", "high", "Recipient ref is missing.", True, "Confirm recipient/contact route."),
        EmailDraftAdapterBlocker("email_draft_blocker_body", "DRAFT_BODY_MISSING", "Candidate draft body/summary is missing.", "high", "Draft body is missing.", True, "Reference Cassandra candidate draft."),
        EmailDraftAdapterBlocker("email_draft_blocker_attachment", "ATTACHMENT_REF_MISSING", "Attachment ref is missing.", "high", "Attachment ref is missing.", True, "Attach invoice artifact ref."),
        EmailDraftAdapterBlocker("email_draft_blocker_attachment_hash", "ATTACHMENT_HASH_MISSING", "Attachment hash/fingerprint proof is missing.", "high", "Attachment hash/fingerprint is missing.", True, "Hash/fingerprint invoice artifact."),
        EmailDraftAdapterBlocker("email_draft_blocker_provider", "PROVIDER_ADAPTER_MISSING", "Live Gmail/Mail draft adapter is unavailable.", "critical", "Live draft provider is unavailable.", True, "Use local .eml or build future gated provider adapter."),
        EmailDraftAdapterBlocker("email_draft_blocker_approval", "APPROVAL_MISSING", "Live provider draft creation lacks approval.", "critical", "Approval is missing.", True, "Create Guardian/operator approval before live provider draft."),
        EmailDraftAdapterBlocker("email_draft_blocker_raw_email", "RAW_EMAIL_ADDRESS_EXPOSED", "Raw private email address appears in output.", "critical", "Raw email address exposure is blocked.", True, "Use tokenized recipient refs."),
        EmailDraftAdapterBlocker("email_draft_blocker_raw_attachment", "RAW_ATTACHMENT_BODY_INCLUDED", "Attachment body or bytes are included.", "critical", "Raw attachment body is blocked.", True, "Use attachment refs only."),
        EmailDraftAdapterBlocker("email_draft_blocker_gmail_send", "GMAIL_SEND_ATTEMPTED", "Adapter attempts Gmail send.", "critical", "Gmail send is blocked.", True, "No send in draft adapter."),
        EmailDraftAdapterBlocker("email_draft_blocker_mail_send", "MAIL_SEND_ATTEMPTED", "Adapter attempts Mail send.", "critical", "Mail send is blocked.", True, "No send in draft adapter."),
        EmailDraftAdapterBlocker("email_draft_blocker_external", "EXTERNAL_ACTION_ATTEMPTED", "Adapter attempts external action.", "critical", "External action is blocked.", True, "Stay local/read-model only."),
        EmailDraftAdapterBlocker("email_draft_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown draft adapter state.", "high", "Unknown draft adapter state fails closed.", True, "Ask for scoped draft/package refs."),
    )


def _bundle(
    request: EmailDraftCreationRequest,
    *,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_files: bool = True,
) -> dict[str, Any]:
    gate = build_gate(request)
    local_artifact: dict[str, Any] | None = None
    if request.requested_mode == "LOCAL_EML_FILE" and gate.draft_create_allowed:
        local_artifact = write_local_eml(request, repo_root=repo_root, artifact_root=artifact_root, write_file=write_files)
    artifact = build_artifact(request, gate, local_artifact=local_artifact)
    proof_plan = build_proof_plan(request, artifact, local_artifact=local_artifact)
    readback = build_readback(request, artifact, gate, proof_plan)
    return {
        "request": asdict(request),
        "draft_artifact": asdict(artifact),
        "gate": asdict(gate),
        "proof_plan": asdict(proof_plan),
        "readback": asdict(readback),
        "local_artifact": local_artifact,
    }


def build_examples(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_files: bool = True,
) -> dict[str, Any]:
    metadata = build_capital_hilton_request(
        requested_mode="METADATA_ONLY",
        provider_target="METADATA_ONLY_DRAFT",
        generated_at=generated_at,
    )
    local = build_capital_hilton_request(generated_at=generated_at)
    missing_recipient = build_capital_hilton_request(generated_at=generated_at, recipient_refs=())
    missing_body = build_capital_hilton_request(generated_at=generated_at, body_summary="")
    missing_attachment = build_capital_hilton_request(generated_at=generated_at, attachment_refs=())
    attempted_send = build_capital_hilton_request(generated_at=generated_at, send_allowed=True)
    live_unavailable = build_capital_hilton_request(
        requested_mode="LIVE_GMAIL_DRAFT_GATED",
        provider_target="GMAIL_DRAFT",
        generated_at=generated_at,
    )
    return {
        "capital_hilton_metadata_draft_package": _bundle(metadata, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
        "capital_hilton_local_eml_draft_artifact": _bundle(local, repo_root=repo_root, artifact_root=artifact_root, write_files=write_files),
        "missing_recipient": _bundle(missing_recipient, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
        "missing_body": _bundle(missing_body, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
        "missing_attachment": _bundle(missing_attachment, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
        "attempted_send": _bundle(attempted_send, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
        "live_provider_unavailable": _bundle(live_unavailable, repo_root=repo_root, artifact_root=artifact_root, write_files=False),
    }


def build_payload(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_files: bool = True,
) -> dict[str, Any]:
    adapter = build_adapter()
    blockers = build_blockers()
    examples = build_examples(
        generated_at=generated_at,
        repo_root=repo_root,
        artifact_root=artifact_root,
        write_files=write_files,
    )
    local_artifacts = tuple(
        example["local_artifact"]
        for example in examples.values()
        if example.get("local_artifact") is not None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "provider_targets": PROVIDER_TARGETS,
        "requested_modes": REQUESTED_MODES,
        "draft_statuses": DRAFT_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "adapter": asdict(adapter),
        "email_draft_adapter_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "local_artifacts": local_artifacts,
        "capital_hilton_expected_operator_readback": (
            "OpenClaw prepared the Capital Hilton email draft package for review. "
            "Nothing has been sent. The draft still needs [missing items] before a future send adapter can be approved."
        ),
        "machine_proof": {
            "all_live_authority_false_except_bounded_local_eml": all(
                value is False
                for key, value in AUTHORITY_BOUNDARY.items()
                if key
                not in {
                    "bounded_local_eml_artifact_allowed",
                    "bounded_local_file_hash_allowed",
                    "local_generated_read_model_allowed",
                }
            ),
            "bounded_local_eml_artifact_created": bool(local_artifacts) and write_files,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "mail_send_performed": False,
            "attachment_send_performed": False,
            "live_gmail_draft_created": False,
            "live_mail_draft_created": False,
            "coupa_access_performed": False,
            "browser_access_performed": False,
            "approval_execution_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_attachment_body_included": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw can prepare Capital Hilton email draft metadata and a bounded local .eml review artifact. "
            "Nothing is sent, no live Gmail/Mail draft is created, and future send remains separately gated."
        ),
        "next_safe_move": "Review the local .eml or metadata draft; keep future send behind Guardian/operator approval and a separate send adapter.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    local = payload["examples"]["capital_hilton_local_eml_draft_artifact"]["readback"]
    metadata = payload["examples"]["capital_hilton_metadata_draft_package"]["readback"]
    lines = [
        "# Gated Email Draft Adapter",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton Local Draft",
        f"- Status: {local['status']}",
        f"- Message: {local['operator_message']}",
        f"- Recipient: {local['recipient_summary']}",
        f"- Attachment: {local['attachment_summary']}",
        f"- Next: {local['next_safe_move']}",
        "",
        "## Metadata Draft",
        f"- Status: {metadata['status']}",
        f"- Message: {metadata['operator_message']}",
        "",
        "## Local Artifacts",
    ]
    for artifact in payload["local_artifacts"]:
        lines.append(f"- {artifact['local_path_policy']} {artifact['hash_or_fingerprint']}")
    lines += ["", "## Blocked"]
    for blocker in payload["email_draft_adapter_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No email send, no Gmail send, no Mail send, no attachment send, no Coupa access, no browser, no approval execution, no workflow run, no agent dispatch, no external action, no credential handling, no raw attachment body, no raw-body ingestion.",
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
    local = payload["examples"]["capital_hilton_local_eml_draft_artifact"]["readback"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "local_draft_status": local["status"],
        "local_artifact_count": len(payload["local_artifacts"]),
        "blocker_count": len(payload["email_draft_adapter_blockers"]),
        "all_live_authority_false_except_bounded_local_eml": payload["machine_proof"]["all_live_authority_false_except_bounded_local_eml"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    fixture: str = "capital_hilton",
    generated_at: str = DEFAULT_GENERATED_AT,
    repo_root: Path = Path.cwd(),
    export_root: Path = DEFAULT_EXPORT_ROOT,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    format_name: str = "summary",
) -> dict[str, Any]:
    if fixture != "capital_hilton":
        raise ValueError("Only capital_hilton fixture is supported in v0")
    payload = build_payload(
        generated_at=generated_at,
        repo_root=repo_root,
        artifact_root=artifact_root,
        write_files=True,
    )
    write_exports(payload, export_root)
    return payload if format_name == "json" else _summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run/export gated email draft adapter.")
    parser.add_argument("--fixture", choices=("capital_hilton",), default="capital_hilton")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--repo-root", default=str(Path.cwd()))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        fixture=args.fixture,
        generated_at=args.generated_at,
        repo_root=Path(args.repo_root),
        export_root=Path(args.export_root),
        artifact_root=Path(args.artifact_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
