"""Mode-shift ledger v1.

Records harden/loosen decisions and later outcomes for the mode-shift engine.
This is a local business-ops SQLite read/write helper only; it grants no
authority to execute shifts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from business_ops_ledger import init_business_ops_ledger


SCHEMA_VERSION = "mode_shift_ledger_v1"

SEED_MODE_SHIFTS: tuple[dict[str, Any], ...] = (
    {
        "structure_ref": "gate-per-task->batch-gate",
        "shift": "loosen",
        "trigger_signals": ["gate overhead exceeded build yield", "batch verification preserved safety"],
        "evidence_refs": ["Operator/MODE-SHIFT-ENGINE-DESIGN-20260707.md#seed:gate-per-task"],
        "decided_by": "strategist",
        "as_of": "2026-07-07T00:00:00+00:00",
        "outcome": {"assessed_at": "2026-07-07T00:00:00+00:00", "verdict": "positive", "evidence": "25 tasks/day"},
    },
    {
        "structure_ref": "roster-sweeps->targeted-probes",
        "shift": "loosen",
        "trigger_signals": ["roster sweeps repeated without proportional signal"],
        "evidence_refs": ["Operator/MODE-SHIFT-ENGINE-DESIGN-20260707.md#seed:roster-sweeps"],
        "decided_by": "strategist",
        "as_of": "2026-07-07T00:00:00+00:00",
        "outcome": {"assessed_at": "2026-07-07T00:00:00+00:00", "verdict": "positive", "evidence": "signal up, waste down"},
    },
    {
        "structure_ref": "serialize-everything->builds-through-gates",
        "shift": "loosen",
        "trigger_signals": ["serial build flow constrained throughput", "gates retained safety"],
        "evidence_refs": ["Operator/MODE-SHIFT-ENGINE-DESIGN-20260707.md#seed:serialize-everything"],
        "decided_by": "strategist",
        "as_of": "2026-07-07T00:00:00+00:00",
        "outcome": {"assessed_at": "2026-07-07T00:00:00+00:00", "verdict": "positive", "evidence": "builds-through-gates held"},
    },
    {
        "structure_ref": "pytest-green->output-probes",
        "shift": "harden",
        "trigger_signals": ["pytest green was not enough to catch fake fixes"],
        "evidence_refs": ["Operator/MODE-SHIFT-ENGINE-DESIGN-20260707.md#seed:output-probes"],
        "decided_by": "strategist",
        "as_of": "2026-07-07T00:00:00+00:00",
        "outcome": {"assessed_at": "2026-07-07T00:00:00+00:00", "verdict": "positive", "evidence": "caught 2 fake-fixes, 5 iterations"},
    },
    {
        "structure_ref": "instance->class fixing",
        "shift": "harden",
        "trigger_signals": ["instance fixes piled where a class existed"],
        "evidence_refs": ["Operator/MODE-SHIFT-ENGINE-DESIGN-20260707.md#seed:class-fixing"],
        "decided_by": "strategist",
        "as_of": "2026-07-07T00:00:00+00:00",
        "outcome": {"assessed_at": "2026-07-07T00:00:00+00:00", "verdict": "positive", "evidence": "117/118 covered whole fleets"},
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _shift_id(structure_ref: str, shift: str, as_of: str) -> str:
    digest = hashlib.sha256(f"{structure_ref}\0{shift}\0{as_of}".encode("utf-8")).hexdigest()
    return f"mshift_{digest[:20]}"


def init_mode_shift_ledger(db_path: str | Path | None = None) -> str:
    path = init_business_ops_ledger(str(db_path) if db_path is not None else None)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS mode_shift_ledger (
  shift_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  structure_ref TEXT NOT NULL,
  shift TEXT NOT NULL,
  trigger_signals_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  as_of TEXT NOT NULL,
  outcome_json TEXT NOT NULL,
  raw_sensitive_data_stored INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip()
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _validate_shift(record: Mapping[str, Any]) -> None:
    shift = str(record.get("shift") or "").strip().lower()
    if shift not in {"harden", "loosen", "freeze"}:
        raise ValueError(f"unsupported mode shift: {shift}")
    if not str(record.get("structure_ref") or "").strip():
        raise ValueError("structure_ref is required")
    outcome = record.get("outcome")
    if not isinstance(outcome, Mapping):
        raise ValueError("outcome mapping is required")
    verdict = str(outcome.get("verdict") or "").strip().lower()
    if verdict not in {"positive", "negative", "neutral"}:
        raise ValueError(f"unsupported outcome verdict: {verdict}")


def record_mode_shift(
    *,
    db_path: str | Path | None = None,
    structure_ref: str,
    shift: str,
    trigger_signals: Sequence[str],
    evidence_refs: Sequence[str],
    decided_by: str,
    as_of: str,
    outcome: Mapping[str, Any],
) -> str:
    record = {
        "structure_ref": structure_ref,
        "shift": shift,
        "trigger_signals": list(trigger_signals),
        "evidence_refs": list(evidence_refs),
        "decided_by": decided_by,
        "as_of": as_of,
        "outcome": dict(outcome),
    }
    _validate_shift(record)
    path = init_mode_shift_ledger(db_path)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    resolved_shift = str(shift).strip().lower()
    shift_id = _shift_id(structure_ref, resolved_shift, as_of)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
INSERT INTO mode_shift_ledger (
  shift_id, schema_version, structure_ref, shift, trigger_signals_json,
  evidence_refs_json, decided_by, as_of, outcome_json,
  raw_sensitive_data_stored, execution_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
ON CONFLICT(shift_id) DO UPDATE SET
  trigger_signals_json = excluded.trigger_signals_json,
  evidence_refs_json = excluded.evidence_refs_json,
  decided_by = excluded.decided_by,
  outcome_json = excluded.outcome_json,
  raw_sensitive_data_stored = 0,
  execution_allowed = 0
""".strip(),
            (
                shift_id,
                SCHEMA_VERSION,
                structure_ref,
                resolved_shift,
                stable_json(list(trigger_signals)),
                stable_json(list(evidence_refs)),
                str(decided_by or "operator"),
                as_of,
                stable_json(dict(outcome)),
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return shift_id


def seed_mode_shift_ledger(db_path: str | Path | None = None) -> int:
    for record in SEED_MODE_SHIFTS:
        record_mode_shift(db_path=db_path, **record)
    return len(SEED_MODE_SHIFTS)


def query_mode_shifts(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = init_mode_shift_ledger(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
SELECT *
FROM mode_shift_ledger
ORDER BY as_of ASC, structure_ref ASC
""".strip()
        ).fetchall()
    finally:
        conn.close()
    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "shift_id": row["shift_id"],
                "schema_version": row["schema_version"],
                "structure_ref": row["structure_ref"],
                "shift": row["shift"],
                "trigger_signals": json.loads(row["trigger_signals_json"]),
                "evidence_refs": json.loads(row["evidence_refs_json"]),
                "decided_by": row["decided_by"],
                "as_of": row["as_of"],
                "outcome": json.loads(row["outcome_json"]),
                "raw_sensitive_data_stored": bool(row["raw_sensitive_data_stored"]),
                "execution_allowed": bool(row["execution_allowed"]),
                "created_at": row["created_at"],
            }
        )
    return results
