"""Default-off Cassandra delivery to Winship's authorized Telegram.

This module is for internal operator delivery only. It never sends to an
external client, never touches SEND_HOLD, and never calls Telegram unless
Winship enables the documented toggle.

Toggle, default off:
  - env: CASSANDRA_TELEGRAM_DELIVERY_ENABLED=1
  - or flag file: /mnt/c/OpenClaw/logs/cassandra_telegram_delivery_enabled.flag

When the toggle is off, delivery writes a dry-run receipt to:
  /mnt/c/OpenClaw/logs/cassandra_telegram_delivery_dryrun.jsonl
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from morning_brief_failover import (
    DETERMINISTIC_PROVIDER,
    PROVIDER_ORDER,
    MorningBriefFacts,
    MorningBriefResult,
    build_guardian_morning_brief,
    load_morning_brief_facts,
    run_morning_brief_failover,
)


SCHEMA_VERSION = "cassandra_telegram_delivery_v0"
TOGGLE_ENV_VAR = "CASSANDRA_TELEGRAM_DELIVERY_ENABLED"
AUTHORIZED_USER_ID_ENV_VAR = "TELEGRAM_AUTHORIZED_USER_ID"
DEFAULT_TOGGLE_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_telegram_delivery_enabled.flag")
DEFAULT_DRY_RUN_LOG_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_telegram_delivery_dryrun.jsonl")
DEFAULT_OPERATOR_BRIEF_PATH = Path("/mnt/e/openclaw/orchestration/artifacts/cassandra_operator_brief.md")
TRUTHY = {"1", "true", "yes", "on", "enabled"}

DeliverySender = Callable[[str], Any]
TelegramSender = Callable[..., Any]


@dataclass(frozen=True)
class TelegramDeliveryReceipt:
    status: str
    delivery_kind: str
    message_text: str
    message_hash: str
    target_ref: str
    toggle_enabled: bool
    dry_run: bool
    sent: bool
    telegram_send_attempted: bool
    telegram_sender_called: bool
    authorized_telegram_only: bool = True
    authorized_telegram_user_id_configured: bool = False
    external_client_send_performed: bool = False
    email_send_performed: bool = False
    send_hold_touched: bool = False
    log_path: str = ""
    log_error: str = ""
    failover_provider: str = ""
    failover_attempts: tuple[dict[str, Any], ...] = ()
    source_refs: tuple[str, ...] = ()
    error_type: str = ""
    error: str = ""
    created_at: str = ""

    def to_dict(self, *, include_message_text: bool = True) -> dict[str, Any]:
        data = asdict(self)
        data["failover_attempts"] = [dict(item) for item in self.failover_attempts]
        data["source_refs"] = list(self.source_refs)
        if not include_message_text:
            data.pop("message_text", None)
        return data


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\x00", "")).strip()


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _clip(text: str, *, limit: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[:limit].rstrip()
    boundary = clipped.rfind(" ")
    if boundary >= max(80, limit // 3):
        clipped = clipped[:boundary]
    return clipped.rstrip(" .,;:") + "..."


def telegram_delivery_enabled(
    *,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = DEFAULT_TOGGLE_PATH,
) -> bool:
    env_map = os.environ if env is None else env
    env_value = str(env_map.get(TOGGLE_ENV_VAR) or "").strip().lower()
    return env_value in TRUTHY or Path(toggle_path).is_file()


def build_telegram_delivery_status(
    *,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = DEFAULT_TOGGLE_PATH,
    dry_run_log_path: str | Path = DEFAULT_DRY_RUN_LOG_PATH,
) -> dict[str, Any]:
    env_map = os.environ if env is None else env
    enabled = telegram_delivery_enabled(env=env_map, toggle_path=toggle_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "delivery_surface": "telegram_operator_internal",
        "toggle_env_var": TOGGLE_ENV_VAR,
        "toggle_path": str(toggle_path),
        "toggle_default": "off",
        "toggle_enabled": enabled,
        "dry_run_log_path": str(dry_run_log_path),
        "default_when_off": "dry_run_to_log",
        "authorized_user_id_env_var": AUTHORIZED_USER_ID_ENV_VAR,
        "authorized_telegram_user_id_configured": bool(str(env_map.get(AUTHORIZED_USER_ID_ENV_VAR) or "").strip()),
        "operator_only": True,
        "external_client_send_allowed": False,
        "send_hold_touched": False,
        "telegram_delivery_state": "enabled_operator_only" if enabled else "dry_run_to_log_toggle_off",
    }


def _read_operator_brief(path: str | Path) -> tuple[str, str]:
    target = Path(path)
    if not target.is_file():
        return "", "operator_brief_missing"
    try:
        return target.read_text(encoding="utf-8", errors="replace"), str(target)
    except Exception as exc:
        return "", f"operator_brief_read_failed:{type(exc).__name__}"


def _operator_brief_from_artifact(
    artifact_text: str,
    facts: MorningBriefFacts,
    *,
    provider_name: str,
) -> str:
    artifact = _clip(artifact_text, limit=2600)
    if len(artifact) < 40:
        return ""
    return (
        f"{provider_name} operator brief. "
        f"{artifact} "
        f"Ledger check: open approval packets {facts.pending_approval_packets}; "
        f"pending side effects {facts.pending_side_effects}; "
        f"open packet records {facts.open_packet_count}. "
        f"Latest ledger note: {_clip(facts.latest_event_summary, limit=240)} "
        "No external send was attempted."
    )


def _operator_brief_providers(artifact_text: str) -> dict[str, Any]:
    return {
        "cassandra": lambda facts: _operator_brief_from_artifact(
            artifact_text,
            facts,
            provider_name="Cassandra",
        ),
        "chief": lambda facts: _operator_brief_from_artifact(
            artifact_text,
            facts,
            provider_name="Chief failover",
        ),
        "hermes": lambda facts: _operator_brief_from_artifact(
            artifact_text,
            facts,
            provider_name="Hermes failover",
        ),
        "guardian": build_guardian_morning_brief,
    }


def build_operator_brief_message(
    *,
    brief_path: str | Path = DEFAULT_OPERATOR_BRIEF_PATH,
    db_path: str | Path | None = None,
    facts: MorningBriefFacts | None = None,
    now: datetime | None = None,
) -> MorningBriefResult:
    artifact_text, source_note = _read_operator_brief(brief_path)
    loaded_facts = facts or load_morning_brief_facts(db_path=db_path, now=now)
    source_notes = tuple(dict.fromkeys(tuple(loaded_facts.source_notes) + (source_note,)))
    enriched_facts = replace(loaded_facts, source_notes=source_notes)
    return run_morning_brief_failover(
        providers=_operator_brief_providers(artifact_text),
        facts=enriched_facts,
        order=PROVIDER_ORDER,
    )


def _resolve_authorized_chat_id(
    *,
    env: Mapping[str, str],
    authorized_chat_id: str | int | None,
) -> tuple[str, str, str]:
    configured = str(env.get(AUTHORIZED_USER_ID_ENV_VAR) or "").strip()
    if authorized_chat_id is not None and str(authorized_chat_id).strip():
        explicit = str(authorized_chat_id).strip()
        if configured and explicit != configured:
            return "", "unauthorized_target_mismatch", f"env:{AUTHORIZED_USER_ID_ENV_VAR}"
        return explicit, "explicit_authorized_chat_id", "explicit_authorized_chat_id"
    if configured:
        return configured, "configured", f"env:{AUTHORIZED_USER_ID_ENV_VAR}"
    return "", "missing", f"env:{AUTHORIZED_USER_ID_ENV_VAR}"


def _append_receipt_log(
    receipt: TelegramDeliveryReceipt,
    *,
    dry_run_log_path: str | Path,
) -> str:
    try:
        path = Path(dry_run_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.open("a", encoding="utf-8").write(stable_json(receipt.to_dict(include_message_text=False)))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return ""


def _default_telegram_sender(message_text: str, *, chat_id: str) -> Any:
    from cassandra_sender import send_message

    return send_message(message_text, chat_id=chat_id)


def deliver_to_authorized_telegram(
    *,
    message_text: str,
    delivery_kind: str,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = DEFAULT_TOGGLE_PATH,
    dry_run_log_path: str | Path = DEFAULT_DRY_RUN_LOG_PATH,
    authorized_chat_id: str | int | None = None,
    telegram_sender: TelegramSender | None = None,
    failover_result: MorningBriefResult | None = None,
    source_refs: tuple[str, ...] = (),
) -> TelegramDeliveryReceipt:
    env_map = os.environ if env is None else env
    enabled = telegram_delivery_enabled(env=env_map, toggle_path=toggle_path)
    target, target_status, target_ref = _resolve_authorized_chat_id(
        env=env_map,
        authorized_chat_id=authorized_chat_id,
    )
    created_at = utc_now()
    base = {
        "delivery_kind": delivery_kind,
        "message_text": message_text,
        "message_hash": _hash_text(message_text),
        "target_ref": target_ref,
        "toggle_enabled": enabled,
        "authorized_telegram_user_id_configured": bool(target),
        "log_path": str(dry_run_log_path),
        "failover_provider": failover_result.provider if failover_result else "",
        "failover_attempts": tuple(attempt.to_dict() for attempt in failover_result.attempts) if failover_result else (),
        "source_refs": source_refs,
        "created_at": created_at,
    }

    if target_status == "unauthorized_target_mismatch":
        receipt = TelegramDeliveryReceipt(
            status="blocked_unauthorized_telegram_target",
            dry_run=True,
            sent=False,
            telegram_send_attempted=False,
            telegram_sender_called=False,
            **base,
        )
        log_error = _append_receipt_log(receipt, dry_run_log_path=dry_run_log_path)
        return replace(receipt, log_error=log_error) if log_error else receipt

    if not enabled:
        receipt = TelegramDeliveryReceipt(
            status="dry_run_logged_toggle_off",
            dry_run=True,
            sent=False,
            telegram_send_attempted=False,
            telegram_sender_called=False,
            **base,
        )
        log_error = _append_receipt_log(receipt, dry_run_log_path=dry_run_log_path)
        return replace(receipt, log_error=log_error) if log_error else receipt

    if not target:
        receipt = TelegramDeliveryReceipt(
            status="blocked_missing_authorized_telegram_id",
            dry_run=True,
            sent=False,
            telegram_send_attempted=False,
            telegram_sender_called=False,
            **base,
        )
        log_error = _append_receipt_log(receipt, dry_run_log_path=dry_run_log_path)
        return replace(receipt, log_error=log_error) if log_error else receipt

    sender = telegram_sender or _default_telegram_sender
    try:
        sender(message_text, chat_id=target)
    except Exception as exc:
        receipt = TelegramDeliveryReceipt(
            status="telegram_delivery_failed",
            dry_run=False,
            sent=False,
            telegram_send_attempted=True,
            telegram_sender_called=True,
            error_type=type(exc).__name__,
            error=str(exc)[:240],
            **base,
        )
        log_error = _append_receipt_log(receipt, dry_run_log_path=dry_run_log_path)
        return replace(receipt, log_error=log_error) if log_error else receipt

    receipt = TelegramDeliveryReceipt(
        status="sent_to_authorized_telegram",
        dry_run=False,
        sent=True,
        telegram_send_attempted=True,
        telegram_sender_called=True,
        **base,
    )
    log_error = _append_receipt_log(receipt, dry_run_log_path=dry_run_log_path)
    return replace(receipt, log_error=log_error) if log_error else receipt


def deliver_operator_brief_to_telegram(
    *,
    brief_path: str | Path = DEFAULT_OPERATOR_BRIEF_PATH,
    db_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = DEFAULT_TOGGLE_PATH,
    dry_run_log_path: str | Path = DEFAULT_DRY_RUN_LOG_PATH,
    authorized_chat_id: str | int | None = None,
    telegram_sender: TelegramSender | None = None,
    now: datetime | None = None,
) -> TelegramDeliveryReceipt:
    failover_result = build_operator_brief_message(brief_path=brief_path, db_path=db_path, now=now)
    source_refs = tuple(failover_result.facts.source_notes) + (str(brief_path), str(failover_result.facts.ledger_path))
    return deliver_to_authorized_telegram(
        message_text=failover_result.text,
        delivery_kind="operator_brief",
        env=env,
        toggle_path=toggle_path,
        dry_run_log_path=dry_run_log_path,
        authorized_chat_id=authorized_chat_id,
        telegram_sender=telegram_sender,
        failover_result=failover_result,
        source_refs=tuple(dict.fromkeys(source_refs)),
    )


def build_reynolds_package_message(
    *,
    intro_email_summary: str,
    invoice_pdf_path: str | Path,
) -> str:
    summary = _clip(intro_email_summary, limit=900) or "Intro email summary is ready for operator review."
    invoice_ref = str(invoice_pdf_path or "").strip() or "invoice PDF path not provided"
    return (
        "Reynolds package is ready for Winship review. "
        f"Intro-email summary: {summary} "
        f"Invoice PDF pointer: {invoice_ref}. "
        "Display only: the external email send remains Lane A gated, SEND_HOLD-bound, and requires Winship's explicit go."
    )


def deliver_reynolds_package_to_telegram(
    *,
    intro_email_summary: str,
    invoice_pdf_path: str | Path,
    package_ready: bool,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = DEFAULT_TOGGLE_PATH,
    dry_run_log_path: str | Path = DEFAULT_DRY_RUN_LOG_PATH,
    authorized_chat_id: str | int | None = None,
    telegram_sender: TelegramSender | None = None,
) -> TelegramDeliveryReceipt:
    if not package_ready:
        message = (
            "Reynolds package is not ready yet. Cassandra will not notify Telegram until the package has a "
            "reviewable intro-email summary and invoice PDF pointer."
        )
        return deliver_to_authorized_telegram(
            message_text=message,
            delivery_kind="reynolds_package_not_ready",
            env=env,
            toggle_path=toggle_path,
            dry_run_log_path=dry_run_log_path,
            authorized_chat_id=authorized_chat_id,
            telegram_sender=telegram_sender,
            source_refs=("reynolds_package_not_ready",),
        )

    message = build_reynolds_package_message(
        intro_email_summary=intro_email_summary,
        invoice_pdf_path=invoice_pdf_path,
    )
    return deliver_to_authorized_telegram(
        message_text=message,
        delivery_kind="reynolds_package",
        env=env,
        toggle_path=toggle_path,
        dry_run_log_path=dry_run_log_path,
        authorized_chat_id=authorized_chat_id,
        telegram_sender=telegram_sender,
        source_refs=("reynolds_package", str(invoice_pdf_path)),
    )


__all__ = [
    "AUTHORIZED_USER_ID_ENV_VAR",
    "DEFAULT_DRY_RUN_LOG_PATH",
    "DEFAULT_OPERATOR_BRIEF_PATH",
    "DEFAULT_TOGGLE_PATH",
    "DETERMINISTIC_PROVIDER",
    "PROVIDER_ORDER",
    "SCHEMA_VERSION",
    "TOGGLE_ENV_VAR",
    "TelegramDeliveryReceipt",
    "build_operator_brief_message",
    "build_reynolds_package_message",
    "build_telegram_delivery_status",
    "deliver_operator_brief_to_telegram",
    "deliver_reynolds_package_to_telegram",
    "deliver_to_authorized_telegram",
    "telegram_delivery_enabled",
]
