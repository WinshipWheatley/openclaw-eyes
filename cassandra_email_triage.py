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

_UNSAFE_OPERATOR_RESPONSE_PATTERNS = (
    r"\bdelete\s+(it|this|that|the\s+email|the\s+message)?\b",
    r"\btrash\s+(it|this|that|the\s+email|the\s+message)?\b",
    r"\barchive\s+(it|this|that|the\s+email|the\s+message)?\b",
    r"\bmove\s+(it|this|that|the\s+email|the\s+message)?\b",
    r"\blabel\s+(it|this|that|the\s+email|the\s+message)?\b",
    r"\breply\s+(to\s+it|to\s+this|to\s+that|to\s+the\s+email|to\s+the\s+message)?\b",
    r"\bsend\s+(an?\s+)?(email|message|reply)\b",
    r"\bcreate\s+(a\s+)?draft\b",
    r"\bdraft\s+(a\s+)?(reply|response|email|message)\b",
)

_RESPONSE_RULES = (
    (r"\bnot\s+sure\b|\bunsure\b|\bunknown\b|\bmanual\s+review\b", "unknown_manual_review", "manual_review"),
    (r"\bsensitive\b|\blegal\b|\bcpa\b|\bmusic\s+law\b|\bpublishing\b", "sensitive_legal_cpa_musiclaw_publishing", "manual_review"),
    (r"\buseful\s+(promo|promotion|promotional)\b|\bpromo\b.*\buseful\b", "useful_promo", "possible_follow_up_later"),
    (r"\bpromo\b|\bpromotional\b|\bpromotion\b", "promotional", "suggest_folder_or_label"),
    (r"\bnewsletter\b", "newsletter", "suggest_folder_or_label"),
    (r"\breceipt\b", "receipt", "suggest_folder_or_label"),
    (r"\binvoice\b|\bpayment\b", "invoice_payment", "possible_follow_up_later"),
    (r"\bgig\s+lead\b|\blead\b.*\bgig\b", "gig_lead", "possible_follow_up_later"),
    (r"\bclient\b|\bvendor\b", "client_vendor", "manual_review"),
    (r"\btravel\b|\bhotel\b|\bevent\b", "travel_hotel_event", "suggest_folder_or_label"),
    (r"\bmusic\s+(business|admin|administration)\b", "music_business_admin", "possible_follow_up_later"),
    (r"\bjunk\b|\bspam\b|\bgarbage\b", "junk", "ignore_future_similar"),
)

_FULL_MESSAGE_FIELD_NAMES = {
    "body",
    "body_text",
    "payload",
    "raw",
    "mime",
    "parts",
    "messages",
    "full_message",
}

_CANDIDATE_TEXT_FIELD_NAMES = (
    "from_name",
    "sender_name",
    "from_email",
    "sender_email",
    "sender_domain",
    "subject",
    "subject_preview",
    "snippet",
    "snippet_preview",
)

_SENSITIVE_CANDIDATE_PATTERNS = (
    r"\blegal\b",
    r"\blaw\s+firm\b",
    r"\battorney\b",
    r"\blawyer\b",
    r"\bcounsel\b",
    r"\bcourt\b",
    r"\blawsuit\b",
    r"\bsubpoena\b",
    r"\bretainer\b",
    r"\bcpa\b",
    r"\btax(?:es)?\b",
    r"\birs\b",
    r"\baccountant\b",
    r"\bmusic\s+law\b",
    r"\bpublishing\b",
    r"\bpublisher\b",
    r"\bprivate\s+correspondence\b",
    r"\bconfidential\b",
    r"\bprivileged\b",
)

_SENSITIVE_BUSINESS_CANDIDATE_PATTERNS = (
    r"\b(client|vendor|gig)\b.*\b(payment|invoice|contract|wire|bank|due|overdue)\b",
    r"\b(payment|invoice|contract|wire|bank|due|overdue)\b.*\b(client|vendor|gig)\b",
)

_LOW_RISK_CANDIDATE_SCORES = (
    (0, (r"\bjunk\b", r"\bspam\b", r"\bcategory_spam\b")),
    (10, (r"\bnewsletter\b", r"\bunsubscribe\b", r"\bdigest\b")),
    (
        20,
        (
            r"\bpromo(?:tional|tion)?\b",
            r"\bcategory_promotions\b",
            r"\bmarketing\b",
            r"\bsale\b",
            r"\bdeal\b",
            r"\boffer\b",
            r"\bcoupon\b",
            r"\bdiscount\b",
            r"\bclearance\b",
        ),
    ),
    (40, (r"\breceipt\b", r"\border\s+confirmation\b", r"\bpurchase\s+confirmation\b")),
)

_HIGHER_RISK_CANDIDATE_PATTERNS = (
    r"\binvoice\b",
    r"\bpayment\b",
    r"\bclient\b",
    r"\bvendor\b",
    r"\bgig\b",
    r"\blead\b",
)


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


def _contains_pattern(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _has_full_message_fields(metadata: dict) -> bool:
    return any(str(key or "").strip().lower() in _FULL_MESSAGE_FIELD_NAMES for key in metadata)


def _prior_triage_ids(prior_records: Iterable[dict] | None) -> tuple[set[str], set[str]]:
    message_ids: set[str] = set()
    thread_ids: set[str] = set()
    for raw_record in prior_records or []:
        if not isinstance(raw_record, dict):
            continue
        message_id = str(raw_record.get("message_id", "") or "").strip()
        thread_id = str(raw_record.get("thread_id", "") or "").strip()
        if message_id:
            message_ids.add(message_id)
        if thread_id:
            thread_ids.add(thread_id)
    return message_ids, thread_ids


def _candidate_text_blob(metadata: dict) -> str:
    text_parts: list[str] = []
    for field_name in _CANDIDATE_TEXT_FIELD_NAMES:
        value = _metadata_value(metadata, field_name)
        if value not in (None, "", []):
            text_parts.append(str(value))
    text_parts.extend(_normalize_labels(_metadata_value(metadata, "gmail_labels_seen", "labels")))
    return re.sub(r"\s+", " ", " ".join(text_parts)).strip().lower()


def _email_triage_candidate_score(metadata: dict) -> int | None:
    text = _candidate_text_blob(metadata)
    if _contains_pattern(text, _SENSITIVE_CANDIDATE_PATTERNS):
        return None
    if _contains_pattern(text, _SENSITIVE_BUSINESS_CANDIDATE_PATTERNS):
        return None

    for score, patterns in _LOW_RISK_CANDIDATE_SCORES:
        if _contains_pattern(text, patterns):
            return score
    if _contains_pattern(text, _HIGHER_RISK_CANDIDATE_PATTERNS):
        return 120
    return 80


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


def build_email_triage_training_question(metadata: dict) -> str:
    """Build the operator-facing triage question for one metadata record."""
    return (
        f"{build_email_triage_operator_prompt(metadata)}\n\n"
        "Reply with a simple classification such as junk, promo, useful promo, "
        "newsletter, receipt, invoice, gig lead, client, travel, or not sure. "
        "This records training intent only."
    )


def select_email_triage_training_candidate(
    messages: Iterable[dict] | None,
    prior_records: Iterable[dict] | None,
    *,
    suppress_prior_threads: bool = True,
) -> dict | None:
    """Return the safest next unclassified metadata record for triage training."""
    prior_message_ids, prior_thread_ids = _prior_triage_ids(prior_records)
    candidates: list[tuple[int, int, dict]] = []

    for index, message in enumerate(messages or []):
        if not isinstance(message, dict):
            continue
        if _has_full_message_fields(message):
            continue
        message_id = str(message.get("message_id", "") or "").strip()
        thread_id = str(message.get("thread_id", "") or "").strip()
        if not message_id or not thread_id:
            continue
        if message_id in prior_message_ids:
            continue
        if suppress_prior_threads and thread_id in prior_thread_ids:
            continue

        score = _email_triage_candidate_score(message)
        if score is None:
            continue
        candidates.append((score, index, dict(message)))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _unsafe_operator_response_reason(response_text: str) -> str:
    response = str(response_text or "").strip().lower()
    for pattern in _UNSAFE_OPERATOR_RESPONSE_PATTERNS:
        if re.search(pattern, response):
            return "unsafe_live_action_requested"
    return ""


def _classify_operator_response(response_text: str) -> tuple[str, str]:
    response = str(response_text or "").strip().lower()
    if not response:
        raise ValueError("response_text is required")

    unsafe_reason = _unsafe_operator_response_reason(response)
    if unsafe_reason:
        raise ValueError(f"unsafe operator response: {unsafe_reason}")

    for pattern, category, handling in _RESPONSE_RULES:
        if re.search(pattern, response):
            return category, handling

    return "unknown_manual_review", "manual_review"


def resolve_email_triage_operator_response(
    metadata: dict,
    response_text: str,
    *,
    confidence: object = 1.0,
    classification_source: str = "operator",
    sensitivity_flags: object = None,
    created_at: str | None = None,
    log_path: Path | str | None = None,
) -> dict:
    """Resolve a simple operator answer and record classification intent only."""
    classification, handling = _classify_operator_response(response_text)
    response_flags = sensitivity_flags
    if classification == SENSITIVE_EMAIL_TRIAGE_CATEGORY and response_flags is None:
        response_flags = ["operator_marked_sensitive"]

    entry = record_email_triage_classification(
        metadata=metadata,
        operator_classification=classification,
        future_suggested_handling=handling,
        confidence=confidence,
        classification_source=classification_source,
        sensitivity_flags=response_flags,
        created_at=created_at,
        log_path=log_path,
    )
    entry["operator_response_text"] = _preview(response_text, 180)
    return entry


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