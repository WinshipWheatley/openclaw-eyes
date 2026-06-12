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

from cassandra_review_coach import build_coach_card, coach_command, detect_coach_intent, render_coach_reply


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


def is_guided_review_message(text: str, *, review_root: str | Path | None = None) -> bool:
    if not text or not text.strip() or _excluded_route_text(text):
        return False
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
    if any(term in text for term in ("direct deposit", "payment privacy", "home address", "public phone", "bank account", "routing number", "tax identifiers", "ssn", "ein", "tokens", "credentials", "secrets", "payment_policy")):
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


def _session_summary_reply(session: Mapping[str, Any]) -> str:
    return f"{str(session.get('topic_display_name') or _topic_display_name(str(session.get('topic') or TOPIC_DATA_ROOM)))} progress: {_progress_line(session)}"


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
        "answer_id": answer["answer_id"],
        "normalized_answer": answer["normalized_answer"],
        "affected_records": answer["affected_record_ids"],
        "selected_option_id": str(answer.get("selected_option_id") or ""),
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
) -> None:
    question_id = str(session.get("current_question_id") or "")
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
    verb = "in progress" if status in {"active", "paused"} else status
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
) -> dict[str, Any] | None:
    """Process a Cassandra guided-review turn without external side effects."""

    if not raw_text or not raw_text.strip() or _excluded_route_text(raw_text):
        return None
    root = _review_root(review_root)
    now = generated_at_utc or utc_now()
    active = _find_active_session(root)
    resolution = resolve_guided_review_topic(raw_text, active_session_context=active)
    topic = str(resolution.get("matched_topic_id") or "")
    if not active and not topic and not resolution.get("clarification_question"):
        return None
    if not active and resolution.get("clarification_question") and not resolution.get("should_start_session"):
        return _clarification_response(resolution, reply_text=str(resolution["clarification_question"]))
    if not active and not resolution.get("should_start_session"):
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
        if control in {"why", "recommend", "examples"}:
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
                reply = _format_question_reply(session, prefix="Recorded.")
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
