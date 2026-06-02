"""Agent TTS plain-text sanitizer V0.

This module converts operator-display copy into voice-safe plain text using the
local agent voice profile contract. It does not connect TTS, send messages,
mutate ledgers or workbooks, open external providers, or grant authority.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import agent_voice_profiles


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agent TTS Text Sanitizer.md")

SCHEMA_VERSION = "agent_tts_text_sanitizer_v0"
READ_MODEL_ID = "agent_tts_text_sanitizer_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "AGENT_TTS_SANITIZER_READY"

DEFAULT_OPERATOR_DISPLAY_FIELDS = (
    "headline",
    "subheadline",
    "status_label",
    "plain_summary",
    "next_safe_action",
)

AUTHORITY_BOUNDARY = {
    "tts_live_connection_allowed": False,
    "message_send_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "workbook_mutation_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "paid": False,
    "sent": False,
}

MARKDOWN_MARKERS_STRIPPED = (
    "backticks",
    "asterisks",
    "hash_headings",
    "bullet_symbols",
    "raw_json",
    "markdown_links",
)

ELLIPSIS_RE = re.compile(r"(?:\.\s*){3,}|\u2026+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HASH_HEADING_RE = re.compile(r"(?m)^\s*#{1,6}\s*")
BULLET_RE = re.compile(r"(?m)^\s*(?:[-+*]|\u2022)\s+")
FENCE_MARKER_RE = re.compile(r"```(?:[A-Za-z0-9_-]+)?")
JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}")
JSON_ARRAY_RE = re.compile(r"\[[^\[\]]*(?:\"|'|:|,)[^\[\]]*\]")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SanitizerRule:
    speaker_ref: str
    punctuation_policy: str
    allow_commas: bool
    allow_ellipses: bool
    allow_em_dash: bool
    dash_replacement: str
    forbidden_terms: tuple[str, ...] = ()


PROFILE_RULES: dict[str, SanitizerRule] = {
    "cassandra": SanitizerRule(
        speaker_ref="cassandra",
        punctuation_policy="commas and ellipses allowed for calm intake cadence",
        allow_commas=True,
        allow_ellipses=True,
        allow_em_dash=False,
        dash_replacement=", ",
    ),
    "chief": SanitizerRule(
        speaker_ref="chief",
        punctuation_policy="periods and colons, no ellipses",
        allow_commas=False,
        allow_ellipses=False,
        allow_em_dash=False,
        dash_replacement=": ",
    ),
    "hermes": SanitizerRule(
        speaker_ref="hermes",
        punctuation_policy="measured commas and em dashes allowed",
        allow_commas=True,
        allow_ellipses=False,
        allow_em_dash=True,
        dash_replacement="\u2014",
    ),
    "guardian": SanitizerRule(
        speaker_ref="guardian",
        punctuation_policy="terse periods, no ellipses",
        allow_commas=False,
        allow_ellipses=False,
        allow_em_dash=False,
        dash_replacement=". ",
    ),
    "niles": SanitizerRule(
        speaker_ref="niles",
        punctuation_policy="relaxed pauses without parody markers",
        allow_commas=True,
        allow_ellipses=True,
        allow_em_dash=False,
        dash_replacement=", ",
        forbidden_terms=("mate", "crikey", "ripper"),
    ),
    "clara": SanitizerRule(
        speaker_ref="clara",
        punctuation_policy="professional punctuation only",
        allow_commas=True,
        allow_ellipses=False,
        allow_em_dash=False,
        dash_replacement=", ",
        forbidden_terms=(
            "internal",
            "agent",
            "system",
            "backend",
            "debug",
            "operator_display",
            "workflow_ref",
            "proof drawer",
            "machine proof",
            "guardian",
            "chief",
            "cassandra",
            "hermes",
            "openclaw",
        ),
    ),
    "openclaw": SanitizerRule(
        speaker_ref="openclaw",
        punctuation_policy="neutral status punctuation",
        allow_commas=True,
        allow_ellipses=False,
        allow_em_dash=False,
        dash_replacement=", ",
    ),
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _speaker_ref(value: str | None) -> str:
    speaker = str(value or "").strip().lower()
    return speaker if speaker in PROFILE_RULES else "openclaw"


def _strip_markdown_links(text: str) -> str:
    return MARKDOWN_LINK_RE.sub(lambda match: match.group(1), text)


def _strip_json_like_blocks(text: str) -> str:
    previous = None
    cleaned = text
    while previous != cleaned:
        previous = cleaned
        cleaned = JSON_OBJECT_RE.sub(" ", cleaned)
        cleaned = JSON_ARRAY_RE.sub(" ", cleaned)
    return cleaned.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")


def _strip_markdown(text: str) -> str:
    cleaned = str(text or "")
    cleaned = _strip_markdown_links(cleaned)
    cleaned = FENCE_MARKER_RE.sub(" ", cleaned)
    cleaned = HASH_HEADING_RE.sub("", cleaned)
    cleaned = BULLET_RE.sub("", cleaned)
    cleaned = _strip_json_like_blocks(cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("*", "")
    return cleaned


def _remove_forbidden_terms(text: str, forbidden_terms: tuple[str, ...]) -> str:
    cleaned = text
    for term in forbidden_terms:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _normalize_spacing(text: str) -> str:
    cleaned = WHITESPACE_RE.sub(" ", text).strip()
    cleaned = re.sub(r"\s+([,.:;?!])", r"\1", cleaned)
    cleaned = re.sub(r"([,.:;?!])(?=\S)", r"\1 ", cleaned)
    cleaned = re.sub(r"\s+\u2014\s+", " \u2014 ", cleaned)
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def _sentence_cleanups(text: str) -> str:
    cleaned = re.sub(r"([.?!])\s*([a-z])", lambda m: f"{m.group(1)} {m.group(2).upper()}", text)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    cleaned = re.sub(r"([.:,;?!])\s*\1+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.:;?!])", r"\1", cleaned)
    cleaned = re.sub(r"(?:^|(?<=[\s.]))[,;:]\s*", "", cleaned)
    return cleaned.strip(" ,;:")


def _apply_profile_punctuation(text: str, rule: SanitizerRule) -> str:
    cleaned = text.replace("\u2026", "...")
    if rule.allow_ellipses:
        cleaned = ELLIPSIS_RE.sub(" __ELLIPSIS__ ", cleaned)
    else:
        cleaned = ELLIPSIS_RE.sub(".", cleaned)

    if rule.allow_em_dash:
        cleaned = cleaned.replace("\u2013", "\u2014").replace("--", "\u2014")
        cleaned = re.sub(r"\s*\u2014\s*", " \u2014 ", cleaned)
    else:
        cleaned = cleaned.replace("\u2014", rule.dash_replacement).replace("\u2013", rule.dash_replacement)
        cleaned = cleaned.replace("--", rule.dash_replacement)

    if not rule.allow_commas:
        cleaned = cleaned.replace(",", ".")

    if rule.speaker_ref in {"chief", "guardian"}:
        cleaned = cleaned.replace(";", ".")
        cleaned = cleaned.replace("?", ".")
        cleaned = cleaned.replace("!", ".")
    elif rule.speaker_ref in {"clara", "openclaw"}:
        cleaned = cleaned.replace("!", ".")

    cleaned = _remove_forbidden_terms(cleaned, rule.forbidden_terms)
    cleaned = _sentence_cleanups(_normalize_spacing(cleaned))
    if rule.allow_ellipses:
        cleaned = cleaned.replace("__ELLIPSIS__", "...")
        cleaned = re.sub(r"\s*\.\.\.\s*", "... ", cleaned).strip()
    return cleaned


def sanitize_text(text: str, *, speaker_ref: str = "openclaw") -> str:
    """Return profile-shaped plain text for local TTS preparation."""

    rule = PROFILE_RULES[_speaker_ref(speaker_ref)]
    cleaned = _strip_markdown(text)
    cleaned = _apply_profile_punctuation(cleaned, rule)
    return cleaned


def sanitize_operator_display(
    operator_display: Mapping[str, Any] | str,
    *,
    speaker_ref: str | None = None,
    fields: tuple[str, ...] = DEFAULT_OPERATOR_DISPLAY_FIELDS,
) -> dict[str, Any]:
    """Sanitize operator_display fields and join them into one TTS string."""

    if isinstance(operator_display, Mapping):
        resolved_speaker = _speaker_ref(speaker_ref or str(operator_display.get("speaker_ref") or ""))
        selected_fields = {
            field: sanitize_text(str(operator_display.get(field) or ""), speaker_ref=resolved_speaker)
            for field in fields
            if operator_display.get(field)
        }
        voice_mode = str(operator_display.get("voice_mode") or "")
        audience = str(operator_display.get("audience") or "internal_operator")
    else:
        resolved_speaker = _speaker_ref(speaker_ref)
        selected_fields = {"text": sanitize_text(str(operator_display), speaker_ref=resolved_speaker)}
        voice_mode = ""
        audience = "internal_operator"

    tts_text = _normalize_spacing(" ".join(value for value in selected_fields.values() if value))
    rule = PROFILE_RULES[resolved_speaker]
    return {
        "schema_version": SCHEMA_VERSION,
        "speaker_ref": resolved_speaker,
        "voice_profile_ref": agent_voice_profiles.voice_profile_ref_for_speaker(resolved_speaker),
        "voice_mode": voice_mode,
        "audience": audience,
        "sanitized_fields": selected_fields,
        "tts_text": tts_text,
        "punctuation_policy": rule.punctuation_policy,
        "markers_stripped": list(MARKDOWN_MARKERS_STRIPPED),
        "tts_live_connection_allowed": False,
        "machine_proof": {
            "plain_text_only": _is_plain_tts_text(tts_text),
            "markdown_removed": True,
            "raw_json_removed": "{" not in tts_text and "}" not in tts_text,
            "profile_rule_applied": resolved_speaker,
            "tts_live_connection_performed": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def _is_plain_tts_text(text: str) -> bool:
    blocked = ("`", "*", "{", "}", "[", "]", "```")
    return not any(marker in text for marker in blocked)


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    examples = [
        {
            "speaker_ref": "cassandra",
            "input": "# St. Anne's\n- `work log` captured... [Proof](proof.json)",
            "output": sanitize_text("# St. Anne's\n- `work log` captured... [Proof](proof.json)", speaker_ref="cassandra"),
        },
        {
            "speaker_ref": "chief",
            "input": "Provider gate... `blocked`, submit missing.",
            "output": sanitize_text("Provider gate... `blocked`, submit missing.", speaker_ref="chief"),
        },
        {
            "speaker_ref": "guardian",
            "input": "Blocked... {\"email_send_allowed\": true}",
            "output": sanitize_text("Blocked... {\"email_send_allowed\": true}", speaker_ref="guardian"),
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "status": CONTRACT_STATUS,
        "source_profile_contract": agent_voice_profiles.READ_MODEL_ID,
        "supported_speaker_refs": list(agent_voice_profiles.SPEAKER_REFS),
        "operator_display_fields": list(DEFAULT_OPERATOR_DISPLAY_FIELDS),
        "markdown_policy": {
            "strip_markers": list(MARKDOWN_MARKERS_STRIPPED),
            "preserve_natural_punctuation_for_cadence": True,
            "raw_json_removed_from_tts_text": True,
        },
        "profile_rules": {
            speaker: {
                "punctuation_policy": rule.punctuation_policy,
                "allow_commas": rule.allow_commas,
                "allow_ellipses": rule.allow_ellipses,
                "allow_em_dash": rule.allow_em_dash,
                "forbidden_terms": list(rule.forbidden_terms),
            }
            for speaker, rule in PROFILE_RULES.items()
        },
        "examples": examples,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "sanitizer_is_local_only": True,
            "tts_live_connection_performed": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Agent TTS Text Sanitizer",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This sanitizer prepares operator-display copy for local TTS by converting it to plain text. It does not call a TTS provider or send messages.",
        "",
        "## What It Strips",
        "",
        "- Backticks and code fence markers.",
        "- Asterisks and markdown emphasis.",
        "- Hash headings.",
        "- Bullet symbols.",
        "- Raw JSON object or array text.",
        "- Markdown links, preserving the readable label.",
        "",
        "## Profile Rules",
        "",
    ]
    for speaker_ref, rule in PROFILE_RULES.items():
        lines.extend(
            [
                f"### `{speaker_ref}`",
                "",
                f"- Policy: {rule.punctuation_policy}",
                f"- Voice profile: `{agent_voice_profiles.voice_profile_ref_for_speaker(speaker_ref)}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- No TTS live connection.",
            "- No message send.",
            "- No email, browser, Gmail, or Coupa.",
            "- No ledger or workbook mutation.",
            "- No paid or sent marking.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_tts_text_sanitizer(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": CONTRACT_STATUS,
        "read_model_path": read_model_path.as_posix(),
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agent TTS Text Sanitizer V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_agent_tts_text_sanitizer(
        export_root=Path(args.export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
