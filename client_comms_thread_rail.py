"""Client communications thread rail v0.

Backend contract/readiness model for Clara-owned external email conversations.
This module creates fixtures and read-models only. It does not poll Gmail,
create Gmail/Mail drafts, send email, read live inboxes, access credentials,
open browsers, call models, or mutate production business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "client_comms_thread_rail_v0"
READ_MODEL_ID = "client_comms_thread_rail"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_GENERATED_AT = "2026-05-28T16:10:00+00:00"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")

CLARA_EXTERNAL_IDENTITY = "CLARA_REID"
CASSANDRA_INTERNAL_IDENTITY = "CASSANDRA"

THREAD_STATUSES = (
    "NOT_STARTED",
    "DRAFT_READY",
    "APPROVAL_REQUIRED",
    "SENT_RECEIPT_CONFIRMED",
    "THREAD_WATCH_READY",
    "REPLY_DETECTED",
    "REPLY_DRAFT_READY",
    "THREAD_ADOPTION_OFFERED",
    "THREAD_ADOPTED",
    "BLOCKED_NEEDS_OPERATOR",
)

AUTHORITY_BOUNDARY = {
    "live_gmail_polling_performed": False,
    "email_send_performed": False,
    "gmail_draft_created": False,
    "browser_or_coupa_access_performed": False,
    "network_call_performed": False,
    "credential_access_performed": False,
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "ledger_posting_performed": False,
    "production_mutation_performed": False,
    "live_model_call_performed": False,
    "tool_execution_performed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClaraFirstContactPolicy:
    client_ref: str
    recipient_ref: str
    first_clara_contact: bool
    prior_clara_thread_exists: bool
    intro_required: bool
    intro_style: str
    operator_context: str
    client_context: str
    reason: str
    disclosure_posture: str


@dataclass(frozen=True)
class ClaraDraftCandidate:
    draft_ref: str
    client_ref: str
    workflow_ref: str
    thread_ref: str
    selected_voice: str
    external_identity: str
    audience: str
    channel: str
    subject: str
    body: str
    draft_only: bool
    sent: bool
    send_allowed: bool
    guardian_output_validation_status: str
    guardian_approval_required: bool
    guardian_approval_request_status: str
    operator_approval_status: str
    send_execution_status: str
    required_receipts_before_send: tuple[str, ...]
    forbidden_claims: tuple[str, ...]


@dataclass(frozen=True)
class CommsThreadRecord:
    thread_ref: str
    client_ref: str
    workflow_ref: str
    channel: str
    external_thread_id: str | None
    subject: str
    participants: tuple[str, ...]
    started_by_openclaw: bool
    started_by_clara: bool
    first_sent_receipt_ref: str | None
    latest_message_receipt_ref: str | None
    watch_status: str
    adoption_status: str
    privacy_class: str
    allowed_response_scope: str
    proof_refs: tuple[str, ...]


@dataclass(frozen=True)
class ReplyWatchResult:
    incoming_message_ref: str
    thread_ref: str
    client_ref: str
    confidence: str
    reply_intent: str
    required_context: tuple[str, ...]
    allowed_to_draft: bool
    needs_operator_input: bool
    needs_child_packages: bool
    guardian_approval_required: bool
    send_allowed: bool
    draft_candidate: dict[str, Any] | None
    operator_summary: str


@dataclass(frozen=True)
class ThreadAdoptionOffer:
    offer_ref: str
    client_ref: str
    workflow_ref: str
    incoming_message_ref: str
    sender_ref: str
    thread_status: str
    adoption_status: str
    operator_notification: str
    actions: tuple[dict[str, Any], ...]
    auto_adopted: bool
    auto_replied: bool
    no_live_email_access: bool


def first_contact_policy(
    *,
    client_ref: str,
    recipient_ref: str,
    prior_clara_thread_exists: bool,
    operator_context: str,
    client_context: str,
) -> ClaraFirstContactPolicy:
    first = not prior_clara_thread_exists
    if client_ref == "live_arts_md":
        intro_style = "warm_invoice_admin_intro"
        reason = "Live Arts MD has no prior Clara-owned email thread in this fixture."
    elif client_ref == "capital_hilton":
        intro_style = "concise_finance_coordination_intro"
        reason = "Capital Hilton finance contact may know Winship, but Clara-specific prior thread proof is absent."
    else:
        intro_style = "brief_contextual_intro"
        reason = "No prior Clara thread proof exists for this recipient."
    return ClaraFirstContactPolicy(
        client_ref=client_ref,
        recipient_ref=recipient_ref,
        first_clara_contact=first,
        prior_clara_thread_exists=prior_clara_thread_exists,
        intro_required=first,
        intro_style=intro_style,
        operator_context=operator_context,
        client_context=client_context,
        reason=reason if first else "Prior Clara thread proof exists; do not repeat the full first-contact intro.",
        disclosure_posture="Clara signs as Clara Reid and does not pretend to be Winship.",
    )


def _client_display(client_ref: str) -> str:
    return {
        "live_arts_md": "Live Arts MD",
        "capital_hilton": "Capital Hilton",
        "st_annes": "St. Anne's",
    }.get(client_ref, client_ref.replace("_", " ").title())


def _first_contact_sentence(policy: ClaraFirstContactPolicy, *, recipient_name: str, work_kind: str) -> str:
    client = _client_display(policy.client_ref)
    if not policy.intro_required:
        return ""
    if policy.client_ref == "live_arts_md":
        return (
            f"Hi {recipient_name} - I'm Clara Reid, helping Winship keep the {client} "
            f"{work_kind} organized and easy to track."
        )
    if policy.client_ref == "capital_hilton":
        return (
            f"Hi {recipient_name} - I'm Clara Reid, helping Winship keep the Capital Hilton "
            f"invoice package and follow-up details organized."
        )
    return f"Hi {recipient_name} - I'm Clara Reid, helping Winship keep this {work_kind} organized."


def build_clara_first_contact_draft(
    *,
    client_ref: str,
    workflow_ref: str,
    recipient_ref: str,
    recipient_name: str,
    subject: str,
    work_kind: str,
    prior_clara_thread_exists: bool = False,
    invoice_related: bool = True,
) -> dict[str, Any]:
    policy = first_contact_policy(
        client_ref=client_ref,
        recipient_ref=recipient_ref,
        prior_clara_thread_exists=prior_clara_thread_exists,
        operator_context="Winship remains the operator and final authority.",
        client_context=f"{_client_display(client_ref)} {'invoice' if invoice_related else 'client'} communication.",
    )
    intro = _first_contact_sentence(policy, recipient_name=recipient_name, work_kind=work_kind)
    body_lines = []
    if intro:
        body_lines.append(intro)
        body_lines.append("")
    if client_ref == "live_arts_md":
        body_lines.extend(
            (
                "Once Winship confirms the invoice file and recipient details, I'll send over the invoice for this period.",
                "",
                "Best,",
                "Clara Reid",
            )
        )
    elif client_ref == "capital_hilton":
        body_lines.extend(
            (
                "Once Winship confirms the invoice file and recipient details, I'll send over the Excel invoice for your records.",
                "",
                "Best,",
                "Clara Reid",
            )
        )
    else:
        body_lines.extend(("I'm preparing this note for review before any send step.", "", "Best,", "Clara Reid"))
    thread_ref = f"client_comms_thread:{client_ref}:{_short_hash(workflow_ref, recipient_ref, subject)}"
    draft = ClaraDraftCandidate(
        draft_ref=f"clara_draft:{_short_hash(client_ref, workflow_ref, recipient_ref, subject)}",
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        thread_ref=thread_ref,
        selected_voice="CLARA",
        external_identity=CLARA_EXTERNAL_IDENTITY,
        audience="external_client",
        channel="email",
        subject=subject,
        body="\n".join(body_lines),
        draft_only=True,
        sent=False,
        send_allowed=False,
        guardian_output_validation_status="SAFE_TO_SHOW_DRAFT",
        guardian_approval_required=True,
        guardian_approval_request_status="NOT_CREATED",
        operator_approval_status="NOT_GRANTED",
        send_execution_status="NOT_SENT",
        required_receipts_before_send=(
            "thread_ref_receipt",
            "recipient_confirmation_receipt",
            "draft_hash_receipt",
            "guardian_approval_request_receipt",
            "operator_approval_receipt",
            "email_send_receipt",
        ),
        forbidden_claims=("sent", "resent", "submitted", "changed invoice amount", "paid", "posted"),
    )
    return {
        "first_contact_policy": asdict(policy),
        "draft_candidate": asdict(draft),
        "thread_registry_record": asdict(
            CommsThreadRecord(
                thread_ref=thread_ref,
                client_ref=client_ref,
                workflow_ref=workflow_ref,
                channel="email",
                external_thread_id=None,
                subject=subject,
                participants=(recipient_ref, "clara_reid"),
                started_by_openclaw=True,
                started_by_clara=True,
                first_sent_receipt_ref=None,
                latest_message_receipt_ref=None,
                watch_status="NOT_STARTED",
                adoption_status="OPENCLAW_OWNED_DRAFT_ONLY",
                privacy_class="CLIENT_COMMS_MINIMIZED",
                allowed_response_scope="draft_only_until_guardian_operator_approval_and_send_receipt",
                proof_refs=(draft.draft_ref,),
            )
        ),
    }


def classify_reply_intent(message_summary: str) -> tuple[str, str, tuple[str, ...], bool, bool]:
    text = message_summary.lower()
    if "change" in text and ("amount" in text or "invoice" in text):
        return ("CHANGE_INVOICE_AMOUNT", "LOW", ("invoice_authority_check", "operator_decision"), False, True)
    if "resend" in text or "send again" in text:
        return ("RESEND_INVOICE_REQUEST", "HIGH", ("thread_ref", "invoice_artifact_ref", "operator_approval"), True, False)
    if "question" in text or "can you" in text:
        return ("CLIENT_QUESTION", "MEDIUM", ("client_context",), True, False)
    return ("UNKNOWN_NEEDS_OPERATOR", "LOW", ("operator_input",), False, True)


def build_reply_watch_result(
    *,
    client_ref: str,
    workflow_ref: str,
    thread_ref: str,
    incoming_message_ref: str,
    message_summary: str,
) -> ReplyWatchResult:
    intent, confidence, required_context, allowed_to_draft, needs_operator = classify_reply_intent(message_summary)
    needs_child = intent == "CHANGE_INVOICE_AMOUNT"
    draft_candidate = None
    if allowed_to_draft:
        body = (
            "Hi [Name] -\n\n"
            "I can prepare the invoice resend once Winship approves the exact message and attachment. "
            "Nothing has been resent yet.\n\n"
            "Best,\nClara Reid"
            if intent == "RESEND_INVOICE_REQUEST"
            else "Hi [Name] -\n\nI'll prepare a careful reply for Winship to review before anything is sent.\n\nBest,\nClara Reid"
        )
        draft_candidate = asdict(
            ClaraDraftCandidate(
                draft_ref=f"clara_reply_draft:{_short_hash(thread_ref, incoming_message_ref)}",
                client_ref=client_ref,
                workflow_ref=workflow_ref,
                thread_ref=thread_ref,
                selected_voice="CLARA",
                external_identity=CLARA_EXTERNAL_IDENTITY,
                audience="external_client",
                channel="email",
                subject="Re: invoice",
                body=body,
                draft_only=True,
                sent=False,
                send_allowed=False,
                guardian_output_validation_status="SAFE_TO_SHOW_DRAFT",
                guardian_approval_required=True,
                guardian_approval_request_status="REQUIRED_BEFORE_SEND",
                operator_approval_status="NOT_GRANTED",
                send_execution_status="NOT_SENT",
                required_receipts_before_send=(
                    "thread_ref_receipt",
                    "reply_draft_hash_receipt",
                    "guardian_approval_request_receipt",
                    "operator_approval_receipt",
                    "email_send_receipt",
                ),
                forbidden_claims=("resent", "sent", "changed invoice amount", "posted", "paid"),
            )
        )
    return ReplyWatchResult(
        incoming_message_ref=incoming_message_ref,
        thread_ref=thread_ref,
        client_ref=client_ref,
        confidence=confidence,
        reply_intent=intent,
        required_context=required_context,
        allowed_to_draft=allowed_to_draft,
        needs_operator_input=needs_operator,
        needs_child_packages=needs_child,
        guardian_approval_required=True,
        send_allowed=False,
        draft_candidate=draft_candidate,
        operator_summary=(
            "Reply detected in a Clara-owned thread; Clara can draft a no-send reply for approval."
            if allowed_to_draft
            else "Reply needs operator input or child packages before Clara can answer."
        ),
    )


def build_thread_adoption_offer(
    *,
    client_ref: str,
    workflow_ref: str,
    sender_ref: str,
    incoming_message_ref: str,
) -> ThreadAdoptionOffer:
    client = _client_display(client_ref)
    sender_label = sender_ref.replace("_", " ").title()
    return ThreadAdoptionOffer(
        offer_ref=f"thread_adoption_offer:{_short_hash(client_ref, workflow_ref, sender_ref, incoming_message_ref)}",
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        incoming_message_ref=incoming_message_ref,
        sender_ref=sender_ref,
        thread_status="THREAD_ADOPTION_OFFERED",
        adoption_status="OPERATOR_DECISION_REQUIRED",
        operator_notification=(
            f"A new email from {sender_label} at {client} arrived outside a Clara thread. "
            "Want OpenClaw to pick up this thread and draft a Clara response?"
        ),
        actions=(
            _adoption_action("ADOPT_THREAD_AND_DRAFT", "Adopt thread and draft", True),
            _adoption_action("IGNORE_THREAD", "Ignore thread", True),
            _adoption_action("SHOW_EMAIL_SUMMARY", "Show email summary", True),
            _adoption_action("ASK_ME_LATER", "Ask me later", True),
        ),
        auto_adopted=False,
        auto_replied=False,
        no_live_email_access=True,
    )


def _adoption_action(action_kind: str, label: str, enabled: bool) -> dict[str, Any]:
    return {
        "action_ref": f"client_comms_action:{_short_hash(action_kind, label)}",
        "action_kind": action_kind,
        "label": label,
        "enabled": enabled,
        "requires_operator_approval": action_kind == "ADOPT_THREAD_AND_DRAFT",
        "no_external_action": True,
        "email_send_allowed": False,
        "hidden_request_payload": {
            "request_type": "CLIENT_COMMS_THREAD_ACTION_REQUEST",
            "intended_use": action_kind.lower(),
            "no_external_action": True,
            "email_send_allowed": False,
            "live_gmail_polling_allowed": False,
        },
    }


def build_fixtures() -> dict[str, Any]:
    live_first = build_clara_first_contact_draft(
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        recipient_ref="live_arts_md_billing_contact_candidate",
        recipient_name="[Live Arts MD contact]",
        subject="Live Arts MD invoice",
        work_kind="invoice package",
        prior_clara_thread_exists=False,
    )
    capital_followup = build_clara_first_contact_draft(
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        recipient_ref="annette_candidate",
        recipient_name="[Annette]",
        subject="Capital Hilton invoice package",
        work_kind="invoice package",
        prior_clara_thread_exists=False,
    )
    existing_thread = build_clara_first_contact_draft(
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        recipient_ref="annette_candidate",
        recipient_name="[Annette]",
        subject="Capital Hilton invoice package",
        work_kind="invoice package",
        prior_clara_thread_exists=True,
    )
    reply_inside = asdict(
        build_reply_watch_result(
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
            thread_ref=existing_thread["draft_candidate"]["thread_ref"],
            incoming_message_ref="incoming_message:capital_hilton:resend_invoice",
            message_summary="Can you resend the invoice?",
        )
    )
    reply_needs_package = asdict(
        build_reply_watch_result(
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
            thread_ref=existing_thread["draft_candidate"]["thread_ref"],
            incoming_message_ref="incoming_message:capital_hilton:change_amount",
            message_summary="Can you change the invoice amount?",
        )
    )
    outside = asdict(
        build_thread_adoption_offer(
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
            sender_ref="annette",
            incoming_message_ref="incoming_message:capital_hilton:outside_clara_thread",
        )
    )
    return {
        "live_arts_md_first_invoice_email": live_first,
        "capital_hilton_followup_thread": capital_followup,
        "existing_clara_thread_no_repeat_intro": existing_thread,
        "reply_inside_clara_thread": reply_inside,
        "reply_requires_child_package": reply_needs_package,
        "new_email_outside_clara_thread": outside,
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    fixtures = build_fixtures()
    rail_contract = {
        "client_ref": "client_scoped",
        "workflow_ref": "workflow_scoped",
        "comms_thread_ref": "thread_scoped",
        "external_identity": CLARA_EXTERNAL_IDENTITY,
        "internal_identity": CASSANDRA_INTERNAL_IDENTITY,
        "audience": "external_client",
        "channel": "email",
        "thread_statuses": THREAD_STATUSES,
        "receipts": (
            "thread_ref_receipt",
            "recipient_confirmation_receipt",
            "draft_hash_receipt",
            "guardian_output_validation_receipt",
            "guardian_approval_request_receipt",
            "operator_approval_receipt",
            "email_send_receipt",
            "reply_detected_receipt",
            "thread_adoption_operator_approval_receipt",
        ),
        "proof_refs": ("generated/read_models/client_comms_thread_rail.json",),
    }
    guardian_model = {
        "guardian_output_validation": "Safe to show a draft only.",
        "guardian_approval_request": "Ask operator to approve a future exact send package.",
        "operator_approval": "Approval for exact message, recipients, thread, and attachments.",
        "send_receipt": "Only this proves an email was actually sent.",
        "send_allowed_without_all_receipts": False,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "rail_contract": rail_contract,
        "first_contact_intro_policy": {
            "policy": "Introduce Clara briefly on first Clara-owned email to a client/contact; do not repeat full intro on later replies in the same thread.",
            "identity_rule": "Clara signs as Clara Reid and does not pretend to be Winship or Cassandra.",
            "contextual_not_canned": True,
            "fixtures": {
                "live_arts_md": fixtures["live_arts_md_first_invoice_email"]["first_contact_policy"],
                "capital_hilton": fixtures["capital_hilton_followup_thread"]["first_contact_policy"],
                "capital_hilton_existing_thread": fixtures["existing_clara_thread_no_repeat_intro"]["first_contact_policy"],
            },
        },
        "thread_registry_shape": asdict(
            CommsThreadRecord(
                thread_ref="client_comms_thread:<client>:<hash>",
                client_ref="<client_ref>",
                workflow_ref="<workflow_ref>",
                channel="email",
                external_thread_id=None,
                subject="<subject>",
                participants=("<recipient_ref>", "clara_reid"),
                started_by_openclaw=False,
                started_by_clara=False,
                first_sent_receipt_ref=None,
                latest_message_receipt_ref=None,
                watch_status="NOT_STARTED",
                adoption_status="NOT_ADOPTED",
                privacy_class="CLIENT_COMMS_MINIMIZED",
                allowed_response_scope="draft_only_until_guardian_operator_approval_and_send_receipt",
                proof_refs=(),
            )
        ),
        "reply_watch_policy": {
            "reply_in_owned_thread": "Route to Clara reply draft workflow if confidence and context are sufficient.",
            "high_risk_or_missing_context": "Create child packages or ask operator before Clara claims facts.",
            "guardian_approval_required": True,
            "send_allowed": False,
            "delegated_package_roles_allowed_when_needed": ("CHIEF", "DATA_ANALYST", "FINANCE_INVOICE_FACTS", "GUARDIAN"),
        },
        "thread_adoption_policy": {
            "outside_owned_thread": "Offer adoption to operator; do not auto-adopt or auto-reply.",
            "unknown_unmatched_email": "Park for operator review.",
            "operator_approval_required_for_adoption": True,
            "actions": tuple(action["action_kind"] for action in fixtures["new_email_outside_clara_thread"]["actions"]),
        },
        "guardian_approval_separation": guardian_model,
        "fixtures": fixtures,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "no_live_gmail_polling": True,
            "no_email_send": True,
            "no_gmail_draft_created": True,
            "no_network_or_credentials": True,
            "clara_drafts_are_draft_only": True,
            "guardian_approval_separated_from_output_validation": True,
            "thread_adoption_requires_operator_approval": True,
            "repo_b_used_as_reference_only": True,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator(payload: Mapping[str, Any]) -> str:
    fixtures = payload["fixtures"]
    live = fixtures["live_arts_md_first_invoice_email"]["draft_candidate"]
    reply = fixtures["reply_inside_clara_thread"]
    outside = fixtures["new_email_outside_clara_thread"]
    lines = [
        "# Client Comms Thread Rail",
        "",
        "- Status: contract/readiness only",
        "- External voice: Clara Reid",
        "- Internal voice: Cassandra",
        f"- Live Arts MD first-contact intro required: `{fixtures['live_arts_md_first_invoice_email']['first_contact_policy']['intro_required']}`",
        f"- Live Arts MD draft: `{live['selected_voice']}` draft-only, sent=`{str(live['sent']).lower()}`",
        f"- Reply watch example: `{reply['reply_intent']}` approval required=`{str(reply['guardian_approval_required']).lower()}`",
        f"- Outside-thread action: `{outside['thread_status']}` auto-adopted=`{str(outside['auto_adopted']).lower()}`",
        "",
        "No Gmail polling, email send, Gmail draft creation, browser/Coupa access, credentials, network calls, workbook reads, ledger posting, live model calls, or production mutation occurred.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Path, Path, Path | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return json_path, operator_path, bridge_path


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    json_path, operator_path, bridge_path = write_exports(payload, export_root, bridge_export_root=bridge_export_root)
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export client communications thread rail read-model.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_read_model(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
