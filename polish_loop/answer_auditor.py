#!/usr/bin/env python3
"""Generic answer auditor for PC4 self-healing.

The auditor checks a narrow factual claim against current local truth sources.
It never reads vault paths and never turns missing truth into a pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
AGENT_PRESENCE_READ_MODEL = "agent_presence.json"
CAPABILITY_INDEX_READ_MODEL = "openclaw_capability_index.json"
CHANGE_SENTINEL_READ_MODEL = "openclaw_change_sentinel.json"
UNIVERSAL_RECEIPTS_SQLITE = DEFAULT_SYSTEM_KNOWLEDGE_ROOT / "universal_receipts.sqlite"
PROOF_TO_RESPONSE_SQLITE = DEFAULT_SYSTEM_KNOWLEDGE_ROOT / "proof_to_response_runtime.sqlite"

FORBIDDEN_PATH_MARKERS = (
    ".chief.env",
    ".google-secrets",
    "OpenClawLegalPrivate",
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
)


@dataclass(frozen=True)
class AuditFinding:
    verdict: str
    agent_id: str
    claim_type: str
    claimed_value: Any
    actual_value: Any
    truth_source: str
    proof_refs: tuple[str, ...]
    delta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        return payload


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _assert_safe_path(path: str | Path) -> None:
    text = _path_text(path)
    if any(marker in text for marker in FORBIDDEN_PATH_MARKERS):
        raise ValueError(f"forbidden truth path: {text}")


def _safe_read_model_root(read_model_root: str | Path) -> Path:
    _assert_safe_path(read_model_root)
    return Path(read_model_root)


def _read_json(path: Path) -> dict[str, Any]:
    _assert_safe_path(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    match = re.search(r"-?\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _verdict(claimed: Any, actual: Any) -> str:
    return "pass" if claimed == actual else "fail"


def _presence_online_count(payload: Mapping[str, Any]) -> int | None:
    value = payload.get("online_count")
    if isinstance(value, int):
        return value
    agents = payload.get("agents")
    if isinstance(agents, list):
        return sum(
            1
            for row in agents
            if isinstance(row, Mapping)
            and str(row.get("actual_state") or row.get("state") or "").lower() == "online"
        )
    return None


def _live_capability_count(payload: Mapping[str, Any]) -> int | None:
    rows = payload.get("generic_capabilities")
    if not isinstance(rows, list):
        rows = payload.get("capabilities")
    if not isinstance(rows, list):
        return None
    return sum(
        1
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("capability_status") or row.get("lifecycle_status") or "") == "LIVE_IMPLEMENTED"
    )


def _capability_is_live(payload: Mapping[str, Any], capability_id: str) -> bool | None:
    rows = payload.get("generic_capabilities")
    if not isinstance(rows, list):
        rows = payload.get("capabilities")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("capability_id") or row.get("id") or row.get("name") or "")
        if row_id == capability_id:
            return str(row.get("capability_status") or row.get("lifecycle_status") or "") == "LIVE_IMPLEMENTED"
    return None


def _row_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_receipts_by_type(
    receipt_type: str,
    *,
    sqlite_path: str | Path = UNIVERSAL_RECEIPTS_SQLITE,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read-only universal receipt lookup.

    The exact universal receipt schema has varied, so this probes table/column
    names and returns an empty list when the source is absent or incompatible.
    """

    _assert_safe_path(sqlite_path)
    path = Path(sqlite_path)
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [
            str(row[0])
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        for table in tables:
            columns = [str(row[1]) for row in con.execute(f"PRAGMA table_info({table})").fetchall()]
            type_column = next((col for col in ("receipt_type", "type", "event_type", "receipt_kind") if col in columns), None)
            if type_column is None:
                continue
            return _row_dicts(
                con,
                f"SELECT * FROM {table} WHERE {type_column}=? LIMIT ?",
                (receipt_type, limit),
            )
    finally:
        con.close()
    return []


def _unverifiable(agent_id: str, claim_type: str, claimed_value: Any, truth_source: str, reason: str) -> AuditFinding:
    return AuditFinding(
        verdict="unverifiable",
        agent_id=agent_id,
        claim_type=claim_type,
        claimed_value=claimed_value,
        actual_value=None,
        truth_source=truth_source,
        proof_refs=(),
        delta={"reason": reason},
    )


def check_agent_claim(
    agent_id: str,
    claim_type: str,
    claim_value: Any,
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> AuditFinding:
    """Compare an agent claim to live local truth.

    Supported claim types intentionally start narrow and deterministic:
    presence online count, live capability count/status, receipt type count,
    proof-to-response receipt count, and change-sentinel freshness.
    """

    root = _safe_read_model_root(read_model_root)
    claim = str(claim_type or "").strip().lower()

    if claim in {"agent_presence_online_count", "presence_online_count", "online_count"}:
        path = root / AGENT_PRESENCE_READ_MODEL
        payload = _read_json(path)
        actual = _presence_online_count(payload)
        claimed = _first_int(claim_value)
        if actual is None or claimed is None:
            return _unverifiable(agent_id, claim_type, claim_value, path.as_posix(), "missing_presence_truth_or_numeric_claim")
        return AuditFinding(
            verdict=_verdict(claimed, actual),
            agent_id=agent_id,
            claim_type=claim_type,
            claimed_value=claimed,
            actual_value=actual,
            truth_source=path.as_posix(),
            proof_refs=(path.as_posix(),),
            delta={"difference": actual - claimed},
        )

    if claim in {"live_capability_count", "capability_live_implemented_count"}:
        path = root / CAPABILITY_INDEX_READ_MODEL
        payload = _read_json(path)
        actual = _live_capability_count(payload)
        claimed = _first_int(claim_value)
        if actual is None or claimed is None:
            return _unverifiable(agent_id, claim_type, claim_value, path.as_posix(), "missing_capability_truth_or_numeric_claim")
        return AuditFinding(
            verdict=_verdict(claimed, actual),
            agent_id=agent_id,
            claim_type=claim_type,
            claimed_value=claimed,
            actual_value=actual,
            truth_source=path.as_posix(),
            proof_refs=(path.as_posix(),),
            delta={"difference": actual - claimed},
        )

    if claim in {"capability_live", "capability_status"}:
        path = root / CAPABILITY_INDEX_READ_MODEL
        payload = _read_json(path)
        capability_id = str(claim_value or "").strip()
        actual = _capability_is_live(payload, capability_id)
        if actual is None or not capability_id:
            return _unverifiable(agent_id, claim_type, claim_value, path.as_posix(), "missing_capability_status_truth")
        return AuditFinding(
            verdict="pass" if actual else "fail",
            agent_id=agent_id,
            claim_type=claim_type,
            claimed_value=capability_id,
            actual_value="LIVE_IMPLEMENTED" if actual else "NOT_LIVE_IMPLEMENTED",
            truth_source=path.as_posix(),
            proof_refs=(path.as_posix(),),
            delta={"capability_id": capability_id},
        )

    if claim in {"receipt_type_count", "universal_receipt_type_count"}:
        receipt_type = str(claim_value.get("receipt_type") if isinstance(claim_value, Mapping) else claim_value or "").strip()
        claimed = _first_int(claim_value.get("count")) if isinstance(claim_value, Mapping) else None
        rows = query_receipts_by_type(receipt_type)
        actual = len(rows)
        if not receipt_type or claimed is None:
            return _unverifiable(agent_id, claim_type, claim_value, UNIVERSAL_RECEIPTS_SQLITE.as_posix(), "missing_receipt_type_or_numeric_claim")
        return AuditFinding(
            verdict=_verdict(claimed, actual),
            agent_id=agent_id,
            claim_type=claim_type,
            claimed_value=claimed,
            actual_value=actual,
            truth_source=UNIVERSAL_RECEIPTS_SQLITE.as_posix(),
            proof_refs=(UNIVERSAL_RECEIPTS_SQLITE.as_posix(),),
            delta={"receipt_type": receipt_type},
        )

    if claim in {"freshness_generated_at", "change_sentinel_generated_at"}:
        path = root / CHANGE_SENTINEL_READ_MODEL
        payload = _read_json(path)
        actual = payload.get("generated_at")
        if not actual:
            return _unverifiable(agent_id, claim_type, claim_value, path.as_posix(), "missing_change_sentinel_truth")
        return AuditFinding(
            verdict=_verdict(str(claim_value), str(actual)),
            agent_id=agent_id,
            claim_type=claim_type,
            claimed_value=str(claim_value),
            actual_value=str(actual),
            truth_source=path.as_posix(),
            proof_refs=(path.as_posix(),),
            delta={},
        )

    return _unverifiable(agent_id, claim_type, claim_value, "", "unsupported_claim_type")
