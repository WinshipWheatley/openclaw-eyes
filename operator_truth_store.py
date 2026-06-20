"""Shared operator-corrected truth store for cross-agent readbacks.

The store records operator-authored entity corrections with provenance so every
agent can prefer them over stale finance/reality context without treating
arbitrary chat as truth.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


STORE_VERSION = "operator_truth_store_v0"
DEFAULT_STORE_PATH = Path("/mnt/c/OpenClaw/logs/operator_truth_store.json")
DEFAULT_SEED_PATH = Path("/mnt/e/openclaw/orchestration/OPERATOR-TRUTH-20260619-evening.md")


ENTITY_DEFS: dict[str, dict[str, Any]] = {
    "capital_hilton": {
        "label": "Capital Hilton",
        "aliases": ("capital hilton", "coupa", "will valcovic"),
        "pii_tier": "LIGHT",
    },
    "st_annes": {
        "label": "St Anne's",
        "aliases": ("st anne", "st anne's", "st annes", "saint anne"),
        "pii_tier": "LIGHT",
    },
    "live_arts_md": {
        "label": "Live Arts MD",
        "aliases": ("live arts md", "live arts", "draper"),
        "pii_tier": "LIGHT",
    },
    "date_awareness.next_friday_20260619": {
        "label": "Date awareness: next Friday from 2026-06-19",
        "aliases": ("next friday", "2026-06-26"),
        "pii_tier": "PUBLIC",
    },
}

CORRECTION_MARKERS = (
    "actually",
    "correct",
    "correction",
    "current status",
    "current truth",
    "cut a check",
    "is paid",
    "owes",
    "paid up",
    "received",
    "stale",
    "the truth",
    "truth is",
    "will cut",
)

_UNSAFE_CONTROL_PHRASES = (
    "alive check",
    "answer one sentence",
    "compact recovery check",
    "deep probe",
    "degraded recovery",
    "health probe",
    "probe prompt",
    "recovery check",
    "stress probe",
)

_VALUE_SIGNAL_PHRASES = (
    "all paid",
    "checked off",
    "completed",
    "cut a check",
    "did his part",
    "did her part",
    "invoice",
    "is paid",
    "owes",
    "paid up",
    "payment",
    "po ",
    "received",
    "submitted",
    "unpaid",
    "verify",
    "verification",
    "waiting for",
    "will cut",
)


def _store_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.environ.get("OPENCLAW_OPERATOR_TRUTH_STORE", "").strip()
    if configured:
        return Path(configured)
    if os.environ.get("OPENCLAW_TEST_MODE") == "1":
        test_path = os.environ.get("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", "").strip()
        if test_path:
            return Path(test_path)
        current_test = os.environ.get("PYTEST_CURRENT_TEST", "").split(" ", 1)[0]
        test_hash = hashlib.sha256(current_test.encode("utf-8")).hexdigest()[:16] if current_test else "session"
        suffix = f"{os.getpid()}_{test_hash}"
        return Path(f"/tmp/openclaw_operator_truth_store_{suffix}.json")
    return DEFAULT_STORE_PATH


def _seed_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.environ.get("OPENCLAW_OPERATOR_TRUTH_SEED", "").strip()
    return Path(configured) if configured else DEFAULT_SEED_PATH


def _seed_enabled(seed_path: str | Path | None = None) -> bool:
    if seed_path is not None:
        return True
    if os.environ.get("OPENCLAW_OPERATOR_TRUTH_SEED", "").strip():
        return True
    return os.environ.get("OPENCLAW_TEST_MODE") != "1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _compact(text: str) -> str:
    return " ".join(str(text or "").replace("\x00", " ").split()).strip()


def _stable_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def validate_operator_truth_value(value: str, *, source_text: str = "") -> tuple[bool, str]:
    """Reject probe/control prompts before they can become cross-agent truth."""
    clean = _compact(value)
    if not clean:
        return False, "empty_value"
    if len(clean) < 8:
        return False, "value_too_short"
    if len(clean) > 600:
        return False, "value_too_long"
    lowered = clean.lower()
    combined = f"{lowered} {_compact(source_text).lower()}".strip()
    if any(phrase in combined for phrase in _UNSAFE_CONTROL_PHRASES):
        return False, "control_prompt"
    if any(token in combined for token in ("cass-deep-", "probe-", "stress-", "recovery-check")):
        return False, "probe_label"
    if lowered.startswith(("answer ", "reply ", "respond ", "summarize ")):
        return False, "instruction_not_value"
    if not any(ch.isalpha() for ch in clean):
        return False, "no_words"
    has_value_signal = (
        any(phrase in lowered for phrase in _VALUE_SIGNAL_PHRASES)
        or "$" in clean
        or any(ch.isdigit() for ch in clean)
    )
    if not has_value_signal:
        return False, "no_business_value_signal"
    return True, ""


def _empty_store() -> dict[str, Any]:
    return {
        "schema_version": STORE_VERSION,
        "entities": {},
        "seeded_sources": {},
    }


def load_operator_truth_store(
    path: str | Path | None = None,
    *,
    ensure_seed: bool = True,
) -> dict[str, Any]:
    target = _store_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        data = _empty_store()
    if not isinstance(data, dict):
        data = _empty_store()
    if not isinstance(data.get("entities"), dict):
        data["entities"] = {}
    if not isinstance(data.get("seeded_sources"), dict):
        data["seeded_sources"] = {}
    data["schema_version"] = STORE_VERSION
    if ensure_seed:
        data = ensure_evening_seed_loaded(data, path=target)
    return data


def save_operator_truth_store(data: Mapping[str, Any], path: str | Path | None = None) -> None:
    target = _store_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema_version"] = STORE_VERSION
    tmp_path = target.with_name(f"{target.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, target)


def _entity_def(entity_key: str) -> dict[str, Any]:
    return ENTITY_DEFS.get(entity_key, {"label": entity_key, "aliases": (entity_key,), "pii_tier": "LIGHT"})


def upsert_operator_truth(
    entity_key: str,
    value: str,
    *,
    source_surface: str,
    source_text: str = "",
    source_ref: str | None = None,
    at: str | None = None,
    path: str | Path | None = None,
    pii_tier: str | None = None,
) -> dict[str, Any]:
    clean_value = _compact(value)
    if not entity_key or not clean_value:
        raise ValueError("entity_key and value are required")
    valid, reason = validate_operator_truth_value(clean_value, source_text=source_text)
    if not valid:
        raise ValueError(f"unsafe operator truth value: {reason}")

    data = load_operator_truth_store(path, ensure_seed=True)
    definition = _entity_def(entity_key)
    record = {
        "entity_key": entity_key,
        "label": definition.get("label", entity_key),
        "value": clean_value,
        "provenance": "operator_corrected",
        "at": at or _utc_now(),
        "source_surface": _compact(source_surface) or "unknown_surface",
        "source_ref": _compact(source_ref or ""),
        "source_text_hash": _stable_hash(source_text),
        "precedence": 100,
        "pii_tier": pii_tier or definition.get("pii_tier", "LIGHT"),
    }
    data["entities"][entity_key] = record
    save_operator_truth_store(data, path)
    return record


def _next_weekday_after(start: date, weekday: int) -> date:
    from datetime import timedelta

    days = (weekday - start.weekday()) % 7
    if days == 0:
        days = 7
    return start + timedelta(days=days)


def _seed_entries() -> tuple[dict[str, str], ...]:
    next_friday = _next_weekday_after(date(2026, 6, 19), 4)
    return (
        {
            "entity_key": "capital_hilton",
            "value": (
                "Coupa is working; $2000 was received through Coupa; a $2000 invoice was submitted; "
                "Capital Hilton will cut a $2000 check on 2026-07-01; gigs are $400 each with the first "
                "played and the second in progress; the next invoice must reflect played gigs; next Friday "
                f"relative to 2026-06-19 is {next_friday.isoformat()}."
            ),
        },
        {
            "entity_key": "st_annes",
            "value": "All paid up.",
        },
        {
            "entity_key": "live_arts_md",
            "value": (
                "Live Arts MD owes the operator for a ton of work; details need codex-desktop context "
                "from the Draper follow-up email chat."
            ),
        },
        {
            "entity_key": "date_awareness.next_friday_20260619",
            "value": f"In the 2026-06-19 evening correction, 'next Friday' means {next_friday.isoformat()}.",
        },
    )


def ensure_evening_seed_loaded(
    data: Mapping[str, Any] | None = None,
    *,
    path: str | Path | None = None,
    seed_path: str | Path | None = None,
) -> dict[str, Any]:
    target = _store_path(path)
    payload = dict(data or _empty_store())
    payload.setdefault("entities", {})
    payload.setdefault("seeded_sources", {})
    if not _seed_enabled(seed_path):
        return payload
    seed = _seed_path(seed_path)
    try:
        seed_text = seed.read_text(encoding="utf-8")
    except Exception:
        return payload

    seed_hash = _stable_hash(seed_text)
    seed_id = seed.name
    if payload["seeded_sources"].get(seed_id) == seed_hash:
        return payload

    for entry in _seed_entries():
        definition = _entity_def(entry["entity_key"])
        payload["entities"][entry["entity_key"]] = {
            "entity_key": entry["entity_key"],
            "label": definition.get("label", entry["entity_key"]),
            "value": entry["value"],
            "provenance": "operator_corrected",
            "at": "2026-06-19T23:00:00+00:00",
            "source_surface": "operator_truth_seed",
            "source_ref": str(seed),
            "source_text_hash": seed_hash,
            "precedence": 100,
            "pii_tier": definition.get("pii_tier", "LIGHT"),
        }
    payload["seeded_sources"][seed_id] = seed_hash
    save_operator_truth_store(payload, target)
    return payload


def _mentioned_entities(text: str) -> list[str]:
    lowered = _compact(text).lower()
    if not lowered:
        return []
    matches: list[str] = []
    for key, definition in ENTITY_DEFS.items():
        aliases = tuple(definition.get("aliases") or ())
        if any(alias and alias.lower() in lowered for alias in aliases):
            matches.append(key)
    return matches


def _looks_like_operator_truth(text: str) -> bool:
    lowered = _compact(text).lower()
    return any(marker in lowered for marker in CORRECTION_MARKERS)


def _summary_from_text(text: str, entity_key: str) -> str:
    clean = _compact(text)
    if not clean:
        return ""
    label = str(_entity_def(entity_key).get("label") or entity_key)
    parts = clean.split(":", 1)
    if len(parts) == 2 and label.lower().split()[0] in parts[0].lower():
        return parts[1].strip(" -")
    return clean


def extract_operator_truth_candidates(
    text: str,
    *,
    source_surface: str,
    source_ref: str | None = None,
    at: str | None = None,
) -> list[dict[str, Any]]:
    if not _looks_like_operator_truth(text):
        return []
    candidates: list[dict[str, Any]] = []
    for entity_key in _mentioned_entities(text):
        value = _summary_from_text(text, entity_key)
        valid, _reason = validate_operator_truth_value(value, source_text=text)
        if not valid:
            continue
        candidates.append(
            {
                "entity_key": entity_key,
                "value": value,
                "source_surface": source_surface,
                "source_ref": source_ref or "",
                "at": at,
                "pii_tier": _entity_def(entity_key).get("pii_tier", "LIGHT"),
            }
        )
    return [candidate for candidate in candidates if candidate["value"]]


def capture_operator_truth_from_text(
    text: str,
    *,
    source_surface: str,
    source_ref: str | None = None,
    at: str | None = None,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for candidate in extract_operator_truth_candidates(
        text,
        source_surface=source_surface,
        source_ref=source_ref,
        at=at,
    ):
        records.append(
            upsert_operator_truth(
                candidate["entity_key"],
                candidate["value"],
                source_surface=candidate["source_surface"],
                source_ref=candidate.get("source_ref") or source_ref,
                source_text=text,
                at=candidate.get("at") or at,
                path=path,
                pii_tier=candidate.get("pii_tier"),
            )
        )
    return records


def find_operator_truth_for_text(
    text: str,
    *,
    path: str | Path | None = None,
) -> tuple[str, dict[str, Any]] | None:
    data = load_operator_truth_store(path, ensure_seed=True)
    for entity_key in _mentioned_entities(text):
        record = data.get("entities", {}).get(entity_key)
        if isinstance(record, dict) and str(record.get("value") or "").strip():
            return entity_key, record
    return None


def _format_record(record: Mapping[str, Any]) -> str:
    label = str(record.get("label") or record.get("entity_key") or "Entity")
    value = _compact(str(record.get("value") or ""))
    provenance = str(record.get("provenance") or "operator_corrected")
    source = str(record.get("source_surface") or "unknown_surface")
    at = str(record.get("at") or "")
    suffix = f" (provenance: {provenance}; source: {source}"
    if at:
        suffix += f"; at: {at}"
    suffix += ")"
    return f"  {label}: {value}{suffix}"


def format_operator_truth_context(
    query: str | None = None,
    *,
    path: str | Path | None = None,
) -> str:
    data = load_operator_truth_store(path, ensure_seed=True)
    entities = data.get("entities", {})
    if not isinstance(entities, dict) or not entities:
        return ""

    keys = _mentioned_entities(query or "")
    if keys:
        records = [entities[key] for key in keys if isinstance(entities.get(key), dict)]
    else:
        records = [record for record in entities.values() if isinstance(record, dict)]
    records = [record for record in records if str(record.get("value") or "").strip()]
    if not records:
        return ""

    records.sort(key=lambda record: str(record.get("label") or record.get("entity_key") or ""))
    return "[OPERATOR-CORRECTED TRUTH - shared across agents]\n" + "\n".join(_format_record(record) for record in records)


__all__ = [
    "capture_operator_truth_from_text",
    "ensure_evening_seed_loaded",
    "extract_operator_truth_candidates",
    "find_operator_truth_for_text",
    "format_operator_truth_context",
    "load_operator_truth_store",
    "save_operator_truth_store",
    "upsert_operator_truth",
    "validate_operator_truth_value",
]
