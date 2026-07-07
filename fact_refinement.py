"""Structured fact refinement for canonical ledger ingest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REFINEMENT_COLUMNS: dict[str, str] = {
    "refined_entity": "TEXT",
    "refined_claim": "TEXT",
    "refined_amount": "TEXT",
    "refined_due_date": "TEXT",
    "refined_status": "TEXT",
    "refined_as_of": "TEXT",
    "provenance_raw": "TEXT",
    "provenance_raw_sha256": "TEXT",
    "needs_operator_review": "INTEGER DEFAULT 0",
    "refinement_status": "TEXT",
}

_DICTATION_MARKERS = (
    "dictation",
    "voice_note",
    "voice note",
    "raw_note",
    "raw note",
    "operator_note",
    "operator note",
    "transcript",
)
_STATUS_WORDS = {
    "open",
    "unpaid",
    "paid",
    "settled",
    "invoice_due",
    "due",
    "not_tracked",
    "needs_review",
}
_KEY_VALUE_RE = re.compile(
    r"\b(entity|client|counterparty|claim|amount|due_date|due date|status|as_of|as of)\s*[:=]\s*([^;\n]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FactRefinement:
    record: dict[str, Any]
    metadata: dict[str, Any]


def refine_fact_record_for_ingest(record: Mapping[str, Any]) -> FactRefinement:
    """Return a sanitized ingest record plus structured refinement metadata."""
    updated = dict(record)
    raw_text = str(updated.get("fact_text") or "")
    parsed = _parse_structured_fields(updated, raw_text)
    is_dictation = _is_dictation_like(updated)
    raw_hash = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()

    metadata: dict[str, Any] = {
        "refined_entity": parsed.get("entity", ""),
        "refined_claim": parsed.get("claim", ""),
        "refined_amount": parsed.get("amount", ""),
        "refined_due_date": parsed.get("due_date", ""),
        "refined_status": parsed.get("status", ""),
        "refined_as_of": parsed.get("as_of", ""),
        "provenance_raw": raw_text if is_dictation else "",
        "provenance_raw_sha256": raw_hash if is_dictation else "",
        "needs_operator_review": 0,
        "refinement_status": "not_required",
    }

    if _has_minimum_structured_fields(parsed):
        updated["fact_text"] = _structured_fact_text(parsed)
        metadata.update(
            {
                "needs_operator_review": 0,
                "refinement_status": "structured",
                "provenance_raw": raw_text if is_dictation else "",
                "provenance_raw_sha256": raw_hash if is_dictation else "",
            }
        )
    elif is_dictation:
        updated["fact_text"] = (
            "Needs operator review: unstructured operator dictation was not promoted "
            f"to a canonical fact. raw_sha256={raw_hash[:16]}."
        )
        updated["truth_status"] = "stale_possible"
        updated["verification_required"] = 1
        metadata.update(
            {
                "needs_operator_review": 1,
                "refinement_status": "needs_operator_review",
            }
        )

    return FactRefinement(record=updated, metadata=metadata)


def ensure_fact_refinement_columns(conn: sqlite3.Connection) -> None:
    """Add refinement metadata columns to canonical_facts when absent."""
    existing = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(canonical_facts)").fetchall()
    }
    for column, column_type in REFINEMENT_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE canonical_facts ADD COLUMN {column} {column_type}")
    conn.commit()


def store_fact_refinement_metadata(
    conn: sqlite3.Connection,
    *,
    fact_id: str,
    metadata: Mapping[str, Any],
    db_path: str | None = None,
) -> None:
    """Persist refinement metadata and emit a review read-model when needed."""
    ensure_fact_refinement_columns(conn)
    values = {column: metadata.get(column, "") for column in REFINEMENT_COLUMNS}
    conn.execute(
        """
        UPDATE canonical_facts
           SET refined_entity = ?,
               refined_claim = ?,
               refined_amount = ?,
               refined_due_date = ?,
               refined_status = ?,
               refined_as_of = ?,
               provenance_raw = ?,
               provenance_raw_sha256 = ?,
               needs_operator_review = ?,
               refinement_status = ?
         WHERE fact_id = ?
        """,
        (
            str(values["refined_entity"] or ""),
            str(values["refined_claim"] or ""),
            str(values["refined_amount"] or ""),
            str(values["refined_due_date"] or ""),
            str(values["refined_status"] or ""),
            str(values["refined_as_of"] or ""),
            str(values["provenance_raw"] or ""),
            str(values["provenance_raw_sha256"] or ""),
            1 if values["needs_operator_review"] else 0,
            str(values["refinement_status"] or ""),
            fact_id,
        ),
    )
    if values["needs_operator_review"]:
        write_fact_refinement_review_item(fact_id=fact_id, metadata=values, db_path=db_path)


def write_fact_refinement_review_item(
    *,
    fact_id: str,
    metadata: Mapping[str, Any],
    db_path: str | None,
) -> None:
    """Surface unparseable facts without copying raw dictation into the read-model."""
    raw_hash = str(metadata.get("provenance_raw_sha256") or "")
    review_path = Path(
        os.environ.get(
            "OPENCLAW_FACT_REFINEMENT_REVIEW_PATH",
            "generated/read_models/fact_refinement_review.json",
        )
    )
    try:
        review_path.parent.mkdir(parents=True, exist_ok=True)
        if review_path.exists():
            payload = json.loads(review_path.read_text())
            if not isinstance(payload, dict):
                payload = {}
        else:
            payload = {}
        rows = payload.get("facts_needing_operator_review")
        if not isinstance(rows, list):
            rows = []
        row = {
            "fact_id": fact_id,
            "review_reason": "unstructured_operator_dictation",
            "raw_sha256": raw_hash,
            "raw_preview_available_in": "canonical_facts.provenance_raw",
            "ledger_path": str(db_path or ""),
        }
        rows = [existing for existing in rows if existing.get("fact_id") != fact_id]
        rows.append(row)
        payload.update(
            {
                "schema_version": "fact_refinement_review_v1",
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "facts_needing_operator_review": rows,
            }
        )
        review_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except Exception:
        return


def _is_dictation_like(record: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        str(record.get(key) or "")
        for key in ("doc_category", "section_heading", "source_description", "source_file")
    ).lower()
    return any(marker in haystack for marker in _DICTATION_MARKERS)


def _parse_structured_fields(record: Mapping[str, Any], raw_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {
        "entity": _string_field(record, "entity", "client", "counterparty"),
        "claim": _string_field(record, "claim"),
        "amount": _string_field(record, "amount"),
        "due_date": _string_field(record, "due_date"),
        "status": _normalize_status(_string_field(record, "status")),
        "as_of": _string_field(record, "as_of"),
    }
    for match in _KEY_VALUE_RE.finditer(raw_text):
        key = match.group(1).lower().replace(" ", "_")
        value = match.group(2).strip().strip(".")
        if key in {"client", "counterparty"}:
            key = "entity"
        elif key == "due_date":
            key = "due_date"
        elif key == "as_of":
            key = "as_of"
        if key == "status":
            value = _normalize_status(value)
        if key in parsed and not parsed[key]:
            parsed[key] = value
    return parsed


def _has_minimum_structured_fields(fields: Mapping[str, str]) -> bool:
    return bool(fields.get("entity") and fields.get("claim") and fields.get("status") and fields.get("as_of"))


def _structured_fact_text(fields: Mapping[str, str]) -> str:
    parts = [
        f"entity={fields.get('entity')}",
        f"claim={fields.get('claim')}",
    ]
    if fields.get("amount"):
        parts.append(f"amount={fields.get('amount')}")
    if fields.get("due_date"):
        parts.append(f"due_date={fields.get('due_date')}")
    parts.extend(
        [
            f"status={fields.get('status')}",
            f"as_of={fields.get('as_of')}",
        ]
    )
    return "Structured fact: " + "; ".join(part for part in parts if part and not part.endswith("=")) + "."


def _string_field(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_status(value: str) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in {"caught_up", "all_caught_up", "paid_up"}:
        return "paid"
    if normalized in {"owed", "owes", "due"}:
        return "due"
    return normalized if normalized in _STATUS_WORDS else normalized
