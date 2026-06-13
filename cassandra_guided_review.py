"""Cassandra guided review sessions.

This module runs local, metadata-only review sessions over existing promotion
review artifacts. It records operator answers and receipts, but never promotes
reference data, changes runtime policy, creates approvals, or touches external
systems.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassandra_review_coach import (
    build_coach_card,
    coach_command,
    detect_coach_intent,
    parse_natural_reply_intent,
    render_coach_reply,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_ROOT = Path("/tmp/openclaw-mission-control/operator_skill_factory_v0")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_DURABLE_REVIEW_ROOT = Path("generated/system_knowledge/operator_skill_factory")
DEFAULT_LEGACY_DURABLE_REVIEW_ROOT = Path("generated/system_knowledge/operator_skill_factory_v0")
DEFAULT_PROMOTION_REVIEW_FILENAME = "openclaw_data_room_promotion_review_v0.json"
DEFAULT_PROMOTION_REVIEW_PATH = DEFAULT_REVIEW_ROOT / DEFAULT_PROMOTION_REVIEW_FILENAME
DEFAULT_DURABLE_PROMOTION_REVIEW_PATH = DEFAULT_DURABLE_REVIEW_ROOT / DEFAULT_PROMOTION_REVIEW_FILENAME
DEFAULT_LEGACY_DURABLE_PROMOTION_REVIEW_PATH = DEFAULT_LEGACY_DURABLE_REVIEW_ROOT / DEFAULT_PROMOTION_REVIEW_FILENAME
DEFAULT_RECEIPT_DIR_NAME = "data_room_guided_review_receipts"

SESSION_SCHEMA_VERSION = "REVIEW_SESSION_V0"
QUESTION_SCHEMA_VERSION = "REVIEW_QUESTION_V0"
ANSWER_SCHEMA_VERSION = "REVIEW_ANSWER_V0"
READ_MODEL_SCHEMA_VERSION = "guided_review_sessions_read_model_v0"
READ_MODEL_NAME = "guided_review_sessions.json"

SESSION_PREFIX = "data_room_guided_review_session"
PROMPT_PREFIX = "data_room_confirmed_reference_promotion_prompt"
ACTIVE_INDEX_NAME = "data_room_guided_review_active_session.json"

AUTHORITY_BOUNDARY = {
    "authoritative": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_generated": False,
    "external_calls_performed": False,
    "approval_created": False,
    "email_sent": False,
    "gmail_draft_created": False,
    "invoice_or_ledger_mutated": False,
    "workbook_pdf_coupa_bank_mutated": False,
    "tax_or_legal_advice_given": False,
}

CONTROL_WORDS = {
    "skip",
    "defer",
    "done",
    "summarize",
    "summary",
    "next",
    "next question",
    "revise previous",
    "why",
    "recommend",
    "examples",
    "use your recommendation",
}

EXCLUDED_ROUTE_TERMS = (
    "approve exact send request",
    "approve the exact send request",
    "exact send request",
    "send authority request",
    "prepare the send authority",
    "draft is approved",
    "draft approved",
    "approved with this exact text",
    "operator_action_approval_request",
    "guardian approval",
    "guardian decision",
)

REVIEWABLE_TOPIC_REGISTRY_SCHEMA_VERSION = "REVIEWABLE_TOPIC_REGISTRY_V0"
TOPIC_DATA_ROOM = "data_room_reference_review"
TOPIC_INVOICE_POLICY = "invoice_policy_review"
TOPIC_PERSONA_IDENTITY = "persona_identity_review"
TOPIC_PAYMENT_PRIVACY = "payment_privacy_review"
TOPIC_RATES_CLIENTS_VENUES = "rates_clients_venues_review"
TOPIC_NILES_CREATIVE = "niles_creative_reference_review"
TOPIC_SYSTEM_STATUS = "system_status_review"

LEGACY_TOPIC_ALIASES = {
    "data_room": TOPIC_DATA_ROOM,
    "invoice_policy": TOPIC_INVOICE_POLICY,
    "clara_reid_rules": TOPIC_PERSONA_IDENTITY,
}

REVIEWABLE_TOPIC_REGISTRY_V0: tuple[dict[str, Any], ...] = (
    {
        "topic_id": TOPIC_DATA_ROOM,
        "display_name": "OpenClaw Data Room / Reference Data Review",
        "short_description": (
            "Review what OpenClaw needs to know about gigs, payments, rates, venues, "
            "clients, invoice identity, persona rules, and business defaults."
        ),
        "aliases": (
            "data room",
            "business info",
            "reference data",
            "skill factory data",
            "stuff the system needs to know",
            "things OpenClaw needs from me",
            "gigs and payments",
            "rates and venues",
            "client info",
            "business details",
            "invoice data",
            "payment details",
            "OpenClaw setup questions",
        ),
        "keyword_groups": (
            ("gigs", "venues", "rates", "payments"),
            ("clients", "payers", "invoices", "billing"),
            ("identity", "Clara Reid", "Winship Live", "Niles"),
            ("expense categories", "tax labels", "business info"),
            ("missing questions", "reference data", "data room"),
            ("system needs to know", "gigs", "details", "payments"),
        ),
        "example_utterances": (
            "Cassandra, let's go over the Data Room.",
            "Let's go over the thing where the system needs to know more specifics about gigs and details and payments.",
            "Can we review the stuff OpenClaw still needs from me?",
            "What do I still need to answer for OpenClaw to work better?",
        ),
        "source_artifact_refs": (
            "/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",
            "/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_tomorrow_review_questions_v0.md",
        ),
        "related_subtopics": (
            TOPIC_INVOICE_POLICY,
            TOPIC_PERSONA_IDENTITY,
            TOPIC_PAYMENT_PRIVACY,
            TOPIC_RATES_CLIENTS_VENUES,
            TOPIC_NILES_CREATIVE,
        ),
        "owner_agent": "cassandra",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": ("business stuff",),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_INVOICE_POLICY,
        "display_name": "Invoice Policy Review",
        "short_description": "Review invoice numbering, identity, payee rules, payment instructions, and billing terms.",
        "aliases": (
            "invoice policy",
            "invoice numbering",
            "invoice identity",
            "payee rules",
            "payment instructions",
            "due on receipt",
            "direct deposit policy",
            "Zelle policy",
            "billing terms",
        ),
        "keyword_groups": (("invoice", "policy"), ("invoice", "numbering"), ("payee", "payment instructions")),
        "example_utterances": ("Go over the invoice policy thing.",),
        "source_artifact_refs": ("/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",),
        "related_subtopics": (TOPIC_DATA_ROOM, TOPIC_PAYMENT_PRIVACY),
        "owner_agent": "cassandra",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_PERSONA_IDENTITY,
        "display_name": "Identity / Persona Rules Review",
        "short_description": "Review Clara Reid, Winship identity, Niles public-facing, sender, signature, and from-name rules.",
        "aliases": (
            "Clara Reid rules",
            "Winship identity",
            "Niles public-facing",
            "sender identity",
            "signature rules",
            "from-name rules",
            "persona policy",
        ),
        "keyword_groups": (("Clara Reid", "rules"), ("Winship", "sender"), ("Niles", "public-facing"), ("signature", "persona")),
        "example_utterances": ("Let's talk through the Clara Reid rules.",),
        "source_artifact_refs": ("/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",),
        "related_subtopics": (TOPIC_DATA_ROOM, TOPIC_NILES_CREATIVE),
        "owner_agent": "cassandra",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_PAYMENT_PRIVACY,
        "display_name": "Payment Privacy Review",
        "short_description": "Review address, phone, direct deposit, Zelle, trust tier, and private payment information rules.",
        "aliases": (
            "payment privacy",
            "address and phone",
            "direct deposit",
            "Zelle",
            "bank details",
            "who can see payment info",
            "trust tier",
            "private payment info",
        ),
        "keyword_groups": (("payment", "privacy"), ("direct deposit", "Zelle"), ("bank", "details"), ("address", "phone")),
        "example_utterances": ("Can we review the payment privacy stuff?",),
        "source_artifact_refs": ("/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",),
        "related_subtopics": (TOPIC_DATA_ROOM, TOPIC_INVOICE_POLICY),
        "owner_agent": "cassandra",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_RATES_CLIENTS_VENUES,
        "display_name": "Rates, Clients, Venues Review",
        "short_description": "Review rates, rate cards, client roster, payer list, venues, gigs, and billing contacts.",
        "aliases": (
            "rates",
            "rate card",
            "client roster",
            "payer list",
            "venues",
            "gigs",
            "Capital Hilton",
            "Live Arts",
            "St. Anne's",
            "billing contacts",
        ),
        "keyword_groups": (("rates", "venues"), ("clients", "payers"), ("gigs", "billing contacts"), ("Capital Hilton", "Live Arts", "St. Anne")),
        "example_utterances": ("What does the system still need to know about rates and venues?",),
        "source_artifact_refs": ("/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",),
        "related_subtopics": (TOPIC_DATA_ROOM, TOPIC_INVOICE_POLICY),
        "owner_agent": "cassandra",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_NILES_CREATIVE,
        "display_name": "Niles Creative Reference Review",
        "short_description": "Review Niles setup, live set notes, music metadata, songs, setlists, Struna, Fundo, and session notes.",
        "aliases": (
            "Niles setup",
            "live set notes",
            "music metadata",
            "songs",
            "setlists",
            "Struna",
            "Fundo",
            "creative prep",
            "session notes",
            "Niles music setup",
        ),
        "keyword_groups": (("Niles", "music"), ("songs", "setlists"), ("Struna", "Fundo"), ("creative", "session notes")),
        "example_utterances": ("Let's go over the Niles music setup questions.",),
        "source_artifact_refs": ("/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_data_room_promotion_review_v0.json",),
        "related_subtopics": (TOPIC_DATA_ROOM, TOPIC_PERSONA_IDENTITY),
        "owner_agent": "niles",
        "review_session_builder": "create_data_room_review_session",
        "risk_level": "low",
        "start_allowed": True,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
    {
        "topic_id": TOPIC_SYSTEM_STATUS,
        "display_name": "System / Build Status Review",
        "short_description": "Review system status, build issues, what needs fixing, what needs Winship, health, and Watch Desk.",
        "aliases": (
            "what broke",
            "system status",
            "build issues",
            "what needs fixing",
            "what needs me",
            "health check",
            "Watch Desk",
        ),
        "keyword_groups": (("what broke", "build"), ("system", "status"), ("needs fixing", "Watch Desk")),
        "example_utterances": ("What broke?",),
        "source_artifact_refs": (),
        "related_subtopics": (),
        "owner_agent": "chief",
        "review_session_builder": "",
        "risk_level": "low",
        "start_allowed": False,
        "requires_clarification_if": (),
        "must_not": tuple(AUTHORITY_BOUNDARY.keys()),
    },
)

TOPICS_BY_ID = {topic["topic_id"]: topic for topic in REVIEWABLE_TOPIC_REGISTRY_V0}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return ROOT / path


def _short_hash(*parts: object) -> str:
    blob = "\0".join(str(part) for part in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON at {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _review_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_REVIEW_ROOT)


def _read_model_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_READ_MODEL_ROOT)


def _promotion_path(path: str | Path | None) -> Path:
    if path is not None:
        return _rooted(path)
    for candidate in (DEFAULT_DURABLE_PROMOTION_REVIEW_PATH, DEFAULT_LEGACY_DURABLE_PROMOTION_REVIEW_PATH):
        durable_path = _rooted(candidate)
        if durable_path.exists():
            return durable_path
    return _rooted(DEFAULT_PROMOTION_REVIEW_PATH)


def _session_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{SESSION_PREFIX}_{_safe_filename(session_id)}.json"


def _operator_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{SESSION_PREFIX}_{_safe_filename(session_id)}_OPERATOR.md"


def _prompt_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{PROMPT_PREFIX}_{_safe_filename(session_id)}.md"


def _parked_note_path(review_root: Path, note_id: str) -> Path:
    return review_root / f"consult_parked_note_{_safe_filename(note_id)}.json"


def _active_index_path(review_root: Path) -> Path:
    return review_root / ACTIVE_INDEX_NAME


def _receipt_root(review_root: Path, receipt_root: str | Path | None = None) -> Path:
    return _rooted(receipt_root) if receipt_root else review_root / DEFAULT_RECEIPT_DIR_NAME


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _control_text(text: str) -> str:
    command = coach_command(text)
    if command:
        return command
    lowered = " ".join(text.strip().lower().split())
    lowered = lowered.strip(" .!?")
    if lowered in {"summary", "summarize", "summarise"}:
        return "summarize"
    if lowered in {"done", "finish", "complete", "that's all", "thats all"}:
        return "done"
    if lowered in {"skip", "skip this", "skip question"}:
        return "skip"
    if lowered in {"defer", "defer this", "defer question"}:
        return "defer"
    if lowered in {"next", "next question"}:
        return "next question"
    if lowered in {"revise previous", "revise last", "change previous", "change last"}:
        return "revise_previous"
    return ""


def _excluded_route_text(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    normalized = _normalize_topic_text(text) if "_normalize_topic_text" in globals() else lowered
    return any(term in lowered or _normalize_topic_text(term) in normalized for term in EXCLUDED_ROUTE_TERMS)


def _normalize_topic_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = (
        lowered.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("/", " ")
        .replace("-", " ")
    )
    return " ".join(re.sub(r"[^a-z0-9'$]+", " ", lowered).split())


def _contains_any(normalized_text: str, phrases: Sequence[str]) -> bool:
    return any(phrase in normalized_text for phrase in phrases)


def _canonical_topic_id(topic: str) -> str:
    value = str(topic or "").strip()
    return LEGACY_TOPIC_ALIASES.get(value, value)


def _topic_record(topic_id: str) -> Mapping[str, Any]:
    return TOPICS_BY_ID.get(_canonical_topic_id(topic_id), TOPICS_BY_ID[TOPIC_DATA_ROOM])


def _topic_display_name(topic_id: str) -> str:
    return str(_topic_record(topic_id).get("display_name") or "Data Room review")


def _short_topic_name(topic_id: str) -> str:
    topic_id = _canonical_topic_id(topic_id)
    names = {
        TOPIC_DATA_ROOM: "Data Room",
        TOPIC_INVOICE_POLICY: "invoice policy",
        TOPIC_PERSONA_IDENTITY: "Clara Reid/persona rules",
        TOPIC_PAYMENT_PRIVACY: "payment privacy",
        TOPIC_RATES_CLIENTS_VENUES: "rates/venues",
        TOPIC_NILES_CREATIVE: "Niles creative setup",
        TOPIC_SYSTEM_STATUS: "system status",
    }
    return names.get(topic_id, _topic_display_name(topic_id))


def _contains_topic_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = _normalize_topic_text(phrase)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text


def _has_review_intent(normalized_text: str) -> bool:
    review_terms = (
        "go over",
        "review",
        "talk through",
        "finish",
        "questions",
        "what does the system still need to know",
        "system still need to know",
        "system needs to know",
        "openclaw still needs from me",
        "openclaw needs from me",
        "still need to answer",
        "need to answer",
        "work better",
        "coach",
        "coach me through",
        "help me think through",
        "help me decide",
        "walk me through",
    )
    return any(term in normalized_text for term in review_terms)


def _active_session_reference(normalized_text: str) -> bool:
    phrases = (
        "continue",
        "keep going",
        "next question",
        "finish that",
        "finish this",
        "finish the questions",
        "back to the questions",
        "that thing",
        "this thing",
        "the questions",
    )
    return any(phrase in normalized_text for phrase in phrases)


def _looks_like_non_review_operator_action(text: str) -> bool:
    normalized = _normalize_topic_text(text)
    if _has_review_intent(normalized):
        return False
    if normalized.startswith(("i got paid", "i spent ", "i did ")):
        return True
    if normalized.startswith(("follow up with ", "send this to ", "hermes ", "niles ")):
        return True
    if normalized in {"what broke", "what broke in the build", "can you handle that thing"}:
        return True
    return False


def _answer_topic_hint(text: str) -> str:
    normalized = _normalize_topic_text(text)
    if not normalized:
        return ""
    payment_terms = (
        "ach",
        "address exposure",
        "bank transfer",
        "check payment",
        "checks",
        "direct deposit",
        "invoice payment details",
        "manual approval",
        "payment info",
        "payment information",
        "payment instruction",
        "zelle",
        "payment method",
        "payment methods",
        "payment privacy",
        "raw payment",
        "bank",
        "routing",
        "account number",
        "home address",
        "phone exposure",
    )
    check_payment = "check" in normalized and _contains_any(normalized, ("zelle", "payment", "direct deposit"))
    if _contains_any(normalized, payment_terms) or check_payment:
        return TOPIC_PAYMENT_PRIVACY
    if _contains_any(normalized, ("clara reid", "signature", "from name", "from-name", "persona", "winship default")):
        return TOPIC_PERSONA_IDENTITY
    if _contains_any(normalized, ("invoice numbering", "invoice number", "payee", "invoice terms", "payment terms")):
        return TOPIC_INVOICE_POLICY
    if _contains_any(normalized, ("rate", "client", "payer", "venue", "capital hilton", "live arts", "st anne")):
        return TOPIC_RATES_CLIENTS_VENUES
    return ""


def _question_topic_hint(question: Mapping[str, Any]) -> str:
    category = str(question.get("category") or "")
    text = _normalize_topic_text(
        " ".join(
            str(question.get(key) or "")
            for key in ("category", "question_text", "context_summary", "risk_if_wrong")
        )
    )
    if category == "payment privacy" or _contains_any(
        text,
        (
            "ach",
            "address exposure",
            "bank transfer",
            "check payment",
            "checks",
            "direct deposit",
            "invoice payment details",
            "payment info",
            "payment information",
            "payment instructions",
            "payment method",
            "payment methods",
            "payment privacy",
            "payment contact details",
            "payment or contact details",
            "trust gated",
            "raw payment",
            "zelle",
        ),
    ):
        return TOPIC_PAYMENT_PRIVACY
    if category in {"identity/persona policy", "Clara Reid use", "Niles public technical-director use"}:
        return TOPIC_PERSONA_IDENTITY
    if category == "invoice numbering/payee policy" or _contains_any(
        text,
        ("invoice numbering", "invoice number", "payee", "invoice terms", "payment terms"),
    ):
        return TOPIC_INVOICE_POLICY
    if category in {"rates", "clients/payers", "venues"}:
        return TOPIC_RATES_CLIENTS_VENUES
    return ""


def _topic_short_label(topic: str) -> str:
    labels = {
        TOPIC_PAYMENT_PRIVACY: "payment/privacy",
        TOPIC_PERSONA_IDENTITY: "identity/persona",
        TOPIC_INVOICE_POLICY: "invoice policy",
        TOPIC_RATES_CLIENTS_VENUES: "rates/clients/venues",
    }
    return labels.get(_canonical_topic_id(topic), "that topic")


def _topic_storage_label(topic: str) -> str:
    labels = {
        TOPIC_PAYMENT_PRIVACY: "payment privacy",
        TOPIC_PERSONA_IDENTITY: "identity/persona",
        TOPIC_INVOICE_POLICY: "invoice policy",
        TOPIC_RATES_CLIENTS_VENUES: "rates/clients/venues",
    }
    return labels.get(_canonical_topic_id(topic), _short_topic_name(topic))


def _answer_topic_mismatch(answer_text: str, question: Mapping[str, Any]) -> dict[str, str]:
    answer_topic = _answer_topic_hint(answer_text)
    question_topic = _question_topic_hint(question)
    protected_topics = {
        TOPIC_PAYMENT_PRIVACY,
        TOPIC_PERSONA_IDENTITY,
        TOPIC_INVOICE_POLICY,
        TOPIC_RATES_CLIENTS_VENUES,
    }
    if answer_topic and question_topic and answer_topic != question_topic:
        if answer_topic in protected_topics and question_topic in protected_topics:
            return {
                "answer_topic": answer_topic,
                "question_topic": question_topic,
                "answer_topic_label": _topic_short_label(answer_topic),
                "question_topic_label": _topic_short_label(question_topic),
            }
    return {}


def _topic_suggestion(topic_id: str) -> dict[str, str]:
    record = _topic_record(topic_id)
    return {
        "topic_id": str(record["topic_id"]),
        "display_name": str(record["display_name"]),
    }


def _clarification_question_for(confidence: str, suggested_topic_ids: Sequence[str]) -> str:
    if confidence == "medium" and suggested_topic_ids:
        primary = _topic_display_name(suggested_topic_ids[0])
        alternatives = [_topic_display_name(topic_id) for topic_id in suggested_topic_ids[1:3]]
        if alternatives:
            return f"I think you mean {primary}. Is that right? I can also review {' or '.join(alternatives)}."
        return f"I think you mean {primary}. Is that right?"
    if confidence == "low":
        return (
            "I'm not sure which review you mean. Do you want Data Room, invoice policy, "
            "Clara Reid/persona rules, payment privacy, rates/venues, Niles creative setup, or system status?"
        )
    return ""


def _score_topic(normalized_text: str, topic: Mapping[str, Any], *, review_intent: bool) -> dict[str, Any]:
    topic_id = str(topic["topic_id"])
    aliases = [str(alias) for alias in topic.get("aliases", [])]
    matched_aliases = [alias for alias in aliases if _contains_topic_phrase(normalized_text, alias)]
    matched_keywords: list[str] = []
    score = 0

    for alias in matched_aliases:
        score += 6 if review_intent else 4
        matched_keywords.extend(_normalize_topic_text(alias).split())

    for group in topic.get("keyword_groups", []):
        if not isinstance(group, (list, tuple)):
            continue
        group_hits = [str(term) for term in group if _contains_topic_phrase(normalized_text, str(term))]
        if len(group_hits) >= 2:
            score += len(group_hits) + 1
            matched_keywords.extend(group_hits)
        elif group_hits and review_intent:
            score += 1
            matched_keywords.extend(group_hits)

    if topic_id == TOPIC_DATA_ROOM and review_intent:
        broad_hits = [
            term
            for term in ("system", "openclaw", "specifics", "details", "payments", "gigs", "business")
            if term in normalized_text
        ]
        if len(broad_hits) >= 3:
            score += len(broad_hits) + 2
            matched_keywords.extend(broad_hits)

    if topic_id == TOPIC_SYSTEM_STATUS and any(term in normalized_text for term in ("what broke", "build issues", "system status", "health check")):
        score += 7
        matched_keywords.append("system status")

    return {
        "topic_id": topic_id,
        "score": score,
        "matched_aliases": sorted(set(matched_aliases)),
        "matched_keywords": sorted(set(matched_keywords)),
    }


def resolve_guided_review_topic(raw_text: str, active_session_context: Any = None) -> dict[str, Any]:
    """Resolve fuzzy operator review requests to a guided review topic.

    This is local classification only. It does not create sessions, promote
    reference data, or call external services.
    """

    normalized = _normalize_topic_text(raw_text)
    if not normalized or _excluded_route_text(normalized):
        return {
            "schema_version": "guided_review_topic_resolution_v0",
            "matched_topic_id": "",
            "confidence": "low",
            "matched_aliases": [],
            "matched_keywords": [],
            "suggested_topics": [],
            "clarification_question": "",
            "should_start_session": False,
            "should_resume_active_session": False,
        }

    active_sessions: list[Mapping[str, Any]] = []
    if isinstance(active_session_context, Mapping):
        active_sessions = [active_session_context]
    elif isinstance(active_session_context, Sequence) and not isinstance(active_session_context, (str, bytes)):
        active_sessions = [item for item in active_session_context if isinstance(item, Mapping)]

    if active_sessions and _active_session_reference(normalized):
        if len(active_sessions) == 1:
            topic_id = _canonical_topic_id(str(active_sessions[0].get("topic") or TOPIC_DATA_ROOM))
            return {
                "schema_version": "guided_review_topic_resolution_v0",
                "matched_topic_id": topic_id,
                "confidence": "high",
                "matched_aliases": [],
                "matched_keywords": ["active_session"],
                "suggested_topics": [_topic_suggestion(topic_id)],
                "clarification_question": "",
                "should_start_session": False,
                "should_resume_active_session": True,
            }
        suggestions = [_topic_suggestion(str(session.get("topic") or TOPIC_DATA_ROOM)) for session in active_sessions[:3]]
        labels = ", ".join(item["display_name"] for item in suggestions)
        return {
            "schema_version": "guided_review_topic_resolution_v0",
            "matched_topic_id": "",
            "confidence": "medium",
            "matched_aliases": [],
            "matched_keywords": ["active_session"],
            "suggested_topics": suggestions,
            "clarification_question": f"Which review should I continue: {labels}?",
            "should_start_session": False,
            "should_resume_active_session": False,
        }

    review_intent = _has_review_intent(normalized)
    system_status_intent = any(term in normalized for term in ("what broke", "system status", "build issues", "health check"))
    if not review_intent and not system_status_intent:
        return {
            "schema_version": "guided_review_topic_resolution_v0",
            "matched_topic_id": "",
            "confidence": "low",
            "matched_aliases": [],
            "matched_keywords": [],
            "suggested_topics": [],
            "clarification_question": "",
            "should_start_session": False,
            "should_resume_active_session": False,
        }

    scores = [_score_topic(normalized, topic, review_intent=review_intent) for topic in REVIEWABLE_TOPIC_REGISTRY_V0]
    scores = sorted(scores, key=lambda row: int(row["score"]), reverse=True)

    if review_intent and "business stuff" in normalized:
        preferred = [TOPIC_DATA_ROOM, TOPIC_INVOICE_POLICY, TOPIC_RATES_CLIENTS_VENUES]
        return {
            "schema_version": "guided_review_topic_resolution_v0",
            "matched_topic_id": TOPIC_DATA_ROOM,
            "confidence": "medium",
            "matched_aliases": [],
            "matched_keywords": ["business"],
            "suggested_topics": [_topic_suggestion(topic_id) for topic_id in preferred],
            "clarification_question": _clarification_question_for("medium", preferred),
            "should_start_session": False,
            "should_resume_active_session": False,
        }

    top = scores[0] if scores else {"score": 0, "topic_id": ""}
    second_score = int(scores[1]["score"]) if len(scores) > 1 else 0
    top_score = int(top.get("score") or 0)
    suggested_topic_ids = [str(row["topic_id"]) for row in scores if int(row["score"]) > 0][:3]
    if not suggested_topic_ids:
        suggested_topic_ids = [TOPIC_DATA_ROOM, TOPIC_INVOICE_POLICY, TOPIC_PERSONA_IDENTITY]

    if top_score >= 6 and top_score - second_score >= 2:
        confidence = "high"
    elif top_score >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    matched_topic_id = str(top.get("topic_id") or "") if confidence != "low" else ""
    topic = _topic_record(matched_topic_id) if matched_topic_id else {}
    should_start = bool(confidence == "high" and topic.get("start_allowed", False))
    if confidence == "low":
        suggested_topic_ids = [TOPIC_DATA_ROOM, TOPIC_INVOICE_POLICY, TOPIC_PERSONA_IDENTITY]

    return {
        "schema_version": "guided_review_topic_resolution_v0",
        "matched_topic_id": matched_topic_id,
        "confidence": confidence,
        "matched_aliases": list(top.get("matched_aliases") or []) if confidence != "low" else [],
        "matched_keywords": list(top.get("matched_keywords") or []) if confidence != "low" else [],
        "suggested_topics": [_topic_suggestion(topic_id) for topic_id in suggested_topic_ids],
        "clarification_question": _clarification_question_for(confidence, suggested_topic_ids),
        "should_start_session": should_start,
        "should_resume_active_session": False,
    }


def _start_topic(text: str) -> str:
    resolution = resolve_guided_review_topic(text)
    if resolution.get("should_start_session"):
        return str(resolution.get("matched_topic_id") or "")
    return ""


def _is_live_chatgpt55_data_room_start_request(text: str) -> bool:
    normalized = _normalize_topic_text(text)
    phrases = (
        "cassandra start the chatgpt 5 5 data room brain",
        "start the chatgpt 5 5 data room brain",
        "cassandra open the chatgpt 5 5 lane for the data room form",
        "open the chatgpt 5 5 lane for the data room form",
        "open chatgpt 5 5 lane for the data room form",
        "cassandra use chatgpt 5 5 to help me fill this out",
        "use chatgpt 5 5 to help me fill this out",
    )
    return any(phrase in normalized for phrase in phrases)


def _is_live_gemini_form_start_request(text: str) -> bool:
    normalized = _normalize_topic_text(text)
    phrases = (
        "cassandra start the gemini data room form lane",
        "start the gemini data room form lane",
        "cassandra use gemini to help me fill this data room form",
        "use gemini to help me fill this data room form",
        "cassandra open the gemini form assistant",
        "open the gemini form assistant",
    )
    return any(phrase in normalized for phrase in phrases)


def _is_data_room_live_lm_brain_start_request(text: str) -> bool:
    normalized = _normalize_topic_text(text)
    phrases = (
        "cassandra start the data room lm brain",
        "start the data room lm brain",
        "cassandra use the lm brain for this data room form",
        "use the lm brain for this data room form",
        "cassandra start helping me fill this form with the lm brain",
        "start helping me fill this form with the lm brain",
    )
    return any(phrase in normalized for phrase in phrases)


def _load_session(review_root: Path, session_id: str) -> dict[str, Any] | None:
    path = _session_path(review_root, session_id)
    if not path.is_file():
        return None
    payload = _load_json(path)
    if payload.get("schema_version") != SESSION_SCHEMA_VERSION:
        return None
    return payload


def _find_active_session(review_root: Path) -> dict[str, Any] | None:
    index_path = _active_index_path(review_root)
    if index_path.is_file():
        try:
            index = _load_json(index_path)
            session_id = str(index.get("review_session_id") or "")
            if session_id:
                session = _load_session(review_root, session_id)
                if session and session.get("status") in {"active", "paused"}:
                    return session
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    for path in sorted(review_root.glob(f"{SESSION_PREFIX}_*.json"), reverse=True):
        if path.name.endswith("_OPERATOR.md") or path.name == ACTIVE_INDEX_NAME:
            continue
        try:
            session = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if session.get("schema_version") == SESSION_SCHEMA_VERSION and session.get("status") in {"active", "paused"}:
            return session
    return None


def has_active_guided_review_session(*, review_root: str | Path | None = None) -> bool:
    return _find_active_session(_review_root(review_root)) is not None


def get_active_guided_review_context(
    *,
    review_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return a compact active-session context for routing gates."""

    session = _find_active_session(_review_root(review_root))
    if session is None:
        return None
    progress = _progress(session)
    session_id = str(session.get("review_session_id") or "")
    topic = str(session.get("topic") or TOPIC_DATA_ROOM)
    current_question_id = str(session.get("current_question_id") or "")
    pending = session.get("pending_interaction") if isinstance(session.get("pending_interaction"), Mapping) else {}
    return {
        "active_context_id": f"guided_review:{session_id}",
        "context_type": "guided_review_session",
        "owner_agent": "cassandra",
        "topic": topic,
        "topic_display_name": str(session.get("topic_display_name") or _topic_display_name(topic)),
        "status": str(session.get("status") or "active"),
        "last_turn_at_utc": str(session.get("updated_at_utc") or session.get("created_at_utc") or ""),
        "resume_phrase": "continue Data Room",
        "source_session_ref": _session_path(_review_root(review_root), session_id).as_posix(),
        "review_session_id": session_id,
        "current_question_id": current_question_id,
        "pending_interaction": dict(pending),
        "remaining_count": progress["remaining"],
        "answered_count": progress["answered"],
        "deferred_count": progress["deferred"],
        "resume_suggestion": "Say 'continue Data Room' when ready.",
    }


def set_guided_review_context_status(
    status: str,
    *,
    review_root: str | Path | None = None,
    read_model_root: str | Path | None = None,
    interrupted_by_ref: str = "",
    generated_at_utc: str | None = None,
) -> dict[str, Any] | None:
    """Set active guided-review status to active/paused without answering."""

    if status not in {"active", "paused"}:
        raise ValueError("guided review status must be active or paused")
    root = _review_root(review_root)
    session = _find_active_session(root)
    if session is None:
        return None
    now = generated_at_utc or utc_now()
    session = dict(session)
    session["status"] = status
    session["updated_at_utc"] = now
    if interrupted_by_ref:
        refs = list(session.get("interrupted_by_refs") or [])
        if interrupted_by_ref not in refs:
            refs.append(interrupted_by_ref)
        session["interrupted_by_refs"] = refs
    session_path = _persist_session(session, review_root=root)
    session["session_artifact_ref"] = session_path.as_posix()
    write_guided_review_read_model([session], read_model_root=read_model_root, generated_at_utc=now)
    _refresh_watch_desk(read_model_root, now)
    return get_active_guided_review_context(review_root=root)


def is_guided_review_message(text: str, *, review_root: str | Path | None = None) -> bool:
    if not text or not text.strip() or _excluded_route_text(text):
        return False
    if (
        _is_live_chatgpt55_data_room_start_request(text)
        or _is_live_gemini_form_start_request(text)
        or _is_data_room_live_lm_brain_start_request(text)
    ):
        return True
    active = _find_active_session(_review_root(review_root))
    resolution = resolve_guided_review_topic(text, active_session_context=active)
    if resolution.get("should_start_session") or resolution.get("should_resume_active_session"):
        return True
    if resolution.get("clarification_question"):
        return True
    if not active:
        return False
    if _control_text(text):
        return True
    # Active sessions treat ordinary operator text as an answer.
    return True


def _redact_sensitive_text(text: str) -> tuple[str, bool]:
    redacted = str(text)
    patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{2}-\d{7}\b",
        r"\b\d{9,}\b",
    ]
    sensitive = False
    for pattern in patterns:
        new_value = re.sub(pattern, "[REDACTED_SENSITIVE_DETAIL]", redacted)
        if new_value != redacted:
            sensitive = True
            redacted = new_value
    return redacted, sensitive


def _normalize_answer(text: str, question: Mapping[str, Any]) -> tuple[str, str, bool]:
    redacted, sensitive = _redact_sensitive_text(text)
    cleaned = " ".join(redacted.strip().split())
    lowered = cleaned.lower()
    if lowered in {"yes", "confirm", "confirmed", "looks good", "approve"}:
        return "confirmed_as_proposed", "high", sensitive
    if lowered in {"no", "reject", "rejected", "do not import"}:
        return "rejected_by_operator", "high", sensitive
    if "not sure" in lowered or "maybe" in lowered or "source" in lowered:
        return f"needs_followup: {cleaned}", "medium", sensitive
    if "direct deposit" in lowered:
        return f"manual_approval_only: {cleaned}", "medium", sensitive
    if "follow" in lowered and "original invoice" in lowered:
        return f"followups_allowed_original_invoices_not_confirmed: {cleaned}", "medium", sensitive
    return cleaned, "medium", sensitive


def _category_for_record(record: Mapping[str, Any]) -> str:
    text = " ".join(
        str(record.get(key) or "")
        for key in ("record_id", "provisional_fact", "proposed_promoted_value", "review_category")
    ).lower()
    text = re.sub(r"[_-]+", " ", text)
    if any(
        term in text
        for term in (
            "ach",
            "address exposure",
            "bank account",
            "bank transfer",
            "check",
            "checks",
            "direct deposit",
            "home address",
            "invoice payment details",
            "payment contact exposure",
            "payment contact",
            "payment contact details",
            "payment info",
            "payment information",
            "payment instruction",
            "payment instructions",
            "payment or contact details",
            "payment method",
            "payment methods",
            "payment policy",
            "payment privacy",
            "phone exposure",
            "public phone",
            "raw account",
            "raw payment",
            "routing number",
            "trust gated",
            "trust-gated",
            "tax identifiers",
            "zelle",
            "ssn",
            "ein",
            "tokens",
            "credentials",
            "secrets",
        )
    ):
        return "payment privacy"
    if "clara" in text:
        return "Clara Reid use"
    if "niles" in text:
        return "Niles public technical-director use"
    if "log rhythm" in text:
        return "Log Rhythm exclusion"
    if any(term in text for term in ("rate", "$500", "$125", "$62.50", "speaker rental", "a/v")):
        return "rates"
    if any(term in text for term in ("client", "payer", "capital hilton", "statler", "live arts", "st. anne", "annapolis choral", "annette", "will")):
        return "clients/payers"
    if "venue" in text or "mileage" in text:
        return "venues"
    if any(term in text for term in ("invoice", "payee", "numbering", "filename", "terms", "status")):
        return "invoice numbering/payee policy"
    if "expense" in text:
        return "expense categories"
    if str(record.get("review_category") or "") == "do_not_import":
        return "do-not-import rules"
    if any(term in text for term in ("identity", "winship", "sender", "persona")):
        return "identity/persona policy"
    return "data room review"


def _priority_for_record(record: Mapping[str, Any]) -> int:
    category = _category_for_record(record)
    order = {
        "payment privacy": 10,
        "identity/persona policy": 20,
        "Clara Reid use": 21,
        "Niles public technical-director use": 22,
        "Log Rhythm exclusion": 23,
        "rates": 30,
        "clients/payers": 40,
        "invoice numbering/payee policy": 50,
        "expense categories": 60,
        "venues": 70,
        "do-not-import rules": 80,
        "data room review": 90,
    }
    return order.get(category, 90)


def _recommended_action(value: Any) -> str:
    action = str(value or "defer").strip().lower().replace(" ", "_")
    if action == "source needed":
        action = "source_needed"
    return action if action in {"confirm", "revise", "reject", "source_needed", "defer"} else "defer"


def _question_text(record: Mapping[str, Any]) -> str:
    category = str(record.get("review_category") or "")
    fact = str(record.get("provisional_fact") or "").lstrip("* ").strip()
    proposed = str(record.get("proposed_promoted_value") or "").lstrip("* ").strip()
    if category == "confirm_ready":
        return f"Can I treat this as confirm-ready for the later promotion packet: {proposed}"
    if category == "needs_correction":
        return f"How should this be revised before promotion: {fact}"
    if category == "needs_source":
        return f"What source or exact operator statement should support this before promotion: {fact}"
    if category == "do_not_import":
        return f"Confirm this remains blocked from active import: {fact}"
    if category == "policy_decision":
        if proposed and fact and fact.lower() not in proposed.lower():
            return f"{proposed} Context: {fact}"
        return proposed or fact
    return proposed or fact


def _topic_matches(record: Mapping[str, Any], topic: str) -> bool:
    topic = _canonical_topic_id(topic)
    if topic in {"", TOPIC_DATA_ROOM}:
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("record_id", "provisional_fact", "proposed_promoted_value", "review_category")
    ).lower()
    category = _category_for_record(record)
    if topic == TOPIC_PERSONA_IDENTITY:
        return category in {"identity/persona policy", "Clara Reid use", "Niles public technical-director use"} or any(
            term in text for term in ("clara", "sender", "signature", "persona", "identity", "niles")
        )
    if topic == TOPIC_INVOICE_POLICY:
        return category == "invoice numbering/payee policy" or any(
            term in text for term in ("invoice", "payee", "terms", "numbering", "status", "billing")
        )
    if topic == TOPIC_PAYMENT_PRIVACY:
        return category == "payment privacy" or any(
            term in text for term in ("payment privacy", "direct deposit", "zelle", "bank", "address", "phone", "trust tier")
        )
    if topic == TOPIC_RATES_CLIENTS_VENUES:
        return category in {"rates", "clients/payers", "venues"} or any(
            term in text for term in ("rate", "client", "payer", "venue", "gig", "capital hilton", "live arts", "st. anne")
        )
    if topic == TOPIC_NILES_CREATIVE:
        return "niles" in text or any(term in text for term in ("song", "setlist", "struna", "fundo", "music", "session"))
    if topic == TOPIC_SYSTEM_STATUS:
        return False
    return True


def build_data_room_review_questions(
    promotion_review: Mapping[str, Any],
    *,
    topic: str = "data_room",
) -> list[dict[str, Any]]:
    records = promotion_review.get("review_records")
    if not isinstance(records, list):
        records = []
    questions: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or not _topic_matches(record, topic):
            continue
        record_id = str(record.get("record_id") or f"record:{index}")
        category = _category_for_record(record)
        question_id = f"review_question:{_short_hash(topic, record_id, record.get('provisional_fact', ''))}"
        questions.append(
            {
                "schema_version": QUESTION_SCHEMA_VERSION,
                "question_id": question_id,
                "category": category,
                "priority": _priority_for_record(record),
                "question_text": _question_text(record),
                "context_summary": str(record.get("provisional_fact") or "").lstrip("* ").strip(),
                "source_record_ids": [record_id],
                "proposed_options": _proposed_options_for(record),
                "risk_if_wrong": str(record.get("risk_if_wrong") or ""),
                "recommended_action": _recommended_action(record.get("recommended_action")),
                "answer_status": "unanswered",
                "answer_text": "",
                "normalized_answer": "",
                "affected_records": [record_id],
                "authoritative": False,
            }
        )
    return sorted(questions, key=lambda q: (int(q["priority"]), q["category"], q["question_id"]))


def _proposed_options_for(record: Mapping[str, Any]) -> list[str]:
    category = str(record.get("review_category") or "")
    action = _recommended_action(record.get("recommended_action"))
    if category == "confirm_ready":
        return ["confirm", "revise", "defer"]
    if category == "needs_source":
        return ["source needed", "provide source", "defer"]
    if category == "do_not_import":
        return ["reject/import blocked", "defer", "revise wording"]
    if action == "revise":
        return ["revise", "defer", "reject"]
    return [action.replace("_", " "), "revise", "defer"]


def create_data_room_review_session(
    *,
    topic: str = "data_room",
    operator: str = "Winship",
    surface: str = "telegram",
    review_root: str | Path | None = None,
    promotion_review_path: str | Path | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    root = _review_root(review_root)
    promotion_path = _promotion_path(promotion_review_path)
    promotion = _load_json(promotion_path)
    topic = _canonical_topic_id(topic or TOPIC_DATA_ROOM)
    created = created_at_utc or utc_now()
    questions = build_data_room_review_questions(promotion, topic=topic)
    session_id = "data_room_review:" + _short_hash(topic, operator, created, len(questions))
    source_refs = [str(promotion_path)]
    source_refs.extend(str(ref) for ref in promotion.get("source_artifacts", []) if str(ref))
    current_question_id = questions[0]["question_id"] if questions else ""
    session = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "review_session_id": session_id,
        "topic": topic,
        "topic_display_name": _topic_display_name(topic),
        "source_artifact_refs": sorted(set(source_refs)),
        "created_at_utc": created,
        "updated_at_utc": created,
        "operator": operator,
        "surface": surface,
        "status": "active" if questions else "blocked",
        "question_queue": questions,
        "current_question_id": current_question_id,
        "answered_questions": [],
        "skipped_questions": [],
        "deferred_questions": [],
        "unresolved_questions": [q["question_id"] for q in questions],
        "answer_records": [],
        "generated_prompt_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "pending_interaction": {},
        "parked_note_refs": [],
        "coach_mode_enabled": True,
        "coaching_style": "concise",
        "coach_interactions": [],
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    _persist_session(session, review_root=root)
    return session


def _question_by_id(session: Mapping[str, Any], question_id: str) -> dict[str, Any] | None:
    for question in session.get("question_queue", []):
        if isinstance(question, Mapping) and question.get("question_id") == question_id:
            return dict(question)
    return None


def _question_index(session: Mapping[str, Any], question_id: str) -> int:
    for index, question in enumerate(session.get("question_queue", [])):
        if isinstance(question, Mapping) and question.get("question_id") == question_id:
            return index
    return -1


def _replace_question(session: dict[str, Any], updated: Mapping[str, Any]) -> None:
    queue = list(session.get("question_queue", []))
    for index, question in enumerate(queue):
        if isinstance(question, Mapping) and question.get("question_id") == updated.get("question_id"):
            queue[index] = dict(updated)
            session["question_queue"] = queue
            return


def _coach_mode_enabled(session: Mapping[str, Any]) -> bool:
    return bool(session.get("coach_mode_enabled"))


def _enable_coach_mode(session: dict[str, Any], *, style: str = "concise") -> None:
    session["coach_mode_enabled"] = True
    session.setdefault("coaching_style", style)
    session.setdefault("coach_interactions", [])


def _coach_card_for_question(session: dict[str, Any], question: Mapping[str, Any]) -> dict[str, Any]:
    current = question.get("coach_card")
    if isinstance(current, Mapping) and current.get("schema_version") == "REVIEW_COACH_CARD_V0":
        card = dict(current)
    else:
        card = build_coach_card(question)
        updated = dict(question)
        updated["coach_card"] = card
        _replace_question(session, updated)
    progress = _progress(session)
    card["question_number"] = progress["current_number"]
    card["question_total"] = progress["total"]
    return card


def _append_coach_interaction(
    session: dict[str, Any],
    *,
    command: str,
    question_id: str,
    now: str,
    selected_option_id: str = "",
) -> None:
    session.setdefault("coach_interactions", []).append(
        {
            "schema_version": "REVIEW_COACH_INTERACTION_V0",
            "command": command,
            "question_id": question_id,
            "selected_option_id": selected_option_id,
            "created_at_utc": now,
            "authoritative": False,
            "runtime_policy_changed": False,
        }
    )


def _append_topic_mismatch_clarification(
    session: dict[str, Any],
    *,
    question_id: str,
    now: str,
    mismatch: Mapping[str, str],
) -> None:
    session.setdefault("coach_interactions", []).append(
        {
            "schema_version": "REVIEW_COACH_INTERACTION_V0",
            "command": "topic_mismatch_clarification",
            "question_id": question_id,
            "detected_answer_topic": str(mismatch.get("answer_topic") or ""),
            "active_question_topic": str(mismatch.get("question_topic") or ""),
            "created_at_utc": now,
            "answer_recorded": False,
            "authoritative": False,
            "runtime_policy_changed": False,
        }
    )


def _append_pending_interaction_event(
    session: dict[str, Any],
    *,
    command: str,
    question_id: str,
    now: str,
    detected_topic: str = "",
    answer_recorded: bool = False,
    note_ref: str = "",
) -> None:
    event = {
        "schema_version": "REVIEW_COACH_INTERACTION_V0",
        "command": command,
        "question_id": question_id,
        "detected_answer_topic": detected_topic,
        "created_at_utc": now,
        "answer_recorded": answer_recorded,
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    if note_ref:
        event["parked_note_ref"] = note_ref
    session.setdefault("coach_interactions", []).append(event)


def _parse_utc_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _active_pending_interaction(session: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    pending = session.get("pending_interaction")
    if not isinstance(pending, Mapping) or pending.get("kind") not in {"topic_switch", "answer_candidate", "condition_request"}:
        return {}
    if int(pending.get("turns_remaining") or 0) <= 0:
        return {}
    created = _parse_utc_timestamp(str(pending.get("created_at_utc") or ""))
    current = _parse_utc_timestamp(now)
    if created and current and (current - created).total_seconds() > 30 * 60:
        return {}
    return dict(pending)


def _clear_pending_interaction(session: dict[str, Any], *, now: str, reason: str) -> None:
    pending = session.get("pending_interaction")
    question_id = ""
    detected_topic = ""
    if isinstance(pending, Mapping):
        question_id = str(pending.get("current_question_id") or "")
        detected_topic = str(pending.get("detected_topic_id") or pending.get("detected_topic") or "")
    session["pending_interaction"] = {}
    _append_pending_interaction_event(
        session,
        command=f"pending_interaction_{reason}",
        question_id=question_id,
        detected_topic=detected_topic,
        now=now,
        answer_recorded=False,
    )


def _pending_prompt(pending: Mapping[str, Any]) -> str:
    detected_label = str(pending.get("detected_topic_prompt_label") or pending.get("detected_topic") or "that topic")
    current_label = str(pending.get("current_question_prompt_label") or "this question")
    return (
        f"That sounds like a {detected_label} answer, but this question is about {current_label}. "
        f"Should I switch to {detected_label} and record it there? I have not recorded it yet."
    )


def _pending_reply_intent(text: str) -> str:
    normalized = _normalize_topic_text(text)
    natural = parse_natural_reply_intent(text)
    if normalized in {"yes", "y", "switch", "yes switch", "yes please switch", "please switch"}:
        return "switch"
    if natural.get("intent") == "confirm_candidate":
        return "switch"
    if normalized.startswith("yes switch") or normalized.startswith("yes please switch"):
        return "switch"
    if normalized.startswith("yes") and "switch" in normalized:
        return "switch"
    if normalized in {"yeah switch it", "put it there", "yes put it there", "record it under payment privacy", "yes put it under payment privacy"}:
        return "switch"
    if normalized in {"no", "nope", "no thanks", "do not switch", "dont switch", "don't switch"}:
        return "no"
    if normalized in {"cancel", "never mind", "nevermind", "stop"}:
        return "cancel"
    if normalized in {"here", "record here", "record it here", "here anyway", "record here anyway", "record it here anyway"}:
        return "here"
    if normalized in {"no keep it here", "no record it here", "no keep here", "keep it here"}:
        return "here"
    return "other"


def _is_global_control_allowed_during_pending(control: str) -> bool:
    return control in {"done", "summarize", "skip", "defer", "next question"}


def _is_bare_yes(text: str) -> bool:
    if _normalize_topic_text(text) in {"yes", "y", "confirm", "confirmed", "looks good", "approve"}:
        return True
    return parse_natural_reply_intent(text).get("intent") == "confirm_candidate"


def _question_matches_topic(question: Mapping[str, Any], topic_id: str) -> bool:
    topic_id = _canonical_topic_id(topic_id)
    question_topic = _question_topic_hint(question)
    if topic_id == TOPIC_PAYMENT_PRIVACY:
        text = _normalize_topic_text(
            " ".join(str(question.get(key) or "") for key in ("category", "question_text", "context_summary"))
        )
        return question_topic == TOPIC_PAYMENT_PRIVACY or _contains_any(
            text,
            (
                "payment privacy",
                "payment instruction",
                "payment instructions",
                "payment method",
                "payment methods",
                "direct deposit",
                "zelle",
                "check",
                "checks",
            ),
        )
    return question_topic == topic_id


def _find_unanswered_matching_question_id(session: Mapping[str, Any], topic_id: str) -> str:
    for question in session.get("question_queue", []):
        if not isinstance(question, Mapping):
            continue
        if question.get("answer_status") != "unanswered":
            continue
        if _question_matches_topic(question, topic_id):
            return str(question.get("question_id") or "")
    return ""


def _set_pending_topic_switch(
    session: dict[str, Any],
    *,
    original_text: str,
    mismatch: Mapping[str, str],
    question: Mapping[str, Any],
    now: str,
    surface: str,
) -> dict[str, Any]:
    redacted_original, _ = _redact_sensitive_text(original_text)
    answer_topic = str(mismatch.get("answer_topic") or "")
    target_question_id = _find_unanswered_matching_question_id(session, answer_topic)
    pending = {
        "kind": "topic_switch",
        "pending_interaction_id": "pending_topic_switch:" + _short_hash(
            redacted_original,
            answer_topic,
            question.get("question_id", ""),
            now,
        ),
        "original_utterance": redacted_original,
        "original_utterance_hash": _text_hash(redacted_original),
        "detected_topic": _topic_storage_label(answer_topic),
        "detected_topic_id": answer_topic,
        "detected_topic_prompt_label": str(mismatch.get("answer_topic_label") or _topic_short_label(answer_topic)),
        "current_question_id": str(question.get("question_id") or ""),
        "current_question_prompt_label": str(mismatch.get("question_topic_label") or _topic_short_label(str(mismatch.get("question_topic") or ""))),
        "target_question_id": target_question_id,
        "created_at_utc": now,
        "surface": surface,
        "turns_remaining": 3,
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    session["pending_interaction"] = pending
    return pending


def _candidate_prompt(candidate_text: str) -> str:
    return f"Should I record this as: {str(candidate_text).strip(' .?')}?"


def _candidate_from_thought_dump(raw_text: str) -> str:
    text = " ".join(str(raw_text or "").strip(" .").split())
    patterns = (
        r"^let me ramble(?: for a second)?[:,-]?\s*(.+)$",
        r"^here'?s the messy version[:,-]?\s*(.+)$",
        r"^i'?m not sure what matters[, ]+but\s+(.+)$",
        r"^i kind of feel like\s+(.+)$",
        r"^i don'?t know[, ]+but\s+(.+)$",
        r"^help me find the thread[:,-]?\s*(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            return " ".join(match.group(1).strip(" .").split())
    return text


def _candidate_from_condition(raw_text: str, condition_text: str) -> str:
    text = " ".join(str(raw_text or condition_text or "").strip(" .").split())
    normalized = _normalize_topic_text(text)
    if "trusted clients" in normalized and ("new clients" in normalized or "for new clients" in normalized):
        return "Use a case-by-case rule: for new clients no, for trusted clients yes."
    if "trusted clients" in normalized and "direct deposit" in normalized:
        return "Direct deposit is manual-only except for trusted clients who specifically request it."
    if normalized in {"sometimes", "it depends", "depends", "case by case"}:
        return ""
    return text


def _set_pending_condition_request(
    session: dict[str, Any],
    *,
    source_intent: Mapping[str, Any],
    current_question_id: str,
    now: str,
    surface: str,
) -> dict[str, Any]:
    pending_id = "pending_condition_request:" + _short_hash(
        session.get("review_session_id", ""),
        current_question_id,
        now,
    )
    pending = {
        "kind": "condition_request",
        "pending_interaction_id": pending_id,
        "current_question_id": current_question_id,
        "created_at_utc": now,
        "surface": surface,
        "turns_remaining": 3,
        "source_intent": dict(source_intent),
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    session["pending_interaction"] = pending
    return pending


def _set_pending_answer_candidate(
    session: dict[str, Any],
    *,
    candidate_text: str,
    source_intent: Mapping[str, Any],
    current_question_id: str,
    now: str,
    surface: str,
) -> dict[str, Any]:
    redacted_candidate, _ = _redact_sensitive_text(candidate_text)
    pending_id = "pending_answer_candidate:" + _short_hash(
        session.get("review_session_id", ""),
        current_question_id,
        redacted_candidate,
        now,
    )
    pending = {
        "kind": "answer_candidate",
        "pending_interaction_id": pending_id,
        "candidate_text": redacted_candidate,
        "candidate_text_hash": _text_hash(redacted_candidate),
        "current_question_id": current_question_id,
        "created_at_utc": now,
        "surface": surface,
        "turns_remaining": 3,
        "source_intent": dict(source_intent),
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    session["pending_interaction"] = pending
    return pending


def _update_pending_answer_candidate(
    session: dict[str, Any],
    pending: Mapping[str, Any],
    *,
    candidate_text: str,
    source_intent: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    redacted_candidate, _ = _redact_sensitive_text(candidate_text)
    updated = dict(pending)
    updated.update(
        {
            "candidate_text": redacted_candidate,
            "candidate_text_hash": _text_hash(redacted_candidate),
            "updated_at_utc": now,
            "turns_remaining": 3,
            "source_intent": dict(source_intent),
            "authoritative": False,
            "runtime_policy_changed": False,
        }
    )
    session["pending_interaction"] = updated
    return updated


def _write_parked_note(
    session: dict[str, Any],
    pending: Mapping[str, Any],
    *,
    review_root: Path,
    now: str,
) -> str:
    note_id = _short_hash(
        session.get("review_session_id", ""),
        pending.get("original_utterance_hash", ""),
        pending.get("current_question_id", ""),
        now,
    )
    path = _parked_note_path(review_root, note_id)
    note = {
        "schema_version": "CONSULT_PARKED_NOTE_V0",
        "note_id": f"consult_parked_note:{note_id}",
        "created_at_utc": now,
        "authoritative": False,
        "runtime_policy_changed": False,
        "confirmed_reference_data_generated": False,
        "original_utterance": str(pending.get("original_utterance") or ""),
        "original_utterance_hash": str(pending.get("original_utterance_hash") or ""),
        "detected_topic": str(pending.get("detected_topic") or ""),
        "source_session_id": str(session.get("review_session_id") or ""),
        "source_question_id": str(pending.get("current_question_id") or ""),
        "reason": "no_matching_question_in_current_session",
    }
    _write_json(path, note)
    ref = f"{path.as_posix()}#parked_note"
    parked_refs = list(session.get("parked_note_refs") or [])
    if ref not in parked_refs:
        parked_refs.append(ref)
    session["parked_note_refs"] = parked_refs
    return ref


def _next_unanswered_question_id(session: Mapping[str, Any], *, after_question_id: str = "") -> str:
    queue = [q for q in session.get("question_queue", []) if isinstance(q, Mapping)]
    start = 0
    if after_question_id:
        current_index = _question_index(session, after_question_id)
        start = current_index + 1 if current_index >= 0 else 0
    for question in queue[start:]:
        if question.get("answer_status") == "unanswered":
            return str(question.get("question_id") or "")
    for question in queue:
        if question.get("answer_status") == "unanswered":
            return str(question.get("question_id") or "")
    return ""


def _refresh_session_lists(session: dict[str, Any]) -> None:
    answered: list[str] = []
    skipped: list[str] = []
    deferred: list[str] = []
    unresolved: list[str] = []
    for question in session.get("question_queue", []):
        if not isinstance(question, Mapping):
            continue
        question_id = str(question.get("question_id") or "")
        status = str(question.get("answer_status") or "unanswered")
        if status == "answered":
            answered.append(question_id)
        elif status == "skipped":
            skipped.append(question_id)
            unresolved.append(question_id)
        elif status == "deferred":
            deferred.append(question_id)
            unresolved.append(question_id)
        else:
            unresolved.append(question_id)
    session["answered_questions"] = answered
    session["skipped_questions"] = skipped
    session["deferred_questions"] = deferred
    session["unresolved_questions"] = unresolved


def _progress(session: Mapping[str, Any]) -> dict[str, int]:
    total = len([q for q in session.get("question_queue", []) if isinstance(q, Mapping)])
    answered = len(session.get("answered_questions", []))
    skipped = len(session.get("skipped_questions", []))
    deferred = len(session.get("deferred_questions", []))
    remaining = max(total - answered - skipped - deferred, 0)
    current_index = _question_index(session, str(session.get("current_question_id") or ""))
    return {
        "total": total,
        "answered": answered,
        "skipped": skipped,
        "deferred": deferred,
        "remaining": remaining,
        "current_number": current_index + 1 if current_index >= 0 else 0,
    }


def _progress_line(session: Mapping[str, Any]) -> str:
    progress = _progress(session)
    return (
        f"{progress['answered']} answered, {progress['deferred']} deferred, "
        f"{progress['skipped']} skipped, {progress['remaining']} remaining."
    )


def _format_question_reply(session: Mapping[str, Any], *, prefix: str = "") -> str:
    question_id = str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return "No active question is available. Say done to generate the promotion prompt."
    if _coach_mode_enabled(session):
        session_dict = dict(session)
        card = _coach_card_for_question(session_dict, question)
        if isinstance(session, dict):
            session.update(session_dict)
        reply = render_coach_reply(
            card,
            "question",
            surface=str(session.get("surface") or "telegram"),
            style=str(session.get("coaching_style") or "concise"),
        )
        return f"{prefix}\n\n{reply}" if prefix else reply
    progress = _progress(session)
    lead = f"{prefix}\n\n" if prefix else ""
    return (
        f"{lead}Question {progress['current_number']} of {progress['total']} — "
        f"{question['category']}: {question['question_text']}\n"
        "Reply with an answer, skip, defer, summarize, or done."
    )


def _recorded_answer_prefix(answer_text: str, question: Mapping[str, Any]) -> str:
    redacted, _ = _redact_sensitive_text(answer_text)
    normalized = _normalize_topic_text(redacted)
    if _question_topic_hint(question) == TOPIC_PAYMENT_PRIVACY:
        mentions_direct_deposit = "direct deposit" in normalized
        mentions_zelle = "zelle" in normalized
        mentions_check = "check" in normalized or "checks" in normalized
        if mentions_direct_deposit and (mentions_zelle or mentions_check):
            return "Recorded: direct deposit stays manual approval only; Zelle and check are okay by default (provisional)."
    return "Recorded."


def _session_summary_reply(session: Mapping[str, Any]) -> str:
    return f"{str(session.get('topic_display_name') or _topic_display_name(str(session.get('topic') or TOPIC_DATA_ROOM)))} progress: {_progress_line(session)}"


def _natural_explanation_reply(session: dict[str, Any], question: Mapping[str, Any], intent: str) -> str:
    if not question:
        return "No active question is available. Say done to generate the promotion prompt."
    _enable_coach_mode(session)
    card = _coach_card_for_question(session, question)
    if intent == "ask_examples":
        return render_coach_reply(
            card,
            "examples",
            surface=str(session.get("surface") or "telegram"),
            style=str(session.get("coaching_style") or "concise"),
        )
    if intent == "ask_recommendation":
        return render_coach_reply(
            card,
            "recommend",
            surface=str(session.get("surface") or "telegram"),
            style=str(session.get("coaching_style") or "concise"),
        )
    category = str(card.get("category") or "review")
    recommendation = str(card.get("recommended_default") or "Use the conservative default for now.")
    why = str(card.get("why_it_matters") or "This affects what can safely be promoted later.")
    if intent == "ask_eli5":
        return (
            f"ELI5 - {category}: we are deciding the safe default before OpenClaw can reuse this information. "
            f"My recommendation: {recommendation}"
        )
    if intent == "ask_analogy":
        return (
            f"Analogy - {category}: treat this like labeling a box before putting it on the shared shelf. "
            f"If the label is wrong, future work can pick the wrong thing. My recommendation: {recommendation}"
        )
    return f"{category}: {why} My recommendation: {recommendation}"


def _answer_id(session_id: str, question_id: str, answer_text: str, created_at: str) -> str:
    return "review_answer:" + _short_hash(session_id, question_id, answer_text, created_at)


def _write_answer_receipt(
    answer: Mapping[str, Any],
    *,
    review_root: Path,
    receipt_root: str | Path | None = None,
) -> str:
    root = _receipt_root(review_root, receipt_root)
    filename = f"{_safe_filename(str(answer['answer_id']))}_receipt.json"
    path = root / filename
    receipt = {
        "schema_version": "REVIEW_ANSWER_RECEIPT_V0",
        "review_session_id": answer["review_session_id"],
        "question_id": answer["question_id"],
        "question_category": answer.get("question_category", ""),
        "answer_id": answer["answer_id"],
        "raw_answer_text": answer.get("raw_answer_text", ""),
        "normalized_answer": answer["normalized_answer"],
        "affected_records": answer["affected_record_ids"],
        "selected_option_id": str(answer.get("selected_option_id") or ""),
        "answer_source": str(answer.get("answer_source") or "operator_reply"),
        "switched_from_question_id": str(answer.get("switched_from_question_id") or ""),
        "category_mismatch_resolved": bool(answer.get("category_mismatch_resolved")),
        "category_mismatch_acknowledged": bool(answer.get("category_mismatch_acknowledged")),
        "mismatch_original_hint": str(answer.get("mismatch_original_hint") or ""),
        "needs_professional_review": bool(answer.get("needs_professional_review")),
        "cpa_review_recommended": bool(answer.get("cpa_review_recommended")),
        "legal_review_recommended": bool(answer.get("legal_review_recommended")),
        "authoritative": False,
        "runtime_policy_changed": False,
        "external_calls_performed": False,
        "approval_created": False,
        "invoice_or_ledger_mutated": False,
        "sensitive_detail_redacted": bool(answer.get("sensitive_detail_redacted")),
        "created_at_utc": answer["created_at_utc"],
    }
    _write_json(path, receipt)
    return f"{path.as_posix()}#receipt"


def _apply_answer(
    session: dict[str, Any],
    answer_text: str,
    *,
    surface: str,
    review_root: Path,
    receipt_root: str | Path | None,
    now: str,
    selected_option_id: str = "",
    selected_option_label: str = "",
    question_id_override: str = "",
    extra_answer_fields: Mapping[str, Any] | None = None,
) -> None:
    question_id = question_id_override or str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return
    normalized, confidence, sensitive = _normalize_answer(answer_text, question)
    redacted_raw, _ = _redact_sensitive_text(answer_text)
    card = _coach_card_for_question(session, question) if _coach_mode_enabled(session) else {}
    cpa_flag = bool(card.get("cpa_review_recommended"))
    legal_flag = bool(card.get("legal_review_recommended"))
    answer = {
        "schema_version": ANSWER_SCHEMA_VERSION,
        "answer_id": _answer_id(session["review_session_id"], question_id, redacted_raw, now),
        "review_session_id": session["review_session_id"],
        "question_id": question_id,
        "question_category": str(question.get("category") or ""),
        "raw_answer_text": redacted_raw,
        "normalized_answer": normalized,
        "affected_record_ids": list(question.get("affected_records") or question.get("source_record_ids") or []),
        "selected_option_id": selected_option_id,
        "selected_option_label": selected_option_label,
        "confidence": confidence,
        "needs_followup": normalized.startswith("needs_followup:"),
        "needs_professional_review": bool(cpa_flag or legal_flag),
        "cpa_review_recommended": cpa_flag,
        "legal_review_recommended": legal_flag,
        "created_at_utc": now,
        "source_surface": surface,
        "authoritative": False,
        "review_status": "answered_pending_promotion",
        "active_for_promotion": True,
        "superseded": False,
        "runtime_policy_changed": False,
        "sensitive_detail_redacted": sensitive,
    }
    if extra_answer_fields:
        answer.update(dict(extra_answer_fields))
    receipt_ref = _write_answer_receipt(answer, review_root=review_root, receipt_root=receipt_root)
    answer["receipt_ref"] = receipt_ref
    question["answer_status"] = "answered"
    question["answer_text"] = redacted_raw
    question["normalized_answer"] = normalized
    question["selected_option_id"] = selected_option_id
    question["needs_professional_review"] = bool(cpa_flag or legal_flag)
    question["cpa_review_recommended"] = cpa_flag
    question["legal_review_recommended"] = legal_flag
    question["authoritative"] = False
    _replace_question(session, question)
    session.setdefault("answer_records", []).append(answer)
    session.setdefault("receipt_refs", []).append(receipt_ref)
    session["current_question_id"] = _next_unanswered_question_id(session, after_question_id=question_id)
    _refresh_session_lists(session)


def _handle_pending_interaction(
    session: dict[str, Any],
    *,
    pending: Mapping[str, Any],
    raw_text: str,
    surface: str,
    review_root: Path,
    receipt_root: str | Path | None,
    now: str,
) -> str:
    natural_intent = parse_natural_reply_intent(raw_text, pending)
    if pending.get("kind") == "answer_candidate":
        candidate_text = str(pending.get("candidate_text") or "")
        current_question_id = str(pending.get("current_question_id") or session.get("current_question_id") or "")
        natural_kind = str(natural_intent.get("intent") or "")
        if natural_kind == "confirm_candidate":
            _apply_answer(
                session,
                candidate_text,
                surface=surface,
                review_root=review_root,
                receipt_root=receipt_root,
                now=now,
                question_id_override=current_question_id,
                extra_answer_fields={"answer_source": "natural_candidate_confirmed"},
            )
            session["pending_interaction"] = {}
            _append_pending_interaction_event(
                session,
                command="pending_answer_candidate_confirmed",
                question_id=current_question_id,
                now=now,
                answer_recorded=True,
            )
            if not session.get("current_question_id"):
                completed = complete_session(session, review_root=review_root, now=now)
                session.clear()
                session.update(completed)
                return (
                    f"Recorded that answer. I wrote the promotion prompt: "
                    f"{_prompt_path(review_root, str(session['review_session_id'])).as_posix()}"
                )
            return _format_question_reply(session, prefix="Recorded that answer.")
        if natural_kind == "reject_candidate":
            session["pending_interaction"] = {}
            _append_pending_interaction_event(
                session,
                command="pending_answer_candidate_declined",
                question_id=current_question_id,
                now=now,
                answer_recorded=False,
            )
            return _format_question_reply(session, prefix="Okay. I did not record that candidate.")
        if natural_kind == "revise_candidate":
            revised = str(natural_intent.get("extracted_revision_text") or "").strip()
            if revised:
                updated = _update_pending_answer_candidate(
                    session,
                    pending,
                    candidate_text=revised,
                    source_intent=natural_intent,
                    now=now,
                )
                _append_pending_interaction_event(
                    session,
                    command="pending_answer_candidate_revised",
                    question_id=current_question_id,
                    now=now,
                    answer_recorded=False,
                )
                return _candidate_prompt(str(updated.get("candidate_text") or revised))
        if natural_kind == "conditional_answer":
            candidate = _candidate_from_condition(raw_text, str(natural_intent.get("condition_text") or ""))
            if candidate:
                updated = _update_pending_answer_candidate(
                    session,
                    pending,
                    candidate_text=candidate,
                    source_intent=natural_intent,
                    now=now,
                )
                _append_pending_interaction_event(
                    session,
                    command="pending_answer_candidate_conditioned",
                    question_id=current_question_id,
                    now=now,
                    answer_recorded=False,
                )
                return _candidate_prompt(str(updated.get("candidate_text") or candidate))
            return "What condition should decide it?"
        if natural_kind in {"ask_explanation", "ask_eli5", "ask_analogy", "ask_examples", "ask_recommendation"}:
            question = _question_by_id(session, current_question_id)
            return _natural_explanation_reply(session, question or {}, natural_kind)
    if pending.get("kind") == "condition_request":
        current_question_id = str(pending.get("current_question_id") or session.get("current_question_id") or "")
        natural_kind = str(natural_intent.get("intent") or "")
        if natural_kind == "conditional_answer":
            candidate = _candidate_from_condition(raw_text, str(natural_intent.get("condition_text") or ""))
            if candidate:
                pending_candidate = _set_pending_answer_candidate(
                    session,
                    candidate_text=candidate,
                    source_intent=natural_intent,
                    current_question_id=current_question_id,
                    now=now,
                    surface=surface,
                )
                _append_pending_interaction_event(
                    session,
                    command="pending_condition_candidate_created",
                    question_id=current_question_id,
                    now=now,
                    answer_recorded=False,
                )
                return _candidate_prompt(str(pending_candidate.get("candidate_text") or candidate))
            return "What condition should decide it?"
        if natural_kind in {"ask_explanation", "ask_eli5", "ask_analogy", "ask_examples", "ask_recommendation"}:
            question = _question_by_id(session, current_question_id)
            return f"{_natural_explanation_reply(session, question or {}, natural_kind)}\nWhat condition should decide it?"
        if natural_kind == "confirm_candidate":
            return "Yes to what? Tell me the condition first."
        if natural_kind == "reject_candidate":
            session["pending_interaction"] = {}
            _append_pending_interaction_event(
                session,
                command="pending_condition_declined",
                question_id=current_question_id,
                now=now,
                answer_recorded=False,
            )
            return _format_question_reply(session, prefix="Okay. I did not record a conditional answer.")

    intent = _pending_reply_intent(raw_text)
    original = str(pending.get("original_utterance") or "")
    current_question_id = str(pending.get("current_question_id") or session.get("current_question_id") or "")
    detected_topic_id = str(pending.get("detected_topic_id") or "")
    detected_label = str(pending.get("detected_topic_prompt_label") or pending.get("detected_topic") or "that topic")

    if intent == "switch":
        target_question_id = str(pending.get("target_question_id") or "")
        if target_question_id:
            _apply_answer(
                session,
                original,
                surface=surface,
                review_root=review_root,
                receipt_root=receipt_root,
                now=now,
                question_id_override=target_question_id,
                extra_answer_fields={
                    "answer_source": "topic_switch_confirmed",
                    "switched_from_question_id": current_question_id,
                    "category_mismatch_resolved": True,
                },
            )
            session["pending_interaction"] = {}
            _append_pending_interaction_event(
                session,
                command="pending_interaction_switched",
                question_id=target_question_id,
                detected_topic=detected_topic_id,
                now=now,
                answer_recorded=True,
            )
            if not session.get("current_question_id"):
                completed = complete_session(session, review_root=review_root, now=now)
                session.clear()
                session.update(completed)
                return (
                    f"Recorded the original {detected_label} answer. All questions are answered, skipped, or deferred. "
                    f"I wrote the promotion prompt: {_prompt_path(review_root, str(session['review_session_id'])).as_posix()}"
                )
            return _format_question_reply(session, prefix=f"Recorded the original {detected_label} answer in the matching question.")
        note_ref = _write_parked_note(session, pending, review_root=review_root, now=now)
        session["pending_interaction"] = {}
        _append_pending_interaction_event(
            session,
            command="pending_interaction_parked_note",
            question_id=current_question_id,
            detected_topic=detected_topic_id,
            note_ref=note_ref,
            now=now,
            answer_recorded=False,
        )
        return (
            f"I parked that {detected_label} note because this session does not have an unanswered matching question. "
            "I have not imported it or changed runtime policy."
        )

    if intent == "no":
        session["pending_interaction"] = {}
        _append_pending_interaction_event(
            session,
            command="pending_interaction_declined",
            question_id=current_question_id,
            detected_topic=detected_topic_id,
            now=now,
            answer_recorded=False,
        )
        return _format_question_reply(session, prefix="Okay. I did not record that. Staying on this question.")

    if intent == "cancel":
        session["pending_interaction"] = {}
        _append_pending_interaction_event(
            session,
            command="pending_interaction_cancelled",
            question_id=current_question_id,
            detected_topic=detected_topic_id,
            now=now,
            answer_recorded=False,
        )
        return _format_question_reply(session, prefix="Cancelled. I did not record that.")

    if intent == "here":
        _apply_answer(
            session,
            original,
            surface=surface,
            review_root=review_root,
            receipt_root=receipt_root,
            now=now,
            question_id_override=current_question_id,
            extra_answer_fields={
                "answer_source": "topic_mismatch_recorded_here",
                "category_mismatch_acknowledged": True,
                "mismatch_original_hint": str(pending.get("detected_topic") or detected_label),
            },
        )
        session["pending_interaction"] = {}
        _append_pending_interaction_event(
            session,
            command="pending_interaction_recorded_here",
            question_id=current_question_id,
            detected_topic=detected_topic_id,
            now=now,
            answer_recorded=True,
        )
        if not session.get("current_question_id"):
            completed = complete_session(session, review_root=review_root, now=now)
            session.clear()
            session.update(completed)
            return (
                "Recorded it here with the topic mismatch acknowledged. "
                f"I wrote the promotion prompt: {_prompt_path(review_root, str(session['review_session_id'])).as_posix()}"
            )
        return _format_question_reply(session, prefix="Recorded it here with the topic mismatch acknowledged.")

    turns_remaining = max(int(pending.get("turns_remaining") or 1) - 1, 0)
    if turns_remaining <= 0:
        session["pending_interaction"] = {}
        _append_pending_interaction_event(
            session,
            command="pending_interaction_expired",
            question_id=current_question_id,
            detected_topic=detected_topic_id,
            now=now,
            answer_recorded=False,
        )
        return _format_question_reply(session, prefix="I let that pending switch expire and did not record it.")

    updated = dict(pending)
    updated["turns_remaining"] = turns_remaining
    session["pending_interaction"] = updated
    _append_pending_interaction_event(
        session,
        command="pending_interaction_reprompted",
        question_id=current_question_id,
        detected_topic=detected_topic_id,
        now=now,
        answer_recorded=False,
    )
    return _pending_prompt(updated)


def _active_answer_records(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    for answer in session.get("answer_records", []):
        if not isinstance(answer, Mapping):
            continue
        if answer.get("superseded") or answer.get("review_status") == "superseded":
            continue
        answers.append(dict(answer))
    return answers


def _latest_active_answer(session: Mapping[str, Any]) -> dict[str, Any] | None:
    for answer in reversed(list(session.get("answer_records", []))):
        if not isinstance(answer, Mapping):
            continue
        if answer.get("superseded") or answer.get("review_status") == "superseded":
            continue
        if answer.get("review_status") == "answered_pending_promotion":
            return dict(answer)
    return None


def _rewind_to_previous_answer(session: dict[str, Any], *, now: str) -> str:
    previous = _latest_active_answer(session)
    if not previous:
        return ""
    previous_answer_id = str(previous.get("answer_id") or "")
    question_id = str(previous.get("question_id") or "")
    for answer in session.get("answer_records", []):
        if isinstance(answer, dict) and answer.get("answer_id") == previous_answer_id:
            answer["superseded"] = True
            answer["active_for_promotion"] = False
            answer["review_status"] = "superseded"
            answer["superseded_at_utc"] = now
            break
    question = _question_by_id(session, question_id)
    if question:
        question["answer_status"] = "unanswered"
        question["answer_text"] = ""
        question["normalized_answer"] = ""
        question["selected_option_id"] = ""
        question["authoritative"] = False
        _replace_question(session, question)
    session["current_question_id"] = question_id
    _refresh_session_lists(session)
    return question_id


def _recommended_option(card: Mapping[str, Any]) -> dict[str, Any]:
    options = [option for option in card.get("options", []) if isinstance(option, Mapping)]
    for option in options:
        if option.get("recommended"):
            return dict(option)
    return dict(options[0]) if options else {}


def _mark_current_question(
    session: dict[str, Any],
    *,
    status: str,
    now: str,
) -> None:
    question_id = str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return
    question["answer_status"] = status
    question["answer_text"] = ""
    question["normalized_answer"] = status
    question["authoritative"] = False
    _replace_question(session, question)
    session["current_question_id"] = _next_unanswered_question_id(session, after_question_id=question_id)
    session["updated_at_utc"] = now
    _refresh_session_lists(session)


def _persist_session(
    session: Mapping[str, Any],
    *,
    review_root: Path,
) -> Path:
    path = _session_path(review_root, str(session["review_session_id"]))
    _write_json(path, session)
    if session.get("status") in {"active", "paused"}:
        _write_json(
            _active_index_path(review_root),
            {
                "schema_version": "guided_review_active_session_index_v0",
                "review_session_id": session["review_session_id"],
                "session_path": path.as_posix(),
                "updated_at_utc": session.get("updated_at_utc"),
                "authoritative": False,
                "runtime_policy_changed": False,
            },
        )
    return path


def _write_operator_summary(session: Mapping[str, Any], *, review_root: Path) -> str:
    path = _operator_path(review_root, str(session["review_session_id"]))
    progress = _progress(session)
    topic_display = str(session.get("topic_display_name") or _topic_display_name(str(session.get("topic") or TOPIC_DATA_ROOM)))
    lines = [
        f"# {topic_display} Guided Review Session {session['review_session_id']}",
        "",
        "Every item remains provisional until Winship explicitly runs a later promotion task.",
        "",
        f"- Topic: {topic_display}",
        f"- Status: {session['status']}",
        f"- Answered: {progress['answered']}",
        f"- Deferred: {progress['deferred']}",
        f"- Skipped: {progress['skipped']}",
        f"- Remaining: {progress['remaining']}",
        f"- Coach mode: {str(bool(session.get('coach_mode_enabled'))).lower()}",
        f"- Authoritative: false",
        f"- Runtime policy changed: false",
        "",
        "## Answers",
    ]
    active_answers = _active_answer_records(session)
    if active_answers:
        for answer in active_answers:
            professional = ""
            if answer.get("cpa_review_recommended") and answer.get("legal_review_recommended"):
                professional = " [CPA/legal review before promotion]"
            elif answer.get("cpa_review_recommended"):
                professional = " [CPA review before promotion]"
            elif answer.get("legal_review_recommended"):
                professional = " [legal review before promotion]"
            selected = f" option={answer['selected_option_id']}" if answer.get("selected_option_id") else ""
            lines.append(f"- * {answer['question_id']}{selected}: {answer['normalized_answer']}{professional}")
    else:
        lines.append("- * No answers recorded.")
    superseded = [
        answer
        for answer in session.get("answer_records", [])
        if isinstance(answer, Mapping) and (answer.get("superseded") or answer.get("review_status") == "superseded")
    ]
    if superseded:
        lines.extend(["", "## Superseded Answers"])
        for answer in superseded:
            lines.append(f"- * Ignored for promotion: {answer.get('answer_id')} for {answer.get('question_id')}")
    lines.extend(["", "## Unresolved Questions"])
    unresolved = set(session.get("unresolved_questions", []))
    for question in session.get("question_queue", []):
        if isinstance(question, Mapping) and question.get("question_id") in unresolved:
            lines.append(f"- * {question['question_id']}: {question['question_text']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.as_posix()


def _write_promotion_prompt(session: Mapping[str, Any], *, review_root: Path) -> str:
    session_path = _session_path(review_root, str(session["review_session_id"]))
    path = _prompt_path(review_root, str(session["review_session_id"]))
    promotion_refs = [ref for ref in session.get("source_artifact_refs", []) if "promotion_review" in str(ref)]
    promotion_ref = promotion_refs[0] if promotion_refs else "openclaw_data_room_promotion_review_v0.json"
    active_answers = _active_answer_records(session)
    answer_lines = []
    flagged_lines = []
    for answer in active_answers:
        selected = f"; selected_option_id={answer.get('selected_option_id')}" if answer.get("selected_option_id") else ""
        flags = []
        if answer.get("cpa_review_recommended"):
            flags.append("CPA review recommended")
        if answer.get("legal_review_recommended"):
            flags.append("legal review recommended")
        flag_text = f"; professional_review_flags={', '.join(flags)}" if flags else ""
        line = f"- {answer.get('question_id')}: {answer.get('normalized_answer')}{selected}{flag_text}"
        answer_lines.append(line)
        if flags:
            flagged_lines.append(line)
    superseded_answers = [
        answer
        for answer in session.get("answer_records", [])
        if isinstance(answer, Mapping) and (answer.get("superseded") or answer.get("review_status") == "superseded")
    ]
    rendered_answers = "\n".join(answer_lines) if answer_lines else "- No active coach answers recorded."
    rendered_flags = "\n".join(flagged_lines) if flagged_lines else "- No CPA/legal professional-review flags on active answers."
    rendered_superseded = "\n".join(
        f"- Ignore superseded answer {answer.get('answer_id')} for {answer.get('question_id')}"
        for answer in superseded_answers
    ) or "- No superseded answers."
    prompt = f"""Task: OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_V0

Repo:
 /home/openclaw

Goal:
Promote only Winship-confirmed Data Room reference items from the guided review answer artifact.

Inputs:
- Answer artifact: {session_path.as_posix()}
- Promotion review artifact: {promotion_ref}

Active coach answers:
{rendered_answers}

Professional-review flags:
{rendered_flags}

Superseded answers:
{rendered_superseded}

Rules:
- Promote only answered/confirmed items with sufficient confidence.
- Ignore superseded answers.
- Keep CPA/legal-flagged items provisional pending professional review.
- Keep unresolved, skipped, deferred, source-needed, and ambiguous items provisional.
- Preserve conflicts that Winship did not explicitly resolve.
- Do not import raw bank, routing, account, tax, SSN, EIN, token, credential, OAuth, API key, secret, or private-note material.
- Do not mutate invoices, ledgers, workbooks, PDFs, Coupa, bank records, or external systems.
- Do not send email, create drafts, call Gmail/Google broker/Calendar/Contacts/browser/Apple Mail/DAW/external APIs, or create approvals.
- Do not import Log Rhythm Records into active identity/client/sender/routing logic.
- Do not import direct deposit details unless explicitly approved and still keep any raw details redacted.
- Do not broadly expose home address or phone unless explicitly approved by trust tier.
- Do not give tax/legal advice.

Return:
OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_READY
or
OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_BLOCKED
"""
    path.write_text(prompt, encoding="utf-8")
    return path.as_posix()


def complete_session(session: dict[str, Any], *, review_root: Path, now: str) -> dict[str, Any]:
    session["status"] = "completed"
    session["updated_at_utc"] = now
    _refresh_session_lists(session)
    operator_ref = _write_operator_summary(session, review_root=review_root)
    prompt_ref = _write_promotion_prompt(session, review_root=review_root)
    generated_refs = list(session.get("generated_prompt_refs", []))
    for ref in (operator_ref, prompt_ref):
        if ref not in generated_refs:
            generated_refs.append(ref)
    session["generated_prompt_refs"] = generated_refs
    session["current_question_id"] = ""
    _persist_session(session, review_root=review_root)
    index = _active_index_path(review_root)
    if index.exists():
        try:
            index.unlink()
        except OSError:
            pass
    return session


def _session_read_model_item(session: Mapping[str, Any]) -> dict[str, Any]:
    progress = _progress(session)
    session_id = str(session.get("review_session_id") or "")
    session_ref = _session_path(DEFAULT_REVIEW_ROOT, session_id).as_posix()
    if session.get("session_artifact_ref"):
        session_ref = str(session["session_artifact_ref"])
    status = str(session.get("status") or "active")
    verb = "in progress" if status == "active" else ("paused" if status == "paused" else status)
    topic_display = str(session.get("topic_display_name") or _topic_display_name(str(session.get("topic") or TOPIC_DATA_ROOM)))
    active_answers = _active_answer_records(session)
    cpa_flagged_count = len([answer for answer in active_answers if answer.get("cpa_review_recommended")])
    legal_flagged_count = len([answer for answer in active_answers if answer.get("legal_review_recommended")])
    return {
        "item_id": f"guided_review:{session_id}",
        "lane": "chief_runtime",
        "urgency": "needs_operator" if status in {"active", "paused"} else "info",
        "plain_line": (
            f"{topic_display} {verb}: {progress['answered']} answered, "
            f"{progress['deferred']} deferred, {progress['remaining']} remaining."
        ),
        "source_receipt_ref": f"{session_ref}#session",
        "one_next_safe_action": "Continue the guided review with Cassandra, or say done to generate the Codex promotion prompt.",
        "push_class": "info",
        "review_session_id": session_id,
        "topic_id": str(session.get("topic") or ""),
        "topic_display_name": topic_display,
        "status": status,
        "coach_mode": bool(session.get("coach_mode_enabled")),
        "cpa_flagged_count": cpa_flagged_count,
        "legal_flagged_count": legal_flagged_count,
        "answered_count": progress["answered"],
        "deferred_count": progress["deferred"],
        "remaining_count": progress["remaining"],
    }


def write_guided_review_read_model(
    sessions: Sequence[Mapping[str, Any]],
    *,
    read_model_root: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> Path:
    root = _read_model_root(read_model_root)
    root.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at_utc or utc_now()
    session_rows = [dict(session) for session in sessions]
    for session in session_rows:
        if not session.get("session_artifact_ref"):
            session["session_artifact_ref"] = _session_path(
                DEFAULT_REVIEW_ROOT,
                str(session["review_session_id"]),
            ).as_posix()
    payload = {
        "schema_version": READ_MODEL_SCHEMA_VERSION,
        "generated_at": generated_at,
        "session_count": len(session_rows),
        "active_session_count": len([s for s in session_rows if s.get("status") in {"active", "paused"}]),
        "sessions": session_rows,
        "watch_desk_items": [_session_read_model_item(session) for session in session_rows],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    path = root / READ_MODEL_NAME
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _refresh_watch_desk(read_model_root: str | Path | None, generated_at: str) -> dict[str, Any]:
    try:
        from watch_desk_feed import export_watch_desk_feed

        return export_watch_desk_feed(
            read_model_root=_read_model_root(read_model_root),
            export_root=_read_model_root(read_model_root),
            generated_at=generated_at,
        )
    except Exception as exc:
        return {
            "read_model_path": "",
            "item_count": 0,
            "new_push_candidate_count": 0,
            "live_push_allowed": False,
            "refresh_error": type(exc).__name__,
        }


def _artifact_refs(session: Mapping[str, Any], *, review_root: Path, read_model_root: str | Path | None) -> dict[str, Any]:
    session_path = _session_path(review_root, str(session["review_session_id"]))
    return {
        "session_json": session_path.as_posix(),
        "operator_markdown": _operator_path(review_root, str(session["review_session_id"])).as_posix(),
        "promotion_prompt": _prompt_path(review_root, str(session["review_session_id"])).as_posix(),
        "data_room_form_fill_refs": list(session.get("data_room_form_fill_refs", [])),
        "guided_review_read_model": (_read_model_root(read_model_root) / READ_MODEL_NAME).as_posix(),
        "receipts": list(session.get("receipt_refs", [])),
        "generated_prompt_refs": list(session.get("generated_prompt_refs", [])),
    }


def _response(
    *,
    session: Mapping[str, Any],
    reply_text: str,
    review_root: Path,
    read_model_root: str | Path | None,
    watch_refresh: Mapping[str, Any] | None = None,
    handled: bool = True,
) -> dict[str, Any]:
    progress = _progress(session)
    return {
        "schema_version": "guided_review_surface_response_v0",
        "handled": handled,
        "reply_text": reply_text,
        "reply": reply_text,
        "review_session_id": session.get("review_session_id", ""),
        "current_question_id": session.get("current_question_id", ""),
        "progress": progress,
        "status": session.get("status", ""),
        "artifact_refs": _artifact_refs(session, review_root=review_root, read_model_root=read_model_root),
        "receipt_refs": list(session.get("receipt_refs", [])),
        "watch_desk_refs": list(session.get("watch_desk_refs", [])),
        "watch_desk_refresh": dict(watch_refresh or {}),
        "safety_flags": dict(AUTHORITY_BOUNDARY),
        "authoritative": False,
        "runtime_policy_changed": False,
        "external_calls_performed": False,
    }


def _clarification_response(resolution: Mapping[str, Any], *, reply_text: str) -> dict[str, Any]:
    return {
        "schema_version": "guided_review_surface_response_v0",
        "handled": True,
        "reply_text": reply_text,
        "reply": reply_text,
        "review_session_id": "",
        "current_question_id": "",
        "progress": {},
        "status": "clarification_required",
        "artifact_refs": {},
        "receipt_refs": [],
        "watch_desk_refs": [],
        "watch_desk_refresh": {},
        "topic_resolution": dict(resolution),
        "safety_flags": dict(AUTHORITY_BOUNDARY),
        "authoritative": False,
        "runtime_policy_changed": False,
        "external_calls_performed": False,
    }


def _live_chatgpt55_lane_active(session: Mapping[str, Any]) -> bool:
    lane = session.get("live_chatgpt55_data_room_lane")
    return bool(isinstance(lane, Mapping) and lane.get("active") is True and lane.get("live_ready") is True)


def _write_live_chatgpt55_state(
    session: dict[str, Any],
    *,
    package: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    lane_status: str,
    live_ready: bool,
    blocked_reason: str,
    now: str,
) -> dict[str, Any]:
    import openclaw_chatgpt55_adapter as chatgpt55

    state = chatgpt55.build_data_room_live_chatgpt55_lane_state(
        package=package,
        result=result or {},
        availability=chatgpt55.is_live_chatgpt55_available(),
        lane_status=lane_status,
        live_ready=live_ready,
        blocked_reason=blocked_reason,
        generated_at_utc=now,
        recent_chat_summary=str((result or {}).get("chat_log_summary_update") or package.get("prior_chat_log_summary") or ""),
        model=chatgpt55.model_label(),
    )
    refs = chatgpt55.write_data_room_live_chatgpt55_lane_state(state)
    state["artifact_refs"] = refs
    session["live_chatgpt55_data_room_lane"] = {
        "schema_version": "DATA_ROOM_LIVE_CHATGPT55_SESSION_LANE_V0",
        "active": bool(live_ready and lane_status == "active"),
        "live_ready": bool(live_ready),
        "lane_status": lane_status,
        "model_label": state["model_label"],
        "last_advisory_request_id": state.get("last_advisory_request_id", ""),
        "last_result_id": state.get("last_result_id", ""),
        "blocked_reason": blocked_reason,
        "state_refs": refs,
        "updated_at_utc": now,
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
    }
    watch_refs = list(session.get("watch_desk_refs") or [])
    for item in state.get("watch_desk_items") or []:
        if isinstance(item, Mapping):
            item_id = str(item.get("item_id") or "")
            if item_id and item_id not in watch_refs:
                watch_refs.append(item_id)
    session["watch_desk_refs"] = watch_refs
    return state


def _activate_live_chatgpt55_data_room_lane(
    session: dict[str, Any],
    *,
    raw_text: str,
    review_root: Path,
    read_model_root: str | Path | None,
    now: str,
    chatgpt55_provider=None,
    chatgpt55_env: Mapping[str, str] | None = None,
) -> str:
    from data_room_form_fill_package import (
        LIVE_CHATGPT55_READINESS_NOTIFICATION,
        build_data_room_form_fill_package,
        write_data_room_form_fill_artifacts,
    )
    import openclaw_chatgpt55_adapter as chatgpt55

    package = build_data_room_form_fill_package(session, created_at_utc=now)
    try:
        result = chatgpt55.call_chatgpt55_data_room_advisory(
            package,
            chatgpt55.READINESS_PROMPT,
            str(package.get("prior_chat_log_summary") or ""),
            provider=chatgpt55_provider,
            created_at_utc=now,
            env=chatgpt55_env,
        )
    except chatgpt55.ChatGPT55AdapterError as exc:
        state = _write_live_chatgpt55_state(
            session,
            package=package,
            result=None,
            lane_status="blocked",
            live_ready=False,
            blocked_reason=exc.reason,
            now=now,
        )
        session.setdefault("data_room_form_fill_refs", []).append(
            {
                "schema_version": "DATA_ROOM_LIVE_CHATGPT55_ARTIFACT_REFS_V0",
                "package_id": package.get("package_id", ""),
                "review_session_id": package.get("review_session_id", ""),
                "live_ready": False,
                "blocked_reason": exc.reason,
                "live_lane_state_refs": dict(state.get("artifact_refs") or {}),
                "external_model_invoked": False,
                "confirmed_reference_data_created": False,
                "runtime_policy_changed": False,
            }
        )
        return f"ChatGPT 5.5 Data Room lane blocked: {exc.reason}. {chatgpt55.safe_next_operator_step(exc.reason)}"

    form_fill_refs = write_data_room_form_fill_artifacts(package, export_operator_copy=False)
    state = _write_live_chatgpt55_state(
        session,
        package=package,
        result=result,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
    )
    live_refs = dict(form_fill_refs)
    live_refs.update(
        {
            "live_ready": True,
            "live_lane_state_refs": dict(state.get("artifact_refs") or {}),
            "last_advisory_request_id": state.get("last_advisory_request_id", ""),
            "last_result_id": state.get("last_result_id", ""),
            "external_model_invoked": True,
            "advisory_only": True,
            "runtime_policy_changed": False,
            "confirmed_reference_data_created": False,
            "hydration_allowed": False,
        }
    )
    session.setdefault("data_room_form_fill_refs", []).append(live_refs)
    generated_refs = list(session.get("generated_prompt_refs") or [])
    for ref in (
        form_fill_refs.get("primary", {}).get("package_path", ""),
        form_fill_refs.get("durable", {}).get("package_path", ""),
        state.get("artifact_refs", {}).get("read_model_path", ""),
    ):
        if ref and ref not in generated_refs:
            generated_refs.append(ref)
    session["generated_prompt_refs"] = generated_refs
    session["latest_data_room_form_fill_package_id"] = package["package_id"]
    return LIVE_CHATGPT55_READINESS_NOTIFICATION


def _handle_live_chatgpt55_data_room_turn(
    session: dict[str, Any],
    *,
    raw_text: str,
    surface: str,
    review_root: Path,
    now: str,
    chatgpt55_provider=None,
    chatgpt55_env: Mapping[str, str] | None = None,
) -> str:
    from data_room_form_fill_package import build_data_room_form_fill_package
    import openclaw_chatgpt55_adapter as chatgpt55

    package = build_data_room_form_fill_package(session, created_at_utc=now)
    try:
        result = chatgpt55.call_chatgpt55_data_room_advisory(
            package,
            raw_text,
            str(package.get("prior_chat_log_summary") or ""),
            provider=chatgpt55_provider,
            created_at_utc=now,
            env=chatgpt55_env,
        )
    except chatgpt55.ChatGPT55AdapterError as exc:
        _write_live_chatgpt55_state(
            session,
            package=package,
            result=None,
            lane_status="unavailable",
            live_ready=False,
            blocked_reason=exc.reason,
            now=now,
        )
        return (
            f"The ChatGPT 5.5 Data Room lane is temporarily unavailable ({exc.reason}). "
            "I am falling back to the deterministic review coach.\n\n"
            f"{_format_question_reply(session)}"
        )

    _write_live_chatgpt55_state(
        session,
        package=package,
        result=result,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
    )
    answer = result.get("proposed_answer") if isinstance(result.get("proposed_answer"), Mapping) else {}
    candidate_text = str(answer.get("plain_english") or answer.get("normalized_decision") or "").strip()
    intent = str(result.get("operator_intent") or "")
    if candidate_text and intent in {"answer_candidate", "conditional", "revise", "thought_dump"}:
        question_id = str(result.get("question_id") or session.get("current_question_id") or "")
        pending_candidate = _set_pending_answer_candidate(
            session,
            candidate_text=candidate_text,
            source_intent={
                "schema_version": "LIVE_CHATGPT55_PENDING_CANDIDATE_SOURCE_V0",
                "intent": intent,
                "request_id": str(result.get("request_id") or ""),
                "result_id": chatgpt55.result_id_for(result),
                "should_record_now": False,
                "confirmed_by_winship": False,
                "safety_flags": dict(result.get("safety_flags") or {}),
            },
            current_question_id=question_id,
            now=now,
            surface=surface,
        )
        _append_pending_interaction_event(
            session,
            command="live_chatgpt55_pending_answer_candidate_created",
            question_id=question_id,
            now=now,
            answer_recorded=False,
        )
        session["pending_interaction"] = pending_candidate
    return str(result.get("assistant_reply") or "")


def _data_room_live_lm_brain_read_model_path(read_model_root: str | Path | None) -> Path:
    if read_model_root:
        return _read_model_root(read_model_root) / "data_room_live_lm_brain_status.json"
    return Path("generated/read_models/data_room_live_lm_brain_status.json")


def _live_lm_brain_active(session: Mapping[str, Any]) -> bool:
    lane = session.get("data_room_live_lm_brain")
    return bool(isinstance(lane, Mapping) and lane.get("active") is True and lane.get("live_lm_brain_ready") is True)


def _set_data_room_live_lm_brain_session_state(
    session: dict[str, Any],
    *,
    run: Mapping[str, Any],
    now: str,
    read_model_root: str | Path | None,
) -> None:
    import data_room_live_lm_brain as lm_brain

    status = run.get("status_read_model") if isinstance(run.get("status_read_model"), Mapping) else {}
    request = run.get("request") if isinstance(run.get("request"), Mapping) else {}
    turn_result = run.get("turn_result") if isinstance(run.get("turn_result"), Mapping) else {}
    ready = bool(status.get("live_lm_brain_ready"))
    state_refs = {
        "read_model_path": _data_room_live_lm_brain_read_model_path(read_model_root).as_posix(),
        "request_ref": str(status.get("readiness_turn_request_ref") or ""),
        "result_ref": str(status.get("readiness_turn_result_ref") or ""),
    }
    session["data_room_live_lm_brain"] = {
        "schema_version": "DATA_ROOM_LIVE_LM_BRAIN_SESSION_LANE_V0",
        "active": ready,
        "live_lm_brain_ready": ready,
        "provider": str(status.get("provider") or "openai"),
        "access_mode": str(status.get("access_mode") or "openai_codex_cli"),
        "worker_kind": str(status.get("worker_kind") or "openai_codex_cli"),
        "last_request_id": str(request.get("request_id") or ""),
        "last_package_id": str(status.get("readiness_turn_package_ref") or ""),
        "last_result_ref": str(status.get("result_ref") or ""),
        "last_validation_ref": str(status.get("validation_ref") or ""),
        "blocked_reason": str(status.get("last_error") or ""),
        "chat_log_summary": str(turn_result.get("chat_log_summary_update") or status.get("chat_log_summary_update") or ""),
        "state_refs": state_refs,
        "updated_at_utc": now,
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
    }
    generated_refs = list(session.get("generated_prompt_refs") or [])
    for ref in state_refs.values():
        if ref and ref not in generated_refs:
            generated_refs.append(ref)
    session["generated_prompt_refs"] = generated_refs
    watch_refs = list(session.get("watch_desk_refs") or [])
    watch_ref = str(status.get("watch_desk_ref") or f"data_room_live_lm_brain:{session.get('review_session_id') or 'unknown'}")
    if watch_ref and watch_ref not in watch_refs:
        watch_refs.append(watch_ref)
    session["watch_desk_refs"] = watch_refs
    if ready:
        session["data_room_live_lm_brain_notification_text"] = lm_brain.READY_NOTIFICATION_TEXT


def _activate_data_room_live_lm_brain(
    session: dict[str, Any],
    *,
    read_model_root: str | Path | None,
    now: str,
    live_lm_brain_runner=None,
    live_lm_brain_timeout_seconds: int = 90,
    live_lm_brain_sqlite_path: str | Path | None = None,
    live_lm_brain_package_root: str | Path | None = None,
    live_lm_brain_turn_root: str | Path | None = None,
) -> str:
    import data_room_live_lm_brain as lm_brain
    import codex_work_package_lifecycle as lifecycle

    run = lm_brain.run_live_lm_turn(
        session,
        lm_brain.READINESS_USER_TURN,
        created_at_utc=now,
        codex_runner=live_lm_brain_runner,
        timeout_seconds=live_lm_brain_timeout_seconds,
        sqlite_path=Path(live_lm_brain_sqlite_path) if live_lm_brain_sqlite_path else lifecycle.DEFAULT_SQLITE_PATH,
        package_root=Path(live_lm_brain_package_root) if live_lm_brain_package_root else lifecycle.DEFAULT_PACKAGE_ROOT,
        turn_root=Path(live_lm_brain_turn_root) if live_lm_brain_turn_root else lm_brain.DEFAULT_TURN_ROOT,
        read_model_path=_data_room_live_lm_brain_read_model_path(read_model_root),
    )
    _set_data_room_live_lm_brain_session_state(session, run=run, now=now, read_model_root=read_model_root)
    if run.get("status") == "ready":
        return lm_brain.READY_NOTIFICATION_TEXT
    status = run.get("status_read_model") if isinstance(run.get("status_read_model"), Mapping) else {}
    reason = str(run.get("reason") or status.get("last_error") or run.get("status") or "blocked")
    return f"Data Room LM brain blocked: {reason}. I did not send a live-LM readiness claim."


def _handle_data_room_live_lm_brain_turn(
    session: dict[str, Any],
    *,
    raw_text: str,
    surface: str,
    read_model_root: str | Path | None,
    now: str,
    live_lm_brain_runner=None,
    live_lm_brain_timeout_seconds: int = 90,
    live_lm_brain_sqlite_path: str | Path | None = None,
    live_lm_brain_package_root: str | Path | None = None,
    live_lm_brain_turn_root: str | Path | None = None,
) -> str:
    import data_room_live_lm_brain as lm_brain
    import codex_work_package_lifecycle as lifecycle

    lane = session.get("data_room_live_lm_brain") if isinstance(session.get("data_room_live_lm_brain"), Mapping) else {}
    run = lm_brain.run_live_lm_turn(
        session,
        raw_text,
        created_at_utc=now,
        recent_chat_summary=str(lane.get("chat_log_summary") or ""),
        codex_runner=live_lm_brain_runner,
        timeout_seconds=live_lm_brain_timeout_seconds,
        sqlite_path=Path(live_lm_brain_sqlite_path) if live_lm_brain_sqlite_path else lifecycle.DEFAULT_SQLITE_PATH,
        package_root=Path(live_lm_brain_package_root) if live_lm_brain_package_root else lifecycle.DEFAULT_PACKAGE_ROOT,
        turn_root=Path(live_lm_brain_turn_root) if live_lm_brain_turn_root else lm_brain.DEFAULT_TURN_ROOT,
        read_model_path=_data_room_live_lm_brain_read_model_path(read_model_root),
    )
    _set_data_room_live_lm_brain_session_state(session, run=run, now=now, read_model_root=read_model_root)
    if run.get("status") != "ready":
        status = run.get("status_read_model") if isinstance(run.get("status_read_model"), Mapping) else {}
        reason = str(run.get("reason") or status.get("last_error") or run.get("status") or "blocked")
        return (
            f"The Data Room LM brain failed on this turn ({reason}). "
            "I am falling back to the deterministic review coach for this turn.\n\n"
            f"{_format_question_reply(session)}"
        )
    result = run.get("turn_result") if isinstance(run.get("turn_result"), Mapping) else {}
    answer = result.get("proposed_answer") if isinstance(result.get("proposed_answer"), Mapping) else {}
    candidate_text = str(answer.get("plain_english") or answer.get("normalized_decision") or "").strip()
    intent = str(result.get("operator_intent") or "")
    if candidate_text and intent in {"answer_candidate", "conditional", "thought_dump"}:
        question_id = str(result.get("question_id") or session.get("current_question_id") or "")
        pending_candidate = _set_pending_answer_candidate(
            session,
            candidate_text=candidate_text,
            source_intent={
                "schema_version": "DATA_ROOM_LIVE_LM_BRAIN_PENDING_CANDIDATE_SOURCE_V0",
                "intent": intent,
                "request_id": str(result.get("request_id") or ""),
                "should_record_now": False,
                "confirmed_by_winship": False,
                "safety_flags": dict(result.get("safety_flags") or {}),
            },
            current_question_id=question_id,
            now=now,
            surface=surface,
        )
        _append_pending_interaction_event(
            session,
            command="data_room_live_lm_brain_pending_answer_candidate_created",
            question_id=question_id,
            now=now,
            answer_recorded=False,
        )
        session["pending_interaction"] = pending_candidate
    return str(result.get("assistant_reply") or "")


def _live_gemini_form_lane_active(session: Mapping[str, Any]) -> bool:
    lane = session.get("data_room_gemini_form_session")
    return bool(isinstance(lane, Mapping) and lane.get("active") is True and lane.get("live_ready") is True)


def _write_live_gemini_form_state(
    session: dict[str, Any],
    *,
    package: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    lane_status: str,
    live_ready: bool,
    blocked_reason: str,
    now: str,
    gemini_env: Mapping[str, str] | None = None,
    pending_candidate: Mapping[str, Any] | None = None,
    codex_finalizer_package_ref: str = "",
    codex_finalizer_status: str = "",
    provider_error: Mapping[str, Any] | None = None,
    minimal_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    import openclaw_gemini_form_adapter as gemini

    existing = session.get("data_room_gemini_form_session") if isinstance(session.get("data_room_gemini_form_session"), Mapping) else {}
    chat_summary = str(
        (result or {}).get("chat_log_summary_update")
        or existing.get("chat_log_summary")
        or package.get("prior_chat_log_summary")
        or ""
    )
    state = gemini.build_data_room_gemini_form_session_state(
        package=package,
        result=result or {},
        availability=gemini.is_live_gemini_form_available(gemini_env),
        lane_status=lane_status,
        live_ready=live_ready,
        blocked_reason=blocked_reason,
        generated_at_utc=now,
        chat_log_summary=chat_summary,
        pending_candidate=pending_candidate or {},
        codex_finalizer_package_ref=codex_finalizer_package_ref or str(existing.get("codex_finalizer_package_ref") or ""),
        codex_finalizer_status=codex_finalizer_status or str(existing.get("codex_finalizer_status") or ""),
        model=gemini.model_label(gemini_env),
        provider_error=provider_error or {},
        minimal_probe=minimal_probe or {},
    )
    refs = gemini.write_data_room_gemini_form_session_state(state)
    state["artifact_refs"] = refs
    session["data_room_gemini_form_session"] = {
        "schema_version": gemini.FORM_SESSION_SCHEMA_VERSION,
        "form_session_id": state["form_session_id"],
        "active": bool(live_ready and lane_status == "active"),
        "live_ready": bool(live_ready),
        "lane_status": lane_status,
        "model_label": state["model_label"],
        "last_gemini_request_id": state.get("last_gemini_request_id", ""),
        "last_gemini_result_id": state.get("last_gemini_result_id", ""),
        "running_chat_log_ref": state.get("running_chat_log_ref", ""),
        "chat_log_summary": state.get("chat_log_summary", ""),
        "blocked_reason": blocked_reason,
        "codex_finalizer_package_ref": state.get("codex_finalizer_package_ref", ""),
        "codex_finalizer_status": state.get("codex_finalizer_status", ""),
        "state_refs": refs,
        "updated_at_utc": now,
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
    }
    watch_refs = list(session.get("watch_desk_refs") or [])
    for item in state.get("watch_desk_items") or []:
        if isinstance(item, Mapping):
            item_id = str(item.get("item_id") or "")
            if item_id and item_id not in watch_refs:
                watch_refs.append(item_id)
    session["watch_desk_refs"] = watch_refs
    generated_refs = list(session.get("generated_prompt_refs") or [])
    for ref in refs.values():
        if ref and ref not in generated_refs:
            generated_refs.append(ref)
    session["generated_prompt_refs"] = generated_refs
    return state


def _activate_live_gemini_form_lane(
    session: dict[str, Any],
    *,
    raw_text: str,
    review_root: Path,
    read_model_root: str | Path | None,
    now: str,
    gemini_form_provider=None,
    gemini_form_env: Mapping[str, str] | None = None,
) -> str:
    from data_room_form_fill_package import build_data_room_form_fill_package
    import openclaw_gemini_form_adapter as gemini

    package = build_data_room_form_fill_package(session, created_at_utc=now)
    availability = gemini.is_live_gemini_form_available(gemini_form_env)
    availability_reason = gemini.availability_blocked_reason(availability)
    if availability_reason:
        state = _write_live_gemini_form_state(
            session,
            package=package,
            result=None,
            lane_status="blocked",
            live_ready=False,
            blocked_reason=availability_reason,
            now=now,
            gemini_env=gemini_form_env,
        )
        session.setdefault("data_room_gemini_form_refs", []).append(
            {
                "schema_version": "DATA_ROOM_GEMINI_FORM_ARTIFACT_REFS_V0",
                "package_id": package.get("package_id", ""),
                "review_session_id": package.get("review_session_id", ""),
                "live_ready": False,
                "blocked_reason": availability_reason,
                "minimal_probe_attempted": False,
                "minimal_probe_success": False,
                "data_room_readiness_attempted": False,
                "gemini_form_state_refs": dict(state.get("artifact_refs") or {}),
                "external_model_invoked": False,
                "confirmed_reference_data_created": False,
                "runtime_policy_changed": False,
            }
        )
        return f"Gemini Data Room form lane blocked: {availability_reason}. {gemini.safe_next_operator_step(availability_reason)}"
    selected_model = gemini.model_label(gemini_form_env)
    import openclaw_lm_consult_spine as consult_spine

    probe = consult_spine.run_minimal_gemini_probe(
        env=gemini_form_env,
        model_label=selected_model,
        transport=gemini_form_provider,
        timeout_seconds=20,
        generated_at_utc=now,
    )
    if not probe.get("success"):
        reason = str(probe.get("status") or "blocked_provider_probe_failed")
        state = _write_live_gemini_form_state(
            session,
            package=package,
            result=None,
            lane_status="blocked",
            live_ready=False,
            blocked_reason=reason,
            now=now,
            gemini_env=gemini_form_env,
            provider_error=probe,
            minimal_probe=probe,
        )
        session.setdefault("data_room_gemini_form_refs", []).append(
            {
                "schema_version": "DATA_ROOM_GEMINI_FORM_ARTIFACT_REFS_V0",
                "package_id": package.get("package_id", ""),
                "review_session_id": package.get("review_session_id", ""),
                "live_ready": False,
                "blocked_reason": reason,
                "minimal_probe_attempted": bool(probe.get("probe_attempted")),
                "minimal_probe_success": False,
                "data_room_readiness_attempted": False,
                "gemini_form_state_refs": dict(state.get("artifact_refs") or {}),
                "external_model_invoked": bool(probe.get("probe_attempted")),
                "confirmed_reference_data_created": False,
                "runtime_policy_changed": False,
            }
        )
        return f"Gemini Data Room form lane blocked: {reason}. {gemini.safe_next_operator_step(reason)}"
    try:
        result = gemini.call_gemini_data_room_form_turn(
            package,
            gemini.READINESS_PROMPT,
            str(package.get("prior_chat_log_summary") or ""),
            provider=gemini_form_provider,
            created_at_utc=now,
            env=gemini_form_env,
        )
    except gemini.GeminiFormAdapterError as exc:
        state = _write_live_gemini_form_state(
            session,
            package=package,
            result=None,
            lane_status="blocked",
            live_ready=False,
            blocked_reason=exc.reason,
            now=now,
            gemini_env=gemini_form_env,
            provider_error=exc.validation,
            minimal_probe=probe,
        )
        session.setdefault("data_room_gemini_form_refs", []).append(
            {
                "schema_version": "DATA_ROOM_GEMINI_FORM_ARTIFACT_REFS_V0",
                "package_id": package.get("package_id", ""),
                "review_session_id": package.get("review_session_id", ""),
                "live_ready": False,
                "blocked_reason": exc.reason,
                "minimal_probe_attempted": bool(probe.get("probe_attempted")),
                "minimal_probe_success": bool(probe.get("success")),
                "data_room_readiness_attempted": True,
                "gemini_form_state_refs": dict(state.get("artifact_refs") or {}),
                "external_model_invoked": True,
                "confirmed_reference_data_created": False,
                "runtime_policy_changed": False,
            }
        )
        return f"Gemini Data Room form lane blocked: {exc.reason}. {gemini.safe_next_operator_step(exc.reason)}"

    log_refs = gemini.append_data_room_gemini_form_turn_log(
        package=package,
        result=result,
        user_turn=gemini.READINESS_PROMPT,
        candidate_created=False,
        created_at_utc=now,
    )
    state = _write_live_gemini_form_state(
        session,
        package=package,
        result=result,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
        gemini_env=gemini_form_env,
        minimal_probe=probe,
    )
    session.setdefault("data_room_gemini_form_refs", []).append(
        {
            "schema_version": "DATA_ROOM_GEMINI_FORM_ARTIFACT_REFS_V0",
            "package_id": package.get("package_id", ""),
            "review_session_id": package.get("review_session_id", ""),
            "live_ready": True,
            "minimal_probe_attempted": bool(probe.get("probe_attempted")),
            "minimal_probe_success": bool(probe.get("success")),
            "data_room_readiness_attempted": True,
            "gemini_form_state_refs": dict(state.get("artifact_refs") or {}),
            "turn_log_refs": log_refs,
            "last_gemini_request_id": state.get("last_gemini_request_id", ""),
            "last_gemini_result_id": state.get("last_gemini_result_id", ""),
            "external_model_invoked": True,
            "advisory_only": True,
            "runtime_policy_changed": False,
            "confirmed_reference_data_created": False,
            "hydration_allowed": False,
        }
    )
    session["latest_data_room_gemini_form_package_id"] = package["package_id"]
    return gemini.GEMINI_FORM_READINESS_NOTIFICATION


def _handle_live_gemini_form_turn(
    session: dict[str, Any],
    *,
    raw_text: str,
    surface: str,
    review_root: Path,
    now: str,
    gemini_form_provider=None,
    gemini_form_env: Mapping[str, str] | None = None,
) -> str:
    from data_room_form_fill_package import build_data_room_form_fill_package
    import openclaw_gemini_form_adapter as gemini

    package = build_data_room_form_fill_package(session, created_at_utc=now)
    try:
        result = gemini.call_gemini_data_room_form_turn(
            package,
            raw_text,
            str((session.get("data_room_gemini_form_session") or {}).get("chat_log_summary") or package.get("prior_chat_log_summary") or ""),
            provider=gemini_form_provider,
            created_at_utc=now,
            env=gemini_form_env,
        )
    except gemini.GeminiFormAdapterError as exc:
        _write_live_gemini_form_state(
            session,
            package=package,
            result=None,
            lane_status="unavailable",
            live_ready=False,
            blocked_reason=exc.reason,
            now=now,
            gemini_env=gemini_form_env,
            provider_error=exc.validation,
        )
        return (
            f"The Gemini Data Room form lane is temporarily unavailable ({exc.reason}). "
            "I am falling back to the deterministic review coach.\n\n"
            f"{_format_question_reply(session)}"
        )

    answer = result.get("proposed_answer") if isinstance(result.get("proposed_answer"), Mapping) else {}
    candidate_text = str(answer.get("plain_english") or answer.get("normalized_decision") or "").strip()
    intent = str(result.get("operator_intent") or "")
    candidate_created = False
    pending_candidate: dict[str, Any] | None = None
    if candidate_text and intent in {"answer_candidate", "conditional", "revise", "thought_dump"}:
        question_id = str(result.get("question_id") or session.get("current_question_id") or "")
        pending_candidate = _set_pending_answer_candidate(
            session,
            candidate_text=candidate_text,
            source_intent={
                "schema_version": "DATA_ROOM_GEMINI_PENDING_CANDIDATE_SOURCE_V0",
                "intent": intent,
                "request_id": str(result.get("request_id") or ""),
                "result_id": gemini.result_id_for(result),
                "result_snapshot": dict(result),
                "should_record_now": False,
                "confirmed_by_winship": False,
                "safety_flags": dict(result.get("safety_flags") or {}),
            },
            current_question_id=question_id,
            now=now,
            surface=surface,
        )
        _append_pending_interaction_event(
            session,
            command="live_gemini_pending_answer_candidate_created",
            question_id=question_id,
            now=now,
            answer_recorded=False,
        )
        session["pending_interaction"] = pending_candidate
        candidate_created = True

    gemini.append_data_room_gemini_form_turn_log(
        package=package,
        result=result,
        user_turn=raw_text,
        candidate_created=candidate_created,
        created_at_utc=now,
    )
    _write_live_gemini_form_state(
        session,
        package=package,
        result=result,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
        gemini_env=gemini_form_env,
        pending_candidate=pending_candidate or {},
    )
    return str(result.get("assistant_reply") or "")


def _append_gemini_confirmation_log_if_needed(
    session: dict[str, Any],
    *,
    pending: Mapping[str, Any],
    before_answer_count: int,
    raw_text: str,
    now: str,
    gemini_form_env: Mapping[str, str] | None = None,
) -> None:
    source = pending.get("source_intent") if isinstance(pending.get("source_intent"), Mapping) else {}
    if source.get("schema_version") != "DATA_ROOM_GEMINI_PENDING_CANDIDATE_SOURCE_V0":
        return
    answers = session.get("answer_records") if isinstance(session.get("answer_records"), list) else []
    if len(answers) <= before_answer_count:
        return
    import openclaw_gemini_form_adapter as gemini
    from data_room_form_fill_package import build_data_room_form_fill_package

    result = source.get("result_snapshot") if isinstance(source.get("result_snapshot"), Mapping) else {}
    latest = answers[-1] if answers and isinstance(answers[-1], Mapping) else {}
    package = build_data_room_form_fill_package(session, created_at_utc=now)
    gemini.append_data_room_gemini_form_turn_log(
        package=package,
        result=result,
        user_turn=raw_text,
        candidate_created=False,
        confirmed_answer_id=str(latest.get("answer_id") or latest.get("receipt_ref") or ""),
        created_at_utc=now,
    )
    _write_live_gemini_form_state(
        session,
        package=package,
        result=result,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
        gemini_env=gemini_form_env,
    )


def _gemini_done_criteria_ready(session: Mapping[str, Any]) -> bool:
    progress = _progress(session)
    pending = session.get("pending_interaction") if isinstance(session.get("pending_interaction"), Mapping) else {}
    unsafe = any(bool(value) for value in (session.get("safety_flags") or {}).values()) if isinstance(session.get("safety_flags"), Mapping) else False
    return bool(progress["remaining"] == 0 and not pending and not unsafe)


def _gemini_finalizer_pending(session: Mapping[str, Any]) -> bool:
    pending = session.get("data_room_gemini_form_finalization")
    return bool(isinstance(pending, Mapping) and pending.get("awaiting_winship_confirmation") is True)


def _begin_gemini_finalizer_confirmation(
    session: dict[str, Any],
    *,
    now: str,
    gemini_form_env: Mapping[str, str] | None = None,
) -> str:
    from data_room_form_fill_package import build_data_room_form_fill_package

    package = build_data_room_form_fill_package(session, created_at_utc=now)
    session["data_room_gemini_form_finalization"] = {
        "schema_version": "DATA_ROOM_GEMINI_FORM_FINALIZATION_CONFIRMATION_V0",
        "awaiting_winship_confirmation": True,
        "created_at_utc": now,
        "prompt": "Do you want Codex to promote the confirmed answers and run hydration?",
        "confirmed_reference_data_created": False,
        "hydration_started": False,
        "codex_package_created": False,
    }
    _write_live_gemini_form_state(
        session,
        package=package,
        result=None,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
        gemini_env=gemini_form_env,
        codex_finalizer_status="awaiting_winship_confirmation",
    )
    return (
        f"Here is where we are: {_progress_line(session)}. "
        "Do you want Codex to promote the confirmed answers and run hydration?"
    )


def _handle_gemini_finalizer_confirmation(
    session: dict[str, Any],
    *,
    raw_text: str,
    now: str,
    read_model_root: str | Path | None,
    gemini_form_env: Mapping[str, str] | None = None,
) -> str:
    import codex_work_package_lifecycle as lifecycle
    import openclaw_gemini_form_adapter as gemini
    from data_room_form_fill_package import build_data_room_form_fill_package

    natural = parse_natural_reply_intent(raw_text, session.get("data_room_gemini_form_finalization") or {})
    if not _is_bare_yes(raw_text) and natural.get("intent") != "confirm_candidate":
        session["data_room_gemini_form_finalization"] = {}
        package = build_data_room_form_fill_package(session, created_at_utc=now)
        _write_live_gemini_form_state(
            session,
            package=package,
            result=None,
            lane_status="active",
            live_ready=True,
            blocked_reason="",
            now=now,
            gemini_env=gemini_form_env,
            codex_finalizer_status="cancelled_by_winship",
        )
        return "Okay. I did not create the Codex finalizer package."

    queue_result = gemini.queue_codex_finalizer_work_package(session, generated_at_utc=now)
    try:
        lifecycle.export_codex_work_package_lifecycle(
            sqlite_path=gemini.DEFAULT_CODEX_FINALIZER_SQLITE_PATH,
            package_root=gemini.DEFAULT_CODEX_FINALIZER_PACKAGE_ROOT,
            export_root=_read_model_root(read_model_root),
            bridge_root=None,
            wiki_path=_read_model_root(read_model_root) / "Codex Work Package Lifecycle.md",
        )
    except Exception:
        pass
    package = build_data_room_form_fill_package(session, created_at_utc=now)
    session["data_room_gemini_form_finalization"] = {
        "schema_version": "DATA_ROOM_GEMINI_FORM_FINALIZATION_CONFIRMATION_V0",
        "awaiting_winship_confirmation": False,
        "confirmed_at_utc": now,
        "codex_package_created": True,
        "codex_finalizer_package_ref": queue_result["package_id"],
        "codex_finalizer_status": queue_result["status"],
        "codex_automatic_dispatch_real": False,
        "confirmed_reference_data_created": False,
        "hydration_started": False,
    }
    _write_live_gemini_form_state(
        session,
        package=package,
        result=None,
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        now=now,
        gemini_env=gemini_form_env,
        codex_finalizer_package_ref=queue_result["package_id"],
        codex_finalizer_status=queue_result["status"],
    )
    return (
        "I queued the Codex finalizer package. It is waiting for Codex dispatch; "
        "there is no approved automatic Codex invocation bridge configured yet."
    )


def process_guided_review_message(
    raw_text: str,
    *,
    surface: str = "telegram",
    operator: str = "Winship",
    review_root: str | Path | None = None,
    read_model_root: str | Path | None = None,
    promotion_review_path: str | Path | None = None,
    receipt_root: str | Path | None = None,
    generated_at_utc: str | None = None,
    chatgpt55_provider=None,
    chatgpt55_env: Mapping[str, str] | None = None,
    gemini_form_provider=None,
    gemini_form_env: Mapping[str, str] | None = None,
    live_lm_brain_runner=None,
    live_lm_brain_timeout_seconds: int = 90,
    live_lm_brain_sqlite_path: str | Path | None = None,
    live_lm_brain_package_root: str | Path | None = None,
    live_lm_brain_turn_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Process a Cassandra guided-review turn without external side effects."""

    if not raw_text or not raw_text.strip() or _excluded_route_text(raw_text):
        return None
    root = _review_root(review_root)
    now = generated_at_utc or utc_now()
    active = _find_active_session(root)
    resolution = resolve_guided_review_topic(raw_text, active_session_context=active)
    live_start_request = _is_live_chatgpt55_data_room_start_request(raw_text)
    gemini_start_request = _is_live_gemini_form_start_request(raw_text)
    lm_brain_start_request = _is_data_room_live_lm_brain_start_request(raw_text)
    topic = str(resolution.get("matched_topic_id") or "")
    if (live_start_request or gemini_start_request or lm_brain_start_request) and not topic:
        topic = TOPIC_DATA_ROOM
    if not active and not topic and not resolution.get("clarification_question"):
        return None
    if (
        not active
        and resolution.get("clarification_question")
        and not resolution.get("should_start_session")
        and not live_start_request
        and not gemini_start_request
        and not lm_brain_start_request
    ):
        return _clarification_response(resolution, reply_text=str(resolution["clarification_question"]))
    if (
        not active
        and not resolution.get("should_start_session")
        and not live_start_request
        and not gemini_start_request
        and not lm_brain_start_request
    ):
        return None
    if not active:
        try:
            session = create_data_room_review_session(
                topic=topic or TOPIC_DATA_ROOM,
                operator=operator,
                surface=surface,
                review_root=root,
                promotion_review_path=promotion_review_path,
                created_at_utc=now,
            )
            session["coach_start_phrase_detected"] = detect_coach_intent(raw_text)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            blocked = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "review_session_id": "data_room_review:blocked",
                "topic": topic or TOPIC_DATA_ROOM,
                "topic_display_name": _topic_display_name(topic or TOPIC_DATA_ROOM),
                "source_artifact_refs": [str(_promotion_path(promotion_review_path))],
                "created_at_utc": now,
                "updated_at_utc": now,
                "operator": operator,
                "surface": surface,
                "status": "blocked",
                "question_queue": [],
                "current_question_id": "",
                "answered_questions": [],
                "skipped_questions": [],
                "deferred_questions": [],
                "unresolved_questions": [],
                "answer_records": [],
                "generated_prompt_refs": [],
                "receipt_refs": [],
                "watch_desk_refs": [],
                "authoritative": False,
                "runtime_policy_changed": False,
            }
            return _response(
                session=blocked,
                reply_text=f"I could not start the Data Room review because the promotion review artifact is unavailable: {type(exc).__name__}.",
                review_root=root,
                read_model_root=read_model_root,
                handled=True,
            )
        if gemini_start_request:
            reply = _activate_live_gemini_form_lane(
                session,
                raw_text=raw_text,
                review_root=root,
                read_model_root=read_model_root,
                now=now,
                gemini_form_provider=gemini_form_provider,
                gemini_form_env=gemini_form_env,
            )
        elif lm_brain_start_request:
            reply = _activate_data_room_live_lm_brain(
                session,
                read_model_root=read_model_root,
                now=now,
                live_lm_brain_runner=live_lm_brain_runner,
                live_lm_brain_timeout_seconds=live_lm_brain_timeout_seconds,
                live_lm_brain_sqlite_path=live_lm_brain_sqlite_path,
                live_lm_brain_package_root=live_lm_brain_package_root,
                live_lm_brain_turn_root=live_lm_brain_turn_root,
            )
        elif live_start_request:
            reply = _activate_live_chatgpt55_data_room_lane(
                session,
                raw_text=raw_text,
                review_root=root,
                read_model_root=read_model_root,
                now=now,
                chatgpt55_provider=chatgpt55_provider,
                chatgpt55_env=chatgpt55_env,
            )
        else:
            total = len(session["question_queue"])
            topic_display = str(session.get("topic_display_name") or _topic_display_name(topic or TOPIC_DATA_ROOM))
            intro = (
                f"Cool. I found {total} provisional {topic_display} items. I'll walk you through "
                "the highest-impact questions first: identity, payment privacy, rates, clients, "
                "invoice numbering. You can answer, skip, defer, revise, summarize, or say done."
            )
            reply = _format_question_reply(session, prefix=intro)
    else:
        session = dict(active)
        control = _control_text(raw_text)
        if topic and not _topic_record(topic).get("start_allowed", False):
            return None
        if not control and not resolution.get("should_resume_active_session") and not topic and _looks_like_non_review_operator_action(raw_text):
            return None
        pending = _active_pending_interaction(session, now=now)
        if session.get("pending_interaction") and not pending:
            _clear_pending_interaction(session, now=now, reason="expired")
        pending_handled = False
        form_fill_handled = False
        from data_room_form_fill_package import (
            DEFAULT_OPERATOR_REPORT_ROOT,
            EXPECTED_PACKAGE_REPLY,
            LIVE_CHATGPT55_PACKAGE_REPLY,
            build_data_room_form_fill_package,
            is_data_room_form_fill_request,
            live_chatgpt55_advisory_path_verified,
            write_data_room_form_fill_artifacts,
        )

        if gemini_start_request:
            reply = _activate_live_gemini_form_lane(
                session,
                raw_text=raw_text,
                review_root=root,
                read_model_root=read_model_root,
                now=now,
                gemini_form_provider=gemini_form_provider,
                gemini_form_env=gemini_form_env,
            )
            form_fill_handled = True
        elif lm_brain_start_request:
            reply = _activate_data_room_live_lm_brain(
                session,
                read_model_root=read_model_root,
                now=now,
                live_lm_brain_runner=live_lm_brain_runner,
                live_lm_brain_timeout_seconds=live_lm_brain_timeout_seconds,
                live_lm_brain_sqlite_path=live_lm_brain_sqlite_path,
                live_lm_brain_package_root=live_lm_brain_package_root,
                live_lm_brain_turn_root=live_lm_brain_turn_root,
            )
            form_fill_handled = True
        elif live_start_request:
            reply = _activate_live_chatgpt55_data_room_lane(
                session,
                raw_text=raw_text,
                review_root=root,
                read_model_root=read_model_root,
                now=now,
                chatgpt55_provider=chatgpt55_provider,
                chatgpt55_env=chatgpt55_env,
            )
            form_fill_handled = True
        elif is_data_room_form_fill_request(raw_text):
            package = build_data_room_form_fill_package(session, created_at_utc=now)
            live_chatgpt55_connected = live_chatgpt55_advisory_path_verified()
            form_fill_refs = write_data_room_form_fill_artifacts(
                package,
                export_operator_copy=True,
                operator_report_root=DEFAULT_OPERATOR_REPORT_ROOT,
            )
            session.setdefault("data_room_form_fill_refs", []).append(form_fill_refs)
            generated_refs = list(session.get("generated_prompt_refs") or [])
            for ref in (
                form_fill_refs.get("primary", {}).get("prompt_path", ""),
                form_fill_refs.get("durable", {}).get("prompt_path", ""),
            ):
                if ref and ref not in generated_refs:
                    generated_refs.append(ref)
            session["generated_prompt_refs"] = generated_refs
            session["latest_data_room_form_fill_package_id"] = package["package_id"]
            reply = LIVE_CHATGPT55_PACKAGE_REPLY if live_chatgpt55_connected else EXPECTED_PACKAGE_REPLY
            form_fill_handled = True
        elif _gemini_finalizer_pending(session):
            reply = _handle_gemini_finalizer_confirmation(
                session,
                raw_text=raw_text,
                now=now,
                read_model_root=read_model_root,
                gemini_form_env=gemini_form_env,
            )
            form_fill_handled = True
        elif pending and not _is_global_control_allowed_during_pending(control):
            pending_snapshot = dict(pending)
            before_answer_count = len(session.get("answer_records") or [])
            reply = _handle_pending_interaction(
                session,
                pending=pending,
                raw_text=raw_text,
                surface=surface,
                review_root=root,
                receipt_root=receipt_root,
                now=now,
            )
            _append_gemini_confirmation_log_if_needed(
                session,
                pending=pending_snapshot,
                before_answer_count=before_answer_count,
                raw_text=raw_text,
                now=now,
                gemini_form_env=gemini_form_env,
            )
            pending_handled = True
        elif pending and _is_global_control_allowed_during_pending(control):
            _clear_pending_interaction(session, now=now, reason=f"interrupted_by_{control.replace(' ', '_')}")

        if form_fill_handled:
            pass
        elif pending_handled:
            pass
        elif _live_lm_brain_active(session) and control not in {
            "done",
            "summarize",
            "skip",
            "defer",
            "next question",
            "use_recommendation",
            "revise_previous",
        }:
            reply = _handle_data_room_live_lm_brain_turn(
                session,
                raw_text=raw_text,
                surface=surface,
                read_model_root=read_model_root,
                now=now,
                live_lm_brain_runner=live_lm_brain_runner,
                live_lm_brain_timeout_seconds=live_lm_brain_timeout_seconds,
                live_lm_brain_sqlite_path=live_lm_brain_sqlite_path,
                live_lm_brain_package_root=live_lm_brain_package_root,
                live_lm_brain_turn_root=live_lm_brain_turn_root,
            )
        elif _live_gemini_form_lane_active(session) and control == "done":
            if _gemini_done_criteria_ready(session):
                reply = _begin_gemini_finalizer_confirmation(
                    session,
                    now=now,
                    gemini_form_env=gemini_form_env,
                )
            else:
                reply = (
                    f"Not ready for Codex finalization yet: {_progress_line(session)}. "
                    "Every question needs to be answered, skipped, or deferred, and no candidate can be pending."
                )
        elif _live_gemini_form_lane_active(session) and control not in {
            "done",
            "summarize",
            "skip",
            "defer",
            "next question",
            "use_recommendation",
            "revise_previous",
        }:
            reply = _handle_live_gemini_form_turn(
                session,
                raw_text=raw_text,
                surface=surface,
                review_root=root,
                now=now,
                gemini_form_provider=gemini_form_provider,
                gemini_form_env=gemini_form_env,
            )
        elif _live_chatgpt55_lane_active(session) and control not in {
            "done",
            "summarize",
            "skip",
            "defer",
            "next question",
            "use_recommendation",
            "revise_previous",
        }:
            reply = _handle_live_chatgpt55_data_room_turn(
                session,
                raw_text=raw_text,
                surface=surface,
                review_root=root,
                now=now,
                chatgpt55_provider=chatgpt55_provider,
                chatgpt55_env=chatgpt55_env,
            )
        elif control in {"why", "recommend", "examples"}:
            _enable_coach_mode(session)
            question = _question_by_id(session, str(session.get("current_question_id") or ""))
            if not question:
                reply = "No active question is available. Say done to generate the promotion prompt."
            else:
                card = _coach_card_for_question(session, question)
                _append_coach_interaction(
                    session,
                    command=control,
                    question_id=str(question.get("question_id") or ""),
                    now=now,
                )
                reply = render_coach_reply(
                    card,
                    control,
                    surface=surface,
                    style=str(session.get("coaching_style") or "concise"),
                )
        elif control == "use_recommendation":
            _enable_coach_mode(session)
            question = _question_by_id(session, str(session.get("current_question_id") or ""))
            if not question:
                reply = "No active question is available. Say done to generate the promotion prompt."
            else:
                card = _coach_card_for_question(session, question)
                option = _recommended_option(card)
                selected_option_id = str(option.get("option_id") or "recommended_default")
                selected_option_label = str(option.get("label") or "recommended default")
                answer_text = str(option.get("answer_text") or card.get("recommended_default") or selected_option_label)
                _append_coach_interaction(
                    session,
                    command=control,
                    question_id=str(question.get("question_id") or ""),
                    selected_option_id=selected_option_id,
                    now=now,
                )
                _apply_answer(
                    session,
                    answer_text,
                    surface=surface,
                    review_root=root,
                    receipt_root=receipt_root,
                    now=now,
                    selected_option_id=selected_option_id,
                    selected_option_label=selected_option_label,
                )
                if not session.get("current_question_id"):
                    session = complete_session(session, review_root=root, now=now)
                    reply = (
                        f"Recorded my recommendation. All questions are answered, skipped, or deferred. "
                        f"I wrote the promotion prompt: {_prompt_path(root, str(session['review_session_id'])).as_posix()}"
                    )
                else:
                    reply = _format_question_reply(session, prefix="Recorded my recommendation.")
        elif control == "revise_previous":
            _enable_coach_mode(session)
            question_id = _rewind_to_previous_answer(session, now=now)
            if not question_id:
                reply = "I do not have a previous answer to revise yet."
            else:
                _append_coach_interaction(session, command=control, question_id=question_id, now=now)
                reply = _format_question_reply(
                    session,
                    prefix="I reopened the previous answered question. The old answer stays in the audit trail but is ignored for promotion.",
                )
        elif not control and (resolution.get("should_resume_active_session") or topic):
            topic_display = str(session.get("topic_display_name") or _topic_display_name(str(session.get("topic") or TOPIC_DATA_ROOM)))
            reply = _format_question_reply(session, prefix=f"Continuing the active {topic_display}.")
        elif control == "summarize":
            reply = _session_summary_reply(session)
        elif control == "done":
            session = complete_session(session, review_root=root, now=now)
            prompt = _prompt_path(root, str(session["review_session_id"]))
            reply = (
                f"Done. Data Room review closed: {_progress_line(session)} "
                f"I wrote the answer artifact and Codex promotion prompt: {prompt.as_posix()}"
            )
        elif control == "skip" or control == "next question":
            _mark_current_question(session, status="skipped", now=now)
            reply = _format_question_reply(session, prefix="Skipped.")
        elif control == "defer":
            _mark_current_question(session, status="deferred", now=now)
            reply = _format_question_reply(session, prefix="Deferred.")
        else:
            question = _question_by_id(session, str(session.get("current_question_id") or ""))
            natural_intent = parse_natural_reply_intent(raw_text)
            natural_kind = str(natural_intent.get("intent") or "")
            if _is_bare_yes(raw_text):
                reply = "Yes to what? Can you give me the answer in a sentence?"
            elif natural_kind in {"ask_explanation", "ask_eli5", "ask_analogy", "ask_examples", "ask_recommendation"}:
                if question:
                    _append_coach_interaction(
                        session,
                        command=natural_kind,
                        question_id=str(question.get("question_id") or ""),
                        now=now,
                    )
                reply = _natural_explanation_reply(session, question or {}, natural_kind)
            elif natural_kind in {"revise_candidate", "thought_dump", "conditional_answer", "soften_candidate", "strengthen_candidate"}:
                if not question:
                    reply = "No active question is available. Say done to generate the promotion prompt."
                elif natural_kind in {"soften_candidate", "strengthen_candidate"}:
                    reply = "What wording should I change? Give me the sentence you want me to consider."
                elif natural_kind == "conditional_answer":
                    candidate = _candidate_from_condition(raw_text, str(natural_intent.get("condition_text") or ""))
                    if not candidate:
                        _set_pending_condition_request(
                            session,
                            source_intent=natural_intent,
                            current_question_id=str(question.get("question_id") or ""),
                            now=now,
                            surface=surface,
                        )
                        _append_pending_interaction_event(
                            session,
                            command="pending_condition_requested",
                            question_id=str(question.get("question_id") or ""),
                            now=now,
                            answer_recorded=False,
                        )
                        reply = "What condition should decide it?"
                    else:
                        pending_candidate = _set_pending_answer_candidate(
                            session,
                            candidate_text=candidate,
                            source_intent=natural_intent,
                            current_question_id=str(question.get("question_id") or ""),
                            now=now,
                            surface=surface,
                        )
                        _append_pending_interaction_event(
                            session,
                            command="pending_answer_candidate_created",
                            question_id=str(question.get("question_id") or ""),
                            now=now,
                            answer_recorded=False,
                        )
                        reply = _candidate_prompt(str(pending_candidate.get("candidate_text") or candidate))
                else:
                    candidate = (
                        str(natural_intent.get("extracted_revision_text") or "").strip()
                        if natural_kind == "revise_candidate"
                        else _candidate_from_thought_dump(raw_text)
                    )
                    if not candidate:
                        reply = "Can you give me the answer in a sentence?"
                    else:
                        pending_candidate = _set_pending_answer_candidate(
                            session,
                            candidate_text=candidate,
                            source_intent=natural_intent,
                            current_question_id=str(question.get("question_id") or ""),
                            now=now,
                            surface=surface,
                        )
                        _append_pending_interaction_event(
                            session,
                            command="pending_answer_candidate_created",
                            question_id=str(question.get("question_id") or ""),
                            now=now,
                            answer_recorded=False,
                        )
                        if natural_kind == "thought_dump":
                            reply = f"Here's the thread I'm hearing: {candidate}\n{_candidate_prompt(candidate)}"
                        else:
                            reply = _candidate_prompt(candidate)
            else:
                mismatch = _answer_topic_mismatch(raw_text, question or {}) if question else {}
                if mismatch:
                    _enable_coach_mode(session)
                    pending = _set_pending_topic_switch(
                        session,
                        original_text=raw_text,
                        mismatch=mismatch,
                        question=question or {},
                        now=now,
                        surface=surface,
                    )
                    _append_topic_mismatch_clarification(
                        session,
                        question_id=str(question.get("question_id") or "") if question else "",
                        now=now,
                        mismatch=mismatch,
                    )
                    reply = _pending_prompt(pending)
                else:
                    _apply_answer(
                        session,
                        raw_text,
                        surface=surface,
                        review_root=root,
                        receipt_root=receipt_root,
                        now=now,
                    )
                    if not session.get("current_question_id"):
                        session = complete_session(session, review_root=root, now=now)
                        reply = (
                            f"Recorded. All questions are answered, skipped, or deferred. "
                            f"I wrote the promotion prompt: {_prompt_path(root, str(session['review_session_id'])).as_posix()}"
                        )
                    else:
                        reply = _format_question_reply(session, prefix=_recorded_answer_prefix(raw_text, question or {}))
        session["updated_at_utc"] = now
        _persist_session(session, review_root=root)

    session_path = _persist_session(session, review_root=root)
    session["session_artifact_ref"] = session_path.as_posix()
    write_guided_review_read_model([session], read_model_root=read_model_root, generated_at_utc=now)
    watch_item = _session_read_model_item(session)
    session["watch_desk_refs"] = [watch_item["item_id"]]
    _persist_session(session, review_root=root)
    write_guided_review_read_model([session], read_model_root=read_model_root, generated_at_utc=now)
    watch_refresh = _refresh_watch_desk(read_model_root, now)
    return _response(
        session=session,
        reply_text=reply,
        review_root=root,
        read_model_root=read_model_root,
        watch_refresh=watch_refresh,
        handled=True,
    )


__all__ = [
    "ANSWER_SCHEMA_VERSION",
    "QUESTION_SCHEMA_VERSION",
    "READ_MODEL_NAME",
    "SESSION_SCHEMA_VERSION",
    "build_data_room_review_questions",
    "complete_session",
    "create_data_room_review_session",
    "has_active_guided_review_session",
    "is_guided_review_message",
    "process_guided_review_message",
    "resolve_guided_review_topic",
    "stable_json",
    "write_guided_review_read_model",
]
