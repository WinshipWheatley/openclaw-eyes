#!/usr/bin/env python3
"""Read-only reconciliation report for knowledge SQLite satellites."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


SEPARATE_CONCERN_FRAGMENTS = (
    "queue",
    "task",
    "lease",
    "control_plane",
    "finance_transaction",
    "payment",
)


def _tables(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    conn = sqlite3.connect(path)
    try:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        out: dict[str, int] = {}
        for name in names:
            try:
                out[name] = int(conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0])
            except sqlite3.Error:
                out[name] = -1
        return out
    finally:
        conn.close()


def _classify(table: str, ledger_tables: set[str]) -> str:
    if table in ledger_tables:
        return "already_present"
    lowered = table.lower()
    if any(fragment in lowered for fragment in SEPARATE_CONCERN_FRAGMENTS):
        return "separate_concern"
    return "unique_fold_in"


def reconcile_satellite(*, ledger_path: str | Path, satellite_path: str | Path) -> dict[str, Any]:
    ledger = Path(ledger_path)
    satellite = Path(satellite_path)
    ledger_table_counts = _tables(ledger)
    satellite_table_counts = _tables(satellite)
    table_reports: dict[str, dict[str, Any]] = {}
    ledger_names = set(ledger_table_counts)
    for table, count in sorted(satellite_table_counts.items()):
        table_reports[table] = {
            "row_count": count,
            "classification": _classify(table, ledger_names),
            "ledger_row_count": ledger_table_counts.get(table),
        }
    return {
        "status": "read_only_diff",
        "ledger_path": str(ledger),
        "satellite_path": str(satellite),
        "table_count": len(satellite_table_counts),
        "tables": table_reports,
    }


def reconcile_many(*, ledger_path: str | Path, satellite_paths: list[str | Path]) -> list[dict[str, Any]]:
    return [
        reconcile_satellite(ledger_path=ledger_path, satellite_path=satellite)
        for satellite in satellite_paths
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=".openclaw/business_ops/ledger.sqlite")
    parser.add_argument("satellites", nargs="+")
    args = parser.parse_args()
    print(
        json.dumps(
            reconcile_many(ledger_path=args.ledger, satellite_paths=args.satellites),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
