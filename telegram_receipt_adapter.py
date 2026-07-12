"""Shared post-delivery receipt helpers for bound Telegram listeners."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fleet_receipt_index import (
    DEFAULT_SQLITE_PATH,
    ReceiptDescriptor,
    ReceiptResolution,
    RegistrationResult,
    build_receipt_descriptor,
    register_delivered_receipt,
    render_receipt_safe_visible_text,
    resolve_receipt_request,
)


_ACTOR_NAMES = {
    "cassandra": "Cassandra",
    "chief": "Chief",
    "guardian": "Guardian",
    "maestro": "Maestro",
    "niles": "Niles",
}
_PROVIDER_SURFACE_BY_DELIVERY = {
    ("cassandra", "cassandra_telegram"): "cassandra_telegram",
    ("chief", "chief_listener"): "chief_router",
    ("guardian", "guardian_listener"): "guardian_listener",
    ("maestro", "operator_maestro_chat"): "operator_maestro_chat",
    ("niles", "niles_producer_listener"): "niles_producer_listener",
}
WORKFLOW_RECEIPT_DB_ENV = "OPENCLAW_WORKFLOW_PACKAGE_DB"


def receipt_index_path(
    override: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    if override is not None and str(override).strip():
        return Path(override)
    env = os.environ if environ is None else environ
    configured = str(env.get("OPENCLAW_FLEET_RECEIPT_INDEX_DB") or "").strip()
    return Path(configured) if configured else DEFAULT_SQLITE_PATH


def reply_to_message_id(message: Any) -> str:
    replied_to = getattr(message, "reply_to_message", None)
    return str(getattr(replied_to, "message_id", "") or "")


def resolve_telegram_receipt_request(
    text: str,
    *,
    surface: str,
    bot_identity: str,
    chat_id: str | int,
    message: Any,
    db_path: str | Path | None = None,
) -> ReceiptResolution | None:
    return resolve_receipt_request(
        text,
        surface=surface,
        bot_identity=bot_identity,
        chat_id=str(chat_id),
        reply_to_message_id=reply_to_message_id(message),
        db_path=receipt_index_path(db_path),
    )


def _canonical_contract_receipt(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    nested = value.get("receipt")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        for key in ("action", "receipt_pointer", "receipt_persisted"):
            if key not in merged and key in value:
                merged[key] = value[key]
        return merged
    return value


def contract_delivery_descriptor(
    receipt: Mapping[str, Any] | None,
    *,
    actor: str,
    surface: str,
    provider_surface: str | None = None,
    occurred_at: str | None = None,
    workflow_db_path: str | Path | None = None,
    contract_db_path: str | Path | None = None,
) -> ReceiptDescriptor | None:
    """Describe only provider receipts that already resolve durably."""

    canonical = _canonical_contract_receipt(receipt)
    actor_value = str(actor or "").strip().lower()
    delivery_surface_value = str(surface or "").strip()
    expected_provider_surface = _PROVIDER_SURFACE_BY_DELIVERY.get(
        (actor_value, delivery_surface_value)
    )
    provider_surface_value = str(provider_surface or delivery_surface_value).strip()
    if (
        expected_provider_surface is None
        or provider_surface_value != expected_provider_surface
    ):
        return None
    action = str(canonical.get("action") or "").strip().lower()
    raw_ref = str(canonical.get("receipt_pointer") or "").strip()
    if not raw_ref:
        return None
    if action == "stage_handoff":
        from workflow_package_queue import DEFAULT_SQLITE_PATH, resolve_workflow_receipt

        provider_path = Path(
            workflow_db_path
            or os.environ.get(WORKFLOW_RECEIPT_DB_ENV)
            or DEFAULT_SQLITE_PATH
        )
        provider_receipt = resolve_workflow_receipt(raw_ref, sqlite_path=provider_path)
        if provider_receipt is None:
            return None
        if str(provider_receipt.get("workflow_ref") or "") not in {
            "live_arts_md_invoice_workflow",
            "cassandra_receivables_nudge_handoff",
        }:
            return None
        if str(provider_receipt.get("source_surface") or "").strip() != provider_surface_value:
            return None
        when = occurred_at or str(provider_receipt.get("created_at") or "")
        if not when:
            when = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return build_receipt_descriptor(
            provider="workflow",
            raw_ref=raw_ref,
            what_happened="A bounded workflow handoff was staged for Cassandra.",
            status="Staged for review; unclaimed and unexecuted.",
            occurred_at=when,
            authority_summary="Queue record only; no business-action authority was granted.",
            no_action_facts=(
                "Nothing was sent.",
                "Nothing was posted to the ledger or changed.",
            ),
            durable=True,
        )

    if action != "preserve_session" or canonical.get("receipt_persisted") is not True:
        return None
    from typed_contract_decision import (
        contract_receipt_binding_sha256,
        resolve_contract_receipt,
    )

    provider_receipt = resolve_contract_receipt(
        raw_ref,
        path=contract_db_path,
    )
    if provider_receipt is None:
        return None
    stored_binding = str(provider_receipt.get("binding_sha256") or "")
    expected_binding = contract_receipt_binding_sha256(actor, provider_surface_value)
    if not stored_binding or stored_binding != expected_binding:
        return None
    created_at_epoch_ms = int(provider_receipt.get("created_at_epoch_ms") or 0)
    provider_occurred_at = (
        datetime.fromtimestamp(created_at_epoch_ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        if created_at_epoch_ms > 0
        else ""
    )
    when = occurred_at or provider_occurred_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    actor_name = _ACTOR_NAMES[actor_value]
    return build_receipt_descriptor(
        provider="typed_contract",
        raw_ref=raw_ref,
        what_happened=f"{actor_name} preserved the active conversation session.",
        status="Session preserved; no workflow action ran.",
        occurred_at=when,
        authority_summary="Conversation continuity only; no business-action authority was granted.",
        no_action_facts=(
            "Nothing was sent.",
            "No ledger, payment, or workflow action ran.",
        ),
        durable=True,
    )


def register_telegram_delivery(
    descriptor: ReceiptDescriptor | None,
    *,
    surface: str,
    bot_identity: str,
    chat_id: str | int,
    source_message_id: str | int,
    delivered_message: Any,
    db_path: str | Path | None = None,
) -> RegistrationResult | None:
    """Index a receipt only when Telegram returned both message identities."""

    if descriptor is None:
        return None
    inbound_id = str(source_message_id or "").strip()
    outbound_id = str(getattr(delivered_message, "message_id", "") or "").strip()
    if not inbound_id or not outbound_id:
        return None
    return register_delivered_receipt(
        descriptor,
        surface=surface,
        bot_identity=bot_identity,
        chat_id=str(chat_id),
        source_message_id=inbound_id,
        delivered_message_id=outbound_id,
        delivery_succeeded=True,
        db_path=receipt_index_path(db_path),
    )


def render_verified_receipt_reply(
    text: Any,
    descriptor: ReceiptDescriptor | None,
    *,
    raw_ref: str = "",
) -> str:
    pointer = descriptor.raw_ref if descriptor is not None else str(raw_ref or "")
    return render_receipt_safe_visible_text(
        text,
        raw_ref=pointer,
        advertise=descriptor is not None,
    )


__all__ = [
    "contract_delivery_descriptor",
    "receipt_index_path",
    "register_telegram_delivery",
    "render_verified_receipt_reply",
    "reply_to_message_id",
    "resolve_telegram_receipt_request",
]
