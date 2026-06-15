"""Gated email-send executor.

This module defines the `email_send` executor boundary without wiring it into
`chief_compose.EXECUTORS`. SEND_HOLD is the absolute first live-send stop. Once
the hold is absent and the packet is execution-approved, the executor can invoke
the Google broker's `google.gmail.send` capability or an injected test sender.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from business_ops_ledger import append_side_effect, init_business_ops_ledger
from compose_contract import ExecutionReceipt


EMAIL_SEND_SURFACE = "email_send"
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
REYNOLDS_INTRO_EMAIL_DRAFT_PATH = Path(
    "/mnt/e/openclaw/orchestration/artifacts/reynolds/intro_email_draft.md"
)
EMAIL_SEND_EXECUTOR_VERSION = "email_send_executor_v1"
EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP = {
    "decision_owner": "Winship",
    "decision_status": "broker_available_after_packet_approval",
    "send_scope_not_activated_here": True,
    "scope_options": (
        {
            "option": "manual_send_handoff",
            "gmail_scope": None,
            "posture": "safest default while SEND_HOLD is active",
        },
        {
            "option": "gmail_draft_only",
            "gmail_scope": "https://www.googleapis.com/auth/gmail.compose",
            "posture": "future draft creation only; still not live send",
        },
        {
            "option": "gmail_live_send",
            "gmail_scope": "https://www.googleapis.com/auth/gmail.send",
            "posture": "requires separate final-send approval after SEND_HOLD lifts",
        },
    ),
    "module_default": "google_access_broker.google.gmail.send after SEND_HOLD absent and packet approved",
}


def email_send_executor_registered() -> bool:
    """Return whether the live compose registry has an email sender installed."""

    from chief_compose import EXECUTORS

    return EMAIL_SEND_SURFACE in EXECUTORS


def email_send_executor_descriptor() -> dict[str, Any]:
    """Describe the unregistered executor boundary for the pc-1 registry lane."""

    return {
        "schema_version": EMAIL_SEND_EXECUTOR_VERSION,
        "surface": EMAIL_SEND_SURFACE,
        "callable": "email_send_executor.execute_email_send_packet",
        "registry_owner": "codex-pc-1",
        "registered_by_this_module": False,
        "send_hold_path": str(DEFAULT_SEND_HOLD_PATH),
        "respects_send_hold": True,
        "requires_packet_surface": EMAIL_SEND_SURFACE,
        "requires_execution_allowed": True,
        "requires_operator_final_send": True,
        "default_transport_attached": True,
        "default_transport": "google_access_broker.call(cassandra, google.gmail.send)",
        "gmail_scope_decision_for_winship": dict(EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP),
        "blocked_external_actions": (
            "smtp_send",
            "apple_mail_send",
            "external_email_send",
        ),
    }


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(payload), sort_keys=True).encode("utf-8")).hexdigest()


def normalize_email_outbound_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the exact operator-previewable outbound email payload."""

    if payload is None:
        raise ValueError("outbound email payload is required")
    normalized = {
        "to": str(payload.get("to") or "").strip(),
        "subject": str(payload.get("subject") or "").strip(),
        "body": str(payload.get("body") or "").strip(),
        "attachment_path": (
            str(payload.get("attachment_path")).strip()
            if payload.get("attachment_path")
            else None
        ),
    }
    missing = [key for key in ("to", "subject", "body") if not normalized[key]]
    if missing:
        raise ValueError(f"outbound email payload missing required field(s): {', '.join(missing)}")
    return normalized


def build_reynolds_email_payload(
    *,
    draft_path: str | Path = REYNOLDS_INTRO_EMAIL_DRAFT_PATH,
    attachment_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the Reynolds intro email payload from the approved draft artifact."""

    text = Path(draft_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    def _header(prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()
        raise ValueError(f"Reynolds draft missing {prefix.rstrip(':')} header")

    subject_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Subject:")),
        None,
    )
    if subject_index is None:
        raise ValueError("Reynolds draft missing Subject header")
    body_start = subject_index + 1
    while body_start < len(lines) and lines[body_start].strip():
        body_start += 1
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    body_end = next(
        (index for index, line in enumerate(lines[body_start:], start=body_start) if line.startswith("## ")),
        len(lines),
    )
    body = "\n".join(line.rstrip() for line in lines[body_start:body_end]).strip()
    return normalize_email_outbound_payload(
        {
            "to": _header("To:"),
            "subject": _header("Subject:"),
            "body": body,
            "attachment_path": str(attachment_path) if attachment_path else None,
        }
    )


def _append_email_side_effect(
    *,
    packet_id: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
) -> str | None:
    init_business_ops_ledger(db_path)
    return append_side_effect(
        packet_id=packet_id,
        effect_type="email_send",
        status=status,
        approval_required=True,
        approval_tier="operator_final_send",
        replay_safe=False,
        external_ref=external_ref,
        db_path=db_path,
    )


def _email_receipt(
    *,
    packet_id: str,
    ok: bool,
    detail: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
    meta: dict[str, Any] | None = None,
) -> ExecutionReceipt:
    side_effect_id = _append_email_side_effect(
        packet_id=packet_id,
        status=status,
        db_path=db_path,
        external_ref=external_ref,
    )
    return ExecutionReceipt(
        packet_id=packet_id,
        surface=EMAIL_SEND_SURFACE,
        ok=ok,
        detail=detail,
        side_effect_id=side_effect_id,
        meta={
            "side_effect_recorded": bool(side_effect_id),
            "requires_operator_final_send": True,
            "gmail_scope_decision_for_winship": dict(EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP),
            **(meta or {}),
        },
    )


def _blocked_receipt(
    *,
    packet_id: str,
    detail: str,
    db_path: str | None,
    status: str = "blocked_no_send",
    meta: dict[str, Any] | None = None,
) -> ExecutionReceipt:
    return _email_receipt(
        packet_id=packet_id,
        ok=False,
        detail=detail,
        status=status,
        db_path=db_path,
        meta={
            "email_send_performed": False,
            "gmail_api_called": False,
            "external_send_performed": False,
            **(meta or {}),
        },
    )


def preview_email_send_payload(
    payload: Mapping[str, Any],
    *,
    packet_id: str = "email_send_preview",
    db_path: str | None = None,
) -> ExecutionReceipt:
    """Return the exact email payload that would be sent, without sending."""

    outbound_payload = normalize_email_outbound_payload(payload)
    return _email_receipt(
        packet_id=packet_id,
        ok=True,
        detail="Email send preview generated. Nothing was sent.",
        status="preview_no_send",
        db_path=db_path,
        meta={
            "preview_only": True,
            "outbound_payload": outbound_payload,
            "payload_hash": _payload_hash(outbound_payload),
            "email_send_performed": False,
            "gmail_api_called": False,
            "external_send_performed": False,
        },
    )


def send_email_via_google_broker(
    *,
    to: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
    approval_state: Mapping[str, Any] | None = None,
    packet_id: str = "",
) -> dict[str, Any]:
    """Invoke the central Google broker for a plain-text Gmail send."""

    if attachment_path:
        return {
            "ok": False,
            "data": None,
            "error": "Gmail broker send does not support attachments; use the invoice Square rail",
        }
    payload = normalize_email_outbound_payload(
        {"to": to, "subject": subject, "body": body, "attachment_path": None}
    )
    request_id = packet_id or f"email_send:{_payload_hash(payload)}"
    approval_context = {
        "exact_send_gate": True,
        "request_id": request_id,
        "idempotency_key": request_id,
        "payload_hash": _payload_hash(payload),
        "authority_refs": [
            str((approval_state or {}).get("packet_hash") or "agent_work_packet_g3")
        ],
        "credential_lease_refs": ["google_access_broker_configured_runtime"],
    }
    from google_access_broker import call

    return call(
        "cassandra",
        "google.gmail.send",
        {
            "to": payload["to"],
            "subject": payload["subject"],
            "body": payload["body"],
            "exact_send_request_id": request_id,
            "idempotency_key": request_id,
            "approval_context": approval_context,
        },
    )


def _provider_result_ok(result: Any) -> bool:
    return not (isinstance(result, Mapping) and result.get("ok") is False)


def _provider_external_ref(result: Any) -> str | None:
    if not isinstance(result, Mapping):
        return None
    data = result.get("data")
    if isinstance(data, Mapping):
        for key in ("message_id", "id"):
            if data.get(key):
                return f"gmail:{data[key]}"
    for key in ("provider_message_id", "message_id", "id"):
        if result.get(key):
            return f"gmail:{result[key]}"
    return None


def build_email_send_executor(
    *,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    email_sender: Callable[..., Any] | None = None,
    outbound_payload: Mapping[str, Any] | None = None,
    preview_only: bool = False,
) -> Callable[..., ExecutionReceipt]:
    """Return a registry-compatible executor wrapper without registering it."""

    def _executor(
        *,
        packet_id: str,
        db_path: str | None = None,
        expected_packet_hash: str | None = None,
    ) -> ExecutionReceipt:
        return execute_email_send_packet(
            packet_id=packet_id,
            db_path=db_path,
            expected_packet_hash=expected_packet_hash,
            send_hold_path=send_hold_path,
            email_sender=email_sender,
            outbound_payload=outbound_payload,
            preview_only=preview_only,
        )

    return _executor


def execute_email_send_packet(
    *,
    packet_id: str,
    db_path: str | None = None,
    expected_packet_hash: str | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    email_sender: Callable[..., Any] | None = None,
    outbound_payload: Mapping[str, Any] | None = None,
    preview_only: bool = False,
) -> ExecutionReceipt:
    """Execute or preview a gated email-send packet.

    The live path is reached only after packet surface, stale hash, SEND_HOLD,
    and execution approval checks pass.
    """

    from chief_compose import get_packet_approval_state

    packet_id = (packet_id or "").strip()
    if not packet_id:
        return ExecutionReceipt(packet_id="", surface=EMAIL_SEND_SURFACE, ok=False, detail="packet_id is required")

    if preview_only:
        try:
            return preview_email_send_payload(outbound_payload, packet_id=packet_id, db_path=db_path)
        except ValueError as exc:
            return _blocked_receipt(
                packet_id=packet_id,
                detail=str(exc),
                status="blocked_invalid_payload",
                db_path=db_path,
                meta={"preview_only": True},
            )

    try:
        state = get_packet_approval_state(
            packet_id,
            expected_packet_hash=expected_packet_hash,
            db_path=db_path,
        )
    except ValueError as exc:
        return _blocked_receipt(packet_id=packet_id, detail=str(exc), db_path=db_path)

    if state["surface"] != EMAIL_SEND_SURFACE:
        return _blocked_receipt(
            packet_id=packet_id,
            detail=f"Packet surface is {state['surface']!r}, not 'email_send'. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if state["stale"]:
        return _blocked_receipt(
            packet_id=packet_id,
            detail="Packet stale-hash check failed. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if Path(send_hold_path).is_file():
        return _blocked_receipt(
            packet_id=packet_id,
            detail="SEND_HOLD is active. Email send is blocked; nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": True},
        )
    if not state["execution_allowed"]:
        return _blocked_receipt(
            packet_id=packet_id,
            detail="Packet is not execution-approved. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )

    try:
        payload = normalize_email_outbound_payload(outbound_payload)
    except ValueError as exc:
        return _blocked_receipt(
            packet_id=packet_id,
            detail=f"{exc}. Nothing was sent.",
            status="blocked_invalid_payload",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )

    sender = email_sender or send_email_via_google_broker
    provider_result = sender(
        **payload,
        approval_state=state,
        packet_id=packet_id,
    )
    if not _provider_result_ok(provider_result):
        return _blocked_receipt(
            packet_id=packet_id,
            detail=f"Gmail broker send failed: {provider_result.get('error', 'unknown error')}",
            status="gmail_send_failed",
            db_path=db_path,
            meta={
                "approval_state": state,
                "send_hold_active": False,
                "outbound_payload": payload,
                "payload_hash": _payload_hash(payload),
                "provider_result": provider_result,
                "gmail_api_called": True,
            },
        )

    external_ref = _provider_external_ref(provider_result)
    return _email_receipt(
        packet_id=packet_id,
        ok=True,
        detail="Gmail broker send path invoked for approved email packet.",
        status="gmail_send_invoked",
        db_path=db_path,
        external_ref=external_ref,
        meta={
            "approval_state": state,
            "send_hold_active": False,
            "outbound_payload": payload,
            "payload_hash": _payload_hash(payload),
            "provider_result": provider_result,
            "email_send_performed": True,
            "gmail_api_called": True,
            "external_send_performed": True,
        },
    )


__all__ = [
    "DEFAULT_SEND_HOLD_PATH",
    "EMAIL_SEND_EXECUTOR_VERSION",
    "EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP",
    "EMAIL_SEND_SURFACE",
    "REYNOLDS_INTRO_EMAIL_DRAFT_PATH",
    "build_email_send_executor",
    "build_reynolds_email_payload",
    "email_send_executor_descriptor",
    "email_send_executor_registered",
    "execute_email_send_packet",
    "normalize_email_outbound_payload",
    "preview_email_send_payload",
    "send_email_via_google_broker",
]
