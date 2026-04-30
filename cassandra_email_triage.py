from __future__ import annotations

"""
cassandra_email_triage.py

Pure metadata-only training helpers for Cassandra email triage.

This module records operator-confirmed classifications from Gmail metadata
only. It does not read Gmail bodies, call brokers, send Telegram messages,
create drafts, request approval, send email, move mail, label mail, or call
models.
"""

import json
import re
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from typing import Iterable


EMAIL_TRIAGE_SCHEMA_VERSION = 1
EMAIL_TRIAGE_EVENT_TYPE_CLASSIFICATION = "email_triage_classification"
EMAIL_TRIAGE_SOURCE_CAPABILITY = "google.gmail.read.metadata"

EMAIL_TRIAGE_TRAINING_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_email_triage_training.jsonl")

EMAIL_TRIAGE_CATEGORIES = (
    "junk",
    "promotional",
    "useful_promo",
    "newsletter",
    "receipt",
    "invoice_payment",
    "gig_lead",
    "client_vendor",
    "travel_hotel_event",
    "music_business_admin",
    "sensitive_legal_cpa_musiclaw_publishing",
    "unknown_manual_review",
)

EMAIL_TRIAGE_SUGGESTED_HANDLINGS = (
    "ignore_future_similar",
    "ask_again_next_time",
    "suggest_folder_or_label",
    "manual_review",
    "possible_follow_up_later",
)

SENSITIVE_EMAIL_TRIAGE_CATEGORY = "sensitive_legal_cpa_musiclaw_publishing"
MANUAL_REVIEW_HANDLING = "manual_review"

_VALID_EMAIL_TRIAGE_CATEGORIES = set(EMAIL_TRIAGE_CATEGORIES)
_VALID_EMAIL_TRIAGE_SUGGESTED_HANDLINGS = set(EMAIL_TRIAGE_SUGGESTED_HANDLINGS)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _preview(value: object, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _metadata_value(metadata: dict | None, *names: str) -> object:
    data = metadata if isinstance(metadata, dict) else {}
    for name in names:
        value = data.get(name)
        if value not in (None, "", []):
            return value
    return ""


def _normalize_sender_email(value: object) -> str:
    parsed = parseaddr(str(value or "").strip())[1].strip().lower()
    if not parsed:
        return ""
    return parsed


def derive_sender_domain(sender_email: object) -> str:
    """Return a lowercase domain from a sender email, or an empty string."""
    email = _normalize_sender_email(sender_email)
    if "@" not in email:
        return ""
    local_part, domain = email.rsplit("@", 1)
    domain = domain.strip().strip("[]").rstrip(".").lower()
    if not local_part or not domain or any(ch.isspace() for ch in domain):
        return ""
    return domain


def _normalize_labels(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_labels: Iterable[object] = [value]
    elif isinstance(value, Iterable):
        raw_labels = value
    else:
        raw_labels = [value]

    labels: list[str] = []
    seen: set[str] = set()
    for raw_label in raw_labels:
        label = str(raw_label or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _normalize_sensitivity_flags(value: object, operator_classification: str) -> list[str]:
    if isinstance(value, dict):
        raw_flags: Iterable[object] = [key for key, enabled in value.items() if enabled]
    elif isinstance(value, str):
        raw_flags = [value] if value.strip() else []
    elif isinstance(value, Iterable):
        raw_flags = value
    else:
        raw_flags = []

    flags: list[str] = []
    seen: set[str] = set()
    for raw_flag in raw_flags:
        flag = str(raw_flag or "").strip().lower()
        if not flag or flag in seen:
            continue
        seen.add(flag)
        flags.append(flag)

    if operator_classification == SENSITIVE_EMAIL_TRIAGE_CATEGORY and "sensitive_category" not in seen:
        flags.append("sensitive_category")
    return flags


def _normalize_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except Exception as exc:
        raise ValueError("confidence must be a number between 0 and 1") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")
    return confidence


def _validate_required_ids(message_id: str, thread_id: str) -> None:
    if not message_id:
        raise ValueError("message_id is required")
    if not thread_id:
        raise ValueError("thread_id is required")


def _validate_classification(operator_classification: str) -> str:
    classification = str(operator_classification or "").strip().lower()
    if classification not in _VALID_EMAIL_TRIAGE_CATEGORIES:
        raise ValueError(f"invalid operator_classification: {operator_classification}")
    return classification


def _validate_suggested_handling(future_suggested_handling: str, operator_classification: str) -> str:
    handling = str(future_suggested_handling or "").strip().lower()
    if handling not in _VALID_EMAIL_TRIAGE_SUGGESTED_HANDLINGS:
        raise ValueError(f"invalid future_suggested_handling: {future_suggested_handling}")
    if operator_classification == SENSITIVE_EMAIL_TRIAGE_CATEGORY and handling != MANUAL_REVIEW_HANDLING:
        raise ValueError("sensitive classifications require manual_review handling")
    return handling


def _normalized_metadata_fields(
    metadata: dict | None,
    *,
    message_id: str = "",
    thread_id: str = "",
    sender_name: str = "",
    sender_email: str = "",
    subject: str = "",
    snippet: str = "",
    gmail_labels_seen: object = None,
) -> dict:
    normalized_message_id = str(message_id or _metadata_value(metadata, "message_id")).strip()
    normalized_thread_id = str(thread_id or _metadata_value(metadata, "thread_id")).strip()
    _validate_required_ids(normalized_message_id, normalized_thread_id)

    normalized_sender_name = _preview(sender_name or _metadata_value(metadata, "sender_name", "from_name"), 120)
    normalized_sender_email = _normalize_sender_email(
        sender_email or _metadata_value(metadata, "sender_email", "from_email")
    )
    labels_source = gmail_labels_seen if gmail_labels_seen is not None else _metadata_value(
        metadata,
        "gmail_labels_seen",
        "labels",
    )

    return {
        "message_id": normalized_message_id,
        "thread_id": normalized_thread_id,
        "sender_name": normalized_sender_name,
        "sender_email": normalized_sender_email,
        "sender_domain": derive_sender_domain(normalized_sender_email),
        "subject_preview": _preview(subject or _metadata_value(metadata, "subject", "subject_preview"), 180),
        "snippet_preview": _preview(snippet or _metadata_value(metadata, "snippet", "snippet_preview"), 260),
        "gmail_labels_seen": _normalize_labels(labels_source),
    }


def build_email_triage_operator_prompt(metadata: dict) -> str:
    """Build a metadata-only operator prompt for email triage training."""
    fields = _normalized_metadata_fields(metadata)
    labels = ", ".join(fields["gmail_labels_seen"]) or "none"
    sender = fields["sender_name"] or "unknown sender"
    if fields["sender_email"]:
        sender = f"{sender} <{fields['sender_email']}>"

    category_lines = "\n".join(f"- {category}" for category in EMAIL_TRIAGE_CATEGORIES)
    handling_lines = "\n".join(f"- {handling}" for handling in EMAIL_TRIAGE_SUGGESTED_HANDLINGS)

    return (
        "Cassandra email triage training\n\n"
        f"Source: {EMAIL_TRIAGE_SOURCE_CAPABILITY} (metadata and snippet only)\n"
        f"Message ID: {fields['message_id']}\n"
        f"Thread ID: {fields['thread_id']}\n"
        f"Sender: {sender}\n"
        f"Sender domain: {fields['sender_domain'] or 'unknown'}\n"
        f"Subject: {fields['subject_preview'] or '(no subject)'}\n"
        f"Snippet: {fields['snippet_preview'] or '(no snippet)'}\n"
        f"Gmail labels seen: {labels}\n\n"
        "Choose one operator classification:\n"
        f"{category_lines}\n\n"
        "Choose one future suggested handling:\n"
        f"{handling_lines}\n\n"
        "Sensitive Legal, CPA, Music Law, Publishing, or private professional items "
        "must stay in manual review. Do not classify from message body content here."
    )


def _triage_log_path(log_path: Path | str | None = None) -> Path:
    return Path(log_path) if log_path is not None else EMAIL_TRIAGE_TRAINING_LOG


def record_email_triage_classification(
    *,
    metadata: dict | None = None,
    message_id: str = "",
    thread_id: str = "",
    sender_name: str = "",
    sender_email: str = "",
    subject: str = "",
    snippet: str = "",
    gmail_labels_seen: object = None,
    operator_classification: str,
    future_suggested_handling: str,
    confidence: object = 1.0,
    classification_source: str = "operator",
    sensitivity_flags: object = None,
    created_at: str | None = None,
    log_path: Path | str | None = None,
) -> dict:
    """Append one operator-confirmed email triage classification to JSONL."""
    classification = _validate_classification(operator_classification)
    handling = _validate_suggested_handling(future_suggested_handling, classification)
    source = str(classification_source or "").strip().lower()
    if not source:
        raise ValueError("classification_source is required")

    fields = _normalized_metadata_fields(
        metadata,
        message_id=message_id,
        thread_id=thread_id,
        sender_name=sender_name,
        sender_email=sender_email,
        subject=subject,
        snippet=snippet,
        gmail_labels_seen=gmail_labels_seen,
    )
    entry = {
        "schema_version": EMAIL_TRIAGE_SCHEMA_VERSION,
        "event_type": EMAIL_TRIAGE_EVENT_TYPE_CLASSIFICATION,
        "created_at": str(created_at or _now()),
        **fields,
        "operator_classification": classification,
        "future_suggested_handling": handling,
        "confidence": _normalize_confidence(confidence),
        "classification_source": source,
        "sensitivity_flags": _normalize_sensitivity_flags(sensitivity_flags, classification),
        "source_capability": EMAIL_TRIAGE_SOURCE_CAPABILITY,
    }

    path = _triage_log_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def _normalize_triage_record(raw_entry: dict, log_index: int) -> dict:
    entry = dict(raw_entry)
    entry["schema_version"] = int(entry.get("schema_version", EMAIL_TRIAGE_SCHEMA_VERSION) or EMAIL_TRIAGE_SCHEMA_VERSION)
    entry["event_type"] = str(entry.get("event_type", EMAIL_TRIAGE_EVENT_TYPE_CLASSIFICATION) or "").strip()
    entry["created_at"] = str(entry.get("created_at", "") or "").strip()
    entry["message_id"] = str(entry.get("message_id", "") or "").strip()
    entry["thread_id"] = str(entry.get("thread_id", "") or "").strip()
    entry["sender_name"] = str(entry.get("sender_name", "") or "").strip()
    entry["sender_email"] = _normalize_sender_email(entry.get("sender_email", ""))
    entry["sender_domain"] = str(entry.get("sender_domain") or derive_sender_domain(entry["sender_email"]))
    entry["subject_preview"] = str(entry.get("subject_preview", "") or "").strip()
    entry["snippet_preview"] = str(entry.get("snippet_preview", "") or "").strip()
    entry["gmail_labels_seen"] = _normalize_labels(entry.get("gmail_labels_seen", []))
    entry["operator_classification"] = str(entry.get("operator_classification", "") or "").strip().lower()
    entry["future_suggested_handling"] = str(entry.get("future_suggested_handling", "") or "").strip().lower()
    entry["classification_source"] = str(entry.get("classification_source", "") or "").strip().lower()
    entry["sensitivity_flags"] = _normalize_sensitivity_flags(
        entry.get("sensitivity_flags", []),
        entry["operator_classification"],
    )
    entry["source_capability"] = str(entry.get("source_capability", EMAIL_TRIAGE_SOURCE_CAPABILITY) or "").strip()
    try:
        entry["confidence"] = _normalize_confidence(entry.get("confidence", 1.0))
    except ValueError:
        entry["confidence"] = 0.0
    entry["_log_index"] = log_index
    return entry


def load_email_triage_classifications(
    *,
    log_path: Path | str | None = None,
    include_invalid: bool = False,
) -> list[dict]:
    """Replay email triage classification records without mutating the log."""
    path = _triage_log_path(log_path)
    if not path.exists():
        return []

    classifications: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for log_index, raw_line in enumerate(handle):
            line = raw_line.strip()
            if not line:
                continue
            try:
                raw_entry = json.loads(line)
                if not isinstance(raw_entry, dict):
                    raise ValueError("line is not a JSON object")
            except Exception as exc:
                if include_invalid:
                    classifications.append({
                        "_log_index": log_index,
                        "_invalid_reason": str(exc),
                        "_raw_line": line,
                    })
                continue
            classifications.append(_normalize_triage_record(raw_entry, log_index))
    return classifications