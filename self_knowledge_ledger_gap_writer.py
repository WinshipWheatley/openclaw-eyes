"""Gated ledger writer for self-knowledge crawler gaps.

Extends the read-only crumb-crawler seed (`self_knowledge_crawler.py`) with a
write path that folds discovered filesystem gaps (files present on disk but
absent from the ledger's known-path inventory tables) into the ONE knowledge
ledger as known-unknown rows.

Safety model, following the house pattern in `scripts/fold_satellite_to_ledger.py`
and `scripts/populate_real_ledger.py`:

  (default)   DRY RUN  — return the would-write plan; the ledger is never opened
                          for writing and no backup is taken.
  confirm=True  WRITE  — back up the ledger file first (timestamped sibling
                          copy, verified non-empty), then write gap rows.
                          Idempotent: replaces only rows previously written by
                          this same fold_source (root), leaving every other
                          row/source in the table untouched — same idempotency
                          rule as fold_satellite_to_ledger.py.

Target table: `knowledge_sysknow_known_unknown`. This table already exists in
the live business-ops ledger (folded there via the same fold-satellite
pattern: unknown_id/subject/unknown_status/reason/next_safe_check plus the
`_fold_source`/`_fold_at` provenance columns) and is exactly the "what the
system knows it does NOT know" home described by
Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md. No new table is invented; this
module only ensures the table exists (CREATE TABLE IF NOT EXISTS with a
matching schema) so tests and fresh ledgers work without it pre-seeded.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from self_knowledge_crawler import diff_filesystem_against_ledger

GAP_TABLE = "knowledge_sysknow_known_unknown"
GAP_COLUMNS = (
    "unknown_id",
    "subject",
    "unknown_status",
    "reason",
    "next_safe_check",
    "_fold_source",
    "_fold_at",
)


def _utc_now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def backup_ledger(ledger_path: str | Path) -> Path:
    """Copy the ledger file to a timestamped sibling path and verify the copy.

    Raises RuntimeError if the resulting backup does not exist or is empty —
    callers must treat that as fail-closed (do NOT proceed to write).
    """
    src = Path(ledger_path)
    backup_path = src.parent / f"{src.name}.bak-{_utc_now_stamp()}"
    shutil.copy2(src, backup_path)
    if not backup_path.exists() or backup_path.stat().st_size <= 0:
        raise RuntimeError(f"ledger backup verification failed: {backup_path}")
    return backup_path


def _fold_source_for(root: Path) -> str:
    return f"self_knowledge_crawler:{root.resolve()}"


def build_gap_write_plan(
    root: str | Path,
    ledger_path: str | Path,
    *,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Return the diff result plus the rows that WOULD be written, unexecuted."""
    root_path = Path(root).resolve()
    diff = diff_filesystem_against_ledger(root_path, ledger_path, max_files=max_files)
    fold_source = _fold_source_for(root_path)
    fold_at = _utc_now_iso()
    rows: list[dict[str, str]] = []
    for gap in diff["unknown_files"]:
        subject = gap["relative_path"]
        rows.append(
            {
                "unknown_id": f"self_knowledge_gap::{subject}",
                "subject": subject,
                "unknown_status": "unconfirmed_gap",
                "reason": (
                    "found on disk by self_knowledge_crawler; absent from the ledger's "
                    "known-path inventory tables"
                ),
                "next_safe_check": (
                    "operator/self-knowledge review: classify and either add to "
                    "file_inventory or record an explicit exclusion"
                ),
                "_fold_source": fold_source,
                "_fold_at": fold_at,
            }
        )
    return {
        "table": GAP_TABLE,
        "fold_source": fold_source,
        "diff_status": diff["status"],
        "counts": diff["counts"],
        "rows": rows,
    }


def write_gaps_to_ledger(
    root: str | Path,
    ledger_path: str | Path,
    *,
    confirm: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Dry-run by default; only writes (after a verified backup) with confirm=True."""
    plan = build_gap_write_plan(root, ledger_path, max_files=max_files)

    if not confirm:
        return {"status": "dry_run", "plan": plan}

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"status": "ledger_unavailable", "plan": plan}

    try:
        backup_path = backup_ledger(ledger)
    except (OSError, RuntimeError) as exc:
        return {"status": "backup_verification_failed", "reason": str(exc), "plan": plan}

    fold_source = plan["fold_source"]
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{GAP_TABLE}" ('
            "unknown_id TEXT, subject TEXT, unknown_status TEXT, reason TEXT, "
            "next_safe_check TEXT, _fold_source TEXT, _fold_at TEXT)"
        )
        # Idempotent: clear only this fold_source's prior rows, matching the
        # fold_satellite_to_ledger.py convention, before re-inserting.
        conn.execute(
            f'DELETE FROM "{GAP_TABLE}" WHERE "_fold_source" = ?', (fold_source,)
        )
        cols = ", ".join(GAP_COLUMNS)
        placeholders = ", ".join("?" for _ in GAP_COLUMNS)
        for row in plan["rows"]:
            conn.execute(
                f'INSERT INTO "{GAP_TABLE}" ({cols}) VALUES ({placeholders})',
                tuple(row[c] for c in GAP_COLUMNS),
            )
        conn.commit()

    return {
        "status": "written",
        "backup_path": str(backup_path),
        "written_count": len(plan["rows"]),
        "table": GAP_TABLE,
        "fold_source": fold_source,
    }


__all__ = [
    "GAP_TABLE",
    "GAP_COLUMNS",
    "backup_ledger",
    "build_gap_write_plan",
    "write_gaps_to_ledger",
]
