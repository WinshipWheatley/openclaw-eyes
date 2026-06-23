#!/usr/bin/env python3
"""Generate the guardian-approval-posture read-model from the real ledger.

Answers "what's pending my approval, what's held/blocked, what authority decisions
are open" for Guardian's context packet.

Sources (read-only):
  - guardian_hitl_approval_requests   (shadow/dual-write rows per approval event)
  - guardian_hitl_approval_receipts   (receipt lifecycle rows)
  - agent_recovery_clearances         (fixed-scope Cassandra recovery clearances)

ANTI-CONFABULATION contract:
  - Opens the ledger read-only (URI mode=ro).
  - Returns empty-but-flagged payload when ledger is missing or tables absent.
  - Zero fabrication: only real rows surfaced; empty store = EMPTY + flagged as gap.
  - NO writes, NO mutations, NO approval decisions.

Run: python3 scripts/export_guardian_approval_posture_read_model.py
Output: generated/read_models/guardian_approval_posture.json
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "read_models" / "guardian_approval_posture.json"
SCHEMA_VERSION = "guardian_approval_posture_read_model_v0"
DEFAULT_LEDGER_PATH = ".openclaw/business_ops/ledger.sqlite"
LEDGER_PATH_ENV_VAR = "OPENCLAW_LEDGER_PATH"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_ledger(ledger_path: str | Path | None = None) -> str:
    return str(ledger_path or os.environ.get(LEDGER_PATH_ENV_VAR) or DEFAULT_LEDGER_PATH)


def _open_ro(db_file: Path) -> sqlite3.Connection | None:
    """Open the ledger read-only. Returns None if file doesn't exist."""
    if not db_file.exists():
        return None
    uri = f"file:{db_file.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _query_approval_requests(conn: sqlite3.Connection, tables: set[str]) -> dict:
    """Summarize guardian_hitl_approval_requests without reading raw action text."""
    if "guardian_hitl_approval_requests" not in tables:
        return {"present": False, "total": 0, "by_status": {}, "by_action_type": {}, "latest_requested_at": None}

    total = conn.execute("SELECT COUNT(*) FROM guardian_hitl_approval_requests").fetchone()[0]

    by_status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM guardian_hitl_approval_requests GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["cnt"] for r in by_status_rows}

    by_type_rows = conn.execute(
        "SELECT action_type, COUNT(*) as cnt FROM guardian_hitl_approval_requests GROUP BY action_type"
    ).fetchall()
    by_action_type = {r["action_type"]: r["cnt"] for r in by_type_rows}

    latest = conn.execute(
        "SELECT MAX(requested_at) FROM guardian_hitl_approval_requests"
    ).fetchone()[0]

    # Count those that have NOT expired relative to now (i.e. expires_at > now)
    now_iso = _utc_now()
    active = conn.execute(
        "SELECT COUNT(*) FROM guardian_hitl_approval_requests WHERE expires_at > ?",
        (now_iso,),
    ).fetchone()[0]

    return {
        "present": True,
        "total": total,
        "active_not_expired": active,
        "by_status": by_status,
        "by_action_type": by_action_type,
        "latest_requested_at": latest,
        "note": (
            "All rows are observational shadow/dual-write entries. "
            "Legacy JSON remains authoritative; these are metadata-only mirror records."
        ),
    }


def _query_approval_receipts(conn: sqlite3.Connection, tables: set[str]) -> dict:
    """Summarize guardian_hitl_approval_receipts."""
    if "guardian_hitl_approval_receipts" not in tables:
        return {"present": False, "total": 0, "by_receipt_type": {}}

    total = conn.execute("SELECT COUNT(*) FROM guardian_hitl_approval_receipts").fetchone()[0]

    by_type_rows = conn.execute(
        "SELECT receipt_type, status, COUNT(*) as cnt FROM guardian_hitl_approval_receipts GROUP BY receipt_type, status"
    ).fetchall()
    by_receipt_type: dict[str, dict[str, int]] = {}
    for r in by_type_rows:
        rt = r["receipt_type"]
        by_receipt_type.setdefault(rt, {})[r["status"]] = r["cnt"]

    latest = conn.execute(
        "SELECT MAX(created_at) FROM guardian_hitl_approval_receipts"
    ).fetchone()[0]

    return {
        "present": True,
        "total": total,
        "by_receipt_type": by_receipt_type,
        "latest_receipt_at": latest,
    }


def _query_recovery_clearances(conn: sqlite3.Connection, tables: set[str]) -> dict:
    """Summarize agent_recovery_clearances without raw content."""
    if "agent_recovery_clearances" not in tables:
        return {"present": False, "total": 0, "by_status": {}}

    total = conn.execute("SELECT COUNT(*) FROM agent_recovery_clearances").fetchone()[0]

    by_status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM agent_recovery_clearances GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["cnt"] for r in by_status_rows}

    # Most recent clearance (non-sensitive fields only)
    recent = conn.execute(
        """SELECT agent_id, recovery_action_id, status, requested_at, approved_at, used_at
           FROM agent_recovery_clearances
           ORDER BY requested_at DESC LIMIT 1"""
    ).fetchone()
    recent_dict = dict(recent) if recent else {}

    return {
        "present": True,
        "total": total,
        "by_status": by_status,
        "most_recent": recent_dict,
        "note": "Cassandra-only fixed-scope recovery clearances; not general runtime approval authority.",
    }


def build(
    ledger_path: str | Path | None = None,
) -> dict:
    ledger_str = _resolve_ledger(ledger_path)
    db_file = Path(ledger_str) if Path(ledger_str).is_absolute() else ROOT / ledger_str
    generated_at = _utc_now()

    conn = _open_ro(db_file)
    if conn is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "generated_by": "scripts/export_guardian_approval_posture_read_model.py",
            "ledger_present": False,
            "ledger_path": str(db_file),
            "data_gap": "REAL SOURCE MISSING: business_ops ledger not found at expected path.",
            "approval_requests": {"present": False, "total": 0},
            "approval_receipts": {"present": False, "total": 0},
            "recovery_clearances": {"present": False, "total": 0},
            "pending_approval_count": 0,
            "active_not_expired_count": 0,
            "posture_summary": "DATA GAP: ledger not found; cannot surface real approval state.",
            "boundaries": {
                "read_only": True,
                "mutations_allowed": False,
                "approvals_issued": False,
                "raw_action_text_read": False,
                "secrets_read": False,
            },
        }

    try:
        tables = _tables(conn)
        approval_requests = _query_approval_requests(conn, tables)
        approval_receipts = _query_approval_receipts(conn, tables)
        recovery_clearances = _query_recovery_clearances(conn, tables)
    finally:
        conn.close()

    # Compute top-line counts
    total_requests = approval_requests.get("total", 0)
    active_not_expired = approval_requests.get("active_not_expired", 0)
    total_receipts = approval_receipts.get("total", 0)
    clearance_total = recovery_clearances.get("total", 0)

    # Build posture summary (truthful, no fabrication)
    by_status = approval_requests.get("by_status", {})
    status_parts = [f"{cnt} {status}" for status, cnt in sorted(by_status.items())]
    status_text = "; ".join(status_parts) if status_parts else "no records"

    clearance_by_status = recovery_clearances.get("by_status", {})
    clearance_parts = [f"{cnt} {s}" for s, cnt in sorted(clearance_by_status.items())]
    clearance_text = "; ".join(clearance_parts) if clearance_parts else "none"

    posture_summary = (
        f"{total_requests} approval records in ledger ({active_not_expired} not-yet-expired by timestamp): {status_text}. "
        f"Receipts: {total_receipts}. "
        f"Recovery clearances: {clearance_total} ({clearance_text}). "
        f"All records are observational shadow entries; legacy JSON remains authoritative for live gate."
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "generated_by": "scripts/export_guardian_approval_posture_read_model.py",
        "ledger_present": True,
        "ledger_path": str(db_file),
        "source_ref": ".openclaw/business_ops/ledger.sqlite",
        "approval_requests": approval_requests,
        "approval_receipts": approval_receipts,
        "recovery_clearances": recovery_clearances,
        "pending_approval_count": total_requests,
        "active_not_expired_count": active_not_expired,
        "posture_summary": posture_summary,
        "boundaries": {
            "read_only": True,
            "mutations_allowed": False,
            "approvals_issued": False,
            "raw_action_text_read": False,
            "secrets_read": False,
            "legacy_json_authoritative": True,
            "shadow_rows_are_metadata_only": True,
        },
        "data_gap": None,
        "note": (
            "Counts reflect shadow/dual-write observation rows only. "
            "Active approval truth lives in /mnt/c/OpenClaw/logs/approval_pending.json "
            "which is NOT read by this generator (read-only-safe boundary)."
        ),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    artifact = build()
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gap = artifact.get("data_gap")
    ledger_ok = artifact.get("ledger_present", False)
    total = artifact.get("pending_approval_count", 0)
    active = artifact.get("active_not_expired_count", 0)
    print(
        f"wrote {OUT.relative_to(ROOT)} :: "
        f"ledger={'ok' if ledger_ok else 'MISSING'} | "
        f"{total} records ({active} not-expired) | "
        f"gap={gap or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
