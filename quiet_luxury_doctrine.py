"""Canonical Quiet Luxury contract loader and deterministic copy critic."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DOCTRINE_PATH = ROOT / "docs/doctrine/CLARA_CASSANDRA_QUIET_LUXURY.md"
CONTRACT_START = "<!-- BEGIN QUIET_LUXURY_CONTRACT -->"
CONTRACT_END = "<!-- END QUIET_LUXURY_CONTRACT -->"
SCHEMA_VERSION = "quiet_luxury_persona_contract_v1"
DOCTRINE_REF = "quiet_luxury:clara_cassandra:v1"

_CRITICAL_FACT_RE = re.compile(r"\b(?:FAILED_SEND|MISSED_DEADLINE|SECURITY_RISK)\b")
_MARKDOWN_RE = re.compile(r"(?:\*\*|```|^\s*[-*]\s+)", re.MULTILINE)


def _contract_json(text: str) -> str:
    if CONTRACT_START not in text or CONTRACT_END not in text:
        raise ValueError("Quiet Luxury document is missing contract boundaries")
    bounded = text.split(CONTRACT_START, 1)[1].split(CONTRACT_END, 1)[0].strip()
    match = re.fullmatch(r"```json\s*(\{.*\})\s*```", bounded, flags=re.DOTALL)
    if match is None:
        raise ValueError("Quiet Luxury machine contract must be one JSON code block")
    return match.group(1)


def load_quiet_luxury_contract(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DOCTRINE_PATH
    payload = json.loads(_contract_json(target.read_text(encoding="utf-8")))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unexpected Quiet Luxury schema version")
    if payload.get("doctrine_ref") != DOCTRINE_REF:
        raise ValueError("Unexpected Quiet Luxury doctrine reference")
    if payload.get("canonical_external_name") != "Clara Reid":
        raise ValueError("Clara Reid is the only canonical external spelling")
    if payload.get("flows", {}).get("clara") != ["Recognize", "Clarify", "Guide", "Confirm"]:
        raise ValueError("Clara concierge flow is incomplete")
    return payload


def doctrine_binding_for_speaker(speaker_ref: str) -> dict[str, Any] | None:
    speaker = str(speaker_ref or "").strip().lower()
    if speaker not in {"cassandra", "clara"}:
        return None
    contract = load_quiet_luxury_contract()
    return {
        "doctrine_ref": contract["doctrine_ref"],
        "doctrine_path": str(DOCTRINE_PATH.relative_to(ROOT)),
        "flow": list(contract["flows"][speaker]),
        "progressive_disclosure": list(contract["progressive_disclosure"]),
        "critic_dimensions": list(contract["critic_dimensions"]),
        "canonical_external_name": contract["canonical_external_name"],
        "severity_integrity": contract["core"]["severity_integrity"],
    }


def _contains_any(lowered: str, phrases: Iterable[str]) -> bool:
    return any(str(phrase).casefold() in lowered for phrase in phrases)


def _contains_bounded_term(lowered: str, terms: Iterable[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(str(term).casefold())}(?!\w)", lowered) is not None
        for term in terms
    )


def _flow_checks(text: str, *, surface: str) -> dict[str, bool]:
    lowered = text.casefold()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if surface != "client_email":
        return {step: True for step in ("Recognize", "Clarify", "Guide", "Confirm")}
    recognize = bool(
        re.search(r"^(?:hi|hello|dear)(?:\s+[^,]+)?,", text.strip(), flags=re.IGNORECASE)
        or re.search(
            r"^(?:invoice attachment|following up|a quick check|thank you)\b",
            text.strip(),
            flags=re.IGNORECASE,
        )
    )
    clarify = bool(
        re.search(r"\b(?:attached|included|invoice|proposal|total|january|february|march|april|may|june|july|august|september|october|november|december|\$\d)", lowered)
    )
    guide = "?" in text and bool(re.search(r"\b(?:could|would|can|please)\b", lowered))
    confirm = bool(
        re.search(r"\b(?:that helps|once|confirmation|no reply is needed|all i need)\b", lowered)
        or (paragraphs and paragraphs[-1].casefold().endswith("clara reid"))
    )
    return {
        "Recognize": recognize,
        "Clarify": clarify,
        "Guide": guide,
        "Confirm": confirm,
    }


def evaluate_quiet_luxury_copy(
    speaker_ref: str,
    text: str,
    *,
    surface: str = "general",
    critical_facts: Iterable[str] = (),
) -> dict[str, Any]:
    speaker = str(speaker_ref or "").strip().lower()
    value = str(text or "")
    lowered = value.casefold()
    contract = load_quiet_luxury_contract()
    anti_patterns: Mapping[str, list[str]] = contract["anti_patterns"]
    false_intimacy = _contains_any(lowered, anti_patterns["false_intimacy"])
    eager = _contains_any(lowered, anti_patterns["eager_agreeable"])
    pressure = _contains_any(lowered, anti_patterns["pressure"])
    stranger = _contains_any(lowered, anti_patterns["polished_stranger"])
    internal = _contains_bounded_term(lowered, contract["client_internal_terms"])
    critical = tuple(str(fact) for fact in critical_facts if str(fact).strip())
    severity_ok = all(fact in value for fact in critical)
    flow = _flow_checks(value, surface=surface)
    ask_present = "?" in value
    easy_ask = not pressure and (
        not ask_present or bool(re.search(r"\b(?:could|would|can|when you have a chance)\b", lowered))
    )
    screenshot_clean = not internal and _MARKDOWN_RE.search(value) is None
    dimensions = {
        "understatement": 1.0 if not eager and "!" not in value else 0.0,
        "no_false_intimacy": 1.0 if not false_intimacy else 0.0,
        "easy_to_decline": 1.0 if easy_ask else 0.0,
        "screenshot_test": 1.0 if screenshot_clean else 0.0,
        "severity_integrity": 1.0 if severity_ok else 0.0,
        "lowest_intensity_tone": 1.0 if not eager and not pressure and "!" not in value else 0.0,
        "organized_not_stranger": 1.0 if not stranger and not false_intimacy else 0.0,
        "persona_fidelity": 1.0 if not eager and not false_intimacy else 0.0,
        "client_surface_clean": 1.0 if not internal else 0.0,
    }
    violations = [name for name, score in dimensions.items() if score != 1.0]
    if surface == "client_email":
        violations.extend(f"flow_{step.casefold()}" for step, present in flow.items() if not present)
    return {
        "passed": not violations,
        "speaker_ref": speaker,
        "surface": surface,
        "doctrine_ref": contract["doctrine_ref"],
        "dimensions": dimensions,
        "flow": flow,
        "critical_facts": list(critical),
        "violations": violations,
    }


def critical_facts_in_text(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_CRITICAL_FACT_RE.findall(str(text or ""))))


__all__ = [
    "DOCTRINE_PATH",
    "DOCTRINE_REF",
    "critical_facts_in_text",
    "doctrine_binding_for_speaker",
    "evaluate_quiet_luxury_copy",
    "load_quiet_luxury_contract",
]
