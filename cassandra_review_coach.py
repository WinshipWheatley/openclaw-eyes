"""Deterministic coach rendering for Cassandra guided reviews."""

from __future__ import annotations

import re
from typing import Any, Mapping

from cassandra_review_coach_packs import coach_pack_for_category


REVIEW_OPTION_SCHEMA_VERSION = "REVIEW_OPTION_V0"
REVIEW_COACH_CARD_SCHEMA_VERSION = "REVIEW_COACH_CARD_V0"
NATURAL_REPLY_INTENT_SCHEMA_VERSION = "NATURAL_REPLY_INTENT_V0"

NATURAL_REPLY_SAFETY_FLAGS = {
    "external_calls_performed": False,
    "runtime_policy_changed": False,
    "approval_created": False,
    "invoice_or_ledger_mutated": False,
    "confirmed_reference_data_generated": False,
}


def _normalize(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = lowered.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    lowered = lowered.replace("?", " ").replace("!", " ")
    return " ".join(re.sub(r"[^a-z0-9']+", " ", lowered).split())


def _text_hash(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _has_pending(pending_interaction: Mapping[str, Any] | None) -> bool:
    return bool(pending_interaction and pending_interaction.get("kind"))


def _extract_revision_text(raw_text: str, normalized: str) -> str:
    patterns = (
        r"^\s*no[, ]+but maybe\s+(.+)$",
        r"^\s*not exactly[, ]+(.+)$",
        r"^\s*(?:that'?s\s+)?close[, ]+but\s+(.+)$",
        r"^\s*that'?s close[, ]+make it\s+(.+)$",
        r"^\s*maybe say\s+(.+)$",
        r"^\s*i mean\s+(.+)$",
        r"^\s*revise that to\s+(.+)$",
        r"^\s*change that to\s+(.+)$",
        r"^\s*make it(?: say)?\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, str(raw_text or "").strip(), flags=re.IGNORECASE)
        if match:
            return " ".join(match.group(1).strip(" .").split())
    marker_patterns = (
        ("no but maybe ", 13),
        ("not exactly ", 12),
        ("close but ", 10),
        ("that's close make it ", 21),
        ("thats close make it ", 20),
        ("maybe say ", 10),
        ("i mean ", 7),
        ("revise that to ", 15),
    )
    for marker, length in marker_patterns:
        if normalized.startswith(marker):
            return normalized[length:].strip()
    return ""


def _condition_text(raw_text: str, normalized: str) -> str:
    if normalized in {"sometimes", "it depends", "depends", "case by case"}:
        return ""
    for marker in ("it depends on ", "depends on ", "only for ", "for "):
        if normalized.startswith(marker):
            return " ".join(str(raw_text).strip(" .").split())
    if any(phrase in normalized for phrase in ("case by case", "depends on whether", "it depends whether")):
        return " ".join(str(raw_text).strip(" .").split())
    return ""


def parse_natural_reply_intent(text: str, pending_interaction: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Classify natural review-coach replies without creating truth or authority."""

    raw = str(text or "")
    normalized = _normalize(raw)
    pending_id = ""
    if pending_interaction:
        pending_id = str(
            pending_interaction.get("pending_interaction_id")
            or pending_interaction.get("candidate_id")
            or pending_interaction.get("original_utterance_hash")
            or ""
        )
    intent = "ambiguous"
    confidence = 0.35
    extracted_revision_text = ""
    condition_text = ""

    confirmation_phrases = {
        "yes",
        "y",
        "yes that's right",
        "yes thats right",
        "yeah that's right",
        "yeah thats right",
        "that's right",
        "thats right",
        "correct",
        "exactly",
        "yep",
        "yup",
        "go with that",
        "yeah go with that",
        "use that",
        "record that",
        "that works",
        "sounds right",
        "yes record that",
        "yes go with that",
    }
    switch_confirm_phrases = {
        "yeah switch it",
        "yes switch it",
        "put it there",
        "yes put it there",
        "record it under payment privacy",
        "yes put it under payment privacy",
        "yes record it under payment privacy",
    }
    rejection_phrases = {"no", "nope", "not that", "no thanks", "reject that"}

    if normalized in confirmation_phrases or normalized in switch_confirm_phrases:
        intent = "confirm_candidate"
        confidence = 0.95
    elif normalized in rejection_phrases:
        intent = "reject_candidate"
        confidence = 0.9
    elif normalized in {"eli5", "explain like i'm five", "explain like im five", "explain simply"}:
        intent = "ask_eli5"
        confidence = 0.95
    elif "analogy" in normalized:
        intent = "ask_analogy"
        confidence = 0.9
    elif normalized in {"examples", "example", "show examples", "give examples"}:
        intent = "ask_examples"
        confidence = 0.95
    elif normalized in {
        "what do you recommend",
        "what would you recommend",
        "what would a normal small business do",
        "what should i do",
    }:
        intent = "ask_recommendation"
        confidence = 0.9
    elif normalized in {
        "what does that mean",
        "help me understand",
        "why does this matter",
        "what could go wrong",
    }:
        intent = "ask_explanation"
        confidence = 0.9
    elif normalized in {"skip", "skip this", "skip question", "next", "next question"}:
        intent = "skip"
        confidence = 0.95
    elif normalized in {"defer", "defer this", "defer question", "i don't know", "i dont know"}:
        intent = "defer"
        confidence = 0.85
    elif normalized in {"done", "finish", "complete", "that's all", "thats all"}:
        intent = "done"
        confidence = 0.95
    elif normalized in {"make it softer", "say it softer", "softer"}:
        intent = "soften_candidate"
        confidence = 0.85
    elif normalized in {"make it stricter", "say it stricter", "stricter"}:
        intent = "strengthen_candidate"
        confidence = 0.85
    else:
        extracted_revision_text = _extract_revision_text(raw, normalized)
        if extracted_revision_text:
            intent = "revise_candidate"
            confidence = 0.9
        elif any(
            phrase in normalized
            for phrase in (
                "let me ramble",
                "here's the messy version",
                "heres the messy version",
                "i'm not sure what matters",
                "im not sure what matters",
                "i kind of feel like",
                "help me find the thread",
                "i don't know but",
                "i dont know but",
            )
        ):
            intent = "thought_dump"
            confidence = 0.75
        else:
            condition_text = _condition_text(raw, normalized)
            if condition_text or normalized in {"sometimes", "it depends", "depends", "case by case"}:
                intent = "conditional_answer"
                confidence = 0.8 if condition_text else 0.65

    pending = _has_pending(pending_interaction)
    return {
        "schema_version": NATURAL_REPLY_INTENT_SCHEMA_VERSION,
        "raw_text_hash": _text_hash(raw),
        "intent": intent,
        "confidence": confidence,
        "extracted_revision_text": extracted_revision_text,
        "condition_text": condition_text,
        "target_pending_interaction_id": pending_id,
        "should_record_now": bool(pending and intent == "confirm_candidate"),
        "requires_confirmation": intent
        in {"revise_candidate", "conditional_answer", "thought_dump", "soften_candidate", "strengthen_candidate"},
        "safety_flags": dict(NATURAL_REPLY_SAFETY_FLAGS),
    }


def detect_coach_intent(text: str) -> bool:
    normalized = _normalize(text)
    return any(
        phrase in normalized
        for phrase in (
            "coach",
            "coach mode",
            "help me think",
            "think through",
            "walk me through",
            "help me decide",
            "review coach",
        )
    )


def coach_command(text: str) -> str:
    normalized = _normalize(text)
    if normalized in {"why", "why does this matter"}:
        return "why"
    if normalized in {
        "recommend",
        "recommendation",
        "what do you recommend",
        "what would you recommend",
        "what's your recommendation",
        "whats your recommendation",
    }:
        return "recommend"
    if normalized in {"examples", "example", "show examples", "give examples"}:
        return "examples"
    if normalized in {
        "use your recommendation",
        "use the recommendation",
        "use your recommended default",
        "use the default",
        "take your recommendation",
        "set that as the default",
        "yes use that",
    }:
        return "use_recommendation"
    if normalized in {"revise previous", "revise last", "change previous", "change last"}:
        return "revise_previous"
    if normalized in {"summarize", "summary", "summarise"}:
        return "summarize"
    if normalized in {"done", "finish", "complete", "that's all", "thats all"}:
        return "done"
    if normalized in {"skip", "skip this", "skip question", "next", "next question"}:
        return "skip"
    if normalized in {"defer", "defer this", "defer question"}:
        return "defer"
    return ""


def build_review_options(question: Mapping[str, Any]) -> list[dict[str, Any]]:
    pack = coach_pack_for_category(str(question.get("category") or ""))
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, template in enumerate(pack.get("option_templates", []), start=1):
        if not isinstance(template, Mapping):
            continue
        option_id = str(template.get("option_id") or f"option_{index}").strip()
        if not option_id or option_id in seen:
            continue
        seen.add(option_id)
        options.append(
            {
                "schema_version": REVIEW_OPTION_SCHEMA_VERSION,
                "option_id": option_id,
                "label": str(template.get("label") or option_id.replace("_", " ")),
                "answer_text": str(template.get("answer_text") or template.get("label") or option_id),
                "tradeoff": str(template.get("tradeoff") or "No special tradeoff recorded."),
                "recommended": option_id == "recommended_default",
            }
        )
        if len(options) >= 4:
            break
    return options


def build_coach_card(question: Mapping[str, Any]) -> dict[str, Any]:
    pack = coach_pack_for_category(str(question.get("category") or ""))
    options = build_review_options(question)
    cpa_flag = bool(pack.get("cpa_review_recommended"))
    legal_flag = bool(pack.get("legal_review_recommended"))
    return {
        "schema_version": REVIEW_COACH_CARD_SCHEMA_VERSION,
        "question_id": str(question.get("question_id") or ""),
        "category": str(question.get("category") or "data room review"),
        "plain_question": str(question.get("question_text") or ""),
        "plain_context": str(pack.get("plain_context") or ""),
        "why_it_matters": str(pack.get("why_it_matters") or ""),
        "recommended_default": str(pack.get("recommended_default") or ""),
        "options": options,
        "example_answers": [str(value) for value in pack.get("example_answers", [])],
        "best_practice_notes": [str(value) for value in pack.get("best_practice_notes", [])],
        "caution_flags": [str(value) for value in pack.get("caution_flags", [])],
        "what_openclaw_will_do": (
            "OpenClaw will store the answer as provisional review evidence for a later promotion prompt. "
            "It will not change runtime policy or create confirmed reference data."
        ),
        "cpa_review_recommended": cpa_flag,
        "legal_review_recommended": legal_flag,
        "needs_professional_review": bool(cpa_flag or legal_flag),
    }


def _option_lines(card: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for option in card.get("options", []):
        if not isinstance(option, Mapping):
            continue
        label = str(option.get("label") or option.get("option_id") or "Option")
        tradeoff = str(option.get("tradeoff") or "").strip()
        line = f"- {label}: {tradeoff}" if tradeoff else f"- {label}"
        lines.append(line)
    return lines[:4]


def render_coach_reply(
    card: Mapping[str, Any],
    command: str,
    surface: str = "telegram",
    style: str = "concise",
) -> str:
    """Render one coach card without JSON, tables, buttons, or model output."""

    category = str(card.get("category") or "review")
    question = str(card.get("plain_question") or "").strip()
    number = card.get("question_number")
    total = card.get("question_total")
    label = f"Question {number} of {total}" if number and total else "Question"
    command = command or "question"

    if command == "why":
        return (
            f"{label} - {category}. Why it matters: {card.get('why_it_matters')}\n"
            f"OpenClaw use: {card.get('what_openclaw_will_do')}\n"
            "Commands: recommend, examples, use your recommendation, skip, defer, done."
        )
    if command == "recommend":
        return (
            f"{label} - {category}. My recommendation: {card.get('recommended_default')}\n"
            "Tradeoff: conservative defaults reduce bad automation, but may need one more review step.\n"
            "Say 'use your recommendation' to record it."
        )
    if command == "examples":
        examples = [str(value) for value in card.get("example_answers", [])][:3]
        rendered = "\n".join(f"- {value}" for value in examples) if examples else "- Use the conservative default for now."
        return f"{label} - {category}. Example answers:\n{rendered}"

    option_lines = "\n".join(_option_lines(card))
    professional = ""
    if card.get("cpa_review_recommended") and card.get("legal_review_recommended"):
        professional = " Professional review flag: CPA and legal review recommended before promotion."
    elif card.get("cpa_review_recommended"):
        professional = " Professional review flag: CPA review recommended before promotion."
    elif card.get("legal_review_recommended"):
        professional = " Professional review flag: legal review recommended before promotion."
    return (
        f"{label} - {category}. {question}\n"
        f"My recommendation: {card.get('recommended_default')}\n"
        f"Why it matters: {card.get('why_it_matters')}{professional}\n"
        f"Options:\n{option_lines}\n"
        "Commands: why, recommend, examples, use your recommendation, skip, defer, revise previous, summarize, done."
    )


__all__ = [
    "REVIEW_COACH_CARD_SCHEMA_VERSION",
    "REVIEW_OPTION_SCHEMA_VERSION",
    "NATURAL_REPLY_INTENT_SCHEMA_VERSION",
    "build_coach_card",
    "build_review_options",
    "coach_command",
    "detect_coach_intent",
    "parse_natural_reply_intent",
    "render_coach_reply",
]
