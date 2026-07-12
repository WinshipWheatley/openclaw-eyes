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
import re
from typing import Any, Mapping

from control_language_policy import classify_control_language


STORE_VERSION = "operator_truth_store_v0"
DEFAULT_STORE_PATH = Path("/mnt/c/OpenClaw/logs/operator_truth_store.json")
DEFAULT_SEED_PATH = Path("/mnt/e/openclaw/orchestration/OPERATOR-TRUTH-20260619-evening.md")
QUARANTINE_VERSION = "operator_truth_quarantine_v0"


class OperatorTruthQuarantineIntegrityError(RuntimeError):
    pass


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

_QUESTION_LEAD_RE = re.compile(
    r"^(?:actually\s+|correction\s*[:—-]?\s*|the\s+truth\s+is\s+)?"
    r"(?:who|what|when|where|why|how|which|did|do|does|is|are|was|were|has|have|had|"
    r"can|could|would|should)\b",
    re.IGNORECASE,
)
_EMBEDDED_QUESTION_RE = re.compile(
    r"(?:^|[:;.!?—-]\s+|\bor\s+)"
    r"(?:who|what|when|where|why|how|which|did|do|does|is|are|was|were|has|have|had|"
    r"can|could|would|should)\b",
    re.IGNORECASE,
)
_WILL_AUXILIARY_QUESTION_RE = re.compile(
    r"^(?:actually\s+|correction\s*[:—-]?\s*)?will\s+"
    r"(?:i|we|you|he|she|they|it|capital\s+hilton|live\s+arts|st\.?\s+anne(?:'s|s)?|"
    r"the\s+(?:client|invoice|check|payment))\b",
    re.IGNORECASE,
)
_QUESTION_REQUEST_RE = re.compile(
    r"\b(?:tell|show|remind)\s+me\s+(?:who|what|when|where|why|how|which)\b|"
    r"\bi\s+wonder\s+(?:who|what|when|where|why|how|which|if|whether)\b|"
    r"\bi(?:\s+am|['’]m)\s+wondering\s+(?:if|whether)\b",
    re.IGNORECASE,
)
_QUESTION_TAG_RE = re.compile(
    r"\b(?:right|correct|isn['’]?t\s+it|aren['’]?t\s+they|didn['’]?t\s+(?:it|they)|"
    r"or\s+(?:not|was|were|did|does|is|are|has|have))\s*[?.!]*$",
    re.IGNORECASE,
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


def _file_digest(path: Path) -> str:
    try:
        return _stable_hash(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def classify_operator_truth_safety(value: str, *, source_text: str = "") -> str:
    """Return a stable rejection reason, or an empty string when safe to persist."""

    clean = _compact(value)
    if not clean:
        return "empty_value"
    if len(clean) < 8:
        return "value_too_short"
    if len(clean) > 600:
        return "value_too_long"
    lowered = clean.lower()
    source = _compact(source_text)
    combined = f"{clean} {source}".strip()
    control = classify_control_language(combined)
    clean_control = classify_control_language(clean)
    if any(reason in control.reason_codes for reason in ("control_phrase", "probe_label")):
        return "control_prompt"
    if "instruction_prefix" in clean_control.reason_codes:
        return "instruction_not_value"
    if "runtime_diagnostic" in control.reason_codes:
        return "runtime_diagnostic"
    if control.is_control_language:
        return "control_language"
    if (
        "?" in clean
        or "?" in source
        or _QUESTION_LEAD_RE.search(clean)
        or _QUESTION_LEAD_RE.search(source)
        or _EMBEDDED_QUESTION_RE.search(clean)
        or _EMBEDDED_QUESTION_RE.search(source)
        or _WILL_AUXILIARY_QUESTION_RE.search(clean)
        or _WILL_AUXILIARY_QUESTION_RE.search(source)
        or _QUESTION_REQUEST_RE.search(clean)
        or _QUESTION_REQUEST_RE.search(source)
        or _QUESTION_TAG_RE.search(clean)
        or _QUESTION_TAG_RE.search(source)
    ):
        return "question_shaped_text"
    if not any(ch.isalpha() for ch in clean):
        return "no_words"
    has_value_signal = (
        any(phrase in lowered for phrase in _VALUE_SIGNAL_PHRASES)
        or "$" in clean
        or any(ch.isdigit() for ch in clean)
    )
    if not has_value_signal:
        return "no_business_value_signal"
    return ""


def validate_operator_truth_value(value: str, *, source_text: str = "") -> tuple[bool, str]:
    """Reject probe/control prompts before they can become cross-agent truth."""
    reason = classify_operator_truth_safety(value, source_text=source_text)
    return not reason, reason


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

    target = _store_path(path)
    before_file_hash = _file_digest(target)
    data = load_operator_truth_store(path, ensure_seed=True)
    definition = _entity_def(entity_key)
    previous_record = data.get("entities", {}).get(entity_key)
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
    committed_data = load_operator_truth_store(path, ensure_seed=False)
    committed_record = committed_data.get("entities", {}).get(entity_key)
    if not isinstance(committed_record, dict) or committed_record != record:
        raise OSError("operator truth write did not pass committed readback verification")
    after_file_hash = _file_digest(target)
    record_hash = _stable_hash(json.dumps(record, sort_keys=True, ensure_ascii=False))
    business_state_mutation = previous_record != record
    receipt = {
        "schema_version": "operator_truth_write_receipt_v0",
        "receipt_id": f"operator_truth_write_receipt:{_stable_hash(f'{entity_key}\0{record_hash}')[:20]}",
        "status": "committed",
        "entity_key": entity_key,
        "record_hash": record_hash,
        "source_text_hash": record["source_text_hash"],
        "store_path": str(target),
        "before_file_hash": before_file_hash,
        "after_file_hash": after_file_hash,
        "file_mutation_performed": before_file_hash != after_file_hash,
        "business_state_mutation_performed": business_state_mutation,
        "committed_at": record["at"],
    }
    return {**record, "write_receipt": receipt}


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


def operator_truth_record_eligibility(record: Mapping[str, Any]) -> tuple[bool, str]:
    if str(record.get("quarantine_status") or "").lower() in {"quarantined", "unrepaired"}:
        return False, "record_quarantined"
    value = _compact(str(record.get("value") or ""))
    return validate_operator_truth_value(value, source_text=value)


def eligible_operator_truth_records(
    data: Mapping[str, Any] | None = None,
    *,
    path: str | Path | None = None,
    ensure_seed: bool = True,
) -> tuple[dict[str, Any], ...]:
    payload = data if isinstance(data, Mapping) else load_operator_truth_store(path, ensure_seed=ensure_seed)
    entities = payload.get("entities") if isinstance(payload, Mapping) else {}
    if not isinstance(entities, Mapping):
        return ()
    return tuple(
        dict(record)
        for record in entities.values()
        if isinstance(record, Mapping) and operator_truth_record_eligibility(record)[0]
    )


def _quarantine_path(store_path: Path, quarantine_path: str | Path | None = None) -> Path:
    if quarantine_path is not None:
        return Path(quarantine_path)
    return store_path.with_name(f"{store_path.stem}.quarantine.json")


def _load_quarantine(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": QUARANTINE_VERSION,
            "records": [],
            "receipts": [],
            "repair_receipts": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OperatorTruthQuarantineIntegrityError("quarantine_json_unreadable") from exc
    if not isinstance(payload, dict):
        raise OperatorTruthQuarantineIntegrityError("quarantine_payload_not_object")
    existing_version = str(payload.get("schema_version") or "")
    if existing_version and existing_version != QUARANTINE_VERSION:
        raise OperatorTruthQuarantineIntegrityError("quarantine_schema_version_mismatch")
    payload["schema_version"] = QUARANTINE_VERSION
    for key in ("records", "receipts", "repair_receipts"):
        if key not in payload:
            payload[key] = []
        elif not isinstance(payload.get(key), list):
            raise OperatorTruthQuarantineIntegrityError(f"quarantine_{key}_not_list")
    return payload


def _save_quarantine(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(payload)
    clean["schema_version"] = QUARANTINE_VERSION
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


def quarantine_unsafe_operator_truth_records(
    *,
    path: str | Path | None = None,
    quarantine_path: str | Path | None = None,
    source_ref: str = "operator_truth_safety_sweep",
    at: str | None = None,
) -> dict[str, Any]:
    """Move unsafe live records to an append-only quarantine before removal.

    The quarantine write happens first.  A crash can therefore leave a copied
    record in both places, but can never silently delete the only copy.
    """

    at = at or _utc_now()
    store_path = _store_path(path)
    archive_path = _quarantine_path(store_path, quarantine_path)
    data = load_operator_truth_store(store_path, ensure_seed=False)
    entities = data.get("entities", {})
    unsafe: list[tuple[str, dict[str, Any], str, str]] = []
    if isinstance(entities, dict):
        for entity_key, raw_record in entities.items():
            if not isinstance(raw_record, dict):
                unsafe.append((str(entity_key), {"value": raw_record}, "invalid_record_shape", _stable_hash(repr(raw_record))))
                continue
            eligible, reason = operator_truth_record_eligibility(raw_record)
            if not eligible:
                record_hash = _stable_hash(json.dumps(raw_record, sort_keys=True, ensure_ascii=False))
                unsafe.append((str(entity_key), dict(raw_record), reason, record_hash))

    before_hash = _file_digest(store_path)
    entity_keys = sorted(entity_key for entity_key, _record, _reason, _hash in unsafe)
    receipt_id = f"operator_truth_quarantine_receipt:{_stable_hash(f'{at}\0{source_ref}\0{entity_keys}')[:20]}"
    receipt: dict[str, Any] = {
        "schema_version": "operator_truth_quarantine_receipt_v0",
        "receipt_id": receipt_id,
        "status": "pending" if unsafe else "no_change",
        "entity_keys": entity_keys,
        "record_count": len(unsafe),
        "source_ref": _compact(source_ref),
        "at": at,
        "store_path": str(store_path),
        "quarantine_path": str(archive_path),
        "before_file_hash": before_hash,
        "after_file_hash": before_hash,
        "file_mutation_performed": False,
        "business_state_mutation_performed": False,
    }
    if not unsafe:
        return receipt

    archive = _load_quarantine(archive_path)
    existing_hashes = {
        str(item.get("record_hash") or "")
        for item in archive["records"]
        if isinstance(item, Mapping)
    }
    for entity_key, record, reason, record_hash in unsafe:
        if record_hash in existing_hashes:
            continue
        archive["records"].append(
            {
                "quarantine_id": f"operator_truth_quarantine:{record_hash[:20]}",
                "quarantine_receipt_id": receipt_id,
                "entity_key": entity_key,
                "record_hash": record_hash,
                "reason": reason,
                "source_ref": _compact(source_ref),
                "quarantined_at": at,
                "record": record,
            }
        )
    archive["receipts"].append(dict(receipt))
    _save_quarantine(archive, archive_path)

    for entity_key in entity_keys:
        data["entities"].pop(entity_key, None)
    save_operator_truth_store(data, store_path)
    receipt.update(
        {
            "status": "quarantined",
            "after_file_hash": _file_digest(store_path),
            "file_mutation_performed": before_hash != _file_digest(store_path),
            "business_state_mutation_performed": True,
        }
    )
    archive = _load_quarantine(archive_path)
    archive["receipts"][-1] = dict(receipt)
    _save_quarantine(archive, archive_path)
    return receipt


def repair_quarantined_operator_truth(
    entity_key: str,
    value: str,
    *,
    source_surface: str,
    source_text: str,
    path: str | Path | None = None,
    quarantine_path: str | Path | None = None,
    source_ref: str = "operator_truth_repair",
    at: str | None = None,
    pii_tier: str | None = None,
) -> dict[str, Any]:
    """Commit a validated replacement while retaining the poisoned provenance."""

    store_path = _store_path(path)
    archive_path = _quarantine_path(store_path, quarantine_path)
    archive = _load_quarantine(archive_path)
    matching = [
        item
        for item in archive["records"]
        if isinstance(item, Mapping) and str(item.get("entity_key") or "") == entity_key
    ]
    if not matching:
        raise ValueError(f"no quarantined operator truth record for {entity_key}")
    valid, reason = validate_operator_truth_value(value, source_text=source_text)
    if not valid:
        raise ValueError(f"unsafe operator truth repair: {reason}")

    quarantined = matching[-1]
    repaired_at = at or _utc_now()
    intended_value_hash = _stable_hash(_compact(value))
    repair_receipt = {
        "schema_version": "operator_truth_repair_receipt_v0",
        "receipt_id": f"operator_truth_repair_receipt:{_stable_hash(f'{entity_key}\0{repaired_at}\0{intended_value_hash}')[:20]}",
        "status": "pending",
        "entity_key": entity_key,
        "quarantine_receipt_id": str(quarantined.get("quarantine_receipt_id") or ""),
        "quarantined_record_hash": str(quarantined.get("record_hash") or ""),
        "intended_value_hash": intended_value_hash,
        "replacement_record_hash": "",
        "write_receipt_id": "",
        "source_ref": _compact(source_ref),
        "at": repaired_at,
        "file_mutation_performed": False,
        "business_state_mutation_performed": False,
    }
    archive["repair_receipts"].append(dict(repair_receipt))
    _save_quarantine(archive, archive_path)

    committed = upsert_operator_truth(
        entity_key,
        value,
        source_surface=source_surface,
        source_text=source_text,
        source_ref=source_ref,
        at=at,
        path=store_path,
        pii_tier=pii_tier,
    )
    write_receipt = dict(committed.get("write_receipt") or {})
    if write_receipt.get("status") != "committed":
        raise OSError("operator truth repair lacks a committed write receipt")
    repair_receipt.update(
        {
            "status": "repaired",
            "replacement_record_hash": str(write_receipt.get("record_hash") or ""),
            "write_receipt_id": str(write_receipt.get("receipt_id") or ""),
            "file_mutation_performed": bool(write_receipt.get("file_mutation_performed")),
            "business_state_mutation_performed": bool(write_receipt.get("business_state_mutation_performed")),
        }
    )
    archive = _load_quarantine(archive_path)
    for index in range(len(archive["repair_receipts"]) - 1, -1, -1):
        if archive["repair_receipts"][index].get("receipt_id") == repair_receipt["receipt_id"]:
            archive["repair_receipts"][index] = dict(repair_receipt)
            break
    _save_quarantine(archive, archive_path)
    return repair_receipt


def find_operator_truth_for_text(
    text: str,
    *,
    path: str | Path | None = None,
) -> tuple[str, dict[str, Any]] | None:
    data = load_operator_truth_store(path, ensure_seed=True)
    for entity_key in _mentioned_entities(text):
        record = data.get("entities", {}).get(entity_key)
        eligible = operator_truth_record_eligibility(record)[0] if isinstance(record, Mapping) else False
        if isinstance(record, dict) and eligible and str(record.get("value") or "").strip():
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
    records = [
        record
        for record in records
        if str(record.get("value") or "").strip() and operator_truth_record_eligibility(record)[0]
    ]
    if not records:
        return ""

    records.sort(key=lambda record: str(record.get("label") or record.get("entity_key") or ""))
    return "[OPERATOR-CORRECTED TRUTH - shared across agents]\n" + "\n".join(_format_record(record) for record in records)


__all__ = [
    "OperatorTruthQuarantineIntegrityError",
    "classify_operator_truth_safety",
    "capture_operator_truth_from_text",
    "ensure_evening_seed_loaded",
    "eligible_operator_truth_records",
    "extract_operator_truth_candidates",
    "find_operator_truth_for_text",
    "format_operator_truth_context",
    "load_operator_truth_store",
    "operator_truth_record_eligibility",
    "quarantine_unsafe_operator_truth_records",
    "repair_quarantined_operator_truth",
    "save_operator_truth_store",
    "upsert_operator_truth",
    "validate_operator_truth_value",
]
