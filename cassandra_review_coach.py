"""Deterministic coach rendering for Cassandra guided reviews."""

from __future__ import annotations

import re
from typing import Any, Mapping

from cassandra_review_coach_packs import coach_pack_for_category


REVIEW_OPTION_SCHEMA_VERSION = "REVIEW_OPTION_V0"
REVIEW_COACH_CARD_SCHEMA_VERSION = "REVIEW_COACH_CARD_V0"


def _normalize(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = lowered.replace("?", " ").replace("!", " ")
    return " ".join(re.sub(r"[^a-z0-9']+", " ", lowered).split())


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
    "build_coach_card",
    "build_review_options",
    "coach_command",
    "detect_coach_intent",
    "render_coach_reply",
]
